# 여러 장으로 촬영한 "하나의 영양제"를 하나의 결과로 병합하기 — 설계·가이드라인

- 작성일: 2026-06-15
- 대상: 영양제 OCR/다중 이미지 분석 파이프라인 (backend `Nutrition-backend` + `mobile`)
- 상태: 설계 가이드 (구현 전, 권위 문서)
- 관련: `docs/ocr_baseline_reports/2026-06-12-ocr-field-match-design-and-team-guideline.md`

---

## 0. 한 줄 요약

> **현재는 "이미지별로 따로 OCR → 이미지별로 따로 LLM 파싱 → 마지막에 구조화된 결과끼리 합치는(late fusion)" 구조**라서, 원통형 영양제처럼 한 라벨이 여러 장에 쪼개져 찍히면 LLM이 라벨 전체를 한 번도 같이 보지 못한다. 그래서 4장 → 4개의 부분/오류 파싱이 만들어지고, 사후 병합으로는 끊긴 표를 복원할 수 없다.
>
> **해결의 핵심은 "병합 지점을 LLM 파싱 *이전*으로 옮기는 것"이다.** 같은 영양제로 찍은 N장의 **OCR 텍스트(또는 이미지 자체)를 먼저 하나로 합친 뒤, 단 1회의 LLM 파싱**으로 1개의 영양제 결과(영양제명 / 성분·함량 / 섭취방법 / 주의사항)를 만든다. 추가로 "한 영양제 묶음" 의도를 **백엔드까지 전달**해야 한다(현재는 모바일 안에서만 사용됨).

---

## 1. 문제 정의

영양제·보충제 패키지는 원통(병) 형태가 많아 한 장에 라벨 전체를 담을 수 없다. 사용자는 한 제품을 **여러 각도/여러 면으로 나눠 촬영**한다(예: ①전면 제품명, ②영양정보 표 왼쪽, ③영양정보 표 오른쪽, ④섭취방법·주의사항).

**원하는 동작**

- 4장을 올려도 **1개의 영양제 결과**가 나온다.
- 그 결과에 **영양제명 / 영양 성분 및 함량 / 섭취 방법 / 주의 사항**이 정확히 채워진다.
- 영문 성분명은 `한글 (English)` 형태로 병기된다. (예: `비타민 D (Vitamin D)`)

**현재 동작(문제)**

- 4장을 올리면 이미지별 독립 파싱 결과 4개가 만들어진다. 모바일에서 "한 영양제 묶음"을 골라도, 화면에서 1개 그룹으로 묶어 보여주려는 시도는 하지만 **병합된 내용 자체가 부실**하다(성분 누락, 제품명 충돌, 중복 성분, 섭취방법/주의사항 누락).

---

## 2. 현재 아키텍처 (코드 기준 사실관계)

### 2.1 모바일 → 백엔드 호출 흐름 (실제 사용 경로)

`mobile/lib/features/supplements/supplement_repository.dart`의 `analyzeSupplementImages()` (`:599`)는 **세션 기반 3-스텝**으로 동작한다.

1. `createSupplementAnalysisSession()` (`:628`) → `POST /supplements/analysis-sessions` → `analysis_group_id` 발급
2. 각 이미지마다 `uploadSupplementAnalysisSessionImage()` (`:636`) → `POST /supplements/analysis-sessions/{id}/images`
   - 전송 필드: `ocr_provider`, `image_role`, `client_request_id` — **여기에 "한 영양제 / 서로 다른 영양제" 플래그는 없음** (`:648-656`)
3. `finalizeSupplementAnalysisSession()` (`:667`) → `POST /supplements/analysis-sessions/{id}/finalize`

> 한 번에 N장을 보내는 일괄 라우트(`analyze_supplement_label_multi`, `supplements.py:1695`)도 존재하지만, 모바일은 위 **세션 기반 경로**를 쓴다. 두 경로 모두 동일한 병합 함수로 수렴한다.

