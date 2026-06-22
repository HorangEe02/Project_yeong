# 설계 대비 구현 평가 — YOLO26 ROI → PaddleOCR → Gemma(Vision QA) → Gemma(Text RAG 권고+면책)

작성: 2026-06-07. 방법: 5개 컴포넌트를 병렬 감사(파일:라인 증거 기반), 런타임 경로/오프라인/스캐폴딩/부재 구분.

## 0. 종합 결론

**"빌드는 거의 완성, 그러나 설계된 end-to-end AI 흐름은 기본값에서 대부분 비활성/분리 상태."**
인프라·안전게이트·스키마는 인상적으로 갖춰졌지만, 설계의 핵심 자동 파이프라인(이미지→ROI→OCR→Vision QA→RAG 권고)은 **기본 배포에서 한 번에 돌지 않는다**. 실질적으로 살아있는 AI 단계는 **PaddleOCR(OCR)** 하나뿐이고, 권고+면책은 살아있으나 **기본값은 결정론(LLM/RAG는 opt-in)**, Vision QA·YOLO는 **코드만 있고 기본 OFF**다.

**종합 구현 성숙도 ≈ 60–65%** (컴포넌트 단순평균 68, e2e 분리·YOLO 미학습 가중 반영).

| # | 컴포넌트 | 설계 역할 | 상태 | 점수 | 라이브 경로? |
|---|---|---|---|---|---|
| 1 | **PaddleOCR** | 메인 OCR | ✅ fully | **90** | 예 (기본 primary, ON) |
| 2 | **Gemma TEXT + RAG 권고/면책** | 권고·경고 + 면책 | ✅ fully | **88** | 예 (단 LLM/벡터RAG opt-in) |
| 3 | **Gemma VISION QA** | 이미지vs텍스트 비교·재전사 | 🟡 mostly | **72** | 예이나 **기본 OFF + 프로드 차단** |
| 4 | **YOLO26 ROI** | 영역 bbox→OCR 보조 | 🟠 partial | **52** | 예이나 **기본 OFF + 가중치 없음** |
| 5 | **E2E 통합** | 한 흐름으로 연결 | 🟠 partial | **38** | **두 요청으로 분리** |

---

## 1. PaddleOCR (메인 OCR) — 90 / fully_implemented ✅

설계와 가장 잘 일치. **기본 primary OCR**이고 실제 서빙 경로에 살아있음.
- `config.py:436-438` `ocr_primary_provider` 기본 `'paddleocr'`, `enable_local_ocr=True`(`:536-542`), 프로드 가드(`:953-954`).
- 실동작 어댑터 `PaddleOCRAdapter`(`src/ocr/providers/paddle.py:58-125,434-468`): paddleocr lazy-load→predict→`rec_texts/scores/polys`→reading-order `OCRResult`. 팩토리 라우팅(`factory.py:71-81,187-203`), CLOVA/Google는 대안, PaddleOCR는 fallback로도 추가(`:206-224`).
- 엔드포인트 `POST /api/v1/supplements/analyze`(`supplements.py:1046`)→`analyze_supplement_image`→`ocr_adapter.extract_text`(`supplement_image_analysis.py:976`). 모델 가중치 캐시 존재(`~/.paddlex/official_models`).

**갭:** ① 95% 정확도 지표(`src/ocr/metrics.py`)가 **런타임 게이트로 연결돼 있지 않음**(평가 인프라일 뿐). ② src에 커밋된 검증 수치 없음(정확도는 오프라인 스크립트). ③ pyproject 핀(`paddlepaddle==3.2.0`) vs 설치본(3.3.1) 드리프트. ④ 클린 컨테이너 첫 실행 시 모델 캐시 provisioning 의존.

---

## 2. Gemma TEXT + RAG 권고/면책 — 88 / fully_implemented ✅

