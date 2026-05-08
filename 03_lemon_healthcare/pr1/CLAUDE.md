# CLAUDE.md — 프로젝트 컨텍스트 (루트)

> 이 문서는 **Claude Code가 이 프로젝트에서 어떤 작업을 하든 가장 먼저 읽어야 하는 컨텍스트**입니다.  
> 모든 코드 생성·수정·리팩토링 작업 전에 이 문서의 규칙을 반드시 준수하세요.

---

## 🎯 프로젝트 한 줄 정의

**Lemon Healthcare — 건강의신 AI 모델**: 영양제·식단·활동을 통합 분석하여 만성질환자 중심의 맞춤형 건강 관리를 제공하는 AI 헬스케어 플랫폼. (주)레몬헬스케어 발주, 경북대학교 AI/빅데이터 전문가 양성 과정 협업 프로젝트.

## 🔑 핵심 메시지 (모든 코드·텍스트에 반영)

> **"필라이즈가 못하는 만성질환자 + 의료데이터 영역으로 차별화한다."**

- 1차 핵심 페르소나: B형 (김건강, 52세 만성질환자)
- 2차 확장 페르소나: A형 (박직장, 38세 예방 직장인)

---

## 📂 폴더 구조 (절대 변경 금지)

```
lemon-healthcare-project/
├── README.md
├── CLAUDE.md                    ← 이 파일 (Tier 1)
├── docs/                        # 기획·설계 문서 (10개)
│   ├── 01-project-overview.md
│   ├── ... (02~10)
│   └── dev-guides/              # 작업 단위 가이드 (Tier 3)
│       ├── 00-setup-environment.md
│       └── ... (01~05)
├── backend/                     # Python 백엔드
│   ├── CLAUDE.md                ← Tier 2 (백엔드 작업 시 추가 참조)
│   ├── src/
│   │   ├── algorithms/          # v1~v4, BMR, TDEE, 7-step
│   │   ├── ocr/                 # OCR Adapter
│   │   ├── llm/                 # LLM Adapter
│   │   ├── nutrition/           # KDRIs 룩업, 결핍 진단
│   │   ├── prediction/          # 체중 예측
│   │   ├── activity/            # 활동점수
│   │   ├── api/                 # FastAPI 라우터
│   │   ├── models/              # Pydantic 스키마, DB 모델
│   │   └── utils/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/
│   ├── requirements.txt
│   └── pyproject.toml
├── mobile/                      # Flutter 모바일 (Phase 2~)
├── data/                        # 정적 데이터
│   ├── CLAUDE.md                ← Tier 2 (데이터 작업 시 추가 참조)
│   └── kdris_2020.csv
├── notebooks/
├── scripts/
└── .github/
```

> ⚠️ 새 폴더가 필요하면 반드시 사용자에게 먼저 확인하세요.

---

## 🔥 작업 시 절대 규칙 (Critical Rules)

### Rule 1. 의료 도메인 표현 절대 금지 단어

코드의 **함수명·변수명·docstring·UI 텍스트·LLM 프롬프트·로그**에서 다음 표현을 **절대 사용하지 마세요**:

| ❌ 금지 | ✅ 대체 |
|--------|--------|
| diagnose, diagnosis | analyze, evaluate, classify |
| prescribe, prescription | recommend, suggest |
| cure, treat, treatment | manage, support |
| guarantee, ensure (효과) | may help, can support |
| "이 약을 드세요" | "전문가와 상담하세요" |
| "당뇨입니다" | "혈당 관련 영양 관리가 필요할 수 있습니다" |

> 📖 **상세 사례**: [docs/10-compliance-checklist.md §10](./docs/10-compliance-checklist.md)

### Rule 2. 외부 API는 반드시 Adapter 패턴

OCR(Cloud Vision, CLOVA), LLM(Claude, GPT) 등 외부 API는 **절대 직접 호출하지 마세요**. Adapter 인터페이스를 통해야 합니다.

```python
# ❌ 잘못된 예
from google.cloud import vision
client = vision.ImageAnnotatorClient()

# ✅ 올바른 예
from src.ocr.base import OCRAdapter
from src.ocr.google_vision import GoogleVisionOCR

ocr: OCRAdapter = GoogleVisionOCR()
text = await ocr.extract_text(image_bytes)
```

> 📖 **상세 패턴**: [backend/CLAUDE.md](./backend/CLAUDE.md)

### Rule 3. 타입 힌트 100% + Pydantic v2 강제

- 모든 함수·메서드에 **타입 힌트 필수** (mypy strict)
- 데이터 모델은 모두 **Pydantic v2 BaseModel** 사용 (`@dataclass` 대신)
- `Any` 타입은 정당한 사유 없이 사용 금지

