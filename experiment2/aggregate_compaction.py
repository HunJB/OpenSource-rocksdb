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
LOG_DIR = f"{home_dir}/rocksdb/experiment2/results/compaction_logs"
OUT_DIR = f"{home_dir}/rocksdb/experiment2/results/aggregated"
os.makedirs(OUT_DIR, exist_ok=True)

# ── [실험 그룹 정의] ──────────────────────────────────────────────────────────
# 각 그룹: (그룹 ID, 그룹 제목, [(exp_key, 표시 레이블, 색상), ...])
GROUPS = [
    (
        'A',
        'A. 백그라운드 Compaction 스레드 수\n(max_background_jobs 조정)',
        [
            ('comp_bg1', 'BG=1\n(jobs=2)',  '#d62728'),
            ('comp_bg2', 'BG=2\n(jobs=3)',  '#ff7f0e'),
            ('comp_bg4', 'BG=4\n(jobs=5)',  '#2ca02c'),
            ('comp_bg8', 'BG=8\n(jobs=9)',  '#1f77b4'),
        ]
    ),
    (
        'B',
        'B. L0 파일 수 트리거 임계값\n(slowdown / stop 조정)',
        [
            ('comp_l0_4_8',    'L0=4/8\n(매우 타이트)',  '#d62728'),
            ('comp_l0_12_24',  'L0=12/24\n(타이트)',     '#ff7f0e'),
            ('comp_l0_20_36',  'L0=20/36\n(기본값)',     '#7f7f7f'),
            ('comp_l0_40_80',  'L0=40/80\n(널널)',       '#2ca02c'),
            ('comp_l0_80_160', 'L0=80/160\n(매우 널널)', '#1f77b4'),
        ]
    ),
    (
        'C',
        'C. 레벨 크기 및 배율 조정\n(max_bytes_for_level_base / multiplier)',
        [
            ('comp_lvl_small',   'L1=64MB\n×5',      '#d62728'),
            ('comp_lvl_default', 'L1=256MB\n×10\n(기본값)', '#7f7f7f'),
            ('comp_lvl_large',   'L1=1GB\n×10',      '#2ca02c'),
            ('comp_lvl_mult20',  'L1=256MB\n×20',    '#1f77b4'),
        ]
    ),
    (
        'D',
        'D. Compaction 알고리즘\n(Level-based vs Universal)',
        [
            ('comp_style_leveled',   'Level-based\n(기본값)', '#1f77b4'),
            ('comp_style_universal', 'Universal',             '#d62728'),
        ]
    ),
    (
        'E',
        'E. Pending Compaction 바이트 임계값\n(soft / hard 조정)',
        [
            ('comp_pend_very_tight', 'Soft=64MB\nHard=256MB', '#d62728'),
            ('comp_pend_tight',      'Soft=512MB\nHard=2GB',  '#ff7f0e'),
            ('comp_pend_loose',      'Soft=4GB\nHard=16GB',   '#2ca02c'),
            ('comp_pend_default',    'Soft=64GB\nHard=256GB\n(기본값)', '#1f77b4'),
        ]
    ),
]

# 초별 스레드 OPS 합산 패턴 (fillrandom 구간)
interval_pattern = re.compile(
    r"thread\s+\d+:\s*\(\d+,\d+\)\s*ops\s*and\s*\(([\d.]+),[\d.]+\)\s*ops/second"
    r"\s*in\s*\([\d.]+,([\d.]+)\)\s*seconds"
)


def parse_log(filepath):
    """로그 파일에서 핵심 지표 추출"""
    time_ops = collections.defaultdict(float)
    write_phase = True
    bytes_written = 0
    compact_write_bytes = 0
    stall_us = 0
    read_ops = 0.0

    with open(filepath, 'r') as f:
        for line in f:
            if 'fillrandom' in line and 'micros/op' in line:
                write_phase = False

            if write_phase:
                m = interval_pattern.search(line)
                if m:
                    t = int(float(m.group(2)))
                    time_ops[t] += float(m.group(1))

            if 'readrandom' in line and 'ops/sec' in line and 'micros/op' in line:
                m = re.search(r'([\d.]+)\s+ops/sec', line)
                if m:
                    read_ops = float(m.group(1))

            m = re.search(r'rocksdb\.bytes\.written COUNT : (\d+)', line)
            if m:
                bytes_written = int(m.group(1))

            m = re.search(r'rocksdb\.compact\.write\.bytes COUNT : (\d+)', line)
            if m:
                compact_write_bytes = int(m.group(1))

            m = re.search(r'rocksdb\.db\.write\.stall\s+P50.*SUM\s*:\s*(\d+)', line)
            if m:
                stall_us = int(m.group(1))

    waf = (bytes_written + compact_write_bytes) / bytes_written if bytes_written > 0 else 0.0
    return {
        'time_ops':  dict(time_ops),
        'stall_us':  stall_us,
        'waf':       waf,
        'read_ops':  read_ops,
    }