- **RAG 2종**: 렉시컬 마크다운 스캐너 + **pgvector**(`llm_wiki_retrieval.py:154-216,434-451`, cosine `<=>` HNSW, entity 부스팅).
- **Ollama Gemma TEXT** 라이브(`ollama.py:244-274` 실제 httpx `/api/chat`), `_explain_with_local_ollama`(`supplement_explanation.py:312-395`), 모델 `gemma4:e4b`(`config.py:395`), local-only 강제(`ollama.py:435-455`).
- **권고/경고**: 결정론 위험분류 `classify_personalized_supplement_risks`(`personalized_nutrition_risk.py:163-228`)가 REVIEW_NEEDED/AVOID_DUPLICATE/DISCUSS_WITH_PROFESSIONAL + 상한초과/중복 경고 산출 → LLM이 WIKI 인용 근거로 한국어 재서술.
- **사용자정보+DB**: 최신 분석 + UserProfile + (동의게이트) BodyProfile/Medical context 주입.
- **면책 항상 출력**: `SUPPLEMENT_IMPACT_DISCLAIMER`(`supplement_recommendation.py:24-27`)가 모든 응답 `clinical_disclaimer`(required, min_length≥1)로 강제, 모바일 렌더(`supplement_flow_screen.dart:2912`).
- **안전장치**: FORBIDDEN_TERMS('진단/치료/처방/복용량 변경') 검사→위반 시 422, 시스템 프롬프트가 진단/처방 금지, 실패 시 결정론 fallback.

**갭(중요):** ① **면책 문구가 설계의 '진단 아님 / 의사 상담' 직접 문장보다 약함** — 고정 disclaimer는 "참고용, 건강상태 확정 아님" 톤이고, '전문가 상담' 표현은 per-insight 액션 메시지(`personalized_nutrition_risk.py:217`)에 흩어져 있음. ② **벡터 RAG 기본 OFF**(`enable_wiki_vector_rag=False`, `config.py:413`)—기본은 렉시컬만. ③ **LLM 재서술 opt-in**(`use_local_llm` 기본 False)—기본 API는 결정론+인용 fallback만(모바일은 true 전달). ④ 의약품-보충제 상호작용은 카테고리 겹침 휴리스틱 수준.

---

## 3. Gemma VISION QA — 72 / mostly_implemented 🟡

설계대로 **진짜 멀티모달**(이미지 바이트 전송)로 구현됐으나 **기본 비활성 + 프로덕션 차단**.
- 실제 비전 호출: `ollama_vision.py:382-400` 이미지(또는 YOLO ROI crop) base64→`messages[].images`→`/api/chat`(`ollama.py:244-274`).
- **OCR vs 이미지 비교·점수화**: `verify_text`(`ollama_vision.py:205-238`)→`verification_status(match/partial/mismatch/uncertain)+confidence+matched/missing fragments+missing_critical_sections`.
- **비전 재전사 fallback**: `extract_text`(`:172-203`)가 OCR 비었/저신뢰 시 대체(`supplement_image_analysis.py:1161-1213`). 모델 `gemma4:e4b`(`config.py:396`). 순서대로 오케스트레이션(`:271,280,289,298`), 불일치 시 사용자 경고코드.

**갭:** ① **기본 OFF**(`enable_multimodal_llm=False`, `multimodal_ocr_assist_policy='disabled'`, `enable_multimodal_verification=False`, `sample_rate=0.0`) + **프로덕션은 docs/17 §9 게이트#1 사인오프 없이는 raise**(`config.py:933-938`). ② **진짜 교정 LOOP 아님** — verify는 사용자 경고코드만 내고, 교정 텍스트를 파서에 **재투입(re-parse)하지 않음**. fallback extract와 verify가 분리. ③ 실서버(Ollama+Gemma) 통합 테스트 없음(모두 Fake client) → 한국어 라벨 QA 실효성 미검증.

---

## 4. YOLO26 ROI (보조) — 52 / partial 🟠

런타임 코드와 분류체계는 갖춰졌으나 **기본 OFF + 학습된 가중치 부재 + 'v26'는 사실상 문자열 태그**.
- 런타임 추론 코드 존재: `vision/ultralytics_runner.py:91,137-140` `ultralytics.YOLO` lazy-load→`model.predict`→bbox 정규화. **클래스 계약 강제**(`:274-296` 보충제 섹션 클래스 없으면 거부).
- **4개 섹션 라벨 모두 정의**: `vision/taxonomy.py:27-30` `ingredient_amounts/intake_method/precautions/allergen_warning`(+추가) + alias 맵.
- **bbox→crop→OCR 핸드오프 코드 존재**: `_prepare_primary_ocr_image_input`→`crop_image_to_bounding_box`(`vision/preprocessing.py:78,109`), policy `crop_before_primary` 시.
- 기본 모델 태그 `vision_classifier_model='yolo26n.pt'`(`config.py:513`). 오프라인 데이터셋/게이트 스크립트 다수(materialize/validate/gate_supplement_section_yolo_dataset).

