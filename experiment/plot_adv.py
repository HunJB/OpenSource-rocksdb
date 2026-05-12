# reader_adv 결과 그래프화

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')

plt.rcParams.update({'figure.dpi': 150, 'font.size': 10})

# ── 최신 adv 실험 폴더 확인 ──────────────────────────────
def get_latest_adv_run():
    f = 'results/exp_data/latest_adv_run.txt'
    if os.path.exists(f):
        with open(f) as fp:
            return fp.read().strip()
    return None

run_id  = get_latest_adv_run()
run_dir = f'results/exp_data/run_{run_id}' if run_id else None

def load_csv(path):
    if path and os.path.exists(path):
        print(f"✓ 로드: {path}")
        return pd.read_csv(path)
    print(f"✗ 없음 (스킵): {path}")
    return None

df_dist  = load_csv(f'{run_dir}/custom_adv_dist.csv'       if run_dir else None)
df_sweep = load_csv(f'{run_dir}/custom_adv_cache_sweep.csv' if run_dir else None)

if df_dist is None and df_sweep is None:
    print("❌ 데이터 없음. reader_adv를 먼저 실행하세요.")
    exit(1)

print(f"\n실험 ID: {run_id}")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
fig.suptitle('RocksDB Pure Data Cache Hit Rate Analysis (Adv)', fontsize=13, fontweight='bold')

# ── 그래프 1: 분포별 순수 데이터 Hit Rate (32MB) ──
if df_dist is not None:
    df_dist = df_dist.sort_values('hit_rate', ascending=False).reset_index(drop=True)
    colors = plt.cm.RdYlGn(np.linspace(0.15, 0.9, len(df_dist)))
    bars = ax1.bar(df_dist['workload'], df_dist['hit_rate'],
                   color=colors, edgecolor='black', linewidth=0.6)
    for b, v in zip(bars, df_dist['hit_rate']):
        ax1.text(b.get_x() + b.get_width()/2, b.get_height() + 0.8,
                 f'{v:.1f}%', ha='center', fontsize=8, fontweight='bold')
    ax1.set_ylabel('Pure Data Hit Rate (%)')
    ax1.set_ylim(0, 115)
    ax1.tick_params(axis='x', rotation=35)
    ax1.grid(axis='y', alpha=0.3)
else:
    ax1.text(0.5, 0.5, 'No Data', ha='center', va='center',
             transform=ax1.transAxes, color='gray')
ax1.set_title('Access Distribution vs Pure Data Hit Rate\n(Cache=32MB, Index Caching Enabled)')

# ── 그래프 2: 캐시 크기별 순수 데이터 Hit Rate ──
styles = {
    'Gaussian_s10': ('forestgreen', '^'),
    'Gaussian_s05': ('limegreen',   'v'),
    'Zipfian_a10':  ('steelblue',   'o'),
    'Zipfian_a05':  ('cornflowerblue', 's'),
    'Hotspot_8020': ('orange',      'D'),
    'Hotspot_9505': ('red',         '*'),
}

if df_sweep is not None:
    for workload in df_sweep['workload'].unique():
        d = df_sweep[df_sweep['workload'] == workload].sort_values('cache_mb')
        color, marker = styles.get(workload, ('purple', 'o'))
        ax2.plot(d['cache_mb'], d['hit_rate'],
                 marker=marker, color=color, lw=2,
                 label=workload, markerfacecolor='white')
    ax2.set_xlabel('Cache Size (MB)')
    ax2.set_ylabel('Pure Data Hit Rate (%)')
    ax2.set_xscale('log', base=2)
    ax2.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax2.set_ylim(0, 100)
    ax2.legend(fontsize=8, loc='lower right')
    ax2.grid(True, alpha=0.3)
else:
    ax2.text(0.5, 0.5, 'No Data', ha='center', va='center',
             transform=ax2.transAxes, color='gray')
ax2.set_title('Cache Size vs Pure Data Hit Rate\n(All Distributions)')

plt.tight_layout()

out_path = f'{run_dir}/cache_analysis_adv.png' if run_dir else 'results/cache_analysis_adv.png'
os.makedirs(os.path.dirname(out_path), exist_ok=True)
plt.savefig(out_path, bbox_inches='tight')
print(f"✓ 저장: {out_path}")
