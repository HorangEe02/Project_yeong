# 01. 원재료명 성분 후보 추출 기능

> 브랜치 성격: feat(ocr)
> 대응 커밋: `6e1b42c` (일부)
> 핵심 파일: `backend/Nutrition-backend/src/services/supplement_parser.py`, `src/llm/ollama.py`, `src/models/schemas/supplement_parser.py`

---

## 1. 문제 (사용자 증상)

영양제 라벨에서 **원재료명(원재료명/원료명) 패널**을 촬영하면 분석 결과가 "성분 후보 0개 / 성분표가 보이지 않아요 / 추가 촬영 필요"로 나왔다.

기존 파이프라인은 성분 후보를 **영양정보(성분표, `supplement_facts`) 표에서만** 생성했다. `supplement_parser.py`가 의도적으로 "제품명·포장·섹션 헤더에서 성분을 추론하지 않는다"는 게이트를 두고 있어서, 함량 표가 없는 원재료명 나열은 후보가 0개였다.

---

## 2. 변경 내용

원재료명/원료명 선언부에서도 **성분명만** 후보로 생성하도록 추가했다.

- 신규 `_extract_ingredient_declaration_candidates()` + 헬퍼(`_split_ingredient_declaration`, `_clean_declaration_ingredient_name`, `_merge_declaration_candidates`)
- `_merge_ocr_pattern_fallbacks`에 배선: **함량 경로(facts/amount)를 먼저** 처리하고, 선언부 이름은 **새 이름만** 뒤에 추가
- 스키마: `SupplementParserIngredientCandidate.source`에 `"ingredient_declaration"` 추가(하위호환)
- Ollama 프롬프트(`ollama.py`): 원재료명에서도 성분명 추출 허용, 단 **함량은 facts 표에서만**

---

## 3. 안전 불변식 (헬스 앱 — 반드시 유지)

- 선언부 유래 후보는 **amount=None, unit=None** (함량 절대 위조 금지)
- 유일한 숫자 캡처: 라벨에 명시된 `<이름> NN.NN%` 형태의 % (스키마가 지원할 때만 `daily_value_percent`)
- 기존 부형제 denylist(`_is_excipient_name`/`_EXCIPIENT_NAME_KEYS`)로 젤라틴/글리세린/정제수/이산화규소 등 드롭
- facts-table 경로 동작 **100% 불변**(이름이 함량과 함께 있으면 함량 우선, 중복 미생성, NFC 정규화 dedup)

---

## 4. UI/게이트 영향

- **원재료명만 있는 이미지**: 성분명 후보 생성(함량 빈칸), `source="ingredient_declaration"`, "이름만 — 함량 수동 확인" 리뷰 신호. `missing_required_sections`가 `supplement_facts`로 하드블록하지 않음 → 불필요한 재촬영 요구 사라짐.
- **영양정보 표 이미지**: 종전대로 함량 포함 추출(불변).

---

## 5. 검증 ✅

- 단위테스트 `test_supplement_parser_declaration.py`(신규) + `test_supplement_parser.py`(2건 추가)
- 전체 services 스위트 통과(별도 문서 02의 sanitizer 수정 포함 최종 163 passed)
- black/ruff/py_compile 통과
