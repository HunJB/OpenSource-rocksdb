import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os
import glob
import datetime
import matplotlib
matplotlib.use('Agg')

# ── 폴더 생성 ─────────────────────────────────────────────
os.makedirs('results/aggregated', exist_ok=True)
os.makedirs('results/exp_data',   exist_ok=True)
os.makedirs('results/graph',      exist_ok=True)

# ── 파일 로드 ─────────────────────────────────────────────
def load_all(pattern):
    files = sorted(glob.glob(f'results/exp_data/run_*/{pattern}'))
    if not files:
        print(f"✗ 없음: run_*/{pattern}")
        return None, []

    dfs = []
    for f in files:
        df = pd.read_csv(f)
        df['source'] = os.path.basename(os.path.dirname(f))
        dfs.append(df)
        print(f"  ✓ 로드: {f}")

    combined = pd.concat(dfs, ignore_index=True)
    print(f"  → 총 {len(files)}개 실험, {len(combined)}개 행 합산\n")
    return combined, files

print("=" * 55)
print("실험 결과 취합 시작")
print("=" * 55)

print("\n[1] custom_dist 파일 취합 중...")
dist_all,  dist_files  = load_all('custom_dist.csv')

print("[2] custom_cache_sweep 파일 취합 중...")
sweep_all, sweep_files = load_all('custom_cache_sweep.csv')

print("[3] dbbench_results 파일 취합 중...")
bench_all, bench_files = load_all('dbbench_results.csv')

# ── 실험 횟수 확인 ────────────────────────────────────────
n_runs = len(dist_files) if dist_files else 0
print(f"\n총 실험 횟수: {n_runs}회")

# ── 파일명 suffix 설정 ────────────────────────────────────
suffix = f"n{n_runs}"   # 예: n50, n100

# ── 평균 계산 ─────────────────────────────────────────────
def aggregate(df, group_cols):
    agg = df.groupby(group_cols)['hit_rate'].agg(
        mean  = 'mean',
        std   = 'std',
        min   = 'min',
        max   = 'max',
        count = 'count'
    ).reset_index()
    agg['std'] = agg['std'].fillna(0)
    return agg

print("\n[4] 평균 계산 중...")

dist_agg  = None
sweep_agg = None
bench_agg = None

if dist_all is not None:
    dist_agg = aggregate(dist_all, ['workload', 'cache_mb'])
    out = f'results/aggregated/aggregated_dist_{suffix}.csv'
    dist_agg.to_csv(out, index=False)
    print(f"  ✓ 저장: {out}")

if sweep_all is not None:
    sweep_agg = aggregate(sweep_all, ['workload', 'cache_mb'])
    out = f'results/aggregated/aggregated_cache_sweep_{suffix}.csv'
    sweep_agg.to_csv(out, index=False)
    print(f"  ✓ 저장: {out}")

if bench_all is not None:
    bench_agg = aggregate(bench_all, ['workload', 'cache_mb'])
    out = f'results/aggregated/aggregated_dbbench_{suffix}.csv'
    bench_agg.to_csv(out, index=False)
    print(f"  ✓ 저장: {out}")

