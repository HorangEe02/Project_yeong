# Quick Questions 데이터 편집 가이드

> v3.3 Phase D — AI 챗봇 헤더의 부서/직급별 추천 칩 6종 데이터 풀.
> 비개발자도 안전하게 편집할 수 있도록 구성됨. 검증 스크립트 통과 시 자동 반영.

---

## 1. 디렉토리 구조

```
data/knowledge_base/quick_questions/
├── _common.json            # 부서·직급 무관 공통 (3 슬롯)
├── _by_level/
│   ├── L1.json             # 신입 (EMPLOYEE L1) — 4 항목
│   ├── L2.json             # 일반 (EMPLOYEE L2) — 4 항목
│   ├── L3.json             # 관리자 (MANAGER L3) — 4 항목
│   └── L4_5.json           # 임원/시스템 (EXECUTIVE L4 + SYS L5) — 4 항목
└── {부서명}.json            # 30 부서 — 4~6 항목
```

각 사용자는 화면에 6 슬롯 노출:
- 공통 3 + 직급 2 + 부서 4 → 트림 후 6
- 부서 데이터 미존재 시 `DEPARTMENT_PROFILES.core_responsibilities` 자동 fallback

---

## 2. 신규 부서 추가하기

### 단계 1: JSON 파일 생성

`{부서명}.json` 파일을 디렉토리에 추가:

```json
{
  "department": "신규팀",
  "division": "관리본부",
  "description": "신규 업무 — 한 줄 요약",
  "questions": [
    {
      "id": "new-task1",
      "label": "업무1 라벨",
      "promptText": "업무1 관련 절차 알려줘",
      "category": "action",
      "min_level": 1,
      "max_level": 5,
      "tags": ["키워드1", "키워드2"]
    }
  ]
}
```

### 필수 필드

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | str | **전역 유니크**. 형식 권장: `{팀코드}-{slug}` (예: `qa-ppap-form`) |
| `label` | str | 칩에 표시되는 짧은 한글 (4~14자 권장) |
| `promptText` | str | 클릭 시 입력창에 채워질 / 자동 send 될 실 텍스트 (5~80자) |
| `category` | str | `scenario` / `action` / `sop` / `general` 중 하나 |
| `min_level` | int | 1~5. 이 직급 이상에게만 노출 |
| `max_level` | int | 1~5. 이 직급 이하에게만 노출 (`min_level <= max_level`) |
| `tags` | list[str] | (선택) 검색용 태그 |

### 단계 2: 검증

```bash
cd ajin-ai-assistant-react
python3 scripts/validate_quick_questions.py
```

기대 출력:
```
[FILES] 36
[QUESTIONS] 205
[UNIQUE IDS] 205
...
[PASS] 모든 검증 통과
```

### 단계 3: 캐시 무효화

서버 재시작 또는:
```python
from features.onboarding.quick_questions import invalidate_cache
invalidate_cache()
```

또는 운영 환경 배포 — `lru_cache` 가 새 데이터로 다시 로드됨.

---

## 3. 검증 규칙 (자동)

`scripts/validate_quick_questions.py` 가 7개 항목 자동 검증:

1. **JSON 파싱 성공**
2. **필수 필드 모두 존재** (id, label, promptText, category, min_level, max_level)
3. **ID 전역 유니크** — 다른 부서 파일과도 충돌 없음
4. **category** ∈ {scenario, action, sop, general}
5. **min_level ≤ max_level**, 둘 다 1~5
6. **promptText 길이 5~80자** (UX 적합성)
7. **박부장형 인물 지칭 금지** — 한국인 성씨 80자 + 직급 6종 정규식

### 박부장형 차단 정규식

```python
[김이박최정강조윤장임한오서신권황안송류홍...][가-힣]{1,2}\s*(?:부장|차장|과장|전무|상무|이사)(?:님)?(?![가-힣])
```

❌ 검출되는 패턴:
- `김민수 부장 어디?`
- `박성훈차장 연락처`
- `이지영 과장님께`

✅ 통과 (false positive 방지):
- `신입사원 온보딩 체크`
- `우리 팀 부장 회의`
- `과장직 승진 평가`

---

## 4. 직급 노출 매트릭스

| `min_level` | `max_level` | 노출 직급 |
|---|---|---|
| 1 | 5 | 모두 (EMPLOYEE 신입~SYS) |
| 1 | 1 | 신입 전용 (`'첫 주 가이드'` 등) |
| 3 | 5 | 관리자 이상 (`'결재 대기'`, `'팀 KPI'`) |
| 4 | 5 | 임원/시스템 (`'전사 대시보드'`) |
| 2 | 3 | 실무자 (가장 흔한 패턴) |

---

## 5. 카테고리 의미

| category | 사용 시점 | 색상(향후) |
|---|---|---|
| `scenario` | 상황 대응 — "OOO 상황에서 어떻게?" | 파란색 |
| `action` | 즉시 실행 — 검색/조회/다운로드 | amber (가장 흔함) |
| `sop` | 표준 절차 학습 | 초록색 |
| `general` | 개념/배경 설명 | 회색 |

현재 분포: action 107 (54%) · sop 40 (20%) · scenario 32 (16%) · general 20 (10%)

---

## 6. 부서명 표기 정합

`department` 필드는 `features/onboarding/department_router.py` 의 `DEPARTMENT_PROFILES` 키와 일치해야 함:

```python
DEPARTMENT_PROFILES = {
    "품질보증팀": ...,
    "비전연구팀": ...,
    "기술교육원": ...,  # '교육원' 도 dept 단위
    ...
}
```

`division` 필드는 본부 표기:
- `생산본부` / `생산기술본부` / `개발본부` / `기술연구소` / `관리본부` / `구매본부` / `재경본부` / `(독립)`

---

## 7. 비개발자 편집 워크플로

1. 부서 책임자가 본 가이드의 § 2 단계 1 양식으로 JSON 작성
2. 데이터 운영자가 `git` 커밋 (또는 풀 리퀘스트)
3. CI 가 `validate_quick_questions.py` 실행 → 검증 통과 시 머지
4. 운영 배포 후 사용자가 챗 화면에서 확인

### 편집 시 흔한 실수

- ID 중복 — 다른 부서 ID 와 같은 prefix 사용 금지 (예: `qa-` 는 품질보증팀 전용)
- 영문 키워드 대문자 — 정규식 매칭은 대소문자 무관하지만 가독성 위해 `SPC`/`PPAP` 같은 약어는 대문자 표기 권장
- promptText 80자 초과 — 너무 길면 SSE body 가 길어지고 사용자 의도가 모호

---

## 8. 데이터 통계 (v3.3 기준)

| 본부 | 팀 수 | 질문 수 |
|---|---|---|
| 생산기술본부 | 8 | 48 |
| 생산본부 | 5 | 30 |
| 관리본부 | 4 | 24 |
| 재경본부 | 4 | 24 |
| 개발본부 | 3 | 18 |
| 구매본부 | 3 | 18 |
| 기술연구소 | 2 | 12 |
| (독립) | 1 | 6 |
| **부서 소계** | **30** | **180** |
| _meta (공통+직급) | 5 | 19 |
| **총계** | **35 파일** | **199 질문** |
