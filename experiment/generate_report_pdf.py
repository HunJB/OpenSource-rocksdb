import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

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

# ── 한글 폰트 등록 ─────────────────────────────────────────
FONT_DIR = '/usr/share/fonts/truetype/nanum/'
pdfmetrics.registerFont(TTFont('Nanum',     FONT_DIR + 'NanumBarunGothic.ttf'))
pdfmetrics.registerFont(TTFont('NanumBold', FONT_DIR + 'NanumBarunGothicBold.ttf'))

# matplotlib도 동일 폰트
fm.fontManager.addfont(FONT_DIR + 'NanumBarunGothic.ttf')
matplotlib.rcParams['font.family'] = 'NanumBarunGothic'
matplotlib.rcParams['axes.unicode_minus'] = False

PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm

# ── 스타일 정의 ────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name, **kw):
    base = kw.pop('parent', 'Normal')
    defaults = dict(fontName='Nanum', fontSize=10, leading=16)
    defaults.update(kw)
    return ParagraphStyle(name, parent=styles[base], **defaults)

title_style    = S('Title',   fontName='NanumBold', fontSize=20, leading=28,
                   alignment=1, spaceAfter=6, textColor=colors.HexColor('#1a1a2e'))
sub_style      = S('Sub',     fontName='Nanum',     fontSize=12, leading=18,
                   alignment=1, spaceAfter=20, textColor=colors.HexColor('#4a4a6a'))
h1_style       = S('H1',      fontName='NanumBold', fontSize=15, leading=22,
                   spaceBefore=18, spaceAfter=8, textColor=colors.HexColor('#1a3a5c'))
h2_style       = S('H2',      fontName='NanumBold', fontSize=12, leading=18,
                   spaceBefore=10, spaceAfter=5, textColor=colors.HexColor('#2c5f8a'))
body_style     = S('Body',    fontSize=10, leading=17, spaceAfter=6)
caption_style  = S('Caption', fontSize=9,  leading=14, alignment=1,
                   textColor=colors.HexColor('#555555'), spaceAfter=10)
code_style     = S('Code',    fontName='Courier', fontSize=8.5, leading=13,
                   backColor=colors.HexColor('#f5f5f5'), leftIndent=12,
                   rightIndent=12, spaceBefore=4, spaceAfter=8,
                   borderColor=colors.HexColor('#dddddd'), borderWidth=0.5,
                   borderPadding=6)

def P(text, style=body_style): return Paragraph(text, style)
def H1(text): return Paragraph(text, h1_style)
def H2(text): return Paragraph(text, h2_style)
def HR(): return HRFlowable(width='100%', thickness=0.5,
                             color=colors.HexColor('#cccccc'), spaceAfter=8)
def SP(h=6): return Spacer(1, h)

# ── 분포 시각화 생성 함수 ──────────────────────────────────
TMP = '/tmp/pdf_dist_imgs'
os.makedirs(TMP, exist_ok=True)

def save_dist_fig(filename, draw_fn, figsize=(7, 2.6)):
    fig, ax = plt.subplots(figsize=figsize)
    draw_fn(ax)
    plt.tight_layout(pad=0.5)
    path = f'{TMP}/{filename}'
    plt.savefig(path, dpi=130, bbox_inches='tight')
    plt.close()
    return path

NUM_KEYS = 100_000
keys = np.arange(NUM_KEYS)

# 분포 그림 생성
def draw_uniform(ax):
    ax.bar(range(10), [1]*10, color='steelblue', alpha=0.75, width=0.8)
    ax.set_ylim(0, 1.6); ax.set_yticks([])
    ax.set_xticks([0,4,9]); ax.set_xticklabels(['key_0','key_50k','key_100k'])
    ax.set_title('Uniform — 모든 키 동일 확률', fontsize=11)
    ax.grid(axis='y', alpha=0.3)