**갭(치명적):** ① **학습 가중치 0개** — repo에 `.pt/.onnx` 없음. `yolo26n.pt`는 문자열일 뿐, 런타임에 generic COCO 체크포인트를 받으면 클래스 계약 불일치→`VisionError`→`return ()` (사실상 ROI 0). ② **기본 OFF**(`enable_vision_classifier=False`, policy `disabled`). ③ **'YOLO26 특정' 근거 빈약** — 의존성 핀은 generic `ultralytics>=8.1`(v8세대), v26 전용 코드 경로 없음, 'yolo26'은 태그/게이트 스크립트 네이밍에만. ④ **커스텀 섹션 검출기 미학습**(게이트가 학습을 계속 BLOCK). ⑤ ultralytics는 게이트-락 optional extra(기본 미설치)→ import 시 raise. ⑥ 모바일 온디바이스 YOLO 없음. ⑦ 멀티-섹션 반복 crop→OCR은 부분(주 경로는 단일 region만 crop).

---

## 5. E2E 통합 — 38 / partial 🟠

설계의 "한 사용자 흐름"이 **두 개의 분리된 요청**으로 구현됨.
- **흐름 A**: `POST /supplements/analyze`→OCR/parse **프리뷰만** 반환(`supplements.py:1046,1276`).
- **흐름 B**(별도 사용자 액션): `GET /recommendations/latest`, `POST /recommendations/explain`(`:2688,2762`).
- **A는 B를 호출하지 않음** — analyze 응답에 권고 없음. 단계 연결이 **사용자 매개(확인/등록)** 이며 자동 파이프라인 아님.
- 기본값에서 YOLO·Vision QA OFF, 권고는 결정론(LLM/RAG opt-in) → "이미지→…→권고" 데이터가 한 자동 흐름으로 흐르지 않음.

---

## 6. 설계 vs 현실 — 명시적 불일치

1. **YOLO26**: 이름만 v26(태그/스크립트). 의존성은 v8세대, **학습 가중치 없음**, 기본 OFF → 현재 섹션 검출 **사실상 미작동**. (설계 의도 대비 가장 큰 갭)
2. **PaddleOCR = 메인 OCR**: ✅ 사실이고 가장 잘 구현. (정확도 95% '검증'만 런타임 밖)
3. **Gemma Vision 비교+재전사 루프**: verify/fallback은 있으나 **닫힌 교정 루프 아님** + 기본 OFF/프로드 차단.
4. **Gemma Text RAG 권고+면책**: 면책 **항상 출력**(강점) + 안전 가드 강함. 단 기본은 결정론(LLM/벡터RAG opt-in), 면책 문구가 '의사 상담' 직접 문장은 아님.
5. **단일 E2E 흐름**: 미실현(2-요청 분리).

---

## 7. 우선순위 권고 (갭 해소)

1. **YOLO26 섹션 검출기 실제 학습 + 가중치 배치** (최우선): 오프라인 게이트 통과 → 커스텀 `.pt` 학습(A100) → repo/아티팩트 스토어에 배치 → `enable_vision_classifier=True` 기본화 검토. (현재 ROI는 코드만 있고 미작동)
2. **E2E 자동 체인 엔드포인트**: `analyze`가 (옵션) 권고까지 한 흐름으로 잇는 엔드포인트/오케스트레이터 추가, 또는 명시적 2-스텝임을 제품 사양으로 확정.
3. **Vision QA 닫힌 루프화**: `verify_text` 결과(불일치/누락 섹션)를 재전사→**파서 재투입**으로 연결(현재는 경고코드만). + 실 Ollama 통합 테스트.
4. **면책 문구 강화**: `clinical_disclaimer`에 '본 정보는 진단이 아니며 자세한 사항은 의사/약사와 상담' **직접 문장** 포함(설계 요구 정확 반영).
5. **기본 활성화 정책 정리**: 벡터 RAG/`use_local_llm`/멀티모달을 어떤 환경에서 켤지 정책화(현재 전부 기본 OFF라 "AI 흐름"이 기본 비활성).
6. **PaddleOCR 95% 게이트 운영화**: 오프라인 eval을 CI/런타임 readiness에 연결(이미 게이트 스크립트 존재).

> 참고: 평가는 정적 코드 증거 기반(라이브 Ollama/DB 미실행). 데이터 적재(임베딩 등)는 data/ 제외로 범위 밖.
