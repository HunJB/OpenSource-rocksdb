"""
RocksDB 블록 캐시 실험 종합 분석 보고서 PDF 생성기
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import os, glob

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, PageBreak, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── 폰트 등록 ──────────────────────────────────────────────
FONT_DIR = '/usr/share/fonts/truetype/nanum/'
pdfmetrics.registerFont(TTFont('Nanum',     FONT_DIR + 'NanumBarunGothic.ttf'))
pdfmetrics.registerFont(TTFont('NanumBold', FONT_DIR + 'NanumBarunGothicBold.ttf'))
fm.fontManager.addfont(FONT_DIR + 'NanumBarunGothic.ttf')
matplotlib.rcParams['font.family'] = 'NanumBarunGothic'
matplotlib.rcParams['axes.unicode_minus'] = False

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm
CONTENT_W = PAGE_W - 2 * MARGIN
TMP = '/tmp/full_report_imgs'
os.makedirs(TMP, exist_ok=True)

# ── 데이터 경로 ────────────────────────────────────────────
AGG  = '/home/ubuntu/rocksdb/experiment/results/aggregated'
LAST = '/home/ubuntu/rocksdb/experiment/results/exp_data/run_20260512_050141_3616733'

dist1506  = pd.read_csv(f'{AGG}/aggregated_dist_n1506.csv')
sweep1506 = pd.read_csv(f'{AGG}/aggregated_cache_sweep_n1506.csv')
dist1006  = pd.read_csv(f'{AGG}/aggregated_dist_n1006.csv')
dist6     = pd.read_csv(f'{AGG}/aggregated_dist_n6.csv')
movedist  = pd.read_csv(f'{LAST}/custom_movedist.csv')
movebatch = pd.read_csv(f'{LAST}/custom_movedist_batch.csv')
showdist  = pd.read_csv(f'{LAST}/showdist.csv')

AREA_COLS = [c for c in showdist.columns if c.startswith('area')]

# ── 스타일 ─────────────────────────────────────────────────
_ss = getSampleStyleSheet()
def S(name, **kw):
    d = dict(fontName='Nanum', fontSize=10, leading=16)
    d.update(kw)
    return ParagraphStyle(name, parent=_ss['Normal'], **d)

sT  = S('sT', fontName='NanumBold', fontSize=22, leading=30, alignment=1,
         textColor=colors.HexColor('#0d2137'), spaceAfter=4)
sS  = S('sS', fontSize=12, leading=18, alignment=1,
         textColor=colors.HexColor('#3a5a7a'), spaceAfter=4)
sD  = S('sD', fontSize=9,  leading=14, alignment=1,
         textColor=colors.HexColor('#666666'), spaceAfter=20)
sH1 = S('sH1', fontName='NanumBold', fontSize=14, leading=20,
         textColor=colors.HexColor('#0d2137'), spaceBefore=16, spaceAfter=6,
         borderPadding=(0,0,4,0))
sH2 = S('sH2', fontName='NanumBold', fontSize=11, leading=17,
         textColor=colors.HexColor('#1a4a7a'), spaceBefore=10, spaceAfter=4)
sB  = S('sB', fontSize=9.5, leading=16, spaceAfter=5)
sCp = S('sCp', fontSize=8.5, leading=13, alignment=1,
         textColor=colors.HexColor('#555'), spaceAfter=8)
sBu = S('sBu', fontSize=9.5, leading=16, leftIndent=14, spaceAfter=3)

def P(t, s=sB): return Paragraph(t, s)
def H1(t): return Paragraph(t, sH1)
def H2(t): return Paragraph(t, sH2)
def HR(): return HRFlowable(width='100%', thickness=0.6,
                             color=colors.HexColor('#b0c4d8'), spaceAfter=6)
def SP(h=6): return Spacer(1, h)
def Img(p, h=None):
    img = Image(p, width=CONTENT_W)
    if h: img._restrictSize(CONTENT_W, h)
    return img
def Cap(t): return Paragraph(t, sCp)

# ── 그래프 저장 헬퍼 ───────────────────────────────────────
def savefig(name, fig):
    p = f'{TMP}/{name}'
    fig.savefig(p, dpi=140, bbox_inches='tight')
    plt.close(fig)
    return p

WCOLORS = {
    'Hotspot_9505': '#d62728', 'Gaussian_s05': '#2ca02c',
    'Zipfian_a10':  '#1f77b4', 'Sequential':   '#7f7f7f',
    'Hotspot_8020': '#ff7f0e', 'Bimodal':       '#9467bd',
    'Gaussian_s10': '#8fbc8f', 'Zipfian_a05':   '#aec7e8',
    'Latest':       '#8c564b', 'Uniform':        '#c7c7c7',
}

# ════════════════════════════════════════════════════════════
# 그래프 1: 전체 워크로드 Hit Rate 비교 (가로 막대)
# ════════════════════════════════════════════════════════════
def fig_overview():
    d = dist1506[dist1506['cache_mb']==32].sort_values('mean')
    fig, ax = plt.subplots(figsize=(10, 5))
    bar_colors = [WCOLORS.get(w, '#aaaaaa') for w in d['workload']]
    bars = ax.barh(d['workload'], d['mean'], xerr=d['std'],
                   color=bar_colors, edgecolor='white', height=0.6,
                   capsize=4, alpha=0.88)
    for bar, (_, row) in zip(bars, d.iterrows()):
        ax.text(row['mean'] + row['std'] + 0.5, bar.get_y() + bar.get_height()/2,
                f"{row['mean']:.1f}%", va='center', fontsize=9, fontweight='bold')
    ax.set_xlim(0, 108)
    ax.set_xlabel('평균 Hit Rate (%)', fontsize=10)
    ax.set_title('워크로드별 평균 Hit Rate (캐시 32MB, n=1,506회)\n오차 막대 = ±1σ', fontsize=11)
    ax.axvline(50, color='gray', lw=0.8, ls='--', alpha=0.5)
    ax.grid(axis='x', alpha=0.3)
    fig.tight_layout()
    return savefig('fig_overview.png', fig)

# ════════════════════════════════════════════════════════════
# 그래프 2: 캐시 크기별 Sweep
# ════════════════════════════════════════════════════════════
def fig_sweep():
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    cache_sizes = [4, 8, 16, 32, 64, 128, 256]

    # 왼쪽: 전체 워크로드
    ax = axes[0]
    for wl in sweep1506['workload'].unique():
        d = sweep1506[sweep1506['workload']==wl].sort_values('cache_mb')
        color = WCOLORS.get(wl, '#aaaaaa')
        ax.plot(d['cache_mb'], d['mean'], 'o-', color=color,
                label=wl, lw=1.8, markersize=5, markerfacecolor='white')
    ax.set_xscale('log', base=2)
    ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax.set_xticks(cache_sizes)
    ax.set_xticklabels([f'{m}MB' for m in cache_sizes], rotation=30, fontsize=8)
    ax.set_ylim(0, 105); ax.set_ylabel('Hit Rate (%)')
    ax.set_title('캐시 크기별 Hit Rate (전체 워크로드)', fontsize=10)
    ax.legend(fontsize=7, loc='lower right', ncol=2)
    ax.grid(True, alpha=0.3)

    # 오른쪽: 포화점 분석 (캐시 크기 구간별 변화율)
    ax2 = axes[1]
    highlight = ['Hotspot_9505', 'Gaussian_s05', 'Zipfian_a10', 'Uniform', 'Latest']
    for wl in highlight:
        d = sweep1506[sweep1506['workload']==wl].sort_values('cache_mb')
        color = WCOLORS.get(wl, '#aaaaaa')
        ax2.plot(d['cache_mb'], d['mean'], 'o-', color=color,
                 label=wl, lw=2.2, markersize=6)
        # 포화 표시
        sat = d[d['mean'] >= d['mean'].max() * 0.99].iloc[0]
        ax2.scatter(sat['cache_mb'], sat['mean'], s=80, color=color,
                    zorder=5, marker='*')

    ax2.set_xscale('log', base=2)
    ax2.xaxis.set_major_formatter(mticker.ScalarFormatter())
    ax2.set_xticks(cache_sizes)
    ax2.set_xticklabels([f'{m}MB' for m in cache_sizes], rotation=30, fontsize=8)
    ax2.set_ylim(0, 105); ax2.set_ylabel('Hit Rate (%)')
    ax2.set_title('주요 워크로드 포화점 비교\n(★ = 포화 시작점)', fontsize=10)
    ax2.legend(fontsize=8, loc='lower right')
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    return savefig('fig_sweep.png', fig)

# ════════════════════════════════════════════════════════════
# 그래프 3: 실험 수렴 분석 (n=6 → n=1006 → n=1506)
# ════════════════════════════════════════════════════════════
def fig_convergence():
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # 왼쪽: n별 hit rate 비교
    ax = axes[0]
    wloads = dist1506[dist1506['cache_mb']==32].sort_values('mean', ascending=False)['workload'].tolist()
    x = np.arange(len(wloads))
    w = 0.28
    for i, (n_label, df_n, color) in enumerate([
        ('n=6',    dist6,    '#f4a460'),
        ('n=1,006', dist1006, '#6baed6'),
        ('n=1,506', dist1506, '#2171b5'),
    ]):
        means = [df_n[(df_n['workload']==wl)&(df_n['cache_mb']==32)]['mean'].values[0]
                 if len(df_n[(df_n['workload']==wl)&(df_n['cache_mb']==32)])>0 else 0
                 for wl in wloads]
        ax.bar(x + (i-1)*w, means, width=w, label=n_label, color=color,
               edgecolor='white', alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(wloads, rotation=35, ha='right', fontsize=8)
    ax.set_ylim(0, 110); ax.set_ylabel('평균 Hit Rate (%)')
    ax.set_title('실험 횟수별 Hit Rate 수렴\n(캐시 32MB)', fontsize=10)
    ax.legend(fontsize=9); ax.grid(axis='y', alpha=0.3)

    # 오른쪽: 표준편차 수렴
    ax2 = axes[1]
    for i, (n_label, df_n, color) in enumerate([
        ('n=6',     dist6,    '#f4a460'),
        ('n=1,006', dist1006, '#6baed6'),
        ('n=1,506', dist1506, '#2171b5'),
    ]):
        stds = [df_n[(df_n['workload']==wl)&(df_n['cache_mb']==32)]['std'].values[0]
                if len(df_n[(df_n['workload']==wl)&(df_n['cache_mb']==32)])>0 else 0
                for wl in wloads]
        ax2.bar(x + (i-1)*w, stds, width=w, label=n_label, color=color,
                edgecolor='white', alpha=0.9)
    ax2.set_xticks(x)
    ax2.set_xticklabels(wloads, rotation=35, ha='right', fontsize=8)
    ax2.set_ylabel('표준편차 (%)')
    ax2.set_title('실험 횟수 증가에 따른 표준편차 수렴\n(통계적 안정성 확인)', fontsize=10)
    ax2.legend(fontsize=9); ax2.grid(axis='y', alpha=0.3)

    fig.tight_layout()
    return savefig('fig_convergence.png', fig)

# ════════════════════════════════════════════════════════════
# 그래프 4: 키 접근 빈도 분포 히스토그램
# ════════════════════════════════════════════════════════════
def fig_showdist():
    highlight = ['Uniform','Gaussian_s05','Gaussian_s10','Zipfian_a10',
                 'Hotspot_9505','Bimodal','Latest']
    fig, axes = plt.subplots(2, 4, figsize=(14, 6))
    axes = axes.flatten()
    for i, wl in enumerate(highlight):
        ax = axes[i]
        row = showdist[showdist['workload']==wl]
        if row.empty:
            ax.set_visible(False); continue
        vals = row[AREA_COLS].values.flatten().astype(float)
        color = WCOLORS.get(wl, '#aaaaaa')
        ax.bar(range(len(vals)), vals, color=color, alpha=0.75, width=1.0)
        ax.set_title(wl, fontsize=9, fontweight='bold')
        ax.set_xticks([0, 24, 49])
        ax.set_xticklabels(['key_0', 'key_50k', 'key_100k'], fontsize=7)
        ax.set_yticks([]); ax.grid(axis='y', alpha=0.3)
    axes[-1].set_visible(False)
    fig.suptitle('워크로드별 키 접근 빈도 분포 (50구간 히스토그램)', fontsize=12, fontweight='bold')
    fig.tight_layout()
    return savefig('fig_showdist.png', fig)

# ════════════════════════════════════════════════════════════
# 그래프 5: 동적 분포 — 전체 vs 정적 비교
# ════════════════════════════════════════════════════════════
def fig_dynamic_compare():
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # 왼쪽: 동적 vs 정적 hit rate 비교
    ax = axes[0]
    static_ref = {
        'Gaussian_s05': 87.22, 'Gaussian_s10': 69.14,
        'Hotspot_9505': 92.69, 'Uniform': 28.02
    }
    dyn_data = {
        row['workload']: row['hit_rate']
        for _, row in movedist.iterrows()
    }
    labels_d = list(dyn_data.keys())
    vals_d   = list(dyn_data.values())
    x = np.arange(len(labels_d))
    bars = ax.bar(x, vals_d, width=0.5, color='#1f77b4', alpha=0.8,
                  edgecolor='white', label='동적 분포 (이동 가우시안)')
    for bar, v in zip(bars, vals_d):
        ax.text(bar.get_x()+bar.get_width()/2, v+1, f'{v:.1f}%',
                ha='center', fontsize=9, fontweight='bold')
    ax.axhline(87.22, color='#2ca02c', lw=1.5, ls='--', alpha=0.7, label='Gaussian_s05 (정적, 87.2%)')
    ax.axhline(69.14, color='#8fbc8f', lw=1.5, ls='--', alpha=0.7, label='Gaussian_s10 (정적, 69.1%)')
    ax.set_xticks(x)
    ax.set_xticklabels([l.replace('moving_gaussian','mg_') for l in labels_d],
                       rotation=20, ha='right', fontsize=8)
    ax.set_ylim(0, 105); ax.set_ylabel('Hit Rate (%)')
    ax.set_title('동적 분포 전체 Hit Rate\nvs 정적 가우시안 비교 (캐시 32MB)', fontsize=10)
    ax.legend(fontsize=8); ax.grid(axis='y', alpha=0.3)

    # 오른쪽: σ별 비교 (std=5% vs std=10%)
    ax2 = axes[1]
    groups = {
        'std=10%\n(넓은 분포)': [
            ('030710', dyn_data.get('moving_gaussian030710', 0)),
            ('020810', dyn_data.get('moving_gaussian020810', 0)),
        ],
        'std=5%\n(좁은 분포)': [
            ('030705', dyn_data.get('moving_gaussian030705', 0)),
            ('020805', dyn_data.get('moving_gaussian020805', 0)),
        ],
    }
    x2 = np.array([0, 1])
    for offset, (grp_label, items) in enumerate(groups.items()):
        vals2 = [v for _, v in items]
        lbls2 = [l for l, _ in items]
        c = '#1f77b4' if '10%' in grp_label else '#2ca02c'
        bars2 = ax2.bar(x2 + offset*2.5, vals2, width=0.6, color=c, alpha=0.8, edgecolor='white')
        for bar, v, l in zip(bars2, vals2, lbls2):
            ax2.text(bar.get_x()+bar.get_width()/2, v+1, f'{v:.1f}%',
                     ha='center', fontsize=9, fontweight='bold')
            ax2.text(bar.get_x()+bar.get_width()/2, -5, l,
                     ha='center', fontsize=8, color='gray')
        ax2.text(np.mean(x2 + offset*2.5), 102, grp_label,
                 ha='center', fontsize=9, fontweight='bold', color=c)
    ax2.set_ylim(0, 110); ax2.set_ylabel('Hit Rate (%)')
    ax2.set_xticks([]); ax2.set_title('σ값별 Hit Rate 비교\n(이동 가우시안)', fontsize=10)
    ax2.grid(axis='y', alpha=0.3)

    fig.tight_layout()
    return savefig('fig_dynamic_compare.png', fig)

# ════════════════════════════════════════════════════════════
# 그래프 6: 배치별 시계열 (동적 분포 4종)
# ════════════════════════════════════════════════════════════
def fig_batch():
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    batches = list(range(10))
    line_styles = {'moving_gaussian030710': ('o-', '#1f77b4', 'mg030710 (피크30→70, σ=10%)'),
                   'moving_gaussian020810': ('s-', '#aec7e8', 'mg020810 (피크20→80, σ=10%)'),
                   'moving_gaussian030705': ('^-', '#2ca02c', 'mg030705 (피크30→70, σ=5%)'),
                   'moving_gaussian020805': ('D-', '#98df8a', 'mg020805 (피크20→80, σ=5%)'),}

    for ax, grp_label, wl_filter in [
        (axes[0], 'std=10% (넓은 분포)',   ['moving_gaussian030710','moving_gaussian020810']),
        (axes[1], 'std=5%  (좁은 분포)',    ['moving_gaussian030705','moving_gaussian020805']),
    ]:
        for wl in wl_filter:
            d = movebatch[movebatch['workload']==wl].sort_values('batch')
            style, color, label = line_styles[wl]
            ax.plot(d['batch'], d['hit_rate'], style, color=color,
                    lw=2.2, markersize=6, label=label)
            # 배치5 급락 표시
            drop = d[d['batch']==5]['hit_rate'].values[0]
            ax.annotate(f'{drop:.1f}%', xy=(5, drop),
                        xytext=(5.3, drop-8 if drop>30 else drop+8),
                        fontsize=8, color=color,
                        arrowprops=dict(arrowstyle='->', color=color, lw=0.8))

        ax.axvline(4.5, color='black', lw=1.5, ls='--', alpha=0.5)
        ax.text(4.6, 5, '패턴\n전환', fontsize=8)
        ax.fill_between(range(5),  0, 105, alpha=0.04, color='blue')
        ax.fill_between(range(5,10),0, 105, alpha=0.04, color='red')
        ax.text(2, 100, '전반부\n(1번 피크)', ha='center', fontsize=8, color='#1a3a6a', alpha=0.7)
        ax.text(7, 100, '후반부\n(2번 피크)', ha='center', fontsize=8, color='#6a1a1a', alpha=0.7)
        ax.set_xlabel('배치 번호'); ax.set_ylabel('Hit Rate (%)')
        ax.set_ylim(0, 110); ax.set_xticks(batches)
        ax.set_title(f'배치별 Hit Rate 시계열 — {grp_label}', fontsize=10)
        ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return savefig('fig_batch.png', fig)

# ════════════════════════════════════════════════════════════
# 그래프 7: 캐시 효율 분류 매트릭스
# ════════════════════════════════════════════════════════════
def fig_matrix():
    fig, ax = plt.subplots(figsize=(10, 5.5))

    # x: 4MB hit rate (저캐시 효율), y: 32MB hit rate (기본 효율)
    # 버블 크기: 포화점 캐시 크기 역수 (작을수록 좋음 → 버블 크게)
    data = {
        'Hotspot_9505': (67.8,  92.7,  8),
        'Zipfian_a10':  (66.9,  80.5,  64),
        'Gaussian_s05': (22.6,  87.2,  32),
        'Sequential':   (74.95, 74.95, 4),
        'Hotspot_8020': (13.4,  70.7,  128),
        'Bimodal':      (11.4,  69.3,  64),
        'Gaussian_s10': (11.4,  69.1,  64),
        'Zipfian_a05':  (12.0,  41.4,  256),
        'Latest':       (4.2,   29.7,  256),
        'Uniform':      (3.8,   28.0,  None),
    }
    for wl, (x4, x32, sat) in data.items():
        color = WCOLORS.get(wl, '#aaaaaa')
        size = 400 if sat is None else max(80, 1200 / sat * 8)
        ax.scatter(x4, x32, s=size, color=color, alpha=0.75, edgecolors='white', lw=1.5)
        ax.annotate(wl.replace('_', '\n'), (x4, x32),
                    xytext=(5, 5), textcoords='offset points', fontsize=7.5)

    ax.axhline(70, color='gray', lw=0.8, ls=':', alpha=0.5)
    ax.axvline(30, color='gray', lw=0.8, ls=':', alpha=0.5)
    ax.text(31, 71, '고효율 영역\n(소캐시·고히트)', fontsize=8, color='green', alpha=0.7)
    ax.text(1,  20, '저효율 영역\n(대용량 캐시 필요)', fontsize=8, color='red', alpha=0.7)
    ax.set_xlabel('4MB 캐시 Hit Rate (%)', fontsize=10)
    ax.set_ylabel('32MB 캐시 Hit Rate (%)', fontsize=10)
    ax.set_title('캐시 효율 매트릭스\n(버블 크기 = 포화점 도달 용이성)', fontsize=11)
    ax.set_xlim(-5, 90); ax.set_ylim(15, 105)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return savefig('fig_matrix.png', fig)

# ── 그래프 생성 ────────────────────────────────────────────
print("그래프 생성 중...")
p_overview  = fig_overview()
p_sweep     = fig_sweep()
p_conv      = fig_convergence()
p_showdist  = fig_showdist()
p_dyncmp    = fig_dynamic_compare()
p_batch     = fig_batch()
p_matrix    = fig_matrix()
print("  ✓ 7개 그래프 완료")

# ════════════════════════════════════════════════════════════
# PDF 문서 구성
# ════════════════════════════════════════════════════════════
OUT = '/home/ubuntu/rocksdb/experiment/results/full_analysis_report.pdf'
doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=MARGIN, rightMargin=MARGIN,
                        topMargin=MARGIN, bottomMargin=MARGIN)

# 색상 테이블 스타일 헬퍼
def make_table(data, col_widths, header_color='#1a3a5c'):
    t = Table(data, colWidths=col_widths)
    n = len(data)
    row_bg = [colors.HexColor('#f0f4f8') if i%2==0 else colors.HexColor('#e8eef5')
              for i in range(n-1)]
    t.setStyle(TableStyle([
        ('FONTNAME',      (0,0), (-1,0),  'NanumBold'),
        ('FONTNAME',      (0,1), (-1,-1), 'Nanum'),
        ('FONTSIZE',      (0,0), (-1,-1), 8.5),
        ('BACKGROUND',    (0,0), (-1,0),  colors.HexColor(header_color)),
        ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),  row_bg),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('GRID',          (0,0), (-1,-1), 0.4, colors.HexColor('#c0cfe0')),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    return t

story = []

# ════ 표지 ════════════════════════════════════════════════
story += [
    SP(50),
    Paragraph('RocksDB 블록 캐시', sT),
    Paragraph('히트율 실험 종합 분석 보고서', sT),
    SP(12),
    HR(),
    SP(8),
    Paragraph('Block Cache Hit Rate Comprehensive Analysis Report', sS),
    SP(20),
]

cover_data = [
    ['항목', '내용'],
    ['실험 대상', 'RocksDB Block Cache (HyperClockCache)'],
    ['DB 구성', '키 100,000개 × 값 1KB = 총 100MB'],
    ['총 실험 횟수', '1,506회 (통계적 수렴 확인)'],
    ['워크로드 종류', '정적 10종 + 동적 4종 (이동 가우시안)'],
    ['캐시 스윕 범위', '4MB ~ 256MB (7단계)'],
    ['측정 지표', 'Block Cache Hit Rate (BLOCK_CACHE_HIT / 전체 요청)'],
    ['실험 환경', 'Linux, RocksDB 최신 버전, 캐시 오염 방지 적용'],
]
story += [make_table(cover_data, [CONTENT_W*0.30, CONTENT_W*0.70]), SP(20), PageBreak()]

# ════ 목차 ════════════════════════════════════════════════
story += [
    H1('목차'),
    HR(),
    P('1. 실험 개요 및 방법론'),
    P('2. 전체 워크로드 Hit Rate 비교'),
    P('3. 캐시 크기별 성능 변화 (Cache Sweep)'),
    P('4. 워크로드별 접근 패턴 분포'),
    P('5. 실험 수렴 및 통계적 신뢰도'),
    P('6. 동적 분포 실험 (Moving Gaussian)'),
    P('7. 캐시 효율 매트릭스 분석'),
    P('8. 핵심 발견 및 결론'),
    PageBreak(),
]

# ════ 1. 실험 개요 ════════════════════════════════════════
story += [
    H1('1. 실험 개요 및 방법론'),
    HR(),
    H2('1-1. 실험 목적'),
    P('RocksDB 블록 캐시의 히트율이 <b>읽기 요청 분포(워크로드)와 캐시 크기에 따라 어떻게 달라지는지</b> '
      '정량적으로 측정합니다. 총 1,506회 반복 실험을 통해 통계적으로 신뢰 가능한 결과를 확보했습니다.'),
    SP(4),
    H2('1-2. 측정 원리'),
    P('RocksDB의 <b>BLOCK_CACHE_HIT</b>와 <b>BLOCK_CACHE_MISS</b> 통계 카운터를 사용해 측정합니다. '
      'writer가 DB를 초기화한 뒤 Flush + CompactRange로 모든 데이터를 SST 파일에 내려 MemTable '
      '영향을 제거합니다. 이후 reader가 각 워크로드별로 50,000건의 읽기 요청을 수행하며 Hit Rate를 기록합니다.'),
    P('Hit Rate = BLOCK_CACHE_HIT / (BLOCK_CACHE_HIT + BLOCK_CACHE_MISS) × 100%'),
    SP(4),
    H2('1-3. 실험 파라미터'),
]
param_data = [
    ['파라미터', '값', '설명'],
    ['NUM_KEYS', '100,000', '전체 키 수'],
    ['VALUE_SIZE', '1 KB', '키당 값 크기 (총 DB ≈ 100MB)'],
    ['NUM_REQUESTS', '50,000', '실험당 읽기 요청 수'],
    ['BATCH', '5,000', '동적 분포 배치 1개 크기'],
    ['BATCH_NUM', '10', '동적 분포 배치 수'],
    ['캐시 크기', '4, 8, 16, 32, 64, 128, 256 MB', '스윕 실험 캐시 목록'],
    ['기준 캐시', '32 MB', 'RocksDB 기본값 (HyperClockCache)'],
    ['총 실험 수', '1,506회', '통계적 신뢰 확보'],
]
story += [make_table(param_data, [CONTENT_W*0.22, CONTENT_W*0.25, CONTENT_W*0.53]), SP(8), PageBreak()]

# ════ 2. 전체 비교 ════════════════════════════════════════
story += [
    H1('2. 전체 워크로드 Hit Rate 비교'),
    HR(),
    Img(p_overview, h=8.5*cm),
    Cap('▲ 32MB 캐시 기준, n=1,506회 실험 평균. 오차 막대 = ±1σ'),
    SP(6),
    H2('2-1. 결과 요약'),
]

dist_table_data = [
    ['순위', '워크로드', '평균 Hit Rate', '표준편차', '포화 캐시'],
    ['1', 'Hotspot_9505',  '92.69%', '±2.39%', '8MB'],
    ['2', 'Gaussian_s05',  '87.22%', '±2.25%', '32MB'],
    ['3', 'Zipfian_a10',   '80.49%', '±2.08%', '64MB'],
    ['4', 'Sequential',    '74.95%', '±1.93%', '무관(블록)'],
    ['5', 'Hotspot_8020',  '70.69%', '±1.83%', '128MB'],
    ['6', 'Bimodal',       '69.25%', '±1.80%', '64MB'],
    ['7', 'Gaussian_s10',  '69.14%', '±1.79%', '64MB'],
    ['8', 'Zipfian_a05',   '41.44%', '±1.09%', '256MB+'],
    ['9', 'Latest',        '29.69%', '±0.79%', '256MB+'],
    ['10','Uniform',       '28.02%', '±0.75%', '한계(56.8%)'],
]
story += [make_table(dist_table_data,
          [CONTENT_W*0.07, CONTENT_W*0.23, CONTENT_W*0.18,
           CONTENT_W*0.18, CONTENT_W*0.34]), SP(6)]

story += [
    H2('2-2. 핵심 관찰'),
    P('• <b>Hit Rate 범위: 28% ~ 93%</b> — 동일한 32MB 캐시에서도 워크로드에 따라 3.3배 차이'),
    P('• <b>Hotspot_9505 vs Uniform: 64.7%p 차이</b> — 접근 집중도가 캐시 효율의 가장 큰 결정 요인'),
    P('• <b>Sequential의 특수성</b> — 캐시 크기와 완전히 무관. 블록 내 공간 지역성만으로 75% 달성'),
    P('• <b>Uniform/Latest의 물리적 한계</b> — 256MB(데이터 2.5배)에서도 57%가 최대'),
    SP(8), PageBreak(),
]

# ════ 3. 캐시 크기별 Sweep ════════════════════════════════
story += [
    H1('3. 캐시 크기별 성능 변화 (Cache Sweep)'),
    HR(),
    Img(p_sweep, h=9*cm),
    Cap('▲ 좌: 전체 워크로드 캐시 스윕  /  우: 주요 워크로드 포화점 비교 (★ = 포화 시작점)'),
    SP(6),
    H2('3-1. 포화점(Saturation Point) 분석'),
    P('포화점이란 캐시를 더 늘려도 Hit Rate가 더 이상 오르지 않는 지점입니다. '
      '실질 Working Set 크기와 일치하며, 이를 초과한 캐시 투자는 효과가 없습니다.'),
    SP(4),
]

sat_data = [
    ['워크로드', '4MB Hit Rate', '포화 캐시 크기', '이론 Working Set', '포화 후 최대 Hit Rate'],
    ['Hotspot_9505', '67.8%', '8MB',    '~5MB (5% × 100MB)',  '92.7%'],
    ['Zipfian_a10',  '66.9%', '64MB+',  '집중 키 위주',        '80.9%'],
    ['Gaussian_s05', '22.6%', '32MB',   '~30MB (σ=5%)',       '87.2%'],
    ['Gaussian_s10', '11.4%', '64MB',   '~60MB (σ=10%)',      '77.6%'],
    ['Sequential',   '75.0%', '무관',   'N/A (블록 지역성)',   '75.0%'],
    ['Uniform',      '3.8%',  '한계없음','이론 최대 56.8%',    '56.7%'],
]
story += [make_table(sat_data,
          [CONTENT_W*0.20, CONTENT_W*0.15, CONTENT_W*0.18,
           CONTENT_W*0.25, CONTENT_W*0.22]),
    SP(6),
    H2('3-2. 캐시 크기 투자 가이드'),
    P('• <b>Hotspot 계열</b>: 데이터의 5~8% 캐시만으로 포화 → 소형 캐시로 최대 효과'),
    P('• <b>Gaussian 계열</b>: Working Set = 6×σ×총키수×값크기. σ가 2배 커지면 필요 캐시도 2배'),
    P('• <b>Zipfian_a10</b>: 4MB에서 이미 66.9% → 초기 캐시 투자 효과가 가장 큰 분포'),
    P('• <b>Uniform/Latest</b>: 캐시를 아무리 늘려도 57% 한계 → 캐시 확장보다 접근 패턴 개선이 우선'),
    SP(8), PageBreak(),
]

# ════ 4. 접근 패턴 분포 ══════════════════════════════════
story += [
    H1('4. 워크로드별 키 접근 패턴 분포'),
    HR(),
    Img(p_showdist, h=9.5*cm),
    Cap('▲ 각 워크로드의 키 공간(0~100k) 접근 빈도를 50구간으로 집계한 히스토그램'),
    SP(6),
    H2('4-1. 분포 형태와 Hit Rate의 관계'),
    P('히스토그램의 <b>뾰족함(집중도)</b>이 클수록 캐시 효율이 높습니다. '
      '집중도가 높으면 적은 수의 블록이 반복 접근되어 캐시 재사용률이 올라가기 때문입니다.'),
    SP(4),
]

dist_char = [
    ['워크로드', '형태 특성', '히트율에 미치는 영향'],
    ['Uniform',      '완전 평탄 — 모든 구간 동일 높이', '캐시 재사용 불가, 최저 효율'],
    ['Gaussian_s05', '단일 뾰족 피크 (좁음)',           '소수 구간 집중 → 최고 효율 그룹'],
    ['Gaussian_s10', '단일 완만 피크 (넓음)',           '범위 확대로 Working Set 증가'],
    ['Zipfian_a10',  '좌측 극단 집중 (역지수형)',        '소수 hot key → 소형 캐시로 포화'],
    ['Hotspot_9505', '좌측 계단형 (명확한 hot/cold)',   '가장 빠른 포화, 최고 Hit Rate'],
    ['Bimodal',      '이중 피크 (대칭)',                '두 Working Set 합산 → 대용량 캐시 필요'],
    ['Latest',       '우측 점진적 상승',               '광범위한 접근 분산 → 낮은 효율'],
]
story += [make_table(dist_char,
          [CONTENT_W*0.18, CONTENT_W*0.35, CONTENT_W*0.47]),
    SP(8), PageBreak(),
]

# ════ 5. 수렴 분석 ════════════════════════════════════════
story += [
    H1('5. 실험 수렴 및 통계적 신뢰도'),
    HR(),
    Img(p_conv, h=9*cm),
    Cap('▲ 좌: 실험 횟수별 평균 Hit Rate 수렴  /  우: 실험 횟수 증가에 따른 표준편차 감소'),
    SP(6),
    H2('5-1. 수렴 분석 결과'),
    P('n=6 → n=1,006 → n=1,506으로 실험 횟수가 늘어남에 따라 평균값이 안정되고 '
      '표준편차가 빠르게 감소합니다. 이는 실험 결과가 통계적으로 신뢰 가능한 수준임을 나타냅니다.'),
    SP(4),
]

conv_data = [
    ['워크로드',     'n=6 평균 (std)',       'n=1,006 평균 (std)',   'n=1,506 평균 (std)',   '수렴 여부'],
    ['Hotspot_9505', '77.3% (±37.9%)',  '92.66% (±2.93%)',  '92.69% (±2.39%)',  '✓ 완전 수렴'],
    ['Gaussian_s05', '72.7% (±35.6%)',  '87.20% (±2.75%)',  '87.22% (±2.25%)',  '✓ 완전 수렴'],
    ['Zipfian_a10',  '67.1% (±32.9%)',  '80.47% (±2.54%)',  '80.49% (±2.08%)',  '✓ 완전 수렴'],
    ['Uniform',      '23.4% (±11.4%)',  '28.02% (±0.91%)',  '28.02% (±0.75%)',  '✓ 완전 수렴'],
    ['Latest',       '24.7% (±12.1%)',  '29.67% (±0.96%)',  '29.69% (±0.79%)',  '✓ 완전 수렴'],
]
story += [make_table(conv_data,
          [CONTENT_W*0.20, CONTENT_W*0.22, CONTENT_W*0.22,
           CONTENT_W*0.22, CONTENT_W*0.14]),
    SP(6),
    H2('5-2. 통계적 신뢰도 판단'),
    P('• n=6 구간에서는 표준편차가 평균의 40~50%에 달해 결과를 신뢰하기 어렵습니다.'),
    P('• n=1,006 이상에서는 표준편차가 ±3% 이내로 안정되어 통계적으로 유의미한 결과를 제공합니다.'),
    P('• n=1,506과 n=1,006의 평균 차이가 모든 워크로드에서 0.1%p 미만으로, '
      '<b>1,000회 이상이면 충분한 실험 횟수</b>임을 확인했습니다.'),
    SP(8), PageBreak(),
]

# ════ 6. 동적 분포 ════════════════════════════════════════
story += [
    H1('6. 동적 분포 실험 (Moving Gaussian)'),
    HR(),
    H2('6-1. 동적 분포란?'),
    P('실험 도중 접근 패턴이 이동하는 분포입니다. 전반부 25,000건은 피크 A 위치, '
      '후반부 25,000건은 피크 B 위치에서 접근이 집중됩니다. '
      '캐시가 새로운 패턴에 적응하는 속도(적응 지연)를 측정하는 데 사용합니다.'),
    SP(4),
]

dyn_meta = [
    ['워크로드', '전반부 피크', '후반부 피크', 'σ', '전체 Hit Rate'],
    ['moving_gaussian030710', '30%', '70%', '10%', '56.19%'],
    ['moving_gaussian020810', '20%', '80%', '10%', '58.23%'],
    ['moving_gaussian030705', '30%', '70%', '5%',  '76.78%'],
    ['moving_gaussian020805', '20%', '80%', '5%',  '76.70%'],
]
story += [make_table(dyn_meta,
          [CONTENT_W*0.33, CONTENT_W*0.13, CONTENT_W*0.13,
           CONTENT_W*0.10, CONTENT_W*0.31]),
    SP(8),
    Img(p_dyncmp, h=9*cm),
    Cap('▲ 좌: 동적 분포 전체 Hit Rate vs 정적 가우시안 비교  /  우: σ별 성능 차이'),
    SP(8), PageBreak(),
    H2('6-2. 배치별 Hit Rate 시계열'),
    Img(p_batch, h=9*cm),
    Cap('▲ 배치 0~4: 1번 피크 워밍업  |  배치 5: 패턴 전환 직후 급락  |  배치 5~9: 2번 피크 재적응'),
    SP(6),
    H2('6-3. 주요 발견'),
]

story += [
    P('• <b>캐시 워밍업 기간</b>: 패턴 전환 없이 진행 시, 초기 3~4 배치(15,000~20,000건)에서 '
      'Hit Rate가 빠르게 상승합니다.'),
    P('• <b>패턴 전환 충격</b>: 배치 5에서 Hit Rate가 급락합니다 '
      '(σ=10%: 78% → 24%, σ=5%: 95% → 38%).'),
    P('• <b>재적응 속도</b>: 전환 후 3~4 배치만에 새 패턴으로 적응 완료 — '
      'LRU 캐시가 오래된 패턴의 블록을 효율적으로 교체합니다.'),
    P('• <b>σ 값의 영향</b>: σ=5%가 σ=10%보다 최고 Hit Rate가 약 16%p 높고, '
      '패턴 전환 직후에도 더 높은 기저값을 유지합니다.'),
    SP(8), PageBreak(),
]

# ════ 7. 캐시 효율 매트릭스 ══════════════════════════════
story += [
    H1('7. 캐시 효율 매트릭스 분석'),
    HR(),
    Img(p_matrix, h=9.5*cm),
    Cap('▲ X축: 4MB(소형) 캐시 Hit Rate  /  Y축: 32MB(기본) 캐시 Hit Rate  /  버블: 포화 용이성'),
    SP(6),
    H2('7-1. 사분면 해석'),
    P('• <b>우상단 (고효율 영역)</b>: 소형 캐시에서도 높고, 기본 캐시에서도 높음 — '
      'Hotspot_9505, Zipfian_a10. 실제 운영에서 가장 이상적인 워크로드.'),
    P('• <b>좌상단 (중형 캐시 필요)</b>: 4MB에서 낮지만 32MB에서 높음 — '
      'Gaussian_s05, Hotspot_8020. Working Set이 중간 크기.'),
    P('• <b>좌하단 (저효율 영역)</b>: 4MB에서도 낮고 32MB에서도 낮음 — '
      'Uniform, Latest, Zipfian_a05. 캐시 확장보다 접근 패턴 자체가 문제.'),
    P('• <b>Sequential의 특수 위치</b>: 4MB에서 이미 75%(높음), 32MB에서도 75%(동일) — '
      '캐시가 전혀 기여하지 않는 유일한 워크로드.'),
    SP(8), PageBreak(),
]

# ════ 8. 결론 ════════════════════════════════════════════
story += [
    H1('8. 핵심 발견 및 결론'),
    HR(),
    H2('8-1. 핵심 발견 요약'),
]

findings = [
    ['#', '발견 내용', '근거'],
    ['1', '접근 집중도가 캐시 효율의 가장 큰 결정 요인\n동일 캐시에서 93% vs 28% (3.3배 차이)',
          'Hotspot_9505(92.7%) vs Uniform(28.0%)'],
    ['2', 'Sequential은 캐시 크기와 완전 무관 (4MB=256MB=75%)\n블록 내 공간 지역성이 캐시를 대체',
          '이론값 3/4=75.0% = 실측 74.95%'],
    ['3', 'Uniform/Latest의 이론적 최대 Hit Rate는 56.8%\n캐시를 무한히 늘려도 이 한계 초과 불가',
          '유니크 블록 수 계산: 25000x(1-e^-2) ≈ 21617'],
    ['4', 'σ가 2배 커지면 필요 캐시 크기도 2배 증가\n(σ=5%: 32MB 포화 / σ=10%: 64MB 포화)',
          'Working Set ≈ 6×σ×키수×값크기'],
    ['5', '패턴 전환 시 15,000~20,000건의 요청으로 캐시 재적응\n전환 직후 Hit Rate 50~70%p 급락',
          'Moving Gaussian 배치 시계열 분석'],
    ['6', '1,000회 이상 실험으로 표준편차 ±3% 이내 수렴\nn=1,006과 n=1,506 차이 0.1%p 미만',
          '수렴 분석 (n=6 → n=1,506)'],
]
story += [make_table(findings,
          [CONTENT_W*0.04, CONTENT_W*0.55, CONTENT_W*0.41]),
    SP(10),
    H2('8-2. 실용적 시사점'),
    P('① <b>캐시 크기 설계</b>: Working Set 크기(= 실질 접근 키 수 × 평균 값 크기)를 먼저 측정하고, '
      '이를 기준으로 캐시 크기를 결정합니다. 포화점 이상의 캐시 투자는 효과가 없습니다.'),
    P('② <b>워크로드 특성 파악</b>: 접근 분포가 얼마나 집중되어 있는지(Zipfian α, Hotspot 비율, '
      'Gaussian σ)를 측정하면 필요 캐시 크기를 사전 예측할 수 있습니다.'),
    P('③ <b>패턴 변화 대응</b>: 접근 패턴이 자주 바뀌는 워크로드에서는 캐시 크기를 늘리기보다 '
      '캐시 적응 속도(eviction policy)를 튜닝하는 것이 더 효과적일 수 있습니다.'),
    P('④ <b>Sequential 스캔 격리</b>: 풀스캔(Sequential)은 캐시를 오염시키지 않도록 '
      'ReadOptions에서 fill_cache=false로 설정하는 것을 권장합니다.'),
    SP(12),
    HR(),
    P('본 보고서는 RocksDB 블록 캐시 실험 환경에서 n=1,506회 측정된 실제 데이터를 기반으로 작성되었습니다.',
      sCp),
]

doc.build(story)
print(f'✓ PDF 생성 완료: {OUT}')
print(f'  파일 크기: {os.path.getsize(OUT)//1024} KB')
