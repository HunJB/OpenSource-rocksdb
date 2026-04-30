# ~/rocksdb/experiment/plot.py
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

plt.rcParams.update({'figure.dpi': 150, 'font.size': 10})
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle('RocksDB Block Cache Hit Rate Analysis\n'
             '(단국대 SW Lab - Block Cache 실험)',
             fontsize=13, fontweight='bold')

# ── 데이터 로드 및 통합 ────────────────────────────────────
df_bench  = pd.read_csv('results/dbbench_results.csv')   # db_bench 결과
df_custom = pd.read_csv('results/custom_dist.csv')        # 커스텀 분포 결과
df_sweep  = pd.read_csv('results/custom_cache_sweep.csv') # 캐시 크기 sweep

# 32MB 기준으로 분포별 hit rate 비교
bench_32  = df_bench[df_bench['cache_mb'] == 32].copy()
custom_32 = df_custom[df_custom['cache_mb'] == 32].copy()

combined = pd.concat([bench_32[['workload','hit_rate']],
                       custom_32[['workload','hit_rate']]])
combined = combined.sort_values('hit_rate', ascending=False).reset_index(drop=True)

# ── 그래프 1: 분포별 Hit Rate 비교 ───────────────────────
colors = plt.cm.RdYlGn(np.linspace(0.15, 0.9, len(combined)))
bars = axes[0].bar(combined['workload'], combined['hit_rate'],
                   color=colors, edgecolor='black', linewidth=0.6)

for b, v in zip(bars, combined['hit_rate']):
    axes[0].text(b.get_x() + b.get_width()/2, b.get_height() + 0.8,
                 f'{v:.1f}%', ha='center', fontsize=8, fontweight='bold')

axes[0].set_title('Access Distribution vs Cache Hit Rate\n(Cache=32MB, N=100K keys, Reads=50K)',
                   fontsize=10)
axes[0].set_ylabel('Cache Hit Rate (%)')
axes[0].set_ylim(0, 115)
axes[0].tick_params(axis='x', rotation=35)
axes[0].axhline(50, color='gray', ls='--', lw=0.8, label='50% baseline')
axes[0].legend(fontsize=8)
axes[0].grid(axis='y', alpha=0.3)

# ── 그래프 2: 캐시 크기 vs Hit Rate (분포별) ──────────────
# db_bench Uniform & Sequential
for wl, color, marker in [('Uniform','steelblue','o'), ('Sequential','tomato','s')]:
    d = df_bench[df_bench['workload']==wl].sort_values('cache_mb')
    if not d.empty:
        axes[1].plot(d['cache_mb'], d['hit_rate'],
                     f'-{marker}', color=color, lw=2, ms=7,
                     label=wl, markerfacecolor='white')

# 커스텀 Gaussian sweep
d_g = df_sweep[df_sweep['workload']=='Gaussian_s10'].sort_values('cache_mb')
if not d_g.empty:
    axes[1].plot(d_g['cache_mb'], d_g['hit_rate'],
                 '-^', color='forestgreen', lw=2, ms=7,
                 label='Gaussian (σ=10%)', markerfacecolor='white')

axes[1].set_title('Cache Size vs Hit Rate\n(N=100K keys, Reads=50K)',
                   fontsize=10)
axes[1].set_xlabel('Cache Size (MB)')
axes[1].set_ylabel('Cache Hit Rate (%)')
axes[1].set_xscale('log', base=2)
axes[1].xaxis.set_major_formatter(mticker.ScalarFormatter())
axes[1].set_ylim(0, 100)
axes[1].grid(True, alpha=0.3)
axes[1].axhline(80, color='red', ls='--', lw=0.8, label='80% target')
axes[1].legend(fontsize=8)

plt.tight_layout()
plt.savefig('results/cache_analysis.png', bbox_inches='tight')
print("✓ 저장: results/cache_analysis.png")
plt.show()