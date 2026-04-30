import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

plt.rcParams.update({'figure.dpi': 150, 'font.size': 10})
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
fig.suptitle('RocksDB Block Cache Hit Rate Analysis', fontsize=13, fontweight='bold')

# ── 파일 존재 여부 확인 후 로드 ───────────────────────────
def load_csv(path):
    if os.path.exists(path):
        print(f"✓ 로드: {path}")
        return pd.read_csv(path)
    else:
        print(f"✗ 없음 (스킵): {path}")
        return None

df_bench  = load_csv('results/dbbench_results.csv')
df_custom = load_csv('results/custom_dist.csv')
df_sweep  = load_csv('results/custom_cache_sweep.csv')

# ── 그래프 1: 분포별 Hit Rate ─────────────────────────────
frames = []
if df_custom is not None:
    frames.append(df_custom[df_custom['cache_mb'] == 32][['workload','hit_rate']])
if df_bench is not None:
    frames.append(df_bench[df_bench['cache_mb'] == 32][['workload','hit_rate']])

if frames:
    combined = pd.concat(frames)
    combined = combined.sort_values('hit_rate', ascending=False).reset_index(drop=True)

    colors = plt.cm.RdYlGn(np.linspace(0.15, 0.9, len(combined)))
    bars = ax1.bar(combined['workload'], combined['hit_rate'],
                   color=colors, edgecolor='black', linewidth=0.6)

    for b, v in zip(bars, combined['hit_rate']):
        ax1.text(b.get_x() + b.get_width()/2, b.get_height() + 0.8,
                 f'{v:.1f}%', ha='center', fontsize=8, fontweight='bold')

    ax1.set_ylabel('Cache Hit Rate (%)')
    ax1.set_ylim(0, 115)
    ax1.tick_params(axis='x', rotation=35)
    ax1.axhline(50, color='gray', ls='--', lw=0.8, label='50% baseline')
    ax1.legend(fontsize=8)
    ax1.grid(axis='y', alpha=0.3)
else:
    ax1.text(0.5, 0.5, 'No Data Available',
             ha='center', va='center', fontsize=12, color='gray',
             transform=ax1.transAxes)

ax1.set_title('Access Distribution vs Cache Hit Rate\n(Cache=32MB, N=100K keys, Reads=50K)')

# ── 그래프 2: 캐시 크기 vs Hit Rate ──────────────────────
has_data = False

if df_sweep is not None:
    d_g = df_sweep[df_sweep['workload'] == 'Gaussian_s10'].sort_values('cache_mb')
    if not d_g.empty:
        ax2.plot(d_g['cache_mb'], d_g['hit_rate'],
                 '-^', color='forestgreen', lw=2, ms=7,
                 label='Gaussian (σ=10%)', markerfacecolor='white')
        has_data = True

if df_bench is not None:
    for wl, color, marker in [('Uniform','steelblue','o'),('Sequential','tomato','s')]:
        d = df_bench[df_bench['workload'] == wl].sort_values('cache_mb')
        if not d.empty:
            ax2.plot(d['cache_mb'], d['hit_rate'],
                     f'-{marker}', color=color, lw=2, ms=7,
                     label=wl, markerfacecolor='white')
            has_data = True

if has_data:
    ax2.set_xlabel('Cache Size (MB)')
    ax2.set_ylabel('Cache Hit Rate (%)')
    ax2.set_xscale('log', base=2)
    ax2.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.3)
    ax2.axhline(80, color='red', ls='--', lw=0.8, label='80% target')
    ax2.legend(fontsize=8)
else:
    ax2.text(0.5, 0.5, 'No Data Available',
             ha='center', va='center', fontsize=12, color='gray',
             transform=ax2.transAxes)

ax2.set_title('Cache Size vs Hit Rate\n(N=100K keys, Reads=50K)')

plt.tight_layout()
os.makedirs('results', exist_ok=True)
plt.savefig('results/cache_analysis.png', bbox_inches='tight')
print("✓ 저장: results/cache_analysis.png")
plt.show()