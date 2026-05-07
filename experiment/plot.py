import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os
import glob
import matplotlib
matplotlib.use('Agg')

os.makedirs('results/exp_data', exist_ok=True)
os.makedirs('results/graph',    exist_ok=True)

# ── 최신 실험 폴더 확인 ───────────────────────────────────
def get_latest_run():
    f = 'results/exp_data/latest_run.txt'
    if os.path.exists(f):
        with open(f) as fp:
            return fp.read().strip()
    return None

ts      = get_latest_run() or "unknown"
run_dir = f'results/exp_data/run_{ts}'
graph_dir = f'results/graph/run_{ts}'
os.makedirs(graph_dir, exist_ok=True)

def load_csv(path):
    if os.path.exists(path):
        print(f"✓ 로드: {path}")
        return pd.read_csv(path)
    print(f"✗ 없음 (스킵): {path}")
    return None

# ── 해당 실험 폴더에서만 로드 ─────────────────────────────
df_custom = load_csv(f'{run_dir}/custom_dist.csv')
df_sweep  = load_csv(f'{run_dir}/custom_cache_sweep.csv')
df_bench  = load_csv(f'{run_dir}/dbbench_results.csv')

print(f"\n실험 타임스탬프: {ts}")

# ── 그래프 생성 ───────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
fig.suptitle(f'RocksDB Block Cache Hit Rate Analysis\n({ts})',
             fontsize=13, fontweight='bold')

styles = {
    'Gaussian_s10': ('forestgreen',    '^', '-'),
    'Gaussian_s05': ('limegreen',      'v', '-'),
    'Zipfian_a10':  ('steelblue',      'o', '-'),
    'Zipfian_a05':  ('cornflowerblue', 's', '-'),
    'Hotspot_8020': ('orange',         'D', '-'),
    'Hotspot_9505': ('red',            '*', '-'),
    'Uniform':      ('gray',           'x', '--'),
    'Sequential':   ('black',          '+', '--'),
    'Bimodal':      ('purple',         'P', '-'),
    'Latest':       ('brown',          'h', '-'),
}

# ── 그래프 1: 분포별 Hit Rate ─────────────────────────────
frames = []
if df_custom is not None:
    frames.append(df_custom[df_custom['cache_mb']==32][['workload','hit_rate']])
if df_bench is not None:
    frames.append(df_bench[df_bench['cache_mb']==32][['workload','hit_rate']])

if frames:
    combined = pd.concat(frames).sort_values(
        'hit_rate', ascending=False).reset_index(drop=True)
    colors = plt.cm.RdYlGn(np.linspace(0.15, 0.9, len(combined)))
    bars = ax1.bar(combined['workload'], combined['hit_rate'],
                   color=colors, edgecolor='black', linewidth=0.6)
    for b, v in zip(bars, combined['hit_rate']):
        ax1.text(b.get_x()+b.get_width()/2, b.get_height()+0.8,
                 f'{v:.1f}%', ha='center', fontsize=8, fontweight='bold')
    ax1.set_ylabel('Cache Hit Rate (%)')
    ax1.set_ylim(0, 115)
    ax1.tick_params(axis='x', rotation=35)
    ax1.axhline(50, color='gray', ls='--', lw=0.8, label='50% baseline')
    ax1.legend(fontsize=8)
    ax1.grid(axis='y', alpha=0.3)
else:
    ax1.text(0.5, 0.5, 'No Data', ha='center', va='center',
             transform=ax1.transAxes, color='gray')
ax1.set_title('Access Distribution vs Cache Hit Rate\n(Cache=32MB)')

# ── 그래프 2: 캐시 크기 vs Hit Rate ──────────────────────
has_data = False
if df_sweep is not None:
    for wl in df_sweep['workload'].unique():
        d = df_sweep[df_sweep['workload']==wl].sort_values('cache_mb')
        color, marker, ls = styles.get(wl, ('purple','o','-'))
        ax2.plot(d['cache_mb'], d['hit_rate'],
                 ls+marker, color=color, lw=2, ms=7,
                 label=wl, markerfacecolor='white')
        has_data = True

if df_bench is not None:
    for wl, color, marker in [('Uniform','gray','x'),('Sequential','black','+')]:
        d = df_bench[df_bench['workload']==wl].sort_values('cache_mb')
        if not d.empty:
            ax2.plot(d['cache_mb'], d['hit_rate'],
                     f'--{marker}', color=color, lw=2, ms=7,
                     label=f'{wl}(bench)', markerfacecolor='white')
            has_data = True

if has_data:
    ax2.set_xlabel('Cache Size (MB)')
    ax2.set_ylabel('Cache Hit Rate (%)')
    ax2.set_xscale('log', base=2)
    ax2.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax2.set_ylim(0, 100)
    ax2.grid(True, alpha=0.3)
    ax2.axhline(80, color='red', ls='--', lw=0.8, label='80% target')
    ax2.legend(fontsize=7, loc='lower right')
else:
    ax2.text(0.5, 0.5, 'No Data', ha='center', va='center',
             transform=ax2.transAxes, color='gray')
ax2.set_title('Cache Size vs Hit Rate (All Distributions)')

plt.tight_layout()

# ── 실험별 폴더에 그래프 저장 ─────────────────────────────
out_path = f'{graph_dir}/cache_analysis.png'
plt.savefig(out_path, bbox_inches='tight')
print(f"\n✓ 저장: {out_path}")