### 2.2 백엔드 처리: 이미지별 독립 파싱 → 사후 병합

- **이미지 업로드 시마다** `analyze_supplement_image()`가 호출되어 그 이미지 하나에 대해 **독립적으로 OCR + LLM 파싱**을 수행하고, **분석 run 1건을 영속화**한다. (일괄 라우트의 루프가 그 증거: `supplements.py:1789-1843`, `for index, image in enumerate(images): result = await analyze_supplement_image(...)`)
- `finalize`는 **이미 파싱·저장된 run들을 다시 불러와** 미리보기로 변환한 뒤 병합한다. (`supplements.py:2001` → `previews = [supplement_analysis_run_to_preview(record) for record in analysis_runs]` → `_build_multi_image_response`)
  - 즉 **finalize 시점에는 각 이미지가 이미 "완성된 구조화 레코드"** 이고, 병합은 그 위에서만 일어난다 = **late fusion(사후 융합)**.

### 2.3 병합 로직 (late fusion 세부)

`_build_merged_multi_image_preview()` (`supplements.py:617`):

- `_has_preview_review_content()` (`:674`)로 "쓸만한" 미리보기만 추린다.
- 제품명: `_select_parsed_product()` (`:865`) — 여러 미리보기 중 **가장 풍부한 1개**를 통째로 채택(나머지 제품명은 버림).
- 성분: `_append_unique_ingredients()` (`:784`) — `(display_name, nutrient_code, amount, unit)` **정확 일치 키로 중복 제거**.
- 섭취방법: `_select_intake_method()` (`:846`) — 텍스트가 있는 **첫 번째** 미리보기 채택.
- 주의사항/기능성: 텍스트 정확 일치로 dedup (`:802`, `:825`).

### 2.4 LLM 파서 계약

- `OllamaSupplementParser.parse_supplement_ocr_text(self, ocr_text: str)` (`ollama.py:328`) — **단일 OCR 텍스트 문자열 1개 → 구조화 결과 1개**. 즉 파서는 "합쳐진 텍스트 1개"를 받으면 1개의 일관된 결과를 낼 능력이 이미 있다. 단지 **이미지별로 N번 호출**되고 있을 뿐이다.
- 계약(`ollama.py:31-43`)에 이미 다음이 명시됨: `parsed_product(product_name/manufacturer/serving_size/daily_servings)`, `ingredient_candidates`, **영문 라벨이면 `display_name`=한글 / `original_name`=영문**(불확실하면 동일하게 두고 `low_confidence_fields` 표시), "**성분이나 번역을 절대 지어내지 말 것**", 필수 섹션 = product_name / supplement_facts / intake_method / precautions.

### 2.5 모바일 렌더 분기

`analysis_result_screen.dart` `_supplementReviewGroups()` (`:523`):

- 미리보기가 2장 이상이고 (`:530`) `lastSupplementBatchIsSingleProduct == true`(기본값, `app_controller.dart:247`)이면, 백엔드의 `mergedPreview`가 내용이 있으면 **1개 그룹**으로, 없으면 폴백으로 묶음 시도. (`:533-548`)
- 즉 **"한 묶음" 의도는 모바일 안에서만 소비**되고 백엔드 병합 전략에는 영향을 주지 못한다(2.1 참고).

---

## 3. 근본 원인

| # | 원인 | 효과 |
|---|------|------|
| **A** | **융합 지점이 LLM 파싱 *이후***(late fusion of structured records) | LLM이 라벨 전체를 한 번도 같이 못 봄. 한 표가 2장에 쪼개지면 각 장에서 부분/오류 파싱 발생 → 사후 병합이 끊긴 표를 복원 불가 (이게 가장 큰 원인) |
| **B** | **"한 영양제 묶음" 플래그가 백엔드에 전달되지 않음** | 백엔드는 의도를 모른 채 항상 이미지별 파싱+사후병합. 단일 제품 전략을 선택할 수 없음 |
| **C** | **순진한 병합/중복제거 휴리스틱** | 제품명: "가장 풍부한 1개"만 채택→오답 채택·충돌 무시. 성분: 정확 일치 dedup→OCR 편차로 같은 성분 중복 또는 "이미지A의 이름 + 이미지B의 함량"이 영영 못 만남. 섭취방법: "첫 텍스트"만 채택 |
| **D** | **각 이미지가 별도 분석 run·감사·학습 아티팩트로 영속화** | run 4건 생성. 병합 실패 시 화면이 이미지별 그룹으로 폴백 → "4개 결과"가 그대로 노출 |

