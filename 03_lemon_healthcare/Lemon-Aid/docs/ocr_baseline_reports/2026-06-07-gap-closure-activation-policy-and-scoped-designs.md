# 갭 해소 — 활성화 정책(#5) + 95% 게이트 CI(#6) + e2e/비전루프 스코프 설계(#2/#3)

작성: 2026-06-07. 평가 리포트(`2026-06-07-pipeline-implementation-evaluation.md`) 우선권고 #2/#3/#5/#6 대응. (#1=YOLO 별도 문서, #4=면책 코드 반영 완료.)

---

## #5 — 기본 OFF 플래그 활성화 정책 (closeable, 본 문서로 확정)

설계의 "AI 흐름"이 기본 비활성인 이유는 안전·비용·검증 게이트 때문. 환경별 권장 활성화:

| 플래그 (config.py) | dev/local | staging | prod | 선행 조건 |
|---|---|---|---|---|
| `ocr_primary_provider=paddleocr` | ✅ on | ✅ on | ✅ on | 모델 캐시 provisioning |
| `enable_local_ocr` | ✅ on | ✅ on | ✅ on | `.venv-paddle`/모델 |
| `enable_wiki_vector_rag` | 선택 | ✅ on | ✅ on | `wiki_chunk_embeddings` 적재 + pgvector |
| `llm_wiki_retrieval_mode=hybrid` | 선택 | ✅ | ✅ | 위와 동일(없으면 lexical fail-open) |
| `use_local_llm`(요청 파라미터) | 선택 | 선택 | 선택 | 로컬 Ollama 가동 |
| `enable_multimodal_llm` / `_verification` | 실험만 | gate#1 후 | **docs/17 §9 사인오프 후** | Ollama vision + 검증 |
| `enable_vision_classifier`(YOLO) + `ocr_roi_preprocessing_policy=crop_before_primary` | gate#2 후 | gate#2 후 | gate#2 후 | **학습된 섹션 검출 `.pt`**(YOLO 문서 참조) |

원칙: ① OCR(PaddleOCR)+면책+결정론 권고는 기본 ON. ② RAG/LLM 재서술은 데이터·서비스 준비된 env에서 ON. ③ 멀티모달·YOLO는 가중치/사인오프 게이트 통과 후 ON. 운영자는 env별 `.env`로 위 표를 적용.

---

## #6 — PaddleOCR 95% 텍스트추출 게이트 = 오프라인/CI 게이트 (closeable)

readiness(`src/readiness.py`)는 **정적·고속 구성 요약**(provider/flag)이라 벤치마크 평가를 넣는 것은 부적절. 95% 게이트는 **오프라인 게이트로 이미 존재**(`gate_paddleocr_text_extraction_target.py`). 이를 CI/릴리스 체크로 형식화:

```bash
# CI 단계 (eval-summary가 생성된 뒤):
PYTHONPATH=Nutrition-backend ./.venv/bin/python scripts/gate_paddleocr_text_extraction_target.py \
  --eval-summary <holdout-eval-summary>.json --min-fixtures 30 \
  --output <gate>.json   # exit 0 = ≥95% 도달, 1 = 미달(릴리스 차단)
```
- eval-summary 생성 체인: `paddleocr_clova_eval.py`(.venv-paddle) → `merge_paddleocr_text_observations_into_benchmark` → `build_paddleocr_text_extraction_eval_summary --eval-split holdout`.
- 권장: GitHub Actions에 "paddleocr-accuracy-gate" job 추가(주간 또는 모델 갱신 시). readiness에는 **provider/flag 노출만** 유지(현행 OK).
- 현재 베이스라인은 95% 미달(리포트 참조) → fine-tune(스케일 데이터셋/A100) 후 게이트 통과 시 prod OCR 정확도 보증.

---

## #2 — E2E 단일 흐름 (스코프 설계, 제품 결정 필요)

현재: `POST /supplements/analyze`(OCR 프리뷰) ↔ `recommend/explain`(별도 요청). 분리는 **의도된 human-in-loop일 가능성**이 높음 — 헬스 앱에서 OCR 파싱 결과를 사용자가 **확인/수정 후** 권고를 받는 것이 안전(오인식 라벨로 잘못된 권고 방지). 따라서 "한 자동 흐름"이 항상 옳은 것은 아님.

권장(둘 중 제품 결정):
- (A, 권장) **현 2-스텝 유지** + 문서에 "analyze→사용자 확인→recommend"를 공식 UX로 명시. 자동 권고는 오인식 리스크.
- (B) **옵트인 단일 엔드포인트** `POST /supplements/analyze?with_recommendation=true`: analyze 후 사용자 프로필/동의가 충족되면 동일 트랜잭션에서 `build_supplement_impact_preview`까지 호출해 프리뷰+권고를 함께 반환. 미충족 시 프리뷰만. **기존 분리 경로는 보존**(비파괴). 구현 위치: `api/v1/supplements.py` analyze 핸들러 끝에서 옵션 분기 + 신규 응답 스키마. 동의/스코프 게이트 재사용. 단위/통합 테스트 필수.

→ 서빙 경로 변경이라 **제품 결정(A vs B) 후** 테스트와 함께 구현 권장(무검증 강행 금지).

---

## #3 — Vision-QA 닫힌 교정 루프 (스코프 설계, 라이브 검증 필요)

현재: `_verify_ocr_with_structured_multimodal`(supplement_image_analysis.py:1321-1352)가 불일치 시 **경고코드만**(`ocr_verification_mismatch`) 반환. 교정 텍스트를 파서에 재투입하지 않음(닫힌 루프 아님). 또한 기본 OFF + prod 사인오프 필요.

권장 설계(라이브 Ollama 검증 후 구현):
1. 오케스트레이션 순서 조정: OCR → (verify 또는 fallback) → **불일치/저커버리지 시 vision `extract_text` 재전사** → 재전사 텍스트로 `parse_supplement_analysis_ocr_text` **재실행** → 두 파스 결과 중 커버리지 높은 것 채택(+사용자에 "보정됨" 표시).
2. 무한 루프 방지: 재시도 1회 한정. 결정론 fallback 유지.
3. 검증: `_FakeHTTPClient` 기반 단위테스트로 (mismatch→재전사→재파스) 경로 + **실 Ollama+Gemma 통합 스모크**(현재 전무)로 한국어 라벨 QA 실효성 확인.

→ 서빙 경로 reorder + 라이브 모델 의존이라 **실 Ollama 검증 환경**에서 테스트와 함께 구현 권장. 기본 OFF이므로 prod 영향 없음(활성화는 #5 정책의 사인오프 게이트).

---

## 처리 요약 (우선권고 순)
- **#1 YOLO26**: 약지도 실증→부적합 확인, 실제 경로(주석+A100) 문서화. (GPU/주석 블로커)
- **#4 면책**: 코드 반영 완료 — "의사·약사 상담 + 의학적 판단 대신 안 함"(금칙어 회피), 17 테스트 통과.
- **#5 활성화 정책**: 본 문서 표로 확정.
- **#6 95% 게이트**: 오프라인/CI 게이트로 형식화(명령/잡 정의), readiness는 현행 유지.
- **#2 e2e / #3 vision-loop**: 서빙 경로 변경 — 제품 결정(#2 A/B) / 라이브 Ollama 검증(#3) 후 테스트 동반 구현하도록 구체 설계 제공(무검증 강행 회피).
