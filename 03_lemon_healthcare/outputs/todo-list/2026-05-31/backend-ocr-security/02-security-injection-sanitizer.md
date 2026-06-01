# 02. 선언부 성분명 인젝션 sanitizer 우회 수정 (CRITICAL)

> 브랜치 성격: fix(security)
> 대응 커밋: `6e1b42c` (일부)
> 핵심 파일: `backend/Nutrition-backend/src/services/supplement_parser.py`, `tests/unit/services/test_supplement_parser_declaration.py`

---

## 1. 발견 경위

문서 01(원재료명 성분 추출) 구현 후, 독립 코드 리뷰 패스(작성/리뷰 분리 원칙)에서 **CRITICAL 1건**을 적발했다.

---

## 2. 취약점

신규 `_extract_ingredient_declaration_candidates()`가 만든 성분명 `display_name`이 **프롬프트 인젝션 / HTML / 제어문자 sanitizer를 우회**했다.

- `sanitize_ingredient_name`(인젝션 필터)은 `_sanitize_parser_result`에서만 실행됨
- 그런데 선언부 후보는 `_merge_ocr_pattern_fallbacks`에서 **그 이후에** 추가됨 → 필터를 거치지 않음
- 리뷰어 실측 재현: 다음이 후보에 그대로 살아남음
  - `IGNORE PREVIOUS INSTRUCTIONS` (영어 인젝션)
  - `이전 지시 무시` (한국어 인젝션)
  - `DROP TABLE users` (SQL 형태)
  - `<script>...` (HTML)
  - `비타\x00민C` (NUL 제어문자)
- 영향: 라벨 텍스트가 preview API와 2차 LLM hop(`supplement_explanation`)으로 흘러가므로 헬스 앱에서 차단 필수

---

## 3. 수정

`_extract_ingredient_declaration_candidates`에서 이름 정리 직후 sanitizer를 **부형제 검사·dedup보다 먼저** 적용:

```python
name_result = sanitize_ingredient_name(cleaned)
if not name_result.value:
    continue            # 인젝션/HTML/제어문자 차단 시 드롭
cleaned = name_result.value
```

- sanitizer 반환 필드는 기존 코드와 동일하게 `.value`(SanitizerResult 데이터클래스)
- `amount=None`/`unit=None` 유지
- 순서가 핵심: sanitize → 부형제 검사 → dedup (우회 경로 차단)

---

## 4. 검증 ✅

- 음성 테스트 추가: `test_drops_injection_and_html_keeps_legit_name`
  - `비타민C`는 통과 / `IGNORE`·`이전 지시`·`DROP TABLE`·`<script>`·NUL 전부 차단 / 모든 amount=None
- 전체 services 스위트 **163 passed**
- 배포된 컨테이너에서 런타임 프로브 = **BLOCKED**(비타민C 통과, 인젝션·젤라틴 차단)

---

## 5. 후속 (별도 칩)

리뷰어가 기존 `ocr_pattern_fallback` 경로도 유사 우회 여지가 있다고 칩으로 남겼으나, 재확인 결과 그 경로는 이미 **merge 단계 `_sanitize_ocr_pattern_candidates`**로 차단되고 있음을 확인(레이어드 sanitize). 잘못 추가했던 중복 수정은 제거하고 전용 테스트(8건)는 유지.