def draw_sequential(ax):
    x = range(10)
    ax.bar(x, [1]*10, color='gray', alpha=0.6, width=0.8)
    for i, xi in enumerate(x):
        ax.annotate('', xy=(xi+0.5, 0.3), xytext=(xi, 0.3),
                    arrowprops=dict(arrowstyle='->', color='black', lw=1.2))
    ax.set_ylim(0, 1.8); ax.set_yticks([])
    ax.set_xticks([0,4,9]); ax.set_xticklabels(['key_0','→ 순서대로','key_50k'])
    ax.set_title('Sequential — 키 번호 순 접근', fontsize=11)

def draw_gaussian(ax):
    x = np.linspace(0, 1, 500)
    for std_r, color, label in [(0.05,'steelblue','σ=5%'), (0.10,'tomato','σ=10%')]:
        y = np.exp(-0.5 * ((x - 0.5) / std_r) ** 2)
        ax.plot(x*10, y, color=color, lw=2.5, label=label)
        ax.fill_between(x*10, y, alpha=0.15, color=color)
    ax.set_yticks([]); ax.set_xticks([0,5,10])
    ax.set_xticklabels(['key_0','key_50k (중심)','key_100k'])
    ax.set_title('Gaussian — 중심 집중, σ로 폭 조절', fontsize=11)
    ax.legend(fontsize=9); ax.grid(axis='y', alpha=0.3)

def draw_zipfian(ax):
    ranks = np.arange(1, 21)
    for alpha, color, label in [(1.0,'steelblue','α=1.0'), (0.5,'tomato','α=0.5')]:
        y = 1.0 / ranks**alpha
        y = y / y.max()
        ax.plot(ranks, y, 'o-', color=color, lw=2, markersize=4, label=label)
    ax.set_xlabel('키 순위 (낮을수록 hot)'); ax.set_yticks([])
    ax.set_title('Zipfian — 소수 hot key에 기하급수적 집중', fontsize=11)
    ax.legend(fontsize=9); ax.grid(alpha=0.3)

def draw_hotspot(ax):
    x = np.linspace(0, 10, 1000)
    y = np.where(x < 2, 0.80/2, 0.20/8)
    ax.fill_between(x, y, alpha=0.5,
                    color=np.where(x < 2, 'red', 'steelblue').tolist()[0])
    y1 = np.where(x < 2, 0.80/2, 0)
    y2 = np.where(x >= 2, 0.20/8, 0)
    ax.fill_between(x, y1, alpha=0.6, color='tomato',    label='hot (20% 키, 요청 80%)')
    ax.fill_between(x, y2, alpha=0.4, color='steelblue', label='cold (80% 키, 요청 20%)')
    ax.axvline(2, color='black', lw=1.5, ls='--')
    ax.set_yticks([]); ax.set_xticks([1, 2, 6])
    ax.set_xticklabels(['hot 구역', '경계\n(20%)', 'cold 구역'])
    ax.set_title('Hotspot — hot/cold 구역 명확히 구분', fontsize=11)
    ax.legend(fontsize=8); ax.grid(axis='y', alpha=0.3)

def draw_bimodal(ax):
    x = np.linspace(0, 1, 500)
    y1 = np.exp(-0.5*((x-0.25)/0.05)**2)
    y2 = np.exp(-0.5*((x-0.75)/0.05)**2)
    y  = y1 + y2
    ax.plot(x*10, y, color='purple', lw=2.5)
    ax.fill_between(x*10, y, alpha=0.25, color='purple')
    ax.set_yticks([]); ax.set_xticks([0, 2.5, 5, 7.5, 10])
    ax.set_xticklabels(['key_0','key_25k\n(1번 피크)','key_50k','key_75k\n(2번 피크)','key_100k'])
    ax.set_title('Bimodal — 두 개의 독립 hot 구역', fontsize=11)
    ax.grid(axis='y', alpha=0.3)