### 3.1 왜 이번 수정으로 해결이 안 됐나

이번 수정은 **모바일의 표시 단계**에서 "한 묶음이면 1개 그룹으로 보여주기"를 추가한 것이다(원인 D의 표면 증상 일부 완화). 하지만 **A·B·C(데이터를 만드는 단계)** 는 그대로다. 그래서:

- 화면은 1개 그룹으로 보일 수 있으나, **그 그룹 내용**(성분·함량·섭취방법)이 여전히 누락/중복/오답이다.
- 백엔드 `mergedPreview`가 부실하면 모바일이 이미지별 그룹으로 폴백해 다시 여러 개로 보인다.

> 결론: **표시 단계가 아니라 "결과를 생성하는 단계"를 고쳐야 한다.**

---

## 4. 해결 방안 (3안 비교)

### 방안 1 — OCR 텍스트 조기 융합 + 단일 LLM 파싱 ✅ **권장(주력)**

"한 영양제 묶음"일 때, **이미지별 OCR까지는 그대로** 하되(OCR은 본질적으로 이미지 단위), **그 OCR 텍스트들을 1개로 합친 뒤 LLM 파싱을 단 1회** 수행해 **1개의 영양제 결과**를 만든다.

- 파서 계약을 바꿀 필요 없음 — `parse_supplement_ocr_text(ocr_text)`는 이미 "합쳐진 텍스트 1개 → 결과 1개"를 지원(`ollama.py:328`).
- 텍스트 단위 중복 제거 로직이 **이미 코드에 존재**: `_merge_ocr_results` / `_line_dedup_key` / `_is_near_duplicate`(`supplement_image_analysis.py:1311/1350/1362`). 지금은 *한 이미지의 여러 영역/프로바이더* 합칠 때만 쓰지만, **이미지 간 합치기에 그대로 재사용** 가능.
- LLM이 라벨 전체 맥락을 한 번에 보므로 끊긴 표·이름/함량 매칭이 LLM의 추론으로 복원된다(원인 A 직접 해결).

### 방안 2 — 멀티이미지 멀티모달 단일 호출

N장의 **이미지 자체**를 멀티모달 비전 LLM에 한 번에 넣고 1개 구조화 결과를 요청(예: 하나의 메시지에 image 1..N + "이들은 같은 제품의 여러 면이다, 하나로 통합하라").

- 장점: OCR 깨짐/표 정렬 손실이 적고 시각 맥락(표 격자, 단위 위치) 활용. 양·언어 혼재 라벨에 강함.
- 단점/제약: 현재 정책상 앱 OCR은 **CLOVA-only**(PaddleOCR A100 학습 중)이고 Gemma는 파서/검증 용도. 멀티모달 경로는 비용·지연·인프라 부담이 큼. **2단계(중기) 옵션**으로 둔다.

### 방안 3 — 현행 late fusion 병합 품질 개선 (스톱갭)

방안 1 도입 전까지 사후 병합의 정확도를 끌어올린다: 정규화 후 dedup, 이름/함량 재결합, 제품명 다수결, 섭취방법 "가장 완전한 것" 선택 등(§6.3).

- 장점: 작은 변경, 빠른 적용.
- 단점: 원인 A(끊긴 표)는 근본 해결 불가. **방안 1의 보완재**로만 가치 있음.

