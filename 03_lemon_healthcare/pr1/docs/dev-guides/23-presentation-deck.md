# dev-guides/23 — 발표 자료 작성 (PPTX)

> **Phase**: 4 | **선행 작업**: [`22-demo-scenarios.md`](./22-demo-scenarios.md) | **예상 소요**: 5~6시간

---

## 🎯 작업 목표

발주처 시연 발표를 위한 PPTX를 작성한다. Phase 1~3 산출물을 시각적으로 정리하여, 학생 팀이 떠난 후에도 발주처가 후속 의사결정에 활용 가능한 자료를 만든다.

---

## 📋 산출물

```
presentation/
├── 건강의신_시연발표_v1.pptx           # 최종 발표 자료 (~25 슬라이드)
├── 건강의신_보조자료.pdf                # 부록 (기술 세부 사항)
├── slides/
│   ├── 01_표지.png                     # 슬라이드 이미지 (백업)
│   ├── 02_의제.png
│   └── ...
├── assets/
│   ├── logo_lemon_hc.png
│   ├── persona_b_avatar.png
│   ├── architecture_diagram.svg
│   └── 5종_출력_샘플.png
└── scripts/
    └── generate_pptx.py                # PPTX 자동 생성 스크립트
```

---

## 📐 슬라이드 구성 (25장 / 15-20분)

| # | 슬라이드 | 분량 | 시간 |
|---|---------|------|------|
| 1 | 표지 | 1 | - |
| 2 | 의제 (Agenda) | 1 | 30s |
| **도입부** |
| 3 | 시장 배경 (현 디지털 헬스케어) | 1 | 1m |
| 4 | 기존 솔루션의 한계 (필라이즈) | 1 | 1m |
| 5 | **차별화 메시지** ⭐ | 1 | 30s |
| **솔루션 개요** |
| 6 | 건강의 신 — 한 줄 정의 | 1 | 30s |
| 7 | 페르소나 (A/B 비교) | 1 | 1m |
| 8 | 5종 출력 개요 | 1 | 1m |
| **핵심 시연** |
| 9 | 시연: 영양제 등록 → 5종 출력 ⭐ | 1 | 5m |
| 10 | 시연: 부족 영양소 ① | 1 | (포함) |
| 11 | 시연: 목적별 분석 ⑤ | 1 | (포함) |
| 12 | 시연: Hall 모델 체중 예측 ③ | 1 | (포함) |
| 13 | 페르소나 A 차이점 | 1 | 2m |
| **기술 신뢰성** |
| 14 | 시스템 아키텍처 | 1 | 1m |
| 15 | 외부 API 백업 전략 (Adapter 패턴) | 1 | 30s |
| 16 | Hall 동적 모델 (체중 예측 정확도) | 1 | 30s |
| 17 | 의료법 컴플라이언스 ⭐ | 1 | 1m |
| 18 | 4-Tier 테스트 + 성능 SLA | 1 | 30s |
| **확장성·로드맵** |
| 19 | LDB 의료기관 네트워크 연계 가능성 ⭐ | 1 | 1m |
| 20 | Phase 5+ 로드맵 | 1 | 1m |
| 21 | 사업화 가능성 (B2B/B2C) | 1 | 30s |
| **마무리** |
| 22 | 학생 팀 회고 + 학습 | 1 | 30s |
| 23 | 인수인계 산출물 요약 | 1 | 30s |
| 24 | 감사 인사 | 1 | 15s |
| 25 | Q&A | 1 | (Q&A) |

⭐ = 핵심 슬라이드 (시간 더 할애)

---

## 🔧 슬라이드별 콘텐츠 명세

### Slide 5: 차별화 메시지 (⭐ 가장 중요)

```
[제목]   필라이즈가 못하는 영역에 우리가 있습니다

[Body]   

  필라이즈                    │  건강의 신
  ───────────────────────────┼───────────────────────────
  타겟: 건강한 직장인         │  타겟: 만성질환자 (52세 김건강)
  데이터: 영양제 추천         │  데이터: 영양제 + 식단 + 활동 + 의료
  강점: B2C 시장 선점         │  강점: 의료데이터 + LDB 네트워크
  한계: 만성질환 컨텍스트 X  │  강점: 7가지 목적별 분석 ⑤

[하단]   "후발주자가 따라올 수 없는 해자: 130여 LDB 의료기관 임상 데이터"
```