def draw_latest(ax):
    x = np.linspace(0, 1, 500)
    skew = 0.8
    # r = 1 - u^(1/skew) 의 PDF: 직접 수치로 시뮬레이션
    rng = np.random.default_rng(42)
    u_samples = rng.uniform(0, 1, 100000)
    r_samples = 1.0 - u_samples ** (1.0 / skew)
    counts, edges = np.histogram(r_samples, bins=50, range=(0,1), density=True)
    centers = (edges[:-1] + edges[1:]) / 2
    ax.bar(centers*10, counts/counts.max(), width=0.18, color='brown', alpha=0.65)
    ax.set_yticks([]); ax.set_xticks([0, 5, 10])
    ax.set_xticklabels(['key_0\n(오래된 키)', 'key_50k', 'key_100k\n(최신 키 ↑)'])
    ax.set_title('Latest — 최신(높은 번호) 키에 편향', fontsize=11)
    ax.grid(axis='y', alpha=0.3)

def draw_moving(ax):
    x = np.linspace(0, 1, 500)
    y1 = np.exp(-0.5*((x-0.30)/0.07)**2)
    y2 = np.exp(-0.5*((x-0.70)/0.07)**2)
    ax.plot(x*10, y1, 'b-',  lw=2.5, label='전반부 (배치 0~4, 피크 30%)')
    ax.plot(x*10, y2, 'r--', lw=2.5, label='후반부 (배치 5~9, 피크 70%)')
    ax.fill_between(x*10, y1, alpha=0.15, color='blue')
    ax.fill_between(x*10, y2, alpha=0.15, color='red')
    ax.annotate('', xy=(7,0.6), xytext=(3,0.6),
                arrowprops=dict(arrowstyle='->', color='black', lw=2))
    ax.text(5, 0.65, '패턴 이동', ha='center', fontsize=10)
    ax.set_yticks([]); ax.set_xticks([0,3,5,7,10])
    ax.set_xticklabels(['key_0','key_30k','key_50k','key_70k','key_100k'])
    ax.set_title('Moving Gaussian — 접근 패턴이 실험 중 이동', fontsize=11)
    ax.legend(fontsize=8); ax.grid(axis='y', alpha=0.3)

img_uniform   = save_dist_fig('uniform.png',   draw_uniform)
img_seq       = save_dist_fig('sequential.png', draw_sequential)
img_gaussian  = save_dist_fig('gaussian.png',   draw_gaussian)
img_zipfian   = save_dist_fig('zipfian.png',    draw_zipfian)
img_hotspot   = save_dist_fig('hotspot.png',    draw_hotspot)
img_bimodal   = save_dist_fig('bimodal.png',    draw_bimodal)
img_latest    = save_dist_fig('latest.png',     draw_latest)
img_moving    = save_dist_fig('moving.png',     draw_moving)

# ── 비교 테이블 그림 ───────────────────────────────────────
def draw_comparison(ax):
    labels = ['Hotspot\n9505','Gaussian\ns05','Zipfian\na10','Sequential',
              'Hotspot\n8020','Bimodal','Gaussian\ns10','Zipfian\na05',
              'Latest','Uniform']
    vals   = [92.69, 87.22, 80.49, 74.95, 70.69, 69.25, 69.14, 41.44, 29.69, 28.02]
    bar_colors = plt.cm.RdYlGn(np.linspace(0.85, 0.15, len(vals)))
    bars = ax.barh(range(len(labels)), vals, color=bar_colors, edgecolor='white', height=0.7)
    ax.set_yticks(range(len(labels))); ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlim(0, 110); ax.set_xlabel('Hit Rate (%)')
    ax.set_title('워크로드별 평균 Hit Rate (32MB 캐시, n=1,506회)', fontsize=11)
    for i, (bar, v) in enumerate(zip(bars, vals)):
        ax.text(v+1, i, f'{v:.1f}%', va='center', fontsize=8.5, fontweight='bold')
    ax.grid(axis='x', alpha=0.3); ax.invert_yaxis()

img_compare = save_dist_fig('comparison.png', draw_comparison, figsize=(7, 3.6))