### 비교표

| 기준 | 방안 1 (OCR 조기융합+단일파싱) | 방안 2 (멀티모달 단일호출) | 방안 3 (병합개선) |
|---|---|---|---|
| 끊긴 표 복원(원인 A) | ◎ | ◎ | △ |
| 구현 난이도 | 중 | 상 | 하 |
| 인프라/비용 | 낮음(기존 OCR·파서 재사용) | 높음 | 매우 낮음 |
| 현 정책(CLOVA-only) 적합 | ◎ | △(정책 변경 필요) | ◎ |
| LLM 호출 수 | **1회**(N→1, 지연·비용↓) | 1회 | 0 (사후) |
| 권장 | **즉시 채택** | 중기 옵션 | 1의 보완 |

> **권장 로드맵: 방안 1을 메인으로 구현하고, 방안 3의 정규화/재결합 휴리스틱을 "융합 후 후처리"로 같이 넣는다. 방안 2는 정확도가 더 필요할 때 중기 도입.**

---

## 5. 권장 설계 상세 (방안 1)

### 5.1 "한 영양제 묶음" 의도를 백엔드까지 전달 (원인 B 해결)

- **세션 생성 시 1회 전달**(권장): `POST /supplements/analysis-sessions`에 `merge_strategy` 폼 필드 추가
  - `merge_strategy = "single_product"`(기본) | `"distinct_products"`.
  - 세션 메타에 저장하고, 업로드된 이미지들의 `parsed_snapshot`/그룹 메타에 함께 기록.
- 모바일: `app_controller`의 `sameSupplementBatch`(`:653/:663`)를 `createSupplementAnalysisSession()` 호출 인자로 흘려보내고, `supplement_repository.dart:628`에서 폼 필드로 전송.
- 호환성: 필드 없으면 `single_product`로 간주(기존 동작과 안전하게 호환). `distinct_products`면 현행 이미지별 결과 유지.

### 5.2 융합 + 단일 파싱 파이프라인 (finalize에서 수행)

핵심 아이디어: **이미지 업로드 단계에서는 "원문 OCR 텍스트만" 확보하고, 무거운 LLM 파싱은 finalize에서 1회만** 한다. (이미지별 LLM 파싱을 N번 하던 것을 1번으로 축소 → 지연·비용도 감소)

```
[업로드 N회]  이미지i → OCR(i) → run(i) 저장 (raw OCR 라인 + image_role + group_id)
                                  ※ single_product 모드에서는 이미지별 LLM 파싱 생략 가능
[finalize 1회]
  if merge_strategy == single_product:
     1) run들을 image_role 순서로 정렬 (front → facts → facts2 → intake → precautions …)
     2) 각 run의 OCR 라인을 역할 마커와 함께 이어붙임:
          === [이미지 1 · 전면] ===
          <ocr lines>
          === [이미지 2 · 영양정보] ===
          <ocr lines>
          ...
     3) 라인 단위 근접중복 제거 (_line_dedup_key / _is_near_duplicate 재사용)
     4) parse_supplement_ocr_text(combined_text)  ← 단일 LLM 파싱 1회
     5) 결과를 "1개의 정규(canonical) 미리보기"로 만들고, evidence_spans는 어느 이미지에서 왔는지 추적 가능하게 image-scoped id 부여(_bounded_prefixed_id 재사용)
  else:  # distinct_products
     기존 이미지별 미리보기 유지
```

- 역할 마커를 넣는 이유: LLM이 "전면=제품명", "영양정보=성분표", "주의=precautions"를 더 잘 배치하도록 약한 힌트를 줌(환각 유발 금지, 어디까지나 라벨 OCR에 있는 내용만).
- `image_role`은 이미 업로드 시 받고 있으므로(`supplements.py:1490`, `_validate_multi_image_roles`) 정렬·마커에 활용.
- 영속화: 단일 정규 미리보기 1건을 그룹의 대표로 노출. 개별 run은 evidence/learning/감사 추적용으로 유지하되, **사용자에게 보이는 결과는 1개**.

