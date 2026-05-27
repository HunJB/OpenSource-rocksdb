import re
import os
import glob
import collections
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# 한글 폰트 설정
try:
    fm.fontManager.addfont('/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf')
    matplotlib.rcParams['font.family'] = 'NanumBarunGothic'
except Exception:
    pass
matplotlib.rcParams['axes.unicode_minus'] = False

home_dir = os.path.expanduser("~")
LOG_DIR = f"{home_dir}/rocksdb/experiment2/results/memtable_logs"
OUT_DIR = f"{home_dir}/rocksdb/experiment2/results/aggregated"
os.makedirs(OUT_DIR, exist_ok=True)

# MemTable 크기별 실험 설정 (크기 오름차순)
# (exp_key, 표시 레이블, MB 크기, 색상)
EXP_CONFIGS = [
    ('mem_2mb',   '2MB',   2,   '#d62728'),
    ('mem_4mb',   '4MB',   4,   '#e85d04'),
    ('mem_8mb',   '8MB',   8,   '#f48c06'),
    ('mem_16mb',  '16MB',  16,  '#fdc500'),
    ('mem_32mb',  '32MB',  32,  '#70e000'),
    ('mem_64mb',  '64MB',  64,  '#2ca02c'),
    ('mem_128mb', '128MB', 128, '#1f77b4'),
    ('mem_256mb', '256MB', 256, '#7f7f7f'),
]

# 초별 스레드 OPS 합산 패턴 (fillrandom 구간)
interval_pattern = re.compile(
    r"thread\s+\d+:\s*\(\d+,\d+\)\s*ops\s*and\s*\(([\d.]+),[\d.]+\)\s*ops/second"
    r"\s*in\s*\([\d.]+,([\d.]+)\)\s*seconds"
)


def parse_log(filepath):
    """로그 파일에서 핵심 지표 추출"""
    time_ops = collections.defaultdict(float)
    write_phase = True   # fillrandom 요약 줄 이전만 시계열로 수집
    bytes_written = 0
    compact_write_bytes = 0
    stall_us = 0
    read_ops = 0.0

    with open(filepath, 'r') as f:
        for line in f:
            # fillrandom 요약 줄 → 이후는 readrandom 구간
            if 'fillrandom' in line and 'micros/op' in line:
                write_phase = False

            # OPS 시계열 (쓰기 구간만)
            if write_phase:
                m = interval_pattern.search(line)
                if m:
                    t = int(float(m.group(2)))
                    time_ops[t] += float(m.group(1))

            # readrandom 요약 OPS
            if 'readrandom' in line and 'ops/sec' in line and 'micros/op' in line:
                m = re.search(r'([\d.]+)\s+ops/sec', line)
                if m:
                    read_ops = float(m.group(1))

            # 통계: 사용자 쓰기 바이트
            m = re.search(r'rocksdb\.bytes\.written COUNT : (\d+)', line)
            if m:
                bytes_written = int(m.group(1))

            # 통계: 컴팩션 쓰기 바이트
            m = re.search(r'rocksdb\.compact\.write\.bytes COUNT : (\d+)', line)
            if m:
                compact_write_bytes = int(m.group(1))

            # 통계: Write Stall 누적 시간 (마이크로초 합산)
            m = re.search(r'rocksdb\.db\.write\.stall\s+P50.*SUM\s*:\s*(\d+)', line)
            if m:
                stall_us = int(m.group(1))

    # WAF = (사용자 쓰기 + 컴팩션 쓰기) / 사용자 쓰기
    waf = (bytes_written + compact_write_bytes) / bytes_written if bytes_written > 0 else 0.0

    return {
        'time_ops': dict(time_ops),
        'stall_us': stall_us,
        'waf': waf,
        'read_ops': read_ops,
    }


def is_completed(filepath):
    with open(filepath, 'r') as f:
        return '[EXPERIMENT_COMPLETED]' in f.read()


# ── [데이터 수집] ─────────────────────────────────────────────────────────────
collected = []