# ── 배치 시계열 그림 ───────────────────────────────────────
def draw_batch(ax):
    batches = list(range(10))
    data = {
        'moving_gaussian030710 (σ=10%)': [23.48,54.16,70.74,76.10,78.44,23.66,44.00,56.28,63.46,71.58],
        'moving_gaussian030705 (σ=5%)':  [38.52,75.32,87.52,92.26,94.58,37.46,74.84,84.42,89.98,92.86],
    }
    colors_list = ['tomato','steelblue']
    for (label, vals), color in zip(data.items(), colors_list):
        ax.plot(batches, vals, 'o-', color=color, lw=2.2, label=label, markersize=5)
    ax.axvline(4.5, color='black', lw=1.5, ls='--', alpha=0.6)
    ax.text(4.6, 20, '패턴\n전환', fontsize=8.5)
    ax.set_xlabel('배치 번호'); ax.set_ylabel('Hit Rate (%)')
    ax.set_title('Moving Gaussian — 배치별 Hit Rate 변화', fontsize=11)
    ax.set_ylim(0, 105); ax.set_xticks(batches)
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

img_batch = save_dist_fig('batch.png', draw_batch, figsize=(7, 3.0))

# ── PDF 문서 구성 ──────────────────────────────────────────
OUT = '/home/ubuntu/rocksdb/experiment/results/workload_distribution_report.pdf'
doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=MARGIN, rightMargin=MARGIN,
                        topMargin=MARGIN, bottomMargin=MARGIN)

W = PAGE_W - 2*MARGIN  # 이미지 최대 너비

def Img(path, width=None, height=None):
    w = width or W
    img = Image(path, width=w)
    if height:
        img._restrictSize(w, height)
    return img

story = []

# ── 표지 ───────────────────────────────────────────────────
story += [
    SP(60),
    P('RocksDB 캐시 실험', title_style),
    SP(8),
    P('읽기 요청 워크로드 분포 설명서', sub_style),
    HR(),
    SP(10),
    P('본 문서는 RocksDB 블록 캐시 히트율 실험에 사용된<br/>'
      '8가지 읽기 요청 분포(워크로드)의 동작 원리, 수식, 그래프,<br/>'
      '실험 결과 및 실제 사례를 정리한 보고서입니다.', body_style),
    SP(10),
]