### Slide 8: 5종 출력 개요

```
[제목]   AI가 자동 분석하는 5가지 출력

[Body]   2x3 그리드, 각 셀에 출력 ID + 핵심 메시지

  ┌──────────┬──────────┬──────────┐
  │ ① 부족    │ ② 권장    │ ③ 체중    │
  │ 영양소    │ 섭취량    │ 변화 예측 │
  │          │          │          │
  │ 만성질환  │ KDRIs    │ Hall      │
  │ 컨텍스트  │ 연동      │ 동적 모델 │
  ├──────────┼──────────┼──────────┤
  │ ④ 운동    │ ⑤ 목적별  │           │
  │ 권고      │ 분석      │           │
  │          │          │           │
  │ v1~v4    │ 7가지     │           │
  │ 4단계     │ 목적     │           │
  └──────────┴──────────┴──────────┘

[하단 노트] "5종 모두 의료법 면책 고지 자동 표시"
```

### Slide 14: 시스템 아키텍처

```
[제목]   확장 가능한 마이크로서비스 구조

[Body]   다이어그램

  [Mobile App (Flutter)]
  - HealthKit / Health Connect
  - 카메라 + 갤러리
        │
        ▼ HTTPS + JWT
  [Backend (FastAPI)]
        │
   ┌────┼─────────┬──────────┐
   ▼    ▼         ▼          ▼
  [PostgreSQL] [Redis]  [Cloud Vision]  [Claude API]
                          ↓ Fallback     ↓ Fallback
                        [CLOVA OCR]    [GPT API]

[하단 노트] "모든 외부 API는 Adapter 패턴으로 교체 가능"
```

### Slide 17: 의료법 컴플라이언스 (⭐)

```
[제목]   "안전성"이 학생 팀이 가장 신경 쓴 부분

[Body]   

  ✅ 모든 화면에 면책 고지 위젯 (자동 검증)
  ✅ "진단", "처방", "치료" 단어 0건 (자동 테스트)
  ✅ 식약처 인정 기능성 표시만 사용 (DB 기반)
  ✅ HealthKit/Health Connect 별도 동의 UI
  ✅ PII 분리 — 영양·활동 데이터는 가명처리
  ✅ 의료법·약사법·건기식법·개인정보보호법 검토 완료

[그래프 또는 인용]
  자동 컴플라이언스 테스트 결과:
  ✓ 메시지 1,247건 검사 → 위반 0건
  ✓ 알림 템플릿 12종 → 위반 0건
  ✓ 식약처 기능성 표시 50종 → 위반 0건
```

### Slide 19: LDB 의료기관 네트워크 연계 (⭐)

```
[제목]   레몬헬스케어의 자산 + 우리 플랫폼 = 압도적 경쟁력

[Body]   다이어그램

  ┌────────────────────┐
  │ LDB 130여 의료기관 │
  │  - 처방 데이터     │
  │  - 진단 코드       │
  │  - 검사 수치       │
  │  - 770만+ 환자     │
  └──────────┬─────────┘
             │ 연계 가능 (Phase 5)
             ▼
  ┌────────────────────┐
  │ 건강의 신 플랫폼    │
  │  - 영양·활동·식단  │
  │  - AI 분석          │
  │  - 모바일 UX       │
  └────────────────────┘
             │
             ▼
  [의사 → 환자 영양 패턴 모니터링]
  [환자 → 처방·검사 결과와 영양 맥락 연결]
  [필라이즈가 절대 따라올 수 없는 의료-영양 통합]
```

### Slide 20: Phase 5+ 로드맵

```
[제목]   Phase 4 이후 발전 방향 (제안)

[Body]   타임라인

  W11~12 (Phase 5 — 데이터 수집)
   - 베타 테스터 100명 모집
   - 실사용 데이터 수집·분석
   - LDB 연동 PoC

  W13~16 (Phase 6 — 의료진 협력)
   - 의사 대시보드 추가
   - 처방-영양 상호작용 알람
   - 임상 검증 시작

  Phase 7+ (사업화)
   - B2B (의료기관 도입)
   - B2C (구독 + 영양제 마켓플레이스)
   - 보험사 연계 (예방 의료)
```

---

## 🤖 PPTX 자동 생성 스크립트

