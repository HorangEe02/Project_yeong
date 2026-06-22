# 43. OCR 3-tier fixture 평가 리포트 상세 설계 및 구현 플랜

작성일: 2026-05-15
범위: Google Vision, CLOVA OCR, PaddleOCR, Ollama vision assist의 fixture 기반 비교 리포트

## 1. 현재 상태 확인

현재 프로젝트에는 OCR provider와 factory 골격, 그리고 redacted fixture report runner가 들어와 있다. 다만 실제 정확도 우열을 말할 단계는 아니다.

| 영역 | 현재 구현 | 설계 판단 |
| --- | --- | --- |
| Google Vision | `google_vision_document` provider가 있고 `DOCUMENT_TEXT_DETECTION` REST 호출 형태를 사용한다. | primary OCR 후보로 유지하되 실제 성능 주장은 fixture report 이후에만 허용한다. |
| PaddleOCR | `paddleocr_local` adapter가 optional dependency와 lazy import 뒤에 있다. | local fallback 후보로 평가하되 기본값은 계속 off다. |
| CLOVA OCR | `clova_ocr` adapter가 external OCR gate, invoke URL, secret 뒤에 있다. | 한국어 OCR 후보지만 외부 전송 동의와 vendor/security review 전에는 기본 off다. |
| Ollama vision assist | `ollama_vision_assist`가 local vision assist와 structured schema validation을 담당한다. | OCR engine이 아니라 local fallback/verification 보조 채널로 평가한다. `confidence=None`을 성능 confidence로 해석하지 않는다. |
| Factory | `build_supplement_image_analysis_adapters()`가 설정 기반으로 primary/fallback/assist 조립을 담당한다. | fail-closed 기본값을 유지하고 fixture runner도 live provider 호출을 기본 실행하지 않는다. |
| 평가 스크립트 | `backend/scripts/evaluate_ocr_three_tier.py`가 JSONL manifest와 provider observations를 aggregate한다. | raw image와 raw OCR text를 저장하지 않는 redacted report runner로 확장한다. |
| Fixture 예시 | `data/supplement_images/manifests/fixtures/supplement_labels/manifest.example.jsonl`이 있다. | 실제 비교용 fixture는 공개 이미지 또는 명시 동의 샘플만 별도 수집한다. |
| Report template | `docs/Nutrition-docs/templates/ocr-three-tier-evaluation-report.md`가 있다. | review gate와 pass/fail 기준을 포함하도록 보강한다. |

핵심 결론:

- Google Vision, CLOVA, PaddleOCR, Ollama vision assist가 모두 코드상 후보로 존재하더라도 기본 동작은 fail-closed여야 한다.
- "Google Vision이 더 정확하다", "CLOVA가 한국어에서 우세하다", "PaddleOCR이 충분하다" 같은 문장은 fixture 평가 전에는 제품 문서나 팀 공유 자료에 쓰지 않는다.
- 다음 구현의 목적은 OCR provider를 운영에 켜는 것이 아니라, provider 우선순위를 결정할 수 있는 재현 가능한 evidence package를 만드는 것이다.

## 2. 공식 문서 확인 근거

이 설계는 2026-05-15 기준 아래 공식 문서를 확인한 뒤 작성했다. 공식 문서가 제공하지 않는 정확도, latency, 비용 효율, 한국어/영어 혼합 라벨 성능 수치는 임의로 만들지 않는다.