### 5.3 LLM 프롬프트 보강 (단일 파싱용)

`parse_supplement_ocr_text`에 들어가는 시스템/계약 텍스트에 다음을 명시(이미 있는 계약 위에 추가):

1. "입력 텍스트는 **하나의 제품을 여러 장으로 촬영**한 것을 이어붙인 것이다. `=== [이미지 n · 역할] ===` 마커로 구분된다. **반드시 1개 제품으로 통합**하라."
2. 제품명: "여러 후보가 보이면 가장 신뢰도 높은 하나로 정한다. 마케팅 문구/용량 표기/성분명을 제품명으로 착각하지 말 것."
3. 성분·함량: "**같은 성분이 여러 이미지에 나오면 1개로 합치고**, 한 이미지에 성분명·다른 이미지에 함량이 나뉘어 있으면 **같은 성분으로 연결**하라. 단위(mg/㎎/g/mcg/μg/㎍/IU/%)는 정규화. **OCR에 없는 함량은 지어내지 말 것**(불명확 시 amount=null + low_confidence)."
4. 섭취방법/주의사항: "여러 이미지에 흩어진 문장을 의미 단위로 통합하되 중복 제거."
5. 영문→한글 병기: 기존 계약 유지(`display_name`=한글, `original_name`=영문, 불확실 시 동일+low_confidence). **번역 환각 금지.**

### 5.4 모바일 변경 최소화

- 백엔드가 `merge_strategy=single_product`에서 **이미 1개로 합친 `mergedPreview`** 를 주므로, `analysis_result_screen.dart`의 분기(`:533-548`)는 그대로 1개 그룹을 렌더하면 된다.
- 폴백(이미지별 그룹) 발생 빈도가 크게 줄어든다(병합 내용이 충실해지므로).
- `lastSupplementBatchIsSingleProduct`는 표시 폴백 판단용으로 유지하되, 1차 판단 근거는 백엔드 응답의 단일 미리보기.

---

## 6. 필드별 정확도 향상 가이드

### 6.1 영양제명 (product_name)

- 전면 이미지(`image_role=front/product`)의 OCR를 제품명 후보의 1순위로 가중.
- LLM에 "용량·수량·성분·인증마크·마케팅 카피를 제품명으로 채택 금지" 명시.
- 사후 보정(방안 3 병행 시): 후보가 충돌하면 **출현 빈도/길이/전면 출처 가중 다수결**. 단, 방안 1에서는 LLM이 통합하므로 보정은 안전망 수준.

### 6.2 영양 성분 및 함량 (ingredient_candidates) — 가장 중요

- **단위 정규화**: `mg/㎎/g/mcg/μg/ug/㎍/IU/%` → 표준 단위. (이미 `supplement_parser.py`에 보강 진행 중인 항목과 정합)
- **줄 분리(split-line) 패턴**: `Vitamin C`(한 줄) + `1,000 mg`(다음 줄)처럼 이름/함량이 줄바꿈으로 끊긴 경우 재결합. 조기 융합이면 LLM이 맥락으로 연결, 사후면 deterministic fallback이 처리.
- **교차 이미지 재결합**: 이미지A에 성분명만, 이미지B에 함량만 있는 경우 → 단일 파싱이면 자연 해결. late fusion이면 "이름만/함량만" 후보를 따로 모아 매칭 시도.
- **중복 제거 강화(정확 일치 → 정규화 일치)**: 키를 `(normalize(display_name), nutrient_code, normalize(amount,unit))`로. `normalize`는 소문자화·공백/괄호 정리·단위 표준화. (`_append_unique_ingredients`의 현행 정확 일치 키 개선)
- **노이즈 제외**: `Serving Size`, 포장 수량("60정"), 복용량 안내, 인증마크, 영양성분기준치(% Daily Value) 헤더 등을 성분으로 오검출하지 않도록 필터. (현재 보강 중인 필터와 정합)

