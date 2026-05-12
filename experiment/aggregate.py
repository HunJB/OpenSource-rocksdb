# 수정 : adv 통합 추가 수행
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os
import glob
import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
fm.fontManager.addfont('/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf')
matplotlib.rcParams['font.family'] = 'NanumBarunGothic'
matplotlib.rcParams['axes.unicode_minus'] = False

# ── 폴더 생성 ─────────────────────────────────────────────
os.makedirs('results/aggregated', exist_ok=True)

def load_all(pattern):
    files = sorted(glob.glob(f'results/exp_data/run_*/{pattern}'))
    if not files:
        print(f"✗ 없음: run_*/{pattern}")
        return None, []
    dfs = []
    for f in files:
        try:
            if os.path.getsize(f) == 0: continue
            df = pd.read_csv(f)
            df['source'] = os.path.basename(os.path.dirname(f))
            dfs.append(df)
        except: continue
    if not dfs: return None, []
    combined = pd.concat(dfs, ignore_index=True)
    return combined, files

# 공통 스타일 사전
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

def aggregate_and_plot(dist_pattern, sweep_pattern, suffix, title_label):
    print(f"\n[{title_label}] 데이터 취합 및 시각화 중...")
    dist_all, dist_files = load_all(dist_pattern)
    sweep_all, _ = load_all(sweep_pattern)
    
    if dist_all is None: return
    n_runs = len(dist_files)

    # 평균/표준편차 계산
    dist_agg = dist_all.groupby(['workload', 'cache_mb'])['hit_rate'].agg(['mean', 'std', 'min', 'max', 'count']).reset_index()
    sweep_agg = sweep_all.groupby(['workload', 'cache_mb'])['hit_rate'].agg(['mean', 'std']).reset_index()

    # ── 그래프 생성 (3개 서브플롯 구조) ──────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(21, 6))
    fig.suptitle(f'RocksDB {title_label} - Aggregated Analysis (n={n_runs})', fontsize=14, fontweight='bold')

    # 1. 분포별 평균 Hit Rate (32MB)
    ax1 = axes[0]
    df32 = dist_agg[dist_agg['cache_mb'] == 32].sort_values('mean', ascending=False)
    colors = plt.cm.RdYlGn(np.linspace(0.15, 0.9, len(df32)))
    bars = ax1.bar(df32['workload'], df32['mean'], yerr=df32['std'], color=colors, edgecolor='black', capsize=4)
    for b, (_, row) in zip(bars, df32.iterrows()):
        ax1.text(b.get_x()+b.get_width()/2, b.get_height() + row['std'] + 1.0, f"{row['mean']:.1f}%", ha='center', fontsize=8)
    ax1.set_title('Avg Hit Rate (32MB)')
    ax1.set_ylabel('Hit Rate (%)')
    ax1.set_ylim(0, 120)
    ax1.tick_params(axis='x', rotation=35)
    ax1.grid(axis='y', alpha=0.3)

    # 2. 캐시 크기별 Sweep
    ax2 = axes[1]
    for wl in sweep_agg['workload'].unique():
        d = sweep_agg[sweep_agg['workload'] == wl].sort_values('cache_mb')
        color, marker, ls = styles.get(wl, ('purple', 'o', '-'))
        ax2.plot(d['cache_mb'], d['mean'], ls+marker, color=color, label=wl, markerfacecolor='white')
        ax2.fill_between(d['cache_mb'], d['mean'] - d['std'], d['mean'] + d['std'], color=color, alpha=0.1)
    ax2.set_title('Cache Size vs Avg Hit Rate')
    ax2.set_xscale('log', base=2)
    ax2.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax2.set_ylim(0, 105)
    ax2.legend(fontsize=7, loc='lower right')
    ax2.grid(True, alpha=0.3)

    # 3. 누적 평균 수렴 확인 (Convergence)
    ax3 = axes[2]
    df32_all = dist_all[dist_all['cache_mb'] == 32].copy()
    df32_all['exp_num'] = df32_all.groupby('workload').cumcount() + 1
    for wl in df32_all['workload'].unique():
        d = df32_all[df32_all['workload'] == wl].copy()
        d['cumulative_mean'] = d['hit_rate'].expanding().mean()
        color, marker, ls = styles.get(wl, ('purple', 'o', '-'))
        ax3.plot(d['exp_num'], d['cumulative_mean'], ls+marker, color=color, label=wl, markerfacecolor='white')
    ax3.set_title('Cumulative Mean Convergence')
    ax3.set_xlabel('Experiment Number')
    ax3.set_ylabel('Cumulative Mean (%)')
    ax3.set_ylim(0, 105)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = f'results/aggregated/aggregated_analysis_{suffix}_n{n_runs}.png'
    plt.savefig(out_path, bbox_inches='tight')
    plt.close()
    print(f"  ✓ 저장 완료: {out_path}")

# ── 실행부 ────────────────────────────────────────────────
print("=" * 55)
print("실험 결과 통합 취합 시작")
print("=" * 55)

# 1. 일반 결과 취합
aggregate_and_plot('custom_dist.csv', 'custom_cache_sweep.csv', 'normal', 'Normal Mode')

# 2. Advanced 결과 취합
aggregate_and_plot('custom_adv_dist.csv', 'custom_adv_cache_sweep.csv', 'advanced', 'Advanced Mode')