def is_completed(filepath):
    with open(filepath, 'r') as f:
        return '[EXPERIMENT_COMPLETED]' in f.read()


def load_group(experiments):
    """그룹 내 모든 실험 데이터 로드 → 집계 딕셔너리 반환"""
    results = []
    for exp_key, label, color in experiments:
        files = glob.glob(f"{LOG_DIR}/{exp_key}_*.log")
        done  = [f for f in files if is_completed(f)]

        if not done:
            print(f"  [알림] {exp_key}: 완료 로그 없음, 제외")
            results.append(None)
            continue

        n    = len(done)
        runs = [parse_log(f) for f in done]
        print(f"  [정보] {exp_key}: {n}회 완료")

        # OPS 시계열
        all_t = sorted(set(t for r in runs for t in r['time_ops']))
        times_v, mean_ops, std_ops = [], [], []
        for t in all_t:
            vals = [r['time_ops'][t] for r in runs if t in r['time_ops']]
            if vals:
                times_v.append(t)
                mean_ops.append(np.mean(vals))
                std_ops.append(np.std(vals))

        mean_ops_arr = np.array(mean_ops)
        overall      = float(np.mean(mean_ops_arr)) if len(mean_ops_arr) > 0 else 0.0
        stall_sec    = np.mean([r['stall_us'] / 1e6 for r in runs])
        waf_vals     = [r['waf'] for r in runs if r['waf'] > 0]
        waf_mean     = np.mean(waf_vals) if waf_vals else 0.0
        ro_vals      = [r['read_ops'] for r in runs if r['read_ops'] > 0]
        read_mean    = np.mean(ro_vals) if ro_vals else 0.0

        results.append({
            'key':     exp_key,
            'label':   label,
            'color':   color,
            'n':       n,
            'times':   times_v,
            'mean_ops': mean_ops_arr,
            'std_ops':  np.array(std_ops),
            'overall':  overall,
            'stall_sec': stall_sec,
            'waf':      waf_mean,
            'read_ops': read_mean,
        })
    return results


def draw_group_figure(group_id, group_title, results, file_ts):
    """그룹 하나에 대한 4분할 비교 그래프 생성"""
    valid = [r for r in results if r is not None]
    if not valid:
        print(f"  [경고] 그룹 {group_id}: 유효 데이터 없음, 건너뜀")
        return None

    labels   = [d['label']    for d in valid]
    colors   = [d['color']    for d in valid]
    x        = range(len(valid))
    ops_vals  = [d['overall']  for d in valid]
    stall_vals= [d['stall_sec'] for d in valid]
    waf_vals  = [d['waf']      for d in valid]
    read_vals = [d['read_ops'] for d in valid]

    fig, axs = plt.subplots(1, 4, figsize=(24, 7))
    fig.suptitle(f'Compaction 실험 — 그룹 {group_id}: {group_title}',
                 fontsize=13, fontweight='bold')

    def bar_chart(ax, values, ylabel, title, fmt='{:.0f}'):
        bars = ax.bar(x, values, color=colors, alpha=0.82, edgecolor='black', linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=11, fontweight='bold')
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        max_v = max(values) if max(values) > 0 else 1
        for i, v in enumerate(values):
            ax.text(i, v + max_v * 0.02, fmt.format(v),
                    ha='center', va='bottom', fontsize=8, fontweight='bold')

    bar_chart(axs[0], ops_vals,   '평균 쓰기 처리량 (OPS/sec)',
              '① 평균 쓰기 OPS', '{:,.0f}')
    bar_chart(axs[1], stall_vals, 'Write Stall 총 시간 (초)',
              '② Write Stall 시간', '{:.1f}s')

    if any(v > 0 for v in waf_vals):
        bar_chart(axs[2], waf_vals, 'Write Amplification Factor',
                  '③ 쓰기 증폭 (WAF)', '{:.2f}×')
    else:
        axs[2].text(0.5, 0.5, '통계 데이터 없음', ha='center', va='center',
                    transform=axs[2].transAxes)
        axs[2].set_title('③ 쓰기 증폭 (WAF)', fontsize=11, fontweight='bold')

    if any(v > 0 for v in read_vals):
        bar_chart(axs[3], read_vals, '읽기 처리량 (OPS/sec)',
                  '④ 읽기 OPS (높을수록 RAF↓)', '{:,.0f}')
    else:
        axs[3].text(0.5, 0.5, '읽기 데이터 없음', ha='center', va='center',
                    transform=axs[3].transAxes)
        axs[3].set_title('④ 읽기 OPS', fontsize=11, fontweight='bold')

    plt.tight_layout(pad=2.5)
    out_path = f"{OUT_DIR}/compaction_group{group_id}_{file_ts}.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ 그룹 {group_id} 완료: {out_path}")
    return valid


