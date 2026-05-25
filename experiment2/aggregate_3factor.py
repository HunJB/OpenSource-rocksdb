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
except:
    pass
matplotlib.rcParams['axes.unicode_minus'] = False

home_dir = os.path.expanduser("~")
LOG_DIR = f"{home_dir}/rocksdb/experiment2/results/logs"
OUT_DIR = f"{home_dir}/rocksdb/experiment2/results/aggregated"
os.makedirs(OUT_DIR, exist_ok=True)

# 3요소 비교 실험 매핑 (그룹별 색상 통일)
exp_configs = {
    # 대조군
    'exp0_baseline':         ('0. Baseline (기준)',    'gray',    '--'),
    # Factor 1: Input 과다 — 초록 계열 (밝을수록 부하 낮음)
    'exp1a_input_threads8':  ('1A. Input 과다 (8T)',   '#66c266', '-'),
    'exp1b_input_threads16': ('1B. Input 과다 (16T)',  '#2ca02c', '-'),
    'exp1c_input_threads32': ('1C. Input 과다 (32T)',  '#1a5e1a', '-'),
    # Factor 2: MemTable 축소 — 주황 계열 (밝을수록 크기 큼)
    'exp2a_mem_16mb':        ('2A. MemTable 16MB',     '#ffb266', '-'),
    'exp2b_mem_4mb':         ('2B. MemTable 4MB',      '#ff7f0e', '-'),
    'exp2c_mem_2mb':         ('2C. MemTable 2MB',      '#8b3a00', '-'),
    # Factor 3: L0 한계 축소 — 파랑 계열 (밝을수록 임계값 높음)
    'exp3a_l0_12_24':        ('3A. L0 한계 12/24',     '#6baed6', '-'),
    'exp3b_l0_8_16':         ('3B. L0 한계 8/16',      '#1f77b4', '-'),
    'exp3c_l0_4_8':          ('3C. L0 한계 4/8',       '#08306b', '-'),
}

log_pattern = re.compile(
    r"thread\s+\d+:\s*\(\d+,\d+\)\s*ops\s*and\s*\(([\d.]+),[\d.]+\)\s*ops/second"
    r"\s*in\s*\([\d.]+,([\d.]+)\)\s*seconds"
)


def parse_log(filepath):
    """로그 파일 → {경과초: 합산OPS} 딕셔너리 (스레드별 OPS 합산)"""
    time_ops = collections.defaultdict(float)
    with open(filepath, 'r') as f:
        for line in f:
            m = log_pattern.search(line)
            if m:
                time_ops[int(float(m.group(2)))] += float(m.group(1))
    return dict(time_ops)


def is_completed(filepath):
    with open(filepath, 'r') as f:
        return '[EXPERIMENT_COMPLETED]' in f.read()


fig, axs = plt.subplots(2, 2, figsize=(24, 16))
ax_time, ax_mean = axs[0, 0], axs[0, 1]
ax_box,  ax_cum  = axs[1, 0], axs[1, 1]

data_found = False
parsed_data = []

for exp_key, (label, color, ls) in exp_configs.items():
    files = glob.glob(f"{LOG_DIR}/{exp_key}_*.log")
    completed_files = [f for f in files if is_completed(f)]

    if not completed_files:
        print(f"[알림] {exp_key}: 완료된 로그 없음, 제외")
        continue

    n_runs = len(completed_files)
    print(f"[정보] {exp_key}: {n_runs}회 완료, 평균 계산 중...")

    runs = [parse_log(f) for f in completed_files]

    # 모든 run에 등장하는 시간 포인트의 합집합으로 정렬
    all_times = sorted(set(t for run in runs for t in run))
    if not all_times:
        continue

    times_valid, mean_ops, std_ops, all_ops_pooled = [], [], [], []

    for t in all_times:
        vals = [run[t] for run in runs if t in run]
        if vals:
            times_valid.append(t)
            mean_ops.append(np.mean(vals))
            std_ops.append(np.std(vals))
            all_ops_pooled.extend(vals)

    mean_arr = np.array(mean_ops)
    std_arr  = np.array(std_ops)

    parsed_data.append({
        'label':        label,
        'color':        color,
        'ls':           ls,
        'times':        times_valid,
        'mean_ops':     mean_arr,
        'std_ops':      std_arr,
        'overall_mean': float(np.mean(mean_arr)),
        'cum':          np.cumsum(mean_arr),
        'all_ops':      all_ops_pooled,
        'n_runs':       n_runs,
    })
    data_found = True

if data_found:
    parsed_data.sort(key=lambda x: x['overall_mean'], reverse=True)
    box_data, box_labels, box_colors = [], [], []

    for d in parsed_data:
        lw = 2.5 if 'Baseline' in d['label'] else 1.5
        label_n = f"{d['label']} (n={d['n_runs']})"

        # 그래프 1: 시간별 OPS (평균선 + 표준편차 음영)
        ax_time.plot(d['times'], d['mean_ops'],
                     label=label_n, color=d['color'],
                     linestyle=d['ls'], linewidth=lw, alpha=0.9)
        if d['n_runs'] > 1:
            ax_time.fill_between(
                d['times'],
                d['mean_ops'] - d['std_ops'],
                d['mean_ops'] + d['std_ops'],
                color=d['color'], alpha=0.12
            )

        # 그래프 4: 누적 진행도
        ax_cum.plot(d['times'], d['cum'],
                    label=d['label'], color=d['color'],
                    linestyle=d['ls'], linewidth=lw)

        # 그래프 3: 박스플롯 — 모든 run의 OPS를 풀링하여 분포 표현
        box_data.append(d['all_ops'])
        box_labels.append(d['label'])
        box_colors.append(d['color'])

    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 그래프 1 ──────────────────────────────────────────
    ax_time.set_title(
        f'1. 시간별 쓰기 처리량 (평균 ± 표준편차) — {current_time_str}',
        fontsize=13, fontweight='bold'
    )
    ax_time.set_xlabel('시간 (Seconds)')
    ax_time.set_ylabel('처리량 (OPS / sec)')
    ax_time.grid(True, linestyle='--', alpha=0.5)
    ax_time.legend(fontsize=8, loc='upper right')

    # ── 그래프 2: 평균 OPS 가로 막대 ─────────────────────
    rev = parsed_data[::-1]
    bars = ax_mean.barh(
        [f"{d['label']} (n={d['n_runs']})" for d in rev],
        [d['overall_mean'] for d in rev],
        color=[d['color'] for d in rev],
        alpha=0.8, edgecolor='black'
    )
    ax_mean.set_title('2. 실험별 평균 쓰기 처리량 (다중 측정 평균)', fontsize=13, fontweight='bold')
    ax_mean.set_xlabel('평균 처리량 (OPS / sec)')
    ax_mean.grid(axis='x', linestyle='--', alpha=0.5)
    max_val = max(d['overall_mean'] for d in parsed_data)
    for bar in bars:
        w = bar.get_width()
        ax_mean.text(
            w + max_val * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f'{w:,.0f}', va='center', ha='left', fontsize=9, fontweight='bold'
        )

    # ── 그래프 3: 박스플롯 ───────────────────────────────
    bplot = ax_box.boxplot(
        box_data, vert=False, patch_artist=True,
        labels=box_labels, flierprops={'marker': '.', 'markersize': 3}
    )
    for patch, color in zip(bplot['boxes'], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax_box.set_title(
        '3. 처리량 분포 및 Write Stall 깊이 (다중 측정 누적 — 상자 작을수록 안정적)',
        fontsize=13, fontweight='bold'
    )
    ax_box.set_xlabel('처리량 분포 (OPS / sec)')
    ax_box.grid(True, linestyle='--', alpha=0.5)
    ax_box.invert_yaxis()

    # ── 그래프 4: 누적 진행도 ────────────────────────────
    ax_cum.set_title('4. 누적 작업 진행도 (목표 1,000만 건)', fontsize=13, fontweight='bold')
    ax_cum.set_xlabel('시간 (Seconds)')
    ax_cum.set_ylabel('누적 처리 건수')
    ax_cum.grid(True, linestyle='--', alpha=0.5)
    ax_cum.axhline(y=10000000, color='red', linestyle='--', linewidth=1, label='Target (10,000,000)')
    ax_cum.legend(fontsize=8, loc='lower right')

    plt.tight_layout(pad=3.0)

    file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"{OUT_DIR}/rocksdb_3factor_{file_timestamp}.png"
    plt.savefig(out_path, dpi=300)
    print(f"  ✓ 4구역 대시보드 완료: {out_path}")

else:
    print("❌ 파싱할 데이터가 없습니다. 로그 파일을 확인하세요.")