| 기술 | 공식 문서에서 확인한 사실 | 설계 반영 |
| --- | --- | --- |
| Google Cloud Vision OCR | Vision OCR은 `TEXT_DETECTION`과 `DOCUMENT_TEXT_DETECTION`을 제공하고, `DOCUMENT_TEXT_DETECTION`은 dense text/document 응답에 최적화되어 있다. URL: <https://cloud.google.com/vision/docs/ocr> | 영양제 라벨처럼 조밀한 텍스트는 `DOCUMENT_TEXT_DETECTION` 기준으로 평가한다. |
| Google `images:annotate` REST | OCR 요청은 `POST https://vision.googleapis.com/v1/images:annotate` 형태로 보낼 수 있다. URL: <https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate> | live observation collector는 이 REST 호출을 opt-in smoke/eval 경로에서만 사용한다. |
| NAVER Cloud CLOVA OCR | Text OCR 호출은 API Gateway Invoke URL과 `X-OCR-SECRET` header를 사용한다. URL: <https://guide.ncloud-docs.com/docs/en/clovaocr-example01> | CLOVA observation collector는 secret과 external OCR consent gate가 없으면 실행하지 않는다. |
| CLOVA request/response schema | 요청 body에는 `version`, `requestId`, `timestamp`, `images` 구조가 있고 response에는 `inferResult`가 있다. URL: <https://api-fin.ncloud-docs.com/docs/clova-ocr-template-api> | report observation에는 provider status와 error code를 별도 기록한다. |
| PaddleOCR 3.x | 공식 사용 예시는 `PaddleOCR()` pipeline과 `predict()` 호출을 제공한다. URL: <https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html> | local fallback collector는 installed dependency와 model cache가 준비된 환경에서만 실행한다. |
| Ollama vision | Ollama vision 모델은 message의 `images` 배열로 이미지 입력을 받으며 REST API는 base64 image data를 기대한다. URL: <https://docs.ollama.com/capabilities/vision> | Ollama assist는 local-only image assist로만 평가하고 외부 LLM으로 보내지 않는다. |
| Ollama structured outputs | Ollama는 `format`에 JSON 또는 JSON Schema를 넣는 structured output pattern과 Pydantic validation 예시를 제공한다. URL: <https://docs.ollama.com/capabilities/structured-outputs> | visible text extraction과 verification 결과는 schema validation 실패를 report error로 남긴다. |

### 확인 한계

공식 문서에서 이 프로젝트의 영양제 라벨 fixture에 대한 provider별 정확도 추천값을 찾을 수 없다. 따라서 pass/fail threshold는 외부 벤더 주장이나 기억이 아니라 팀이 수집한 fixture 결과와 review policy로 정해야 한다.

## 3. 브레인스토밍 결과

### 3.1 평가 방식

검토안:

1. CI에서 live Google/CLOVA/Paddle/Ollama를 모두 호출한다.
   - 장점: 실제 provider 호출 결과를 계속 볼 수 있다.
   - 단점: secret, 비용, 네트워크, model cache, 외부 전송 동의가 CI 안정성과 privacy gate를 깨뜨린다.
2. JSONL manifest에 redacted provider observations를 저장하고 report runner가 aggregate한다.
   - 장점: raw image/raw OCR text 없이 재현 가능한 비교 리포트를 만들 수 있다.
   - 단점: observation 생성 단계는 별도 opt-in runner가 필요하다.
3. raw OCR text를 fixture에 저장해서 parser regression을 직접 비교한다.
   - 장점: 디버깅이 쉽다.
   - 단점: 라벨 원문 전체 저장이 privacy policy와 충돌하고, 제품 문서에 원문이 유출될 수 있다.

결정: 2번을 채택한다. 기본 CI는 redacted manifest와 aggregate script만 검증하고, live provider 호출은 별도 opt-in command로 분리한다.

### 3.2 Provider role 분리

Provider를 단순 순위표로 비교하지 않는다. 역할이 다르기 때문이다.

| Role | Provider | 평가 질문 |
| --- | --- | --- |
| Tier 1 primary OCR | Google Vision `google_vision_document` | 조밀한 영양제 라벨에서 비어 있지 않은 OCR 후보와 structured parse 성공률이 충분한가? |
| Tier 2 local fallback OCR | PaddleOCR `paddleocr_local` | 외부 전송 없이 Google 실패/저신뢰 케이스를 보완하는가? |
| Tier 2 external fallback OCR | CLOVA OCR `clova_ocr` | 한국어/영어 혼합 라벨에서 추가 이득이 있고, external consent와 vendor review 비용을 정당화하는가? |
| Tier 3 local assist/verification | Ollama `ollama_vision_assist` | visible text 기반 보조 결과가 hallucination 없이 mismatch 검출이나 empty OCR fallback에 기여하는가? |