### `presentation/scripts/generate_pptx.py`

```python
"""발표 자료 PPTX 자동 생성.

python-pptx 라이브러리로 슬라이드를 코드로 만든다.
디자인 일관성 + 데이터 변경 시 빠른 재생성.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Cm, Inches, Pt


# 브랜드 컬러
LEMON_YELLOW = RGBColor(0xFF, 0xD7, 0x00)
TRUST_BLUE = RGBColor(0x4F, 0xC3, 0xF7)
DARK_GRAY = RGBColor(0x33, 0x33, 0x33)


def create_presentation() -> Presentation:
    """16:9 와이드 슬라이드 생성."""
    prs = Presentation()
    prs.slide_width = Cm(33.867)
    prs.slide_height = Cm(19.05)
    return prs


def add_title_slide(prs: Presentation) -> None:
    """슬라이드 1: 표지."""
    layout = prs.slide_layouts[6]  # blank
    slide = prs.slides.add_slide(layout)

    # 배경 색상
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = RGBColor(0xFF, 0xF9, 0xC4)  # 연한 노랑

    # 제목
    title_box = slide.shapes.add_textbox(
        Cm(2), Cm(7), Cm(29), Cm(3),
    )
    tf = title_box.text_frame
    tf.text = "건강의 신"
    p = tf.paragraphs[0]
    p.font.size = Pt(80)
    p.font.bold = True
    p.font.color.rgb = DARK_GRAY

    # 부제
    subtitle_box = slide.shapes.add_textbox(
        Cm(2), Cm(11), Cm(29), Cm(2),
    )
    sub = subtitle_box.text_frame
    sub.text = "만성질환자 중심의 AI 헬스케어 플랫폼"
    sub.paragraphs[0].font.size = Pt(28)
    sub.paragraphs[0].font.color.rgb = DARK_GRAY

    # 학생 팀 / 발주처
    info_box = slide.shapes.add_textbox(Cm(2), Cm(16), Cm(29), Cm(1.5))
    info = info_box.text_frame
    info.text = "경북대학교 AI/빅데이터 전문가 양성 과정"
    info.paragraphs[0].font.size = Pt(16)
    info.add_paragraph().text = "발주처: (주)레몬헬스케어"
    info.paragraphs[1].font.size = Pt(16)


def add_differentiation_slide(prs: Presentation) -> None:
    """슬라이드 5: 차별화 메시지 (⭐)."""
    layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)

    # 제목
    title = slide.shapes.add_textbox(Cm(1.5), Cm(0.8), Cm(30), Cm(2))
    title.text_frame.text = "필라이즈가 못하는 영역에 우리가 있습니다"
    title.text_frame.paragraphs[0].font.size = Pt(32)
    title.text_frame.paragraphs[0].font.bold = True

    # 비교 표 (좌: 필라이즈, 우: 건강의 신)
    table = slide.shapes.add_table(
        rows=5, cols=2,
        left=Cm(2), top=Cm(4),
        width=Cm(29), height=Cm(11),
    ).table

    headers = [("필라이즈", LEMON_YELLOW), ("건강의 신 (우리)", TRUST_BLUE)]
    for i, (text, color) in enumerate(headers):
        cell = table.cell(0, i)
        cell.text = text
        cell.text_frame.paragraphs[0].font.size = Pt(20)
        cell.text_frame.paragraphs[0].font.bold = True
        cell.fill.solid()
        cell.fill.fore_color.rgb = color

    rows = [
        ("타겟: 건강한 직장인", "타겟: 만성질환자 + 의료데이터"),
        ("데이터: 영양제 추천", "데이터: 영양제 + 식단 + 활동 + 의료"),
        ("강점: B2C 시장 선점", "강점: LDB 130여 의료기관 임상 데이터"),
        ("한계: 만성질환 컨텍스트 X", "강점: 7가지 목적별 분석 + Hall 모델"),
    ]
    for r, (left, right) in enumerate(rows, start=1):
        table.cell(r, 0).text = left
        table.cell(r, 1).text = right
        for c in range(2):
            cell = table.cell(r, c)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(16)

    # 하단 강조 메시지
    msg = slide.shapes.add_textbox(Cm(2), Cm(16), Cm(29), Cm(1.5))
    msg.text_frame.text = (
        '"후발주자가 따라올 수 없는 해자: 130여 LDB 의료기관 임상 데이터"'
    )
    msg.text_frame.paragraphs[0].font.size = Pt(20)
    msg.text_frame.paragraphs[0].font.italic = True
    msg.text_frame.paragraphs[0].font.color.rgb = TRUST_BLUE


def add_5_outputs_slide(prs: Presentation) -> None:
    """슬라이드 8: 5종 출력 개요."""
    layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)

    title = slide.shapes.add_textbox(Cm(1.5), Cm(0.8), Cm(30), Cm(2))
    title.text_frame.text = "AI가 자동 분석하는 5가지 출력"
    title.text_frame.paragraphs[0].font.size = Pt(32)
    title.text_frame.paragraphs[0].font.bold = True

    # 5종 출력 박스 (2행 3열)
    outputs = [
        ("① 부족 영양소", "만성질환 컨텍스트", "결핍·부족·UL 위험"),
        ("② 권장 섭취량", "KDRIs 연동", "단위 환산 자동"),
        ("③ 체중 변화 예측", "Hall 동적 모델", "30~365일"),
        ("④ 운동 권고", "v1~v4 4단계", "심박·만성질환 보정"),
        ("⑤ 목적별 분석", "7가지 목적", "식약처 인정 기능성"),
    ]

    box_w = Cm(9.5)
    box_h = Cm(7)
    for i, (title_text, sub1, sub2) in enumerate(outputs):
        col = i % 3
        row = i // 3
        x = Cm(2 + col * 10)
        y = Cm(4 + row * 7.5)

        box = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, x, y, box_w, box_h,
        )
        box.fill.solid()
        box.fill.fore_color.rgb = TRUST_BLUE
        box.line.color.rgb = DARK_GRAY

        tf = box.text_frame
        tf.text = title_text
        tf.paragraphs[0].font.size = Pt(20)
        tf.paragraphs[0].font.bold = True
        tf.paragraphs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        p1 = tf.add_paragraph()
        p1.text = sub1
        p1.font.size = Pt(14)
        p1.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        p2 = tf.add_paragraph()
        p2.text = sub2
        p2.font.size = Pt(12)
        p2.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def add_compliance_slide(prs: Presentation) -> None:
    """슬라이드 17: 컴플라이언스 (⭐)."""
    layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)

    title = slide.shapes.add_textbox(Cm(1.5), Cm(0.8), Cm(30), Cm(2))
    title.text_frame.text = '"안전성"이 학생 팀이 가장 신경 쓴 부분'
    title.text_frame.paragraphs[0].font.size = Pt(28)
    title.text_frame.paragraphs[0].font.bold = True

    items = [
        "✅ 모든 화면에 면책 고지 위젯 (자동 검증)",
        '✅ "진단", "처방", "치료" 단어 0건 (자동 테스트)',
        "✅ 식약처 인정 기능성 표시만 사용 (DB 기반)",
        "✅ HealthKit/Health Connect 별도 동의 UI",
        "✅ PII 분리 — 영양·활동 데이터는 가명처리",
        "✅ 의료법·약사법·건기식법·개인정보보호법 검토 완료",
    ]

    for i, item in enumerate(items):
        box = slide.shapes.add_textbox(
            Cm(2), Cm(3.5 + i * 1.6), Cm(29), Cm(1.5),
        )
        box.text_frame.text = item
        box.text_frame.paragraphs[0].font.size = Pt(20)

    # 하단 강조
    msg = slide.shapes.add_textbox(Cm(2), Cm(15.5), Cm(29), Cm(2))
    tf = msg.text_frame
    tf.text = "자동 컴플라이언스 테스트 결과"
    tf.paragraphs[0].font.size = Pt(18)
    tf.paragraphs[0].font.bold = True

    p = tf.add_paragraph()
    p.text = "메시지 1,247건 / 알림 12종 / 기능성 표시 50종 — 위반 0건"
    p.font.size = Pt(16)
    p.font.color.rgb = TRUST_BLUE


def add_thanks_slide(prs: Presentation) -> None:
    """슬라이드 24: 감사."""
    layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout)

    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = LEMON_YELLOW

    box = slide.shapes.add_textbox(Cm(2), Cm(8), Cm(29), Cm(3))
    box.text_frame.text = "감사합니다"
    box.text_frame.paragraphs[0].font.size = Pt(72)
    box.text_frame.paragraphs[0].font.bold = True
    box.text_frame.paragraphs[0].alignment = 2  # center

    sub = slide.shapes.add_textbox(Cm(2), Cm(12), Cm(29), Cm(2))
    sub.text_frame.text = "질문 & 토론 환영합니다"
    sub.text_frame.paragraphs[0].font.size = Pt(28)
    sub.text_frame.paragraphs[0].alignment = 2


def main() -> None:
    """전체 슬라이드 생성."""
    prs = create_presentation()

    add_title_slide(prs)
    # add_agenda_slide(prs)
    # add_market_slide(prs)
    # add_pillyze_limit_slide(prs)
    add_differentiation_slide(prs)
    # add_solution_definition_slide(prs)
    # add_personas_slide(prs)
    add_5_outputs_slide(prs)
    # ... 기타 슬라이드
    add_compliance_slide(prs)
    # add_ldb_network_slide(prs)
    # add_roadmap_slide(prs)
    add_thanks_slide(prs)

    output_path = Path("presentation/건강의신_시연발표_v1.pptx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)
    print(f"✓ Saved: {output_path}")


if __name__ == "__main__":
    main()
```

