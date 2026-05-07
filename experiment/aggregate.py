import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os
import glob

# ── 폴더 생성 ─────────────────────────────────────────────
os.makedirs('results/exp_data', exist_ok=True)
os.makedirs('results/graph',    exist_ok=True)

# ── 파일 로드 ─────────────────────────────────────────────
def load_all(pattern):
    """패턴에 맞는 모든 파일 로드 후 합치기"""
    files = sorted(glob.glob(f'results/exp_data/*{pattern}'))
    if not files:
        print(f"✗ 없음: *{pattern}")
        return None

    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df['source'] = os.path.basename(f)  # 출처 파일명 기록
        dfs.append(df)
        print(f"  ✓ 로드: {f}")

    combined = pd.concat(dfs, ignore_index=True)
    print(f"  → 총 {len(files)}개 파일, {len(combined)}개 행 합산\n")
    return combined

print("=" * 55)
print("실험 결과 취합 시작")
print("=" * 55)

print("\n[1] custom_dist 파일 취합 중...")
dist_all   = load_all('_custom_dist.csv')

print("[2] custom_cache_sweep 파일 취합 중...")
sweep_all  = load_all('_custom_cache_sweep.csv')

print("[3] dbbench_results 파일 취합 중...")
bench_all  = load_all('_dbbench_results.csv')

# ── 평균 계산 ─────────────────────────────────────────────
def aggregate(df, group_cols):
    """같은 분포끼리 평균/표준편차 계산"""
    agg = df.groupby(group_cols)['hit_rate'].agg(
        mean='mean',
        std='std',
        min='min',
        max='max',
        count='count'
    ).reset_index()
    agg['std'] = agg['std'].fillna(0)  # 실험 1회면 std=NaN → 0
    return agg

print("\n[4] 평균 계산 중...")

# 실험 1: 분포별 hit_rate 평균
dist_agg  = None
sweep_agg = None
bench_agg = None

if dist_all is not None:
    dist_agg = aggregate(dist_all, ['workload', 'cache_mb'])
    dist_agg.to_csv('results/exp_data/aggregated_dist.csv', index=False)
    print("  ✓ 저장: results/exp_data/aggregated_dist.csv")
    print(dist_agg.to_string(index=False))

if sweep_all is not None:
    sweep_agg = aggregate(sweep_all, ['workload', 'cache_mb'])
    sweep_agg.to_csv('results/exp_data/aggregated_cache_sweep.csv', index=False)
    print("\n  ✓ 저장: results/exp_data/aggregated_cache_sweep.csv")

if bench_all is not None:
    bench_agg = aggregate(bench_all, ['workload', 'cache_mb'])
    bench_agg.to_csv('results/exp_data/aggregated_dbbench.csv', index=False)
    print("  ✓ 저장: results/exp_data/aggregated_dbbench.csv")

# ── 그래프 생성 ───────────────────────────────────────────
print("\n[5] 그래프 생성 중...")