### 3.3 Fixture 단위

Fixture는 "이미지 한 장"이 아니라 평가 가능한 metadata bundle이다.

필수 metadata:

- `fixture_id`: 안정적인 ID
- `image_path` 또는 `artifact_ref`: repository 내부 synthetic/public sample 또는 승인된 외부 artifact 참조
- `image_sha256`: 이미지 무결성 확인용 hash
- `source_rights`: `public`, `team_consent`, `synthetic` 중 하나
- `language_mix`: `ko`, `en`, `ko_en`, `other`
- `label_density`: `low`, `medium`, `dense`
- `expected.ingredients[]`: 사용자/검수자가 확인한 성분명, 함량, 단위
- `allowed_providers[]`: 외부 전송 가능한 provider 목록
- `notes`: raw OCR text가 아닌 검수 메모

금지 metadata:

- raw image bytes
- full raw OCR text
- 사용자 식별자
- 제품 구매처, 처방, 질환 같은 평가 목적 밖의 민감 맥락

### 3.4 Observation 단위

Observation은 provider가 fixture를 처리한 결과의 redacted summary다.

권장 schema:

```json
{
  "provider": "google_vision_document",
  "tier_role": "primary_ocr",
  "status": "success",
  "latency_ms": 720,
  "text_non_empty": true,
  "confidence": 0.82,
  "parser_success": true,
  "parsed_ingredients": [
    {"name": "vitamin c", "amount": "500", "unit": "mg"}
  ],
  "error_code": null,
  "fallback_reason": null,
  "roi_used": false,
  "requires_user_confirmation": true
}
```

주의:

- `parsed_ingredients`는 parser가 만든 structured field만 허용한다. 원문 OCR 전체 텍스트를 넣지 않는다.
- Ollama의 `confidence`는 공식 confidence가 아니므로 `null`로 둔다.
- `status=success`여도 사용자 확인은 필요하다. OCR report는 자동 섭취 추천이나 복용량 변경 근거가 아니다.

## 4. 리포트 설계

### 4.1 현재 runner 기준 metric

`backend/scripts/evaluate_ocr_three_tier.py`가 이미 계산하는 metric:

- `fixture_count`
- `missing_image_count`
- `observation_count`
- provider별 `calls`
- provider별 `text_non_empty_rate`
- provider별 `parser_success_rate`
- provider별 `average_latency_ms`
- provider별 `ingredient_name_exact_rate`
- provider별 `errors`
- `raw_artifacts_stored=false`
- `raw_ocr_text_stored=false`

현재 한계:

- `ingredient_name_exact_rate`는 expected ingredient name 교집합 기반의 단순 recall에 가깝고 false positive precision을 설명하지 않는다.
- amount/unit match, Korean/English language mix, ROI crop delta, latency percentile이 없다.
- fixture 수가 적어도 report가 생성되므로, report 상단에 "통계적 결론 불가" 문구가 필요하다.

### 4.2 P1에서 보강할 metric

| Metric | 목적 | 최소 산출 조건 |
| --- | --- | --- |
| ingredient precision/recall/F1 | 누락과 과잉 추출을 분리 | expected/observed normalized ingredient set |
| amount_unit_exact_rate | 함량과 단위 OCR 품질 확인 | expected amount/unit 존재 |
| language_bucket_breakdown | 한국어/영어 혼합 라벨 차이 확인 | `language_mix` metadata |
| density_bucket_breakdown | dense label에서 provider 약점 확인 | `label_density` metadata |
| latency_p50/p95 | 평균 latency 왜곡 방지 | provider observation 5개 이상 |
| fallback_trigger_rate | fallback 정책의 실제 호출 빈도 확인 | `fallback_reason` metadata |
| roi_delta | YOLO crop이 primary OCR을 개선했는지 확인 | 같은 fixture의 original/crop observation pair |
| hallucination_flag_count | Ollama assist가 visible text 밖 추론을 했는지 확인 | reviewer flag 또는 blocked-output test |