for exp_key, label, size_mb, color in EXP_CONFIGS:
    files = glob.glob(f"{LOG_DIR}/{exp_key}_*.log")
    completed_files = [f for f in files if is_completed(f)]

    if not completed_files:
        print(f"[알림] {exp_key}: 완료된 로그 없음, 제외")
        continue

    n = len(completed_files)
    print(f"[정보] {exp_key}: {n}회 완료, 파싱 중...")
    runs = [parse_log(f) for f in completed_files]

    # OPS 시계열 평균 ± 표준편차
    all_times = sorted(set(t for r in runs for t in r['time_ops']))
    times_v, mean_ops, std_ops = [], [], []
    for t in all_times:
        vals = [r['time_ops'][t] for r in runs if t in r['time_ops']]
        if vals:
            times_v.append(t)
            mean_ops.append(np.mean(vals))
            std_ops.append(np.std(vals))

    mean_ops_arr = np.array(mean_ops)
    std_ops_arr  = np.array(std_ops)

    # 지표 평균
    overall_mean = float(np.mean(mean_ops_arr)) if len(mean_ops_arr) > 0 else 0.0
    stall_sec    = np.mean([r['stall_us'] / 1e6 for r in runs])
    waf_mean     = np.mean([r['waf'] for r in runs if r['waf'] > 0]) if any(r['waf'] > 0 for r in runs) else 0.0
    read_ops_mean = np.mean([r['read_ops'] for r in runs if r['read_ops'] > 0]) if any(r['read_ops'] > 0 for r in runs) else 0.0

    collected.append({
        'key':          exp_key,
        'label':        label,
        'size_mb':      size_mb,
        'color':        color,
        'n':            n,
        'times':        times_v,
        'mean_ops':     mean_ops_arr,
        'std_ops':      std_ops_arr,
        'overall_mean': overall_mean,
        'stall_sec':    stall_sec,
        'waf':          waf_mean,
        'read_ops':     read_ops_mean,
    })

if not collected:
    print("❌ 파싱할 데이터가 없습니다. 로그 파일을 확인하세요.")
    exit(1)

# 크기 오름차순 정렬
collected.sort(key=lambda x: x['size_mb'])

sizes       = [d['size_mb']      for d in collected]
labels      = [d['label']        for d in collected]
colors      = [d['color']        for d in collected]
means       = [d['overall_mean'] for d in collected]
stall_vals  = [d['stall_sec']    for d in collected]
waf_vals    = [d['waf']          for d in collected]
read_vals   = [d['read_ops']     for d in collected]

current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ── [시각화: 2×2 대시보드] ───────────────────────────────────────────────────
fig, axs = plt.subplots(2, 2, figsize=(22, 14))
ax_knee, ax_stall = axs[0, 0], axs[0, 1]
ax_waf,  ax_time  = axs[1, 0], axs[1, 1]

fig.suptitle(
    f'MemTable 크기 스윕 실험 — Write Stall 최소화 연구  ({current_time_str})',
    fontsize=15, fontweight='bold', y=1.01
)

# ── 그래프 1: OPS vs MemTable 크기 (포화 지점 곡선) ──────────────────────────
ax_knee.plot(sizes, means, 'o-', color='steelblue', linewidth=2.5,
             markersize=6, zorder=3)
for s, v, c, lbl in zip(sizes, means, colors, labels):
    ax_knee.scatter([s], [v], color=c, s=100, zorder=5)
    ax_knee.annotate(
        f'{v:,.0f}',
        xy=(s, v),
        xytext=(0, 10),
        textcoords='offset points',
        ha='center', fontsize=8, fontweight='bold'
    )
ax_knee.set_xscale('log', base=2)
ax_knee.set_xticks(sizes)
ax_knee.set_xticklabels(labels, fontsize=9)
ax_knee.set_title('1. 평균 쓰기 처리량 vs MemTable 크기  (포화 지점 탐색)',
                  fontsize=12, fontweight='bold')
ax_knee.set_xlabel('MemTable 크기 (log₂ scale)')
ax_knee.set_ylabel('평균 쓰기 처리량 (OPS/sec)')
ax_knee.grid(True, linestyle='--', alpha=0.5)

# ── 그래프 2: Write Stall 시간 vs MemTable 크기 ───────────────────────────────
bars2 = ax_stall.bar(range(len(collected)), stall_vals, color=colors,
                     alpha=0.82, edgecolor='black', linewidth=0.8)
ax_stall.set_xticks(range(len(collected)))
ax_stall.set_xticklabels(labels, fontsize=9)
ax_stall.set_title('2. 누적 Write Stall 시간 vs MemTable 크기',
                   fontsize=12, fontweight='bold')
ax_stall.set_ylabel('Write Stall 총 시간 (초, 4스레드 합산)')
ax_stall.grid(axis='y', linestyle='--', alpha=0.5)
max_stall = max(stall_vals) if max(stall_vals) > 0 else 1
for i, v in enumerate(stall_vals):
    ax_stall.text(i, v + max_stall * 0.02, f'{v:.1f}s',
                  ha='center', va='bottom', fontsize=9, fontweight='bold')