fig, axes = plt.subplots(1, 3, figsize=(21, 6))
fig.suptitle('RocksDB Block Cache Hit Rate - Aggregated Analysis\n'
             f'(실험 횟수 기반 평균)',
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

# ── 그래프 1: 분포별 평균 Hit Rate (막대 + 오차막대) ──────
ax1 = axes[0]
if dist_agg is not None:
    df32 = dist_agg[dist_agg['cache_mb'] == 32].sort_values(
        'mean', ascending=False).reset_index(drop=True)

    colors = plt.cm.RdYlGn(np.linspace(0.15, 0.9, len(df32)))
    bars = ax1.bar(df32['workload'], df32['mean'],
                   yerr=df32['std'],          # 표준편차 오차막대
                   color=colors, edgecolor='black',
                   linewidth=0.6, capsize=4,
                   error_kw={'elinewidth': 1.5, 'ecolor': 'black'})

    for b, (_, row) in zip(bars, df32.iterrows()):
        ax1.text(b.get_x()+b.get_width()/2,
                 b.get_height() + row['std'] + 1.0,
                 f"{row['mean']:.1f}%\n(n={int(row['count'])})",
                 ha='center', fontsize=7, fontweight='bold')

    ax1.set_ylabel('Cache Hit Rate (%)')
    ax1.set_ylim(0, 120)
    ax1.tick_params(axis='x', rotation=35)
    ax1.axhline(50, color='gray', ls='--', lw=0.8, label='50% baseline')
    ax1.legend(fontsize=8)
    ax1.grid(axis='y', alpha=0.3)
else:
    ax1.text(0.5, 0.5, 'No Data', ha='center', va='center',
             transform=ax1.transAxes, color='gray')

ax1.set_title('Avg Hit Rate by Distribution\n(Cache=32MB, ±std)')

# ── 그래프 2: 캐시 크기별 평균 Hit Rate (선 그래프) ───────
ax2 = axes[1]
has_data = False

if sweep_agg is not None:
    for wl in sweep_agg['workload'].unique():
        d = sweep_agg[sweep_agg['workload']==wl].sort_values('cache_mb')
        color, marker, ls = styles.get(wl, ('purple','o','-'))
        ax2.plot(d['cache_mb'], d['mean'],
                 ls+marker, color=color, lw=2, ms=7,
                 label=wl, markerfacecolor='white')
        # 표준편차 음영
        ax2.fill_between(d['cache_mb'],
                         d['mean'] - d['std'],
                         d['mean'] + d['std'],
                         alpha=0.1, color=color)
        has_data = True

if bench_agg is not None:
    for wl, color, marker in [('Uniform','gray','x'),('Sequential','black','+')]:
        d = bench_agg[bench_agg['workload']==wl].sort_values('cache_mb')
        if not d.empty:
            ax2.plot(d['cache_mb'], d['mean'],
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

ax2.set_title('Cache Size vs Avg Hit Rate\n(shaded=±std)')

# ── 그래프 3: 실험 횟수별 수렴 여부 (분포별 평균 변화) ────
ax3 = axes[2]
if dist_all is not None:
    df32_all = dist_all[dist_all['cache_mb'] == 32].copy()
    df32_all['exp_num'] = df32_all.groupby('workload').cumcount() + 1

    for wl in df32_all['workload'].unique():
        d = df32_all[df32_all['workload'] == wl].copy()
        # 누적 평균 계산
        d['cumulative_mean'] = d['hit_rate'].expanding().mean()
        color, marker, ls = styles.get(wl, ('purple','o','-'))
        ax3.plot(d['exp_num'], d['cumulative_mean'],
                 ls+marker, color=color, lw=2, ms=7,
                 label=wl, markerfacecolor='white')

    ax3.set_xlabel('실험 횟수')
    ax3.set_ylabel('누적 평균 Hit Rate (%)')
    ax3.set_ylim(0, 100)
    ax3.grid(True, alpha=0.3)
    ax3.legend(fontsize=7, loc='center right')
    ax3.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
else:
    ax3.text(0.5, 0.5, 'No Data', ha='center', va='center',
             transform=ax3.transAxes, color='gray')

ax3.set_title('Cumulative Mean Hit Rate\n(실험 횟수별 수렴 확인)')

plt.tight_layout()
out_path = 'results/graph/aggregated_analysis.png'
plt.savefig(out_path, bbox_inches='tight')
print(f"\n✓ 저장: {out_path}")
plt.show()

# ── 텍스트 요약 출력 ──────────────────────────────────────
if dist_agg is not None:
    print("\n" + "="*55)
    print("분포별 평균 Hit Rate 요약 (Cache=32MB)")
    print("="*55)
    df32 = dist_agg[dist_agg['cache_mb']==32].sort_values(
        'mean', ascending=False)
    print(f"{'분포':<18} {'평균':>8} {'표준편차':>8} "
          f"{'최소':>8} {'최대':>8} {'실험횟수':>8}")
    print("-"*55)
    for _, row in df32.iterrows():
        print(f"{row['workload']:<18} "
              f"{row['mean']:>7.2f}% "
              f"{row['std']:>7.2f}% "
              f"{row['min']:>7.2f}% "
              f"{row['max']:>7.2f}% "
              f"{int(row['count']):>8}")