```python
# ❌ 잘못된 예
def calculate_bmi(w, h):
    return w / (h/100) ** 2

# ✅ 올바른 예
def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """체중과 키로 BMI를 계산한다.

    Args:
        weight_kg: 체중 (kg, 10~300 범위)
        height_cm: 키 (cm, 50~250 범위)

    Returns:
        BMI 값 (소수점 1자리, kg/m²).

    Raises:
        ValueError: 입력값이 허용 범위를 벗어난 경우.

    Examples:
        >>> calculate_bmi(70.0, 175)
        22.9
    """
    height_m = height_cm / 100
    return round(weight_kg / (height_m ** 2), 1)
```

### Rule 4. Google-style Docstring 100% 강제

- 모든 public 함수·메서드·클래스에 **Google-style docstring 필수**
- 필수 섹션: `Args`, `Returns`, `Raises`, `Examples` (해당 시)
- 한국어 설명 + 영어 코드 예시 권장

### Rule 5. 단위 테스트 동반 필수

새 함수·클래스를 만들 때마다 **반드시 단위 테스트를 함께** 작성하세요. 회사 가이드 PPTX의 계산 예시는 **모두 단위 테스트로 변환**되어야 합니다.

```
src/algorithms/v1.py        ← 구현
└─ tests/unit/test_v1.py    ← 동반 테스트 (가이드 예시 포함)
```

### Rule 6. 민감 정보 절대 커밋 금지

- API 키, 비밀번호, 사용자 데이터를 **절대 git에 커밋하지 마세요**
- 환경 변수는 `.env` (gitignore) → `.env.example` (커밋)
- Service Account JSON, 인증서, 키스토어 모두 금지

### Rule 7. 언어 정책

- **코드·docstring·주석**: 영어 우선, 한국어 보조
- **변수명·함수명**: 영어만 (snake_case)
- **사용자 노출 텍스트**: 한국어 (UI, 에러 메시지)
- **테스트 케이스 docstring**: 한국어 OK (예: "50대 여성 비만1단계 검증")

### Rule 8. 한국·아시아 BMI 기준 사용

서양 기준 25 미만 정상이 아니라, **한국·아시아 기준** 사용:
- 18.5 미만: 저체중
- 18.5~22.9: 정상
- 23.0~24.9: 과체중
- 25.0~29.9: 비만 1단계
- 30.0+: 비만 2단계

---

## 📚 작업 → 참조 문서 매핑

작업 종류에 따라 어떤 docs/N번 문서를 먼저 읽어야 하는지:

| 작업 종류 | 1순위 참조 | 2순위 참조 |
|---------|----------|---------|
| 알고리즘 구현 (v1~v4, BMR, 7-step) | `docs/07-core-algorithm.md` | `docs/dev-guides/0X-*.md` |
| 부족 영양소 진단 / 목적별 분석 | `docs/07-core-algorithm.md` §4 | `docs/09-data-catalog.md` |
| OCR / LLM Adapter | `docs/07-core-algorithm.md` §4.1 | `docs/06-tech-stack.md` §3 |
| FastAPI 라우터 | `docs/06-tech-stack.md` | `backend/CLAUDE.md` |
| DB 스키마 | `docs/06-tech-stack.md` §3.3 | `docs/09-data-catalog.md` §8 |
| KDRIs / 식약처 데이터 | `docs/09-data-catalog.md` | `data/CLAUDE.md` |
| 사용자 노출 텍스트 (UI/에러) | `docs/10-compliance-checklist.md` §10 | `docs/03-project-intent.md` |
| 권한·동의 UI | `docs/10-compliance-checklist.md` §5.2 | — |
| 면책 고지 표시 | `docs/10-compliance-checklist.md` §2.3 | — |
| GitHub 협업 (브랜치·커밋·PR) | `docs/05-github-guidelines.md` | — |
| 새 기능 일정 / 누가 할지 | `docs/08-implementation-plan.md` | — |
| 시장·페르소나 컨텍스트 필요 | `docs/03-project-intent.md` | `docs/04-market-research.md` |

---

## 🛠 자주 사용하는 명령어

### 백엔드 개발

```bash
cd backend

# 가상환경 활성화
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate      # Windows

# 의존성 설치
pip install -r requirements.txt

# 개발 서버 실행
uvicorn src.main:app --reload --port 8000

# 코드 품질 (커밋 전 필수)
black src tests --line-length=100
ruff check src tests --fix
mypy src --strict

# 테스트
pytest                                    # 전체
pytest -v                                 # 상세
pytest --cov=src --cov-report=term-missing
pytest tests/unit/test_v1.py::test_v1_50f_obese1_7000steps  # 특정 테스트
```

### Docker