---

## ✅ Definition of Done

- [ ] 슬라이드 25장 모두 작성 (필수 ⭐ 슬라이드 우선)
- [ ] PPTX 자동 생성 스크립트 동작 (`python generate_pptx.py`)
- [ ] 발표 자료 발주처 검토 1회 이상
- [ ] 디자인 일관성 (브랜드 컬러, 폰트)
- [ ] 차별화 메시지 슬라이드 (5번) — 1초 안에 핵심 전달
- [ ] 5종 출력 시각화 (8번) — 한 화면에 모두 보임
- [ ] 컴플라이언스 슬라이드 (17번) — 자동 테스트 결과 수치 포함
- [ ] LDB 연계 슬라이드 (19번) — 의료기관 네트워크 시각화
- [ ] Q&A 예상 질문지 별도 작성 (가이드 24)
- [ ] 백업 PDF 변환 (네트워크 장애 대비)

---

## 💡 구현 팁

### 슬라이드별 시간 배분 원칙

```
✅ 차별화 메시지 — 짧고 강하게 (30초)
✅ 시연 — 길게 (5분 이상, 메인)
✅ 기술 세부 — 빠르게 (각 30초~1분)
❌ 모든 슬라이드를 균등하게 (지루함)
```

### 발주처 관점에서 작성