### 6.3 섭취 방법 (intake_method)

- "첫 텍스트 채택"(`_select_intake_method:846`) → **"가장 완전한(긴/문장형) intake 텍스트 채택"** 으로 변경. 또는 여러 이미지의 intake 문장을 의미 단위로 통합.
- `image_role=intake_method`인 이미지의 출처를 가중.

### 6.4 주의 사항 (precautions)

- 정확 일치 dedup → 정규화 후 dedup. 알레르기/상호작용/보관/임부수유 등 항목을 누락 없이 모으되 의미 중복만 제거.
- 의료법 표현 가이드 준수(과장·치료 보장 표현 금지) — 표시 단계에서 면책 고지 유지.

### 6.5 영문 성분명 한글 병기 (`한글 (English)`)

- 백엔드 계약 유지(`display_name`=한글, `original_name`=영문). 모바일은 `display_name`이 이미 `한글 (English)` 형태면 `원문:` 중복 라인 숨김(이번 수정 유지).
- 한글 변환 사전(자주 나오는 성분 화이트리스트)을 두면 LLM 불확실성을 줄일 수 있음(예: Vitamin C→비타민 C, Zinc→아연, Magnesium→마그네슘…). 사전에 없거나 모호하면 원문 유지 + low_confidence.

---

## 7. 단계별 구현 계획

| 단계 | 내용 | 위험도 |
|---|---|---|
| **P0** | `merge_strategy`(single/distinct) 플래그를 세션 생성 API + 모바일에 추가, 백엔드 그룹 메타에 저장. 기본 single. | 낮음 |
| **P1** | finalize에서 `single_product`일 때 **OCR 텍스트 조기 융합 + 단일 파싱** 경로 구현(§5.2). 라인 dedup은 기존 함수 재사용. | 중 |
| **P2** | 단일 파싱 프롬프트 보강(§5.3) + 단위/노이즈/재결합 후처리(§6.2). | 중 |
| **P3** | 업로드 단계의 이미지별 LLM 파싱을 single 모드에서 생략(지연·비용↓). distinct 모드는 현행 유지. | 중 |
| **P4** | (선택) 멀티모달 단일 호출(방안 2) 실험 — 정확도 추가 필요 시. | 상 |

> P0→P1→P2까지만 해도 "4개로 나오는" 문제와 "성분 누락"의 핵심이 해소된다. P3는 성능 최적화, P4는 정확도 상향 옵션.

---

## 8. 테스트·검증 계획

- **단위(백엔드)**
  - OCR 텍스트 융합: 역할 마커 삽입, 라인 근접중복 제거, 빈/공백 라인 처리.
  - 단일 파싱 결과: 끊긴 표(이미지2=이름들, 이미지3=함량들)에서 이름↔함량 정확 결합.
  - 성분 정규화 dedup: `Vitamin C 1000mg` vs `Vitamin C  1,000 ㎎` → 1건.
  - 노이즈 필터: `Serving Size`, 수량, %DV 헤더 제외.
  - `merge_strategy=distinct`면 기존 이미지별 결과 유지(회귀 방지).
- **단위(모바일)**
  - single이면 1개 그룹, distinct면 N그룹.
  - `한글 (English)` 표시 및 `원문:` 중복 숨김.
- **통합/수동**
  - 실제 원통형 영양제 3~5종을 4장씩 촬영해 1개 결과로 합쳐지는지, 4개 필드가 채워지는지 확인.
- **품질 지표(권장)**: 성분 recall(라벨 대비 추출률), 함량 정확도, 제품명 정확도, "결과 개수=1" 비율을 회귀 지표로 추적(`docs/ocr_baseline_reports`의 평가 포맷 활용).

---

## 9. 리스크·주의사항