# 실험 조건 테이블
cond_data = [
    ['항목', '값'],
    ['총 키 수', '100,000개'],
    ['키당 값 크기', '1 KB'],
    ['총 DB 크기', '약 100 MB'],
    ['읽기 요청 수', '50,000회 / 실험'],
    ['캐시 비교 기준', '32 MB (RocksDB 기본값)'],
    ['총 실험 횟수', '1,506회 (통계 신뢰 수준)'],
]
t = Table(cond_data, colWidths=[W*0.38, W*0.62])
t.setStyle(TableStyle([
    ('FONTNAME',    (0,0), (-1,0),  'NanumBold'),
    ('FONTNAME',    (0,1), (-1,-1), 'Nanum'),
    ('FONTSIZE',    (0,0), (-1,-1), 10),
    ('BACKGROUND',  (0,0), (-1,0),  colors.HexColor('#1a3a5c')),
    ('TEXTCOLOR',   (0,0), (-1,0),  colors.white),
    ('BACKGROUND',  (0,1), (-1,-1), colors.HexColor('#f8f9fa')),
    ('ROWBACKGROUNDS', (0,1), (-1,-1),
     [colors.HexColor('#f8f9fa'), colors.HexColor('#eef1f5')]),
    ('ALIGN',       (0,0), (-1,-1), 'CENTER'),
    ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
    ('GRID',        (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
    ('ROWHEIGHT',   (0,0), (-1,-1), 22),
    ('TOPPADDING',  (0,0), (-1,-1), 5),
    ('BOTTOMPADDING',(0,0),(-1,-1), 5),
]))
story += [t, SP(20), PageBreak()]

# ── 전체 비교 그래프 ───────────────────────────────────────
story += [
    H1('전체 워크로드 Hit Rate 비교'),
    HR(),
    Img(img_compare, height=10*cm),
    P('▲ 32MB 캐시, n=1,506회 실험 평균. 접근 집중도가 높을수록 hit rate가 높다.', caption_style),
    SP(10),
]

# ── 분포별 상세 설명 ───────────────────────────────────────
def dist_section(title, hit_rate, img_path, desc_paras, code_text=None):
    items = [
        H1(title),
        HR(),
    ]
    # hit rate 배지
    badge_data = [['32MB 캐시 Hit Rate', f'{hit_rate}']]
    badge = Table(badge_data, colWidths=[W*0.4, W*0.6])
    badge.setStyle(TableStyle([
        ('FONTNAME',    (0,0), (0,0), 'NanumBold'),
        ('FONTNAME',    (1,0), (1,0), 'NanumBold'),
        ('FONTSIZE',    (0,0), (-1,-1), 11),
        ('BACKGROUND',  (0,0), (0,0), colors.HexColor('#eef1f5')),
        ('BACKGROUND',  (1,0), (1,0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR',   (1,0), (1,0), colors.white),
        ('ALIGN',       (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('GRID',        (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('ROWHEIGHT',   (0,0), (-1,-1), 28),
    ]))
    items.append(badge)
    items.append(SP(8))
    if code_text:
        items.append(Paragraph(code_text, code_style))
    items.append(Img(img_path, height=7*cm))
    for para in desc_paras:
        items.append(P(para))
    items.append(SP(8))
    return KeepTogether(items)


story.append(dist_section(
    '1. Uniform (균등 분포)',
    '28.02% (최저)',
    img_uniform,
    [
        '모든 키에 <b>동일한 접근 확률</b>을 부여합니다. 어느 키가 선택될지 전혀 예측할 수 없어 '
        '캐시 재사용이 가장 어렵습니다.',
        '캐시가 256MB(전체 데이터의 2.5배)여도 hit rate는 56.8%가 한계입니다. '
        '이는 50,000회 요청으로 접근하는 유니크 블록 수 자체가 약 21,617개에 그치기 때문입니다.',
        '<b>실제 예시:</b> 로그 분석에서 무작위 레코드 샘플링, 전체 테이블 통계 계산',
    ],
    'keys[i] = uniform_random(0, 99999)',
))

story.append(dist_section(
    '2. Sequential (순차 분포)',
    '74.95% (캐시 크기 무관)',
    img_seq,
    [
        '키 0번부터 순서대로 접근합니다. 캐시 크기가 4MB이든 256MB이든 <b>항상 74.95%</b>로 동일합니다.',
        'RocksDB 블록(4KB)에 약 4개의 키가 담기므로, 첫 번째 키만 MISS(디스크 읽기)가 발생하고 '
        '같은 블록의 나머지 3개 키는 자동으로 HIT됩니다. 이론값 3/4 = 75.0%와 실측이 일치합니다.',
        '<b>실제 예시:</b> 테이블 풀스캔, 백업/복원, ETL 파이프라인, 순차 로그 읽기',
    ],
    'keys[i] = i % NUM_KEYS  →  0, 1, 2, ..., 49999',
))

story.append(dist_section(
    '3. Gaussian (가우시안 / 정규 분포)',
    'σ=5%: 87.22%  /  σ=10%: 69.14%',
    img_gaussian,
    [
        '키 공간 중앙(key_50000)을 중심으로, <b>σ(표준편차)가 작을수록 좁게 집중</b>됩니다.',
        'σ=5%의 실질 working set은 약 30MB로 32MB 캐시에 수용 가능하여 87%를 달성합니다. '
        'σ=10%는 working set이 약 60MB로 커져 32MB 캐시가 부족, 69%에 머뭅니다.',
        '2,204회 실험에서 σ=5%의 최솟값(87.09%)이 σ=10%의 최댓값(69.86%)보다 항상 높아, '
        '단 한 번도 역전이 발생하지 않았습니다.',
        '<b>실제 예시:</b> 특정 가격대 상품 집중 조회, 중간 등급 사용자 트래픽, 특정 연령대 집중',
    ],
    'keys[i] ~ N(mean=50000, std=σ×100000)  →  범위 밖은 재추출',
))

story.append(dist_section(
    '4. Zipfian (지프 분포)',
    'α=1.0: 80.49%  /  α=0.5: 41.44%',
    img_zipfian,
    [
        '순위(rank) r인 키의 접근 확률이 <b>1/r^α에 비례</b>합니다. α가 클수록 상위 소수 키에 '
        '트래픽이 기하급수적으로 집중됩니다.',
        'α=1.0에서는 4MB(전체의 4%) 캐시만으로 66.9% hit rate를 달성합니다. '
        '상위 몇 개의 hot key만 캐시하면 대부분의 요청을 처리할 수 있습니다.',
        'α=0.5는 집중도가 낮아 Uniform에 가까워지며, 캐시 효율도 크게 떨어집니다.',
        '<b>실제 예시:</b> 인기 SNS 게시물(바이럴 컨텐츠), 검색 키워드 빈도, 전자상거래 베스트셀러',
    ],
    'P(rank=r) ∝ 1/r^α  →  CDF를 사용한 역변환 샘플링',
))

story.append(dist_section(
    '5. Hotspot (핫스팟 분포)',
    'Hotspot_9505: 92.69%  /  Hotspot_8020: 70.69%',
    img_hotspot,
    [
        '키 공간을 <b>hot/cold 두 구역으로 명확히 구분</b>합니다. '
        'Hotspot_9505는 상위 5% 키(5,000개 = 5MB)에 요청의 95%를 집중시킵니다.',
        '5MB working set이 8MB 캐시에 완전히 수용되므로, 8MB부터 hit rate가 포화됩니다. '
        'Zipfian과 달리 hot/cold 경계가 계단처럼 명확합니다.',
        '<b>실제 예시:</b> 최근 N일 데이터만 집중 조회(오래된 데이터 거의 미접근), '
        '특정 지역 사용자 집중 서비스, 특정 카테고리 집중 쇼핑몰',
    ],
    '80% 확률: hot(0~19999)  /  20% 확률: cold(20000~99999)',
))

story.append(dist_section(
    '6. Bimodal (이중 피크 분포)',
    '69.25%',
    img_bimodal,
    [
        '<b>두 개의 독립적인 가우시안 분포를 50:50으로 혼합</b>합니다. '
        '1번 피크(25% 지점)와 2번 피크(75% 지점)에 각각 접근이 집중됩니다.',
        '각 피크의 working set ≈ 15MB이므로 합산 30MB이지만, '
        '32MB 캐시로는 두 피크를 동시에 충분히 수용하기 약간 부족해 69.25%에 머뭅니다. '
        '64MB부터 포화됩니다.',
        '<b>실제 예시:</b> 오전/오후 두 번의 피크 트래픽, 국내/해외 두 사용자군, '
        '두 개의 주력 상품군에만 집중되는 조회',
    ],
    '50% 확률: N(25000, 5000)  /  50% 확률: N(75000, 5000)',
))

story.append(dist_section(
    '7. Latest (최신 편향 분포)',
    '29.69%',
    img_latest,
    [
        '<b>키 번호가 클수록(최근에 삽입된 키일수록) 더 자주 접근</b>됩니다. '
        'u^(1/skewness) 변환으로 샘플 값을 키 공간 상단으로 편향시킵니다.',
        'skewness=0.8은 완만한 편향이어서 접근 범위가 여전히 넓고, '
        '32MB hit rate가 Uniform(28.0%)과 큰 차이 없이 낮습니다. '
        '256MB 캐시에서도 57%가 최대입니다.',
        '<b>실제 예시:</b> 소셜 타임라인(최신 게시물 위주), 최근 주문/거래 내역 조회, '
        '로그 테이블에서 최근 에러 조회',
    ],
    'r = 1 - u^(1/0.8),  keys[i] = clamp(r × NUM_KEYS, 0, 99999)',
))

story.append(dist_section(
    '8. Moving Gaussian (이동 가우시안 분포)',
    '배치별 23%~95% (동적 변화)',
    img_moving,
    [
        '<b>실험 도중 접근 패턴이 이동</b>합니다. 전반부 25,000건은 30%(또는 20%) 구간에, '
        '후반부 25,000건은 70%(또는 80%) 구간에 집중됩니다.',
        '패턴 전환 직후 hit rate가 50~70%p 급락하며, 새 패턴에 적응하는 데 '
        '약 15,000~20,000건의 요청이 필요합니다. σ가 작을수록 최고 hit rate가 높고(95% vs 78%) '
        '적응도 빠릅니다.',
        '<b>실제 예시:</b> 출퇴근 시간대 지역 변화, 계절별 상품 카테고리 이동, '
        '이벤트로 인한 급격한 트래픽 패턴 변화',
    ],
    '전반부: N(30000, σ×100000) / 후반부: N(70000, σ×100000)',
))

# ── 배치 시계열 ────────────────────────────────────────────
story += [
    H1('Moving Gaussian — 배치별 Hit Rate 시계열'),
    HR(),
    Img(img_batch, height=8.5*cm),
    P('▲ 배치 0~4: 1번 피크(30%) 워밍업 → 배치 5: 패턴 전환 직후 급락 → 배치 5~9: 2번 피크(70%) 재적응', caption_style),
]

# ── 종합 비교표 ────────────────────────────────────────────
story += [PageBreak(), H1('종합 비교표'), HR()]

table_data = [
    ['분포', '접근 형태', '32MB\nHit Rate', '캐시\n포화점', '실제 예시'],
    ['Hotspot_9505', '계단형 (5% hot)',     '92.7%', '8MB',   '바이럴 컨텐츠'],
    ['Gaussian_s05', '종형 (σ=5%)',         '87.2%', '32MB',  '특정 범위 집중 조회'],
    ['Zipfian_a10',  '역지수형 (α=1.0)',    '80.5%', '64MB+', '검색, SNS'],
    ['Sequential',   '순차형',              '75.0%', '무관',  '풀스캔, 백업'],
    ['Hotspot_8020', '계단형 (20% hot)',    '70.7%', '128MB', '카테고리 집중'],
    ['Bimodal',      '쌍봉형',              '69.3%', '64MB',  '두 사용자군'],
    ['Gaussian_s10', '종형 (σ=10%)',        '69.1%', '64MB',  '넓은 범위 조회'],
    ['Zipfian_a05',  '역지수형 (α=0.5)',    '41.4%', '128MB+','약한 편향'],
    ['Latest',       '우측 편향형',         '29.7%', '256MB+','최신 데이터 조회'],
    ['Uniform',      '완전 평탄형',         '28.0%', '포화없음','무작위 샘플링'],
]

row_colors = [colors.HexColor('#1a3a5c')] + \
    [colors.HexColor('#f0f4f0') if i%2==0 else colors.HexColor('#e4ecf4')
     for i in range(len(table_data)-1)]

col_w = [W*0.20, W*0.20, W*0.13, W*0.13, W*0.34]
t2 = Table(table_data, colWidths=col_w)
t2.setStyle(TableStyle([
    ('FONTNAME',     (0,0), (-1,0),  'NanumBold'),
    ('FONTNAME',     (0,1), (-1,-1), 'Nanum'),
    ('FONTSIZE',     (0,0), (-1,-1), 9),
    ('TEXTCOLOR',    (0,0), (-1,0),  colors.white),
    ('ROWBACKGROUNDS',(0,0),(-1,-1), row_colors),
    ('ALIGN',        (0,0), (-1,-1), 'CENTER'),
    ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
    ('GRID',         (0,0), (-1,-1), 0.4, colors.HexColor('#bbbbbb')),
    ('TOPPADDING',   (0,0), (-1,-1), 6),
    ('BOTTOMPADDING',(0,0), (-1,-1), 6),
    ('WORDWRAP',     (0,0), (-1,-1), True),
]))
story += [t2, SP(16)]

story += [
    HR(),
    P('본 보고서는 RocksDB 실험 환경(n=1,506회)에서 측정된 실제 데이터를 기반으로 작성되었습니다.',
      caption_style),
]

doc.build(story)
print(f'✓ PDF 생성 완료: {OUT}')