```bash
docker compose up -d              # 전체 시작
docker compose logs -f backend    # 로그
docker compose down               # 종료
docker compose down -v            # 볼륨도 삭제 (DB 초기화)
```

### Git (Conventional Commits)

```bash
git checkout -b feature/algo-v1-step-score
git commit -m "feat(algo): add v1 step score calculation"
git push -u origin feature/algo-v1-step-score
```

> 📖 **상세 컨벤션**: [docs/05-github-guidelines.md](./docs/05-github-guidelines.md)

---

## ✅ 모든 작업 완료 후 체크리스트

코드 변경 후 PR 올리기 전에 반드시 확인:

- [ ] 새 함수·클래스에 **타입 힌트 100%**
- [ ] 새 함수·클래스에 **Google-style docstring** (Args/Returns/Raises/Examples)
- [ ] **Pydantic v2** 모델 사용 (dataclass X)
- [ ] **단위 테스트** 동반 (회사 가이드 예시 포함)
- [ ] **금지 표현** 0건 (diagnose, prescribe, cure, treat 등)
- [ ] **외부 API** 직접 호출 X — Adapter 패턴 경유
- [ ] **민감 정보** 커밋 X (.env, API 키, JSON 키)
- [ ] `black`, `ruff`, `mypy --strict` 통과
- [ ] `pytest` 전체 통과
- [ ] 한국어/영어 언어 정책 준수
- [ ] 변경된 docs/ 동반 갱신 (영향 시)

---

## 🚫 절대 하지 말 것 (Anti-Patterns)

```
❌ from any_module import *           ─ wildcard import 금지
❌ except Exception: pass             ─ silent exception 금지
❌ # TODO: fix later                  ─ 머지 전 모두 해소
❌ print() in src/ code               ─ logger 사용
❌ time.sleep() in async functions    ─ asyncio.sleep() 사용
❌ datetime.now() without timezone    ─ datetime.now(UTC) 명시
❌ Hard-coded strings                 ─ 상수·enum·설정값으로
❌ Magic numbers                      ─ 명명된 상수로
❌ JSON 직접 파싱 / 직접 직렬화        ─ Pydantic 모델 통과
❌ 의료 진단·처방 표현                ─ 정보 제공 표현으로
```

---

## 🎓 새 기능 개발 워크플로 (표준)

```
1. 관련 docs/ 문서 읽기 (위의 매핑 표 참조)
2. dev-guides/0X-*.md 가 있으면 그것을 메인 명세로 사용
3. feature/<scope>-<description> 브랜치 생성
4. 구현 + 테스트 동반 작성
5. 로컬 검증: black, ruff, mypy --strict, pytest
6. 커밋 (Conventional Commits 형식)
7. PR 생성 (자동으로 PR 템플릿 채워짐)
8. CI 통과 확인 → 리뷰 요청
9. 머지 후 브랜치 삭제
```

---

## 🤖 Claude Code에게 작업 의뢰하는 표준 패턴

사용자가 Claude Code에 다음과 같이 작업을 의뢰할 때:

```
"docs/dev-guides/01-bmi-and-v1-algorithm.md 보고 구현해줘"
```

→ Claude Code는:
1. 먼저 이 `CLAUDE.md` 를 읽고 프로젝트 규칙 숙지
2. `backend/CLAUDE.md` 읽고 백엔드 추가 규칙 숙지 (백엔드 작업 시)
3. `docs/dev-guides/01-bmi-and-v1-algorithm.md` 의 명세 따라 구현
4. 명세에 명시된 모든 단위 테스트 작성
5. 마지막 체크리스트 모두 검증 후 보고

---

## 📜 라이선스 헤더

새 Python 파일 상단에 다음 라이선스 헤더는 **불필요**합니다 (저장소 LICENSE로 충분). 단, 파일 모듈 docstring은 권장:

```python
"""v1 활동점수 산출 알고리즘.

회사 가이드의 v1 정의를 구현한 모듈. 권장 걸음수와 기본점수를 계산한다.

Reference:
    docs/07-core-algorithm.md §3.2
"""

from __future__ import annotations

# ... 코드 ...
```

---

## 🔗 핵심 문서 단축 링크

- 알고리즘 명세: [docs/07-core-algorithm.md](./docs/07-core-algorithm.md)
- 기술 스택: [docs/06-tech-stack.md](./docs/06-tech-stack.md)
- 컴플라이언스: [docs/10-compliance-checklist.md](./docs/10-compliance-checklist.md)
- GitHub 규칙: [docs/05-github-guidelines.md](./docs/05-github-guidelines.md)
- 데이터 카탈로그: [docs/09-data-catalog.md](./docs/09-data-catalog.md)

---

**마지막 갱신**: 2026-05-03 | **버전**: v1.0