# ── 배경정보 메타파일 저장 ────────────────────────────────
meta_path = f'results/aggregated/aggregated_meta_{suffix}.txt'
with open(meta_path, 'w') as f:
    f.write("=" * 50 + "\n")
    f.write("취합 실험 배경정보\n")
    f.write("=" * 50 + "\n")
    f.write(f"취합 생성 시각  : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"총 실험 횟수    : {n_runs}회\n")
    f.write(f"파일 suffix     : {suffix}\n")
    f.write("\n")
    f.write("포함된 실험 목록:\n")
    for i, fpath in enumerate(dist_files, 1):
        run_name = os.path.basename(os.path.dirname(fpath))
        # meta.txt에서 seed 읽기
        meta_file = f'results/exp_data/{run_name}/meta.txt'
        seed_info = ""
        if os.path.exists(meta_file):
            with open(meta_file) as mf:
                for line in mf:
                    if 'seed' in line:
                        seed_info = line.strip()
                        break
        f.write(f"  {i:3d}. {run_name}  ({seed_info})\n")
    f.write("\n")
    f.write("취합 파일 목록:\n")
    f.write(f"  - aggregated_dist_{suffix}.csv\n")
    f.write(f"  - aggregated_cache_sweep_{suffix}.csv\n")
    f.write(f"  - aggregated_dbbench_{suffix}.csv\n")
    f.write(f"  - aggregated_analysis_{suffix}.png\n")
    f.write(f"  - aggregated_meta_{suffix}.txt\n")

print(f"  ✓ 저장: {meta_path}")

# ── 그래프 생성 ───────────────────────────────────────────
print("\n[5] 그래프 생성 중...")

fig, axes = plt.subplots(1, 3, figsize=(21, 6))
fig.suptitle(
    f'RocksDB Block Cache Hit Rate - Aggregated Analysis\n'
    f'(총 {n_runs}회 실험 기반 평균)',
    fontsize=13, fontweight='bold'
)

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

# ── 그래프 1: 분포별 평균 Hit Rate ───────────────────────
ax1 = axes[0]
if dist_agg is not None:
    df32 = dist_agg[dist_agg['cache_mb'] == 32].sort_values(
        'mean', ascending=False).reset_index(drop=True)
    colors = plt.cm.RdYlGn(np.linspace(0.15, 0.9, len(df32)))
    bars = ax1.bar(df32['workload'], df32['mean'],
                   yerr=df32['std'],
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
ax1.set_title(f'Avg Hit Rate by Distribution\n(Cache=32MB, n={n_runs}회, ±std)')

# ── 그래프 2: 캐시 크기별 평균 Hit Rate ──────────────────
ax2 = axes[1]
has_data = False

if sweep_agg is not None:
    for wl in sweep_agg['workload'].unique():
        d = sweep_agg[sweep_agg['workload']==wl].sort_values('cache_mb')
        color, marker, ls = styles.get(wl, ('purple','o','-'))
        ax2.plot(d['cache_mb'], d['mean'],
                 ls+marker, color=color, lw=2, ms=7,
                 label=wl, markerfacecolor='white')
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
ax2.set_title(f'Cache Size vs Avg Hit Rate\n(n={n_runs}회, shaded=±std)')

# ── 그래프 3: 누적 평균 수렴 확인 ────────────────────────
ax3 = axes[2]
if dist_all is not None:
    df32_all = dist_all[dist_all['cache_mb'] == 32].copy()
    df32_all['exp_num'] = df32_all.groupby('workload').cumcount() + 1
    for wl in df32_all['workload'].unique():
        d = df32_all[df32_all['workload'] == wl].copy()
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
ax3.set_title(f'Cumulative Mean Hit Rate\n(실험 횟수별 수렴 확인, n={n_runs}회)')

plt.tight_layout()

# ── results/aggregated/ 에 저장 ───────────────────────────
out_path = f'results/aggregated/aggregated_analysis_{suffix}.png'
plt.savefig(out_path, bbox_inches='tight')
print(f"  ✓ 저장: {out_path}")

# ── 터미널 요약 출력 ──────────────────────────────────────
if dist_agg is not None:
    print("\n" + "="*60)
    print(f"분포별 평균 Hit Rate 요약 (Cache=32MB, 총 {n_runs}회 실험)")
    print("="*60)
    print(f"{'분포':<18} {'평균':>8} {'표준편차':>8} "
          f"{'최소':>8} {'최대':>8} {'실험횟수':>8}")
    print("-"*60)
    df32 = dist_agg[dist_agg['cache_mb']==32].sort_values(
        'mean', ascending=False)
    for _, row in df32.iterrows():
        print(f"{row['workload']:<18} "
              f"{row['mean']:>7.2f}% "
              f"{row['std']:>7.2f}% "
              f"{row['min']:>7.2f}% "
              f"{row['max']:>7.2f}% "
              f"{int(row['count']):>8}")

print("\n" + "="*60)
print(f"취합 완료: results/aggregated/ ({suffix})")
print("="*60)