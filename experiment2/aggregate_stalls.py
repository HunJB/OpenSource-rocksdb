import sys
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

# ── [0~10번 순서대로 정렬된 실험 매핑] ───────────────────────────
exp_configs = {
    'exp0_default':              ('0. 기본값 (Default Baseline)', 'gray', '--'),
    'exp1_thread_1':             ('1. 단일 스레드 (Threads=1)', 'brown', '-'),
    'exp2_thread_8':             ('2. 중간 스레드 (Threads=8)', 'green', '-'),
    'exp3_thread_16':            ('3. 과다 스레드 (Threads=16)', 'red', '-'),
    'exp4_small_memtable':       ('4. 작은 MemTable (2MB)', 'orange', '-'),
    'exp5_low_l0_limit':         ('5. 낮은 L0 한계 (Stall 유발)', 'purple', '-'),
    'exp6_pending_compaction':   ('6. Pending Compaction 병목', 'magenta', '-'),
    'exp7_universal_compaction': ('7. Universal Compaction', 'teal', '--'),
    'exp8_direct_io':            ('8. Direct I/O (OS캐시 배제)', 'blue', '--'),
    'exp9_sync_commit':          ('9. Sync Commit (fsync 강제)', 'black', '-.'),
    'exp10_flush_threads':       ('10. 플러시 스레드 증가 (Flush=4)', 'olive', '-')
}
# ────────────────────────────────────────────────────────

log_pattern = re.compile(r"thread\s+\d+:\s*\(\d+,\d+\)\s*ops\s*and\s*\(([\d.]+),[\d.]+\)\s*ops/second\s*in\s*\([\d.]+,([\d.]+)\)\s*seconds")

fig, axs = plt.subplots(2, 2, figsize=(24, 16))
ax_time = axs[0, 0]; ax_mean = axs[0, 1]
ax_box = axs[1, 0]; ax_cum = axs[1, 1]

data_found = False
parsed_data = [] 

for exp_key, (label, color, ls) in exp_configs.items():
    search_pattern = f"{LOG_DIR}/{exp_key}_*.log"
    files = glob.glob(search_pattern)
    
    if not files:
        print(f"[알림] {exp_key} 실험 로그가 없어 시각화에서 제외합니다.")
        continue
        
    latest_file = max(files, key=os.path.getctime)
    time_ops_map = collections.defaultdict(float)
        
    with open(latest_file, 'r') as f:
        for line in f:
            match = log_pattern.search(line)
            if match:
                ops_sec = float(match.group(1))
                total_sec = int(float(match.group(2)))
                time_ops_map[total_sec] += ops_sec
                
    if time_ops_map:
        times = sorted(time_ops_map.keys())
        ops_per_sec = [time_ops_map[t] for t in times]
        mean_ops = sum(ops_per_sec) / len(ops_per_sec)
        cumulative_ops = np.cumsum(ops_per_sec)
        
        parsed_data.append({
            'label': label, 'color': color, 'ls': ls,
            'times': times, 'ops': ops_per_sec, 'mean': mean_ops,
            'cum': cumulative_ops
        })
        data_found = True

if data_found:
    parsed_data.sort(key=lambda x: x['mean'], reverse=True)
    box_data = []; box_labels = []; box_colors = []

    for d in parsed_data:
        lw = 2.5 if "기본값" in d['label'] else 1.5
        ax_time.plot(d['times'], d['ops'], label=d['label'], color=d['color'], linestyle=d['ls'], linewidth=lw, alpha=0.8)
        ax_cum.plot(d['times'], d['cum'], label=d['label'], color=d['color'], linestyle=d['ls'], linewidth=lw)
        box_data.append(d['ops'])
        box_labels.append(d['label'].split(' ')[0] + " " + d['label'].split(' ')[1])
        box_colors.append(d['color'])

    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ax_time.set_title(f'1. 시간에 따른 쓰기 처리량 변화 (Total OPS) - {current_time_str}', fontsize=14, fontweight='bold')
    ax_time.set_xlabel('시간 (Seconds)')
    ax_time.set_ylabel('처리량 (OPS / sec)')
    ax_time.grid(True, linestyle='--', alpha=0.5)
    ax_time.legend(fontsize=9, loc='upper right')

    rev_data = parsed_data[::-1]
    labels = [d['label'] for d in rev_data]
    means = [d['mean'] for d in rev_data]
    colors = [d['color'] for d in rev_data]
    
    bars = ax_mean.barh(labels, means, color=colors, alpha=0.8, edgecolor='black')
    ax_mean.set_title('2. 실험별 평균 쓰기 처리량 (산술 평균)', fontsize=14, fontweight='bold')
    ax_mean.set_xlabel('평균 처리량 (OPS / sec)')
    ax_mean.grid(axis='x', linestyle='--', alpha=0.5)
    for bar in bars:
        width = bar.get_width()
        ax_mean.text(width + (max(means) * 0.01), bar.get_y() + bar.get_height()/2, 
                 f'{width:,.0f}', va='center', ha='left', fontsize=10, fontweight='bold')

    bplot = ax_box.boxplot(box_data, vert=False, patch_artist=True, labels=box_labels, flierprops={'marker': '.', 'markersize': 3})
    for patch, color in zip(bplot['boxes'], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax_box.set_title('3. 처리량 안정성 및 Write Stall 깊이 (Box Plot)', fontsize=14, fontweight='bold')
    ax_box.set_xlabel('처리량 분포 (OPS / sec) - 상자가 작을수록 안정적')
    ax_box.grid(True, linestyle='--', alpha=0.5)
    ax_box.invert_yaxis()

    ax_cum.set_title('4. 누적 작업 진행도 (목표 1000만 건 달성 경주)', fontsize=14, fontweight='bold')
    ax_cum.set_xlabel('시간 (Seconds)')
    ax_cum.set_ylabel('누적 처리 데이터 건수')
    ax_cum.grid(True, linestyle='--', alpha=0.5)
    ax_cum.axhline(y=10000000, color='red', linestyle='--', linewidth=1, label='Target (10,000,000)')
    ax_cum.legend(fontsize=9, loc='lower right')

    plt.tight_layout(pad=3.0)
    
    file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"{OUT_DIR}/rocksdb_dashboard_{file_timestamp}.png"
    plt.savefig(out_path, dpi=300)
    print(f"  ✓ 4구역 대시보드 시각화 완료: {out_path}")
else:
    print("❌ 파싱할 데이터가 없습니다. 로그 파일을 확인하세요.")