def draw_summary(all_group_bests, file_ts):
    """각 그룹에서 쓰기 OPS 최고 시나리오를 모아 종합 비교"""
    if not all_group_bests:
        return

    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    labels   = [f"[{gid}] {d['key']}"  for gid, d in all_group_bests]
    colors   = [d['color']              for _,   d in all_group_bests]
    ops_v    = [d['overall']            for _,   d in all_group_bests]
    stall_v  = [d['stall_sec']          for _,   d in all_group_bests]
    waf_v    = [d['waf']                for _,   d in all_group_bests]
    read_v   = [d['read_ops']           for _,   d in all_group_bests]
    x        = range(len(all_group_bests))

    fig, axs = plt.subplots(2, 2, figsize=(20, 12))
    fig.suptitle(
        f'Compaction 실험 종합 요약 — 그룹별 최고 시나리오 비교  ({current_time_str})',
        fontsize=14, fontweight='bold'
    )

    def summary_bar(ax, values, ylabel, title, fmt):
        bars = ax.bar(x, values, color=colors, alpha=0.85, edgecolor='black')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=9, rotation=15, ha='right')
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=12, fontweight='bold')
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        max_v = max(values) if max(values) > 0 else 1
        for i, v in enumerate(values):
            ax.text(i, v + max_v * 0.02, fmt.format(v),
                    ha='center', va='bottom', fontsize=9, fontweight='bold')

    summary_bar(axs[0, 0], ops_v,   '평균 쓰기 처리량 (OPS/sec)',
                '1. 쓰기 처리량 (그룹별 최고)', '{:,.0f}')
    summary_bar(axs[0, 1], stall_v, 'Write Stall 총 시간 (초)',
                '2. Write Stall 시간 (낮을수록 우수)', '{:.1f}s')

    if any(v > 0 for v in waf_v):
        summary_bar(axs[1, 0], waf_v, 'WAF',
                    '3. 쓰기 증폭 WAF (낮을수록 우수)', '{:.2f}×')
    else:
        axs[1, 0].text(0.5, 0.5, '통계 데이터 없음', ha='center', va='center',
                       transform=axs[1, 0].transAxes)

    if any(v > 0 for v in read_v):
        summary_bar(axs[1, 1], read_v, '읽기 처리량 (OPS/sec)',
                    '4. 읽기 OPS (높을수록 RAF↓)', '{:,.0f}')
    else:
        axs[1, 1].text(0.5, 0.5, '읽기 데이터 없음', ha='center', va='center',
                       transform=axs[1, 1].transAxes)

    plt.tight_layout(pad=3.0)
    out_path = f"{OUT_DIR}/compaction_summary_{file_ts}.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"  ✓ 종합 요약 완료: {out_path}")


# ── [메인: 전체 그룹 처리] ────────────────────────────────────────────────────
file_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
all_group_bests = []   # (그룹ID, best_dict)

print("=" * 60)
print("  Compaction 실험 결과 집계 시작")
print("=" * 60)

for group_id, group_title, experiments in GROUPS:
    print(f"\n[그룹 {group_id}] {group_title.splitlines()[0]}")
    results = load_group(experiments)
    valid   = draw_group_figure(group_id, group_title, results, file_ts)

    if valid:
        best = max(valid, key=lambda d: d['overall'])
        all_group_bests.append((group_id, best))
        print(f"  → 그룹 {group_id} 최고: {best['key']} "
              f"(OPS={best['overall']:,.0f}, Stall={best['stall_sec']:.1f}s, "
              f"WAF={best['waf']:.2f}×)")

# 종합 요약 그래프
print(f"\n[종합 요약]")
draw_summary(all_group_bests, file_ts)

# ── [콘솔 전체 요약 출력] ────────────────────────────────────────────────────
print()
print("=" * 78)
print(f"{'Exp':25s} {'OPS':>10s} {'Stall(s)':>10s} {'WAF':>8s} {'ReadOPS':>10s}")
print("-" * 78)
for group_id, group_title, experiments in GROUPS:
    print(f"  ── 그룹 {group_id} ──")
    for exp_key, label, color in experiments:
        files = glob.glob(f"{LOG_DIR}/{exp_key}_*.log")
        done  = [f for f in files if is_completed(f)]
        if not done:
            print(f"  {exp_key:23s}  (데이터 없음)")
            continue
        runs = [parse_log(f) for f in done]
        all_t = sorted(set(t for r in runs for t in r['time_ops']))
        ops_list = []
        for t in all_t:
            vals = [r['time_ops'][t] for r in runs if t in r['time_ops']]
            if vals:
                ops_list.append(np.mean(vals))
        overall   = np.mean(ops_list) if ops_list else 0.0
        stall_sec = np.mean([r['stall_us'] / 1e6 for r in runs])
        waf_vs    = [r['waf'] for r in runs if r['waf'] > 0]
        waf_m     = np.mean(waf_vs) if waf_vs else 0.0
        ro_vs     = [r['read_ops'] for r in runs if r['read_ops'] > 0]
        ro_m      = np.mean(ro_vs) if ro_vs else 0.0
        print(f"  {exp_key:25s} {overall:>10,.0f} {stall_sec:>10.1f} "
              f"{waf_m:>7.2f}x {ro_m:>10,.0f}")
print("=" * 78)