### 4.3 Report section

Markdown report는 아래 순서로 생성한다.

1. 실행 정보: generated_at, manifest, fixture count, observation count, provider versions, environment tag
2. Safety status: raw image stored false, raw OCR text stored false, consent bucket 확인
3. Statistical status: fixture 수가 threshold 미만이면 "provider 우열 결론 불가" 표시
4. Provider metrics: provider별 calls, non-empty, parser success, ingredient F1, amount/unit, latency, errors
5. Segment metrics: language/density/ROI 여부별 breakdown
6. Failure cases: raw text 없이 fixture_id, provider, error_code, mismatch category만 표시
7. Decision gate: keep off, enable local fallback trial, external vendor review, collect more fixtures 중 하나
8. Reviewer checklist: privacy, consent, vendor, parser, user confirmation 검토 항목

### 4.4 Threshold policy 초안

정확도 수치는 fixture 실행 후 채운다. 구현 시점에는 아래 policy만 둔다.

| 조건 | 리포트 결론 |
| --- | --- |
| fixture < 30 | 통계적 결론 불가. runner와 redaction 검증만 인정 |
| provider observations missing | 해당 provider 비교 불가 |
| raw artifact flag true | report invalid |
| raw OCR text detected | report invalid |
| external provider consent missing | external provider observation invalid |
| Ollama hallucination flag present | assist 결과 자동 채택 금지 |

## 5. 구현 플랜

### Phase P1-OCR-R0. 현재 runner 경로와 문서 정합성 고정

목표: 문서, command, 테스트가 실제 경로를 가리키게 한다.

작업:

- `40-ocr-3-tier-expansion-design-plan.md`의 script 경로가 `backend/scripts/evaluate_ocr_three_tier.py`임을 확인한다.
- `docs/Nutrition-docs/templates/ocr-three-tier-evaluation-report.md`에 statistical status와 decision gate section을 추가한다.
- root docs index에서 이 문서를 찾을 수 있게 연결한다.

완료 기준:

- `rg "evaluate_ocr_three_tier" yeong-Lemon-Aid/docs` 결과가 실제 파일 경로와 맞다.
- Markdown trailing whitespace가 없다.

### Phase P1-OCR-R1. Manifest schema 강화

목표: fixture가 비교 가능한 최소 metadata를 갖도록 한다.

작업:

- manifest row validator에 `fixture_id`, `expected`, `source_rights`, `language_mix`, `label_density` 권장 field를 문서화한다.
- forbidden raw key 검사를 유지하고 recursive 검사를 테스트로 고정한다.
- sample manifest를 "example only, not benchmark"로 명확히 표시한다.

완료 기준:

- raw OCR text key가 nested object에 있어도 `ValueError`가 난다.
- fixture 수가 threshold 미만이면 report에 우열 결론 불가 문구가 나온다.

### Phase P1-OCR-R2. Observation schema와 metric 확장

목표: provider별 단순 평균을 의사결정 가능한 metric으로 확장한다.

작업:

- `tier_role`, `status`, `confidence`, `error_code`, `fallback_reason`, `roi_used`, `requires_user_confirmation` field를 observation schema로 정의한다.
- ingredient precision/recall/F1과 amount/unit exact match를 추가한다.
- latency는 average 외에 p50/p95를 추가한다.
- provider별 unsupported/missing observation을 report에 별도로 표시한다.

완료 기준:

- provider가 extra ingredient를 반환하면 precision 하락이 metric에 반영된다.
- amount/unit mismatch가 ingredient name match와 별도로 드러난다.

### Phase P1-OCR-R3. Opt-in live observation collector 분리

목표: CI 안정성을 깨지 않고 실제 provider output을 수집할 수 있게 한다.

작업:

