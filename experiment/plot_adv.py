// reader_adv 결과 그래프화

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

plt.rcParams.update({'figure.dpi': 150, 'font.size': 10})
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
fig.suptitle('RocksDB Pure Data Cache Hit Rate Analysis (Adv)', fontsize=13, fontweight='bold')

df_dist = pd.read_csv('results/custom_adv_dist.csv')
df_sweep = pd.read_csv('results/custom_adv_cache_sweep.csv')

# ── 그래프 1: 분포별 순수 데이터 Hit Rate (32MB) ──
df_dist = df_dist.sort_values('hit_rate', ascending=False).reset_index(drop=True)
colors = plt.cm.RdYlGn(np.linspace(0.15, 0.9, len(df_dist)))
bars = ax1.bar(df_dist['workload'], df_dist['hit_rate'], color=colors, edgecolor='black', linewidth=0.6)

for b, v in zip(bars, df_dist['hit_rate']):
    ax1.text(b.get_x() + b.get_width()/2, b.get_height() + 0.8, f'{v:.1f}%', ha='center', fontsize=8, fontweight='bold')

ax1.set_ylabel('Pure Data Hit Rate (%)')
ax1.set_ylim(0, 115)
ax1.tick_params(axis='x', rotation=35)
ax1.set_title('Access Distribution vs Pure Data Hit Rate\n(Cache=32MB, Index Caching Enabled)')

# ── 그래프 2: 캐시 크기별 순수 데이터 Hit Rate ──
styles = {'Gaussian_s10':('forestgreen','^'), 'Gaussian_s05':('limegreen','v'), 
          'Zipfian_a10':('steelblue','o'), 'Zipfian_a05':('cornflowerblue','s'),
          'Hotspot_8020':('orange','D'), 'Hotspot_9505':('red','*')}

for workload in df_sweep['workload'].unique():
    d = df_sweep[df_sweep['workload'] == workload].sort_values('cache_mb')
    color, marker = styles.get(workload, ('purple', 'o'))
    ax2.plot(d['cache_mb'], d['hit_rate'], marker=marker, color=color, lw=2, label=workload, markerfacecolor='white')

ax2.set_xlabel('Cache Size (MB)')
ax2.set_ylabel('Pure Data Hit Rate (%)')
ax2.set_xscale('log', base=2)
ax2.xaxis.set_major_formatter(mticker.ScalarFormatter())
ax2.set_ylim(0, 100)
ax2.legend(fontsize=8, loc='lower right')
ax2.set_title('Cache Size vs Pure Data Hit Rate\n(All Distributions)')

plt.tight_layout()
plt.savefig('results/cache_analysis_adv.png')
print("✓ 저장: results/cache_analysis_adv.png")
