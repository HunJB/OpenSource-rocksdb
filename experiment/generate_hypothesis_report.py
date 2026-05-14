"""
가설 검증 발표 설명서 PDF 생성
평가 기준: 실험 설계 타당성(20점), 결과 분석·해석(25점), 독창성(10점) 집중
"""
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

FONT_DIR = '/usr/share/fonts/truetype/nanum/'
pdfmetrics.registerFont(TTFont('Nanum',     FONT_DIR + 'NanumBarunGothic.ttf'))
pdfmetrics.registerFont(TTFont('NanumBold', FONT_DIR + 'NanumBarunGothicBold.ttf'))

PAGE_W, PAGE_H = A4
MARGIN   = 1.8 * cm
CONTENT_W = PAGE_W - 2 * MARGIN
TMP = '/tmp/hypo_imgs'

# ── 스타일 ─────────────────────────────────────────────────
_ss = getSampleStyleSheet()
def S(name, **kw):
    d = dict(fontName='Nanum', fontSize=10, leading=16)
    d.update(kw)
    return ParagraphStyle(name, parent=_ss['Normal'], **d)

sTitle  = S('sTitle', fontName='NanumBold', fontSize=21, leading=28, alignment=1,
             textColor=colors.HexColor('#0d2137'), spaceAfter=6)
sSub    = S('sSub',   fontSize=11, leading=17, alignment=1,
             textColor=colors.HexColor('#3a5a7a'), spaceAfter=20)
sH1     = S('sH1',   fontName='NanumBold', fontSize=14, leading=20,
             textColor=colors.HexColor('#0d2137'), spaceBefore=14, spaceAfter=6)
sH2     = S('sH2',   fontName='NanumBold', fontSize=11, leading=17,
             textColor=colors.HexColor('#1a4a7a'), spaceBefore=8, spaceAfter=4)
sH3     = S('sH3',   fontName='NanumBold', fontSize=10, leading=15,
             textColor=colors.HexColor('#c0392b'), spaceBefore=6, spaceAfter=3)
sBody   = S('sBody', fontSize=9.5, leading=16, spaceAfter=4)
sBullet = S('sBullet', fontSize=9.5, leading=16, leftIndent=14, spaceAfter=3)
sBox    = S('sBox',  fontSize=9.5, leading=16,
             backColor=colors.HexColor('#f0f7ff'),
             borderColor=colors.HexColor('#2980b9'), borderWidth=1,
             borderPadding=8, spaceAfter=8)
sWarn   = S('sWarn', fontSize=9.5, leading=16,
             backColor=colors.HexColor('#fff8f0'),
             borderColor=colors.HexColor('#e67e22'), borderWidth=1,
             borderPadding=8, spaceAfter=8)
sCaption= S('sCap',  fontSize=8.5, leading=13, alignment=1,
             textColor=colors.HexColor('#555'), spaceAfter=8)
sScript = S('sScript', fontName='NanumBold', fontSize=9, leading=15,
             textColor=colors.HexColor('#1a5c1a'),
             backColor=colors.HexColor('#f0fff0'),
             borderColor=colors.HexColor('#27ae60'), borderWidth=0.5,
             borderPadding=6, spaceAfter=6)

def P(t, s=sBody):   return Paragraph(t, s)
def H1(t):           return Paragraph(t, sH1)
def H2(t):           return Paragraph(t, sH2)
def H3(t):           return Paragraph(t, sH3)
def HR():            return HRFlowable(width='100%', thickness=0.6,
                                        color=colors.HexColor('#b0c4d8'), spaceAfter=6)
def SP(h=6):         return Spacer(1, h)
def Img(p, h=None):
    img = Image(p, width=CONTENT_W)
    if h: img._restrictSize(CONTENT_W, h)
    return img
def Cap(t):          return Paragraph(t, sCaption)
def Box(t):          return Paragraph(t, sBox)
def Warn(t):         return Paragraph(t, sWarn)
def Script(t):       return Paragraph(t, sScript)