- **개인정보/RLS**: 원문 이미지·원문 OCR 텍스트는 **영속 저장 금지** 원칙 유지(`raw_image_stored=False`, `raw_ocr_text_stored=False` 감사 메타와 정합). 융합 텍스트는 파싱을 위한 일시 메모리에서만 사용.
- **동의(consent)**: 단일 파싱 경로도 외부 OCR/이미지 처리 동의 게이트를 그대로 통과해야 함(`require_user_consent`).
- **트랜잭션/RLS**: finalize 라우트는 RLS 컨텍스트 세션 사용(`get_rls_context_session`, `supplements.py:1933`). 단일 파싱·영속화도 같은 라우트-소유 트랜잭션 규칙을 따른다.
- **멱등성(idempotency)**: 업로드 `client_request_id` 규칙 유지. finalize 재호출 시 동일 그룹은 동일 결과를 재구성해야 함(현행 finalize가 persisted run에서 재구성하는 성질과 정합).
- **학습 아티팩트/임베딩**: single 모드에서 이미지별 파싱을 생략하면 이미지별 learning_artifacts 흐름이 달라질 수 있음 → 그룹 단위 아티팩트로 재정의 필요(별도 검토).
- **지연(latency)**: 업로드 N번 + LLM 1번 구조는 현재(LLM N번)보다 빠를 가능성이 큼. 단, finalize 한 번에 부하가 몰리므로 finalize 타임아웃·진행 표시 점검.
- **호환성**: `merge_strategy` 미전송 클라이언트는 single로 안전 폴백.

---

## 10. 핵심 정리 (의사결정용)

1. **문제는 표시가 아니라 생성 단계.** late fusion(파싱 후 병합) → **early fusion(OCR 합친 뒤 단일 파싱)** 으로 전환.
2. **"한 영양제 묶음" 플래그를 백엔드까지 전달**(현재 모바일 전용).
3. 기존 자산 재사용: 파서는 단일 텍스트 파싱 지원(`ollama.py:328`), 라인 dedup 함수 존재(`supplement_image_analysis.py:1311`), 역할 라벨 존재(`image_roles`).
4. 4개 필드(제품명/성분·함량/섭취/주의)는 단일 파싱 + 정규화·재결합·노이즈필터로 정확도 확보.
5. 단계: P0(플래그)→P1(융합·단일파싱)→P2(프롬프트·후처리)→P3(성능)→P4(멀티모달, 선택).

---

## 참고자료 (웹 리서치)

- Justia/USPTO, *Optical character recognition system using multiple images and method of use* (US9465774) — 다중 이미지 OCR의 early/late/hybrid fusion 정의. https://patents.justia.com/patent/9465774
- Justia, *Merging optical character recognized text from frames of image data* (US9659224) — 다중 프레임 OCR 텍스트의 문서 단위 융합. https://patents.justia.com/patent/9659224
- GeeksforGeeks, *Early Fusion vs. Late Fusion in Multimodal Data Processing*. https://www.geeksforgeeks.org/deep-learning/early-fusion-vs-late-fusion-in-multimodal-data-processing/
- MDPI *J. Imaging* (2025), *Extract Nutritional Information from Bilingual Food Labels Using Large Language Models* — 한/영 혼재 라벨에서 LLM 기반 영양정보 추출(본 과제의 `한글 (English)` 요구와 직접 연관). https://www.mdpi.com/2313-433X/11/8/271 (PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC12387780/)
- Roboflow Blog, *Extract Nutrition Data from Food Labels with Computer Vision* — 성분/영양표 사진을 함께 처리해 구조화. https://blog.roboflow.com/read-food-labels-computer-vision/
- nyris, *OCR and LLM: The AI Power Duo* — OCR→LLM 후처리로 필드 구조화·오류 보정. https://www.nyris.io/blog-posts/ocr-and-llm-the-ai-power-duo
- Anthropic Cookbook, *Using vision with tools* — 멀티이미지 입력 + 구조화 출력(방안 2 참고). https://platform.claude.com/cookbook/tool-use-vision-with-tools