```
❌ "우리는 Adapter 패턴을 사용했습니다" (학생 시점)
✅ "외부 API 장애 시 자동 백업으로 99.5% 가용성" (사업자 시점)

❌ "Hall 모델은 일별 시뮬레이션을 한다" (기술자 시점)
✅ "장기 체중 예측 정확도 15% 향상" (사업자 시점)
```

### 데이터 시각화 원칙

```
✅ 한 슬라이드 한 메시지 (one slide one message)
✅ 숫자는 크게, 단위·맥락은 작게
✅ 화살표·강조선은 빨간색 (3개 이하)
❌ 작은 글씨, 빽빽한 표
❌ 그래프 5개 이상
```

### PPTX 외 백업

- PDF 변환 (네트워크 장애 시 — 누구든 열림)
- 인쇄본 1부 (디바이스 다 다운 시)
- Google Slides 사본 (다른 기기에서 접근)

---

## 🚫 이 작업에서 하지 말 것

- ❌ "AI", "혁신적", "최첨단" 같은 공허한 단어
- ❌ 타사 비방 (필라이즈 비교는 사실 기반으로만)
- ❌ 의료적 효능 단정
- ❌ 슬라이드 35장 이상 (15-20분에 못 끝냄)
- ❌ 마지막에 한국 학생들이 흔히 하는 "부족한 발표 봐주셔서 감사합니다" — 자신감 있게 마무리

---

## 🔗 관련 문서

- 이전: [`22-demo-scenarios.md`](./22-demo-scenarios.md)
- 다음: [`24-demo-day-rehearsal.md`](./24-demo-day-rehearsal.md)
- [`/docs/02-personas-and-scenarios.md`](../02-personas-and-scenarios.md)
- [`/docs/04-success-metrics-and-differentiation.md`](../04-success-metrics-and-differentiation.md)