def make_table(data, col_widths, hc='#1a3a5c'):
    t = Table(data, colWidths=col_widths)
    n = len(data)
    row_bg = [colors.HexColor('#f0f4f8') if i%2==0 else colors.HexColor('#e2eaf5')
              for i in range(n-1)]
    t.setStyle(TableStyle([
        ('FONTNAME',      (0,0), (-1,0),  'NanumBold'),
        ('FONTNAME',      (0,1), (-1,-1), 'Nanum'),
        ('FONTSIZE',      (0,0), (-1,-1), 8.5),
        ('BACKGROUND',    (0,0), (-1,0),  colors.HexColor(hc)),
        ('TEXTCOLOR',     (0,0), (-1,0),  colors.white),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),  row_bg),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('GRID',          (0,0), (-1,-1), 0.4, colors.HexColor('#c0cfe0')),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    return t

# ════════════════════════════════════════════════════════════
OUT = '/home/ubuntu/rocksdb/experiment/results/hypothesis_analysis_report.pdf'
doc = SimpleDocTemplate(OUT, pagesize=A4,
                        leftMargin=MARGIN, rightMargin=MARGIN,
                        topMargin=MARGIN, bottomMargin=MARGIN)
story = []

# ════ 표지 ════════════════════════════════════════════════
story += [
    SP(40),
    P('오픈소스 SW 분석 (빅데이터)', sSub),
    P('RocksDB 블록 캐시 Hit Rate 실험', sTitle),
    SP(6),
    P('가설 검증 및 결과 분석 발표 자료', sTitle),
    SP(12),
    HR(),
    SP(8),
]

cover_data = [
    ['항목', '내용'],
    ['실험 주제', 'RocksDB 블록 캐시 Hit Rate와 읽기 분포의 관계'],
    ['핵심 가설', '접근이 특정 구간에 집중될수록 캐시 히트율이 높다'],
    ['실험 규모', 'n=1,506회 반복 실험 (10가지 워크로드 × 7가지 캐시 크기)'],
    ['발표 시간', '10 ~ 12분'],
    ['주요 발견', '가설 일치 8종 / 예상 외 결과 2종 (Bimodal, Sequential)'],
]
story += [make_table(cover_data, [CONTENT_W*0.28, CONTENT_W*0.72]),
          SP(20), PageBreak()]

# ════ 1. 가설 설정 ════════════════════════════════════════
story += [
    H1('1. 가설 설정'),
    HR(),
    H2('1-1. 연구 동기'),
    P('RocksDB의 블록 캐시는 자주 접근되는 데이터를 메모리에 보관해 디스크 읽기를 줄입니다. '
      '실제 서비스에서 읽기 요청이 어떤 분포로 들어오느냐에 따라 캐시 효율이 달라질 것이라는 '
      '문제의식에서 출발했습니다.'),
    SP(4),
    H2('1-2. 핵심 가설'),
    Box('<b>"읽기 요청이 특정 키 구간에 집중될수록(분포가 뾰족할수록) '
        'Block Cache Hit Rate가 높아질 것이다."</b>'),
    H2('1-3. 가설의 근거'),
    P('• 캐시는 한정된 메모리(32MB)를 가집니다.'),
    P('• 접근이 소수의 키에 집중되면 → 그 키들이 캐시에 계속 머물며 반복 HIT'),
    P('• 접근이 전체 키에 분산되면 → 캐시 용량을 초과해 교체가 빈번히 발생 → HIT 감소'),
    SP(4),
    H2('1-4. 검증 대상 워크로드'),
]
hypo_table = [
    ['워크로드', '집중도', '예상 Hit Rate', '예상 근거'],
    ['Hotspot_9505', '매우 높음\n(5% 키에 95% 집중)', '최고 (90%+)', '소수 키가 캐시에 안정적 상주'],
    ['Hotspot_8020', '높음\n(20% 키에 80% 집중)', '높음 (70%+)', '약간 넓은 hot 구간'],
    ['Gaussian_s05', '높음 (좁은 종형)', '높음 (85%+)', 'σ=5% → 좁은 working set'],
    ['Gaussian_s10', '중간 (넓은 종형)', '중간 (65~75%)', 'σ=10% → 넓어진 working set'],
    ['Zipfian_a10',  '매우 높음 (역지수)', '높음 (80%+)', '상위 키에 기하급수적 집중'],
    ['Zipfian_a05',  '중간 (약한 역지수)', '중간 (40~50%)', '집중도 약해 Uniform에 가까움'],
    ['Bimodal',      '높음 (이중 피크)', '높음 (80%+)', '두 피크 각각 집중됨'],
    ['Sequential',   '낮음 (순차, 반복無)', '낮음 (30%~)', '같은 키 재접근 없음'],
    ['Latest',       '낮음 (우측 편향)', '낮음 (30%~)', '넓게 분산된 접근'],
    ['Uniform',      '없음 (완전 균등)', '최저 (20%~)', '캐시 재사용 불가'],
]
story += [make_table(hypo_table,
          [CONTENT_W*0.19, CONTENT_W*0.22, CONTENT_W*0.18, CONTENT_W*0.41]),
          SP(8), PageBreak()]

# ════ 2. 가설 vs 실제 ════════════════════════════════════
story += [
    H1('2. 가설 vs 실제 실험 결과 비교'),
    HR(),
    Img(f'{TMP}/hypo_compare.png', h=9*cm),
    Cap('▲ 좌: 가설(예상)과 실제 측정값 비교  /  우: 예상 대비 실제 차이(%p)'),
    SP(6),
    H2('2-1. 결과 요약'),
]

result_table = [
    ['워크로드', '예상', '실제', '일치 여부', '판정'],
    ['Hotspot_9505', '90%+',  '92.69%', '✓ 일치', '가설 지지'],
    ['Gaussian_s05', '85%+',  '87.22%', '✓ 일치', '가설 지지'],
    ['Zipfian_a10',  '80%+',  '80.49%', '✓ 일치', '가설 지지'],
    ['Hotspot_8020', '70%+',  '70.69%', '✓ 일치', '가설 지지'],
    ['Gaussian_s10', '65~75%','69.14%', '✓ 일치', '가설 지지'],
    ['Zipfian_a05',  '40~50%','41.44%', '✓ 일치', '가설 지지'],
    ['Latest',       '30%+',  '29.69%', '✓ 일치', '가설 지지'],
    ['Uniform',      '최저',  '28.02%', '✓ 일치', '가설 지지'],
    ['Bimodal',      '80%+',  '69.25%', '✗ 불일치', '예상보다 낮음'],
    ['Sequential',   '30%~',  '74.95%', '✗ 불일치', '예상보다 훨씬 높음'],
]
t = make_table(result_table,
    [CONTENT_W*0.19, CONTENT_W*0.13, CONTENT_W*0.12,
     CONTENT_W*0.16, CONTENT_W*0.40])
t.setStyle(TableStyle([
    ('FONTNAME',   (0,0), (-1,0),  'NanumBold'),
    ('FONTNAME',   (0,1), (-1,-1), 'Nanum'),
    ('FONTSIZE',   (0,0), (-1,-1), 8.5),
    ('BACKGROUND', (0,0), (-1,0),  colors.HexColor('#1a3a5c')),
    ('TEXTCOLOR',  (0,0), (-1,0),  colors.white),
    ('BACKGROUND', (0,9), (-1,9),  colors.HexColor('#fde8d8')),
    ('BACKGROUND', (0,10),(-1,10), colors.HexColor('#fde8d8')),
    ('ROWBACKGROUNDS',(0,1),(-1,8),
     [colors.HexColor('#f0f4f8'), colors.HexColor('#e2eaf5')]*4),
    ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
    ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
    ('GRID',       (0,0), (-1,-1), 0.4, colors.HexColor('#c0cfe0')),
    ('TOPPADDING', (0,0), (-1,-1), 5),
    ('BOTTOMPADDING',(0,0),(-1,-1),5),
]))
story += [t, SP(6),
    P('8종은 가설대로 동작했으나, <b>Bimodal(쌍봉형)</b>과 <b>Sequential(순차)</b>에서 '
      '예상과 다른 결과가 나타났습니다. 이 두 경우를 심층 분석합니다.'),
    SP(8), PageBreak(),
]

# ════ 3. Bimodal 심층 분석 ════════════════════════════════
story += [
    H1('3. 예상과 달랐던 이유 ① — Bimodal (쌍봉형)'),
    HR(),
    Warn('<b>예상:</b> 두 구간에 집중되므로 Hit Rate 80% 이상 기대<br/>'
         '<b>실제:</b> 69.25% — Gaussian_s10(69.14%)과 거의 동일, 예상보다 약 11%p 낮음'),
    Img(f'{TMP}/bimodal_analysis.png', h=8*cm),
    Cap('▲ 좌: Bimodal vs Gaussian_s05 분포 형태  /  중: 캐시 크기별 hit rate  /  우: Working Set 크기'),
    SP(6),
    H2('3-1. 원인 분석: Working Set이 두 배가 된다'),
    P('가설을 세울 때의 착각은 <b>"두 구간에 집중 = 효율적"</b>이라고 생각한 것입니다. '
      '그러나 캐시 관점에서 중요한 것은 <b>"몇 개의 키를 캐시해야 하는가"</b>입니다.'),
    SP(4),
]

ws_table = [
    ['분포', '피크 위치', '피크당 Working Set', '총 Working Set', '32MB 캐시로 수용?'],
    ['Gaussian_s05', '중앙(50%) 1개', '~30MB (σ=5%)', '~30MB', '✓ 가능 (32MB > 30MB)'],
    ['Bimodal',      '25%, 75% 2개', '각 ~15MB', '합산 ~30MB\n(But 분리된 영역!)', '△ 간신히'],
]
story += [make_table(ws_table,
          [CONTENT_W*0.17, CONTENT_W*0.17, CONTENT_W*0.20,
           CONTENT_W*0.23, CONTENT_W*0.23]),
    SP(6),
    H2('3-2. 캐시 입장에서 본 Bimodal의 불리함'),
    P('• Gaussian_s05는 키 35,000~65,000 <b>연속 구간</b>을 캐시하면 됩니다.'),
    P('• Bimodal은 키 10,000~40,000 <b>AND</b> 키 60,000~90,000을 <b>동시에</b> 캐시해야 합니다.'),
    P('• 두 피크를 오가며 접근하면 LRU 캐시가 1번 피크 블록을 교체하고 2번 피크 블록을 올리는 과정을 반복합니다.'),
    P('• 이 <b>캐시 thrashing(교체 반복)</b> 현상이 32MB 환경에서 두드러집니다.'),
    SP(4),
    H2('3-3. 포화점에서 확인되는 차이'),
    P('캐시를 충분히 키우면(64MB) 두 피크를 모두 수용 가능해 hit rate가 77.6%로 상승합니다. '
      '<b>Bimodal이 낮았던 이유는 분포가 나빠서가 아니라, 32MB 캐시가 두 Working Set을 동시에 수용하기 부족했기 때문입니다.</b>'),
    Box('핵심: 집중된 구간이 여러 개여도 <b>총 Working Set > 캐시 크기</b>이면 캐시 효율이 떨어진다.\n'
        'Bimodal의 진짜 적정 캐시 크기는 64MB.'),
    SP(8), PageBreak(),
]

# ════ 4. Sequential 심층 분석 ════════════════════════════
story += [
    H1('4. 예상과 달랐던 이유 ② — Sequential (순차 접근)'),
    HR(),
    Warn('<b>예상:</b> 같은 키를 반복 접근하지 않으므로 Hit Rate 낮을 것 (30%대 예상)<br/>'
         '<b>실제:</b> 74.95% — 예상보다 약 45%p 높음. 그리고 캐시 크기와 완전히 무관.'),
    Img(f'{TMP}/sequential_analysis.png', h=8*cm),
    Cap('▲ 좌: 블록 내 MISS/HIT 구조  /  중: 캐시 크기별 hit rate(완전 수평)  /  우: 이론값 검증'),
    SP(6),
    H2('4-1. 왜 예상이 틀렸나: 키(Key) ≠ 블록(Block)'),
    P('가설을 세울 때 <b>"Sequential은 같은 키를 반복하지 않는다"</b>고 생각했습니다. '
      '이것은 사실입니다. 그러나 RocksDB의 캐시 단위는 <b>키가 아니라 블록(Block)</b>입니다.'),
    SP(4),
]

block_table = [
    ['단위', '크기', '포함 내용'],
    ['키(Key)', '~1KB', '1개의 키-값 쌍'],
    ['블록(Block)', '~4KB', '약 4개의 키-값 쌍이 연속으로 묶임'],
    ['블록 캐시', '32MB', '블록 단위로 저장/교체'],
]
story += [make_table(block_table,
          [CONTENT_W*0.25, CONTENT_W*0.20, CONTENT_W*0.55]),
    SP(6),
    H2('4-2. 공간 지역성(Spatial Locality)의 작동'),
    P('순차 접근 시 블록 내에서 발생하는 일:'),
    P('① key_0 접근 → 블록[0](key_0~key_3 포함) 디스크에서 읽기 → MISS, 캐시에 적재'),
    P('② key_1 접근 → 블록[0]이 이미 캐시에 있음 → <b>HIT</b>'),
    P('③ key_2 접근 → 블록[0]이 이미 캐시에 있음 → <b>HIT</b>'),
    P('④ key_3 접근 → 블록[0]이 이미 캐시에 있음 → <b>HIT</b>'),
    P('⑤ key_4 접근 → 블록[1](key_4~key_7 포함) → MISS, 캐시에 적재'),
    SP(4),
    Box('블록당 키 4개 → 첫 키만 MISS, 나머지 3개는 HIT\n'
        '이론적 Hit Rate = 3/4 = <b>75.0%</b> ← 실측값 74.95%와 완벽히 일치'),
    H2('4-3. 왜 캐시 크기와 무관한가'),
    P('순차 접근은 각 블록을 딱 한 번씩만 읽습니다. 블록을 읽는 시점에 캐시에 올라가지만, '
      '다음에 그 블록으로 돌아오지 않습니다. 따라서 <b>캐시가 크든 작든 재사용이 발생하지 않아</b> '
      '캐시 크기가 hit rate에 영향을 미치지 못합니다.'),
    P('이는 Sequential 스캔이 캐시를 "오염"시킬 수 있다는 운영 시사점을 줍니다. '
      'RocksDB에서는 이를 위해 <b>ReadOptions::fill_cache = false</b> 옵션을 제공합니다.'),
    Box('핵심: "키 반복 없음"이 아니라 <b>"블록 내 인접 키들이 함께 캐시됨"</b>이 결정적.\n'
        'Sequential의 hit rate는 캐시가 아닌 <b>블록 크기 / 키 크기</b> 비율이 결정한다.'),
    SP(8), PageBreak(),
]

# ════ 5. 종합 검증 결과 ══════════════════════════════════
story += [
    H1('5. 가설 검증 종합 결과'),
    HR(),
    Img(f'{TMP}/hypo_summary.png', h=8.5*cm),
    Cap('▲ 워크로드를 4가지 유형으로 분류한 가설 검증 결과'),
    SP(6),
    H2('5-1. 4가지 유형 분류'),
]

type_table = [
    ['유형', '해당 워크로드', '결론'],
    ['가설 일치\n(집중↑ → hit율↑)',
     'Hotspot_9505/8020\nZipfian_a10\nGaussian_s05',
     '접근 집중도가 캐시 효율을 결정\n소수 블록 반복 접근 → 높은 hit율'],
    ['부분 일치\n(집중하지만 예상보다 낮음)',
     'Bimodal\nGaussian_s10',
     '집중도는 높으나 Working Set이\n32MB 캐시 한계를 초과함'],
    ['가설 불일치\n(다른 원리 작동)',
     'Sequential',
     '키 반복 없어도 블록 내 공간 지역성으로\n75% 달성. 캐시 크기 무관.'],
    ['가설 일치\n(분산 → hit율 낮음)',
     'Zipfian_a05\nLatest\nUniform',
     '분산된 접근 → 낮은 캐시 효율\nUniform은 이론적 한계 56.8%'],
]
story += [make_table(type_table,
          [CONTENT_W*0.23, CONTENT_W*0.28, CONTENT_W*0.49]),
    SP(8),
    H2('5-2. 가설의 한계와 보완'),
    P('원래 가설은 <b>"접근 집중도 → hit율"</b>의 단순한 관계를 가정했습니다. '
      '실험을 통해 더 정확한 두 가지 법칙을 도출했습니다.'),
    SP(4),
]

law_table = [
    ['법칙', '내용', '해당 워크로드'],
    ['법칙 1\n(집중도 법칙)',
     '접근이 집중될수록 hit율 높음\n단, Working Set이 캐시 크기 이하일 때만 성립',
     'Hotspot, Zipfian, Gaussian'],
    ['법칙 2\n(공간 지역성 법칙)',
     '키 반복 없어도 블록 내 인접 키가\n함께 로드되어 hit가 발생',
     'Sequential\n(예상 밖 발견)'],
    ['법칙 3\n(Working Set 법칙)',
     'Working Set > 캐시 크기이면\n집중도와 무관하게 hit율 저하',
     'Bimodal (32MB 부족)\nGaussian_s10 (60MB 필요)'],
]
story += [make_table(law_table,
          [CONTENT_W*0.18, CONTENT_W*0.50, CONTENT_W*0.32]),
    SP(8), PageBreak(),
]

# ════ 6. 발표 스크립트 가이드 ════════════════════════════
story += [
    H1('6. 발표 스크립트 가이드 (10~12분)'),
    HR(),
    P('평가 기준에 맞춰 각 항목별 발표 포인트를 정리했습니다.'),
    SP(6),
]

script_sections = [
    ('도입부 (1~1.5분)', '#1a5c1a',
     '안녕하세요. 저희 팀은 RocksDB의 블록 캐시 히트율이 읽기 요청 분포에 따라 '
     '얼마나 달라지는지를 실험했습니다. 가설은 "접근이 특정 구간에 집중될수록 캐시 효율이 높아진다"입니다. '
     '총 1,506회 반복 실험으로 통계적으로 신뢰 가능한 결과를 확보했습니다.'),
    ('실험 설계 설명 (2~2.5분) [배점 20점]', '#1a4a7a',
     '10가지 워크로드를 설계했습니다. 분포의 집중도를 체계적으로 변화시키면서 — '
     'Hotspot처럼 극단적으로 집중된 것부터 Uniform처럼 완전히 분산된 것까지 — '
     '각각의 캐시 히트율을 측정했습니다. 캐시 크기도 4MB~256MB 7단계로 변화시켜 포화점도 분석했습니다.'),
    ('주요 결과 (2~2.5분) [배점 25점]', '#1a4a7a',
     '8종의 워크로드는 가설대로 동작했습니다. 집중도가 가장 높은 Hotspot_9505가 92.7%로 1위, '
     '분산된 Uniform이 28%로 최하위를 기록했습니다. 32MB 캐시에서 3.3배 차이가 납니다.'),
    ('예상과 다른 결과 ① Bimodal (1.5~2분) [배점 25점 핵심]', '#7b341e',
     '저희가 Bimodal을 80% 이상으로 예상한 이유는 두 구간에 집중되므로 효율적일 것이라 판단했기 때문입니다. '
     '그러나 실제는 69.25%였습니다. 원인은 Working Set이었습니다. '
     '두 피크의 Working Set을 합산하면 약 30~60MB로 32MB 캐시를 초과합니다. '
     '단일 피크 Gaussian_s05와 달리 두 영역을 동시에 캐시해야 해서 교체가 잦아졌습니다. '
     '캐시를 64MB로 늘리면 77.6%로 회복되어, 이 분석이 옳음을 검증했습니다.'),
    ('예상과 다른 결과 ② Sequential (1.5~2분) [배점 25점 핵심]', '#7b341e',
     'Sequential은 같은 키를 반복 접근하지 않으므로 낮은 hit율을 예상했습니다. '
     '그러나 실제로는 75%가 나왔고, 놀랍게도 캐시 크기를 4MB에서 256MB로 늘려도 동일했습니다. '
     '원인은 블록 내 공간 지역성입니다. RocksDB는 키를 4KB 블록에 묶어 저장합니다. '
     'key_0에 접근하면 블록 전체(key_0~key_3)가 캐시에 올라와, key_1~3은 자동으로 HIT됩니다. '
     '블록당 키가 4개이므로 이론적 hit율은 3/4 = 75%이며, 실측 74.95%와 일치합니다.'),
    ('결론 및 시사점 (1분)', '#1a5c1a',
     '가설은 대체로 지지되었으나, 두 가지 중요한 보완이 필요했습니다. '
     '첫째, 집중도뿐 아니라 Working Set이 캐시 크기에 맞는지가 중요합니다. '
     '둘째, 키 반복이 없어도 블록 공간 지역성으로 인한 히트가 발생합니다. '
     '이 두 발견은 실제 RocksDB 캐시 튜닝에 직접 적용할 수 있는 지침입니다.'),
]

for title, color, script in script_sections:
    story += [
        Paragraph(title, S('sh', fontName='NanumBold', fontSize=10, leading=15,
                             textColor=colors.HexColor(color), spaceBefore=8, spaceAfter=3)),
        Paragraph(script, S('sc', fontSize=9, leading=15,
                              backColor=colors.HexColor('#fafafa'),
                              borderColor=colors.HexColor(color), borderWidth=0.8,
                              borderPadding=7, spaceAfter=6)),
    ]

story += [SP(8), PageBreak()]

# ════ 7. 예상 질문 & 답변 ════════════════════════════════
story += [
    H1('7. 예상 질의응답 준비 [배점 10점]'),
    HR(),
]

qa_data = [
    ['예상 질문', '답변 요점'],
    ['Sequential이 캐시 크기와 무관한 것이\n실제 운영에서는 어떤 의미인가?',
     'Sequential 스캔이 캐시를 점유하지만 재사용이 없어 낭비입니다. '
     'RocksDB는 ReadOptions::fill_cache=false 옵션으로 이를 방지할 수 있습니다.'],
    ['1,506회 실험은 어떻게 정했나?',
     'n=6에서 표준편차가 ±38%로 불안정했고, n=1,006부터 ±3% 이내로 수렴했습니다. '
     'n=1,006과 n=1,506의 평균 차이가 0.1%p 미만이어서 1,000회 이상이면 충분하다 판단했습니다.'],
    ['Bimodal에서 64MB 캐시 시 hit율이 왜\nGaussian_s05(87%)보다 낮은 77%인가?',
     'σ=5% Gaussian은 working set이 30MB로 매우 집중적인 반면, '
     'Bimodal은 분리된 두 구간(각 15MB)이라 캐시 교체가 더 많이 발생합니다.'],
    ['Uniform의 이론적 한계가 56.8%인 이유는?',
     '50,000회 요청으로 접근하는 유니크 블록 수가 25,000×(1-e⁻²)≈21,617개에 그칩니다. '
     '나머지 28,383회가 재접근(HIT)이 되어 28,383/50,000 = 56.8%가 물리적 상한입니다.'],
    ['이 실험 결과를 실제 서비스에 어떻게 적용하나?',
     '서비스의 접근 분포를 분석해 Working Set 크기를 추정하고, '
     '캐시 크기를 Working Set의 100~110%로 설정하면 최적 효율을 달성할 수 있습니다.'],
]
story += [make_table(qa_data, [CONTENT_W*0.38, CONTENT_W*0.62]), SP(8), PageBreak()]

# ════ 8. 평가기준 대응 체크리스트 ══════════════════════
story += [
    H1('8. 발표 평가 기준 대응 체크리스트'),
    HR(),
]

check_data = [
    ['평가 항목', '배점', '대응 내용', '해당 발표 파트'],
    ['태도 및 발표 전달력', '10점',
     '발표 스크립트 숙지 후 자연스럽게 전달\n목소리 크기·속도 조절', '전체'],
    ['발표 시간 준수', '5점',
     '스크립트 기준 10~12분 구성\n도입1.5 + 설계2 + 결과2 + 예상외2×2 + 결론1분', '6섹션 시간 배분'],
    ['실험 설계의 타당성', '20점',
     '• 목적: 분포별 캐시 효율 정량 비교 명확\n'
     '• 변수: 워크로드 10종 × 캐시 7단계 체계적\n'
     '• 신뢰성: n=1,506회, 수렴 분석으로 검증', '섹션 1, 6(설계 설명)'],
    ['결과 분석 및 해석', '25점',
     '• 시각화: 7개 그래프, 비교표 다수\n'
     '• 논리적 해석: 이론값-실측값 일치 검증\n'
     '• 예상 외 결과: Bimodal·Sequential 심층 분석', '섹션 3, 4, 5'],
    ['발표 자료 구성', '10점',
     '• 가설 → 실험 → 결과 → 분석 → 결론 구조\n'
     '• 그래프, 표, 발표 스크립트 체계적 구성', '전체 PDF'],
    ['독창성', '10점',
     '• Sequential의 블록 공간 지역성 발견\n'
     '• Bimodal Working Set 분석\n'
     '• 이론값과 실측값 일치 검증 (3/4=75.0%)', '섹션 3, 4'],
    ['팀워크 및 역할 분담', '10점',
     '팀원별 발표 섹션 분배\n질의응답 시 협력 대응', '발표 당일'],
    ['질의응답 대응력', '10점',
     '섹션 7의 예상 질문 5가지 사전 준비\n이론적 근거 포함한 답변 준비', '섹션 7'],
    ['합계', '100점', '', ''],
]
story += [make_table(check_data,
          [CONTENT_W*0.22, CONTENT_W*0.08, CONTENT_W*0.45, CONTENT_W*0.25]),
    SP(10),
    HR(),
    P('본 자료는 팀 프로젝트 발표 준비를 위해 실험 결과를 정리한 문서입니다.', sCaption),
]

doc.build(story)
import os
print(f'✓ PDF 생성 완료: {OUT}')
print(f'  파일 크기: {os.path.getsize(OUT)//1024} KB')