# ── 그래프 3: WAF vs MemTable 크기 ───────────────────────────────────────────
if any(v > 0 for v in waf_vals):
    bars3 = ax_waf.bar(range(len(collected)), waf_vals, color=colors,
                       alpha=0.82, edgecolor='black', linewidth=0.8)
    ax_waf.set_xticks(range(len(collected)))
    ax_waf.set_xticklabels(labels, fontsize=9)
    ax_waf.set_title('3. 쓰기 증폭(WAF) vs MemTable 크기\n'
                     'WAF = (user_written + compact_written) / user_written',
                     fontsize=12, fontweight='bold')
    ax_waf.set_ylabel('Write Amplification Factor (배율)')
    ax_waf.grid(axis='y', linestyle='--', alpha=0.5)
    max_waf = max(waf_vals) if max(waf_vals) > 0 else 1
    for i, v in enumerate(waf_vals):
        if v > 0:
            ax_waf.text(i, v + max_waf * 0.02, f'{v:.2f}×',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')
    # Read OPS를 보조 y축으로 추가
    if any(v > 0 for v in read_vals):
        ax_waf2 = ax_waf.twinx()
        ax_waf2.plot(range(len(collected)), read_vals, 's--',
                     color='navy', linewidth=1.5, markersize=7,
                     label='Read OPS (우축)', zorder=5)
        ax_waf2.set_ylabel('읽기 처리량 (OPS/sec)', color='navy')
        ax_waf2.tick_params(axis='y', labelcolor='navy')
        ax_waf2.legend(loc='upper right', fontsize=8)
else:
    ax_waf.text(0.5, 0.5,
                '통계 데이터 없음\n(--statistics=1 로그 확인 필요)',
                ha='center', va='center', transform=ax_waf.transAxes, fontsize=12)
    ax_waf.set_title('3. 쓰기 증폭(WAF) vs MemTable 크기', fontsize=12, fontweight='bold')

# ── 그래프 4: OPS 시계열 (모든 MemTable 크기 동시 비교) ─────────────────────
for d in collected:
    if not d['times']:
        continue
    lw = 2.5 if d['size_mb'] == 64 else 1.5  # 기본값(64MB) 강조
    ax_time.plot(d['times'], d['mean_ops'],
                 label=f"{d['label']} (n={d['n']})",
                 color=d['color'], linewidth=lw, alpha=0.9)
    if d['n'] > 1:
        ax_time.fill_between(
            d['times'],
            d['mean_ops'] - d['std_ops'],
            d['mean_ops'] + d['std_ops'],
            color=d['color'], alpha=0.10
        )
ax_time.set_title('4. 시간별 쓰기 처리량 (MemTable 크기별 비교)\n'
                  '음영: ±1 표준편차 (n≥2인 경우)',
                  fontsize=12, fontweight='bold')
ax_time.set_xlabel('시간 (Seconds)')
ax_time.set_ylabel('처리량 (OPS/sec)')
ax_time.grid(True, linestyle='--', alpha=0.5)
ax_time.legend(fontsize=8, loc='upper right', ncol=2)

plt.tight_layout(pad=3.0)

file_ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
out_path = f"{OUT_DIR}/memtable_sweep_{file_ts}.png"
plt.savefig(out_path, dpi=300, bbox_inches='tight')
print(f"  ✓ MemTable 스윕 대시보드 완료: {out_path}")

# ── [콘솔 요약 출력] ─────────────────────────────────────────────────────────
print()
print("=" * 72)
print(f"{'Exp':12s} {'OPS':>10s} {'Stall(s)':>10s} {'WAF':>8s} {'ReadOPS':>10s}")
print("-" * 72)
if collected:
    baseline = next((d for d in collected if d['size_mb'] == 64), None)
    for d in collected:
        rel = f"({d['overall_mean']/baseline['overall_mean']*100:.0f}%)" if baseline and baseline['overall_mean'] > 0 else ""
        print(f"{d['label']:12s} {d['overall_mean']:>10,.0f} {rel:>8s} "
              f"{d['stall_sec']:>8.1f}s {d['waf']:>7.2f}x {d['read_ops']:>10,.0f}")
print("=" * 72)
print(f"기준(64MB 기본값) 대비 상대 처리량 표시")