- `scripts/collect_ocr_observations.py`를 별도 opt-in runner로 설계한다.
- Google/CLOVA는 secret과 consent flag가 없으면 즉시 skip한다.
- PaddleOCR은 dependency/model cache가 없으면 skip한다.
- Ollama는 local URL readiness가 없으면 skip한다.
- collector는 raw OCR text를 manifest에 쓰지 않고 parser output과 aggregate metadata만 append한다.

완료 기준:

- 기본 CI에서는 collector가 실행되지 않는다.
- opt-in 실행 결과는 redacted manifest 또는 별도 observation JSONL만 만든다.
- secret 값과 raw OCR text가 파일에 남지 않는다.

### Phase P1-OCR-R4. Report template과 review gate 보강

목표: report가 수치를 보여주는 표가 아니라 켜도 되는지 판단하는 gate가 되게 한다.

작업:

- template에 "No accuracy claim before fixture threshold" 문구를 추가한다.
- decision gate를 `keep_off`, `local_fallback_trial`, `external_vendor_review`, `collect_more_fixtures` 중 하나로 제한한다.
- failure case section은 raw text 없이 mismatch category만 보여준다.

완료 기준:

- fixture threshold 미달 report는 provider 우열을 자동 결론 내리지 않는다.
- external provider를 켜려면 consent/vendor/security checklist가 미완료로 표시된다.

### Phase P1-OCR-R5. CI 연결

목표: GitHub CI에서 redaction과 report runner 재현성을 검증한다.

작업:

- backend unit test에 report runner tests를 유지한다.
- CI는 synthetic/example manifest로만 실행한다.
- live OCR smoke는 `RUN_GOOGLE_VISION_SMOKE`, `RUN_CLOVA_OCR_SMOKE`, `RUN_PADDLEOCR_SMOKE`, `RUN_OLLAMA_VISION_SMOKE` 같은 opt-in gate 뒤에 둔다.

완료 기준:

- secret 없는 GitHub PR에서 report runner unit test가 통과한다.
- live provider 실패가 기본 PR gate를 깨지 않는다.

## 6. 실행 command 초안

현재 경로 기준:

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python scripts/evaluate_ocr_three_tier.py \
  --manifest ../data/supplement_images/manifests/fixtures/supplement_labels/manifest.example.jsonl \
  --output-dir /private/tmp/lemon-ocr-eval-smoke
```

테스트:

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m pytest Nutrition-backend/tests/unit/scripts/test_evaluate_ocr_three_tier.py -q --no-cov
```

리포트 산출물 권장 위치:

```text
yeong-Lemon-Aid/outputs/generated/ocr-eval/<YYYY-MM-DD>/
```

운영 전에는 generated report를 그대로 신뢰하지 않고, fixture source rights와 consent evidence를 같이 review해야 한다.

## 7. PR/commit 분리 계획

권장 commit 단위:

1. `docs(ocr): design fixture evaluation report gate`
   - Why: provider 우열을 주장하기 전에 redacted fixture report 기준을 팀이 공유해야 한다.
2. `test(ocr): harden redacted fixture report runner`
   - Why: raw OCR text나 raw image bytes가 평가 산출물에 섞이면 privacy gate가 깨진다.
3. `feat(ocr): add opt-in provider observation collector`
   - Why: 기본 CI는 안정적으로 유지하면서 실제 provider 비교 데이터를 수집해야 한다.
4. `ci(ocr): run fixture report smoke without external providers`
   - Why: GitHub PR에서 secret 없는 환경으로도 report runner 재현성을 확인해야 한다.

## 8. 이번 P1에서 완료로 볼 수 있는 상태

- 공식 문서와 현재 코드 기준으로 provider 역할이 분리되어 있다.
- 실제 정확도 주장을 금지하는 문구가 report와 팀 문서에 들어가 있다.
- redacted manifest와 report runner가 raw image/raw OCR text를 거부한다.
- fixture 수와 observation 수가 부족하면 report가 provider 우열을 결론 내지 않는다.
- 다음 구현자가 `backend/scripts/evaluate_ocr_three_tier.py`와 template을 어떤 순서로 보강해야 하는지 명확하다.
