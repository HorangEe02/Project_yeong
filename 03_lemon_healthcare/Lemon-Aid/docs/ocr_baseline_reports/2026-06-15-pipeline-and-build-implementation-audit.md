# OCR 파이프라인 + 환경별 빌드 구현 감사 (2026-06-15)

대상 설계: **YOLO 영역검출 → OCR(1순위 CLOVA, 2순위 PaddleOCR) → Gemma 4 Vision 텍스트 변환**.
방법: 5개 차원 병렬 코드/config/컨테이너-env 감사(워크플로 `ocr-pipeline-and-build-audit`). 모든 판정은 file:line 증거 기반.

## 한 줄 결론
**설계는 코드에 전부 구현·배선·테스트되어 있으나, 현재 런타임은 설계의 "축소 부분집합"으로 동작한다** —
오늘 라이브 파이프라인은 사실상 **CLOVA OCR(전체 이미지) + Gemma 검증(요청의 ~20%)** 뿐이고, YOLO ROI·PaddleOCR·Gemma 텍스트추출(assist)은 모두 config로 꺼져 있다. 환경별 빌드는 **부분 구성**(릴리스 보안은 견고하나 환경별 URL/플레이버 배선·iOS·CI 빌드가 미완).

## 차원별 결과

| 차원 | 구현 | 설계일치 | 현재 활성 |
|---|---|---|---|
| YOLO 영역검출 | ✅ yes | ✅ yes | ❌ **no** |
| OCR CLOVA→Paddle | ✅ yes | ⚠️ partial | ⚠️ **partial** (CLOVA만) |
| Gemma 4 Vision | ✅ yes | ⚠️ partial | ⚠️ **partial** (검증만, 20%) |
| 모바일 빌드/환경 | ⚠️ partial | ⚠️ partial | ⚠️ partial |
| 백엔드/프론트/Docker/CI | ✅ yes | ⚠️ partial | ⚠️ partial |

### 1. YOLO 영역검출 — 구현 O, 활성 X
- 구현·배선 정상: `ocr/factory.py:_build_vision_adapter`(`YoloLabelDetector`/`UltralyticsYoloRunner`) → `supplement_image_analysis._detect_label_regions_if_enabled` → `_select_vision_region` → ROI를 primary OCR 입력으로. 모델 클래스 계약 강제(`_validate_model_class_contract`: 제너릭 COCO 모델 거부, COCO-거부 단위 테스트 존재).
- **현재 OFF**: 컨테이너 `ENABLE_VISION_CLASSIFIER=false`, `OCR_ROI_PREPROCESSING_POLICY=disabled` → vision adapter=None, ROI 미생성, **OCR는 항상 전체 이미지 처리**.
- **차단 요인 2개**: (a) **학습된 섹션 검출기 미배포**(default `yolo26n.pt`/컨테이너 `yolov8n.pt`=제너릭 → 계약 거부, 플래그 켜도 VisionError로 swallow), (b) 프로덕션 기동 검증이 `docs/17 §9 gate #2`(스폰서+의료법 리뷰) 사인오프 전엔 플래그/정책 활성화 하드 차단. 또한 ROI crop은 `OCR_ROI_PREPROCESSING_POLICY='crop_before_primary'`일 때만 실제 크롭(그 외엔 메타데이터만).

### 2. OCR 체인 CLOVA→Paddle — 구현 O, CLOVA만 활성
- 구현 정상: `build_supplement_ocr_adapter`(primary 디스패치), `_build_fallback_ocr_adapters`(약결과 시 **교체** fallback: Paddle→CLOVA 순), `_build_secondary_merge_ocr_adapter`(line-union **앙상블 병합**). 파이프라인 순서: primary→앙상블 병합→multimodal assist→fallback 체인→검증.
- **CLOVA primary는 활성**(`OCR_PRIMARY_PROVIDER=clova`, `ENABLE_CLOVA_OCR=true`, `ALLOW_EXTERNAL_OCR=true`) — 설계대로.
- **Paddle은 전 역할에서 OFF**: `ENABLE_LOCAL_OCR=false`(PaddleOCR 재학습 중, .env 주석) → fallback·앙상블 둘 다 미동작. 라이브 OCR 경로는 CLOVA primary 단독.
- ⚠️ **설계일치 partial 이유**: **코드 기본값이 설계와 반대**(`ocr_primary_provider='paddleocr'`, `enable_clova_ocr=false`) — CLOVA-primary는 오직 .env/컨테이너 env override로 성립. **docker-compose.yml 리터럴 기본값도 paddle/local-true/clova-false** → 컨테이너 런타임 env와 불일치(drift 위험: override 없이 recreate하면 Paddle primary로 뜸).

### 3. Gemma 4 Vision — 구현 O, 검증 역할만 활성(20%)
- 구현 정상: `OllamaVisionAssistAdapter`(모델 태그 `gemma4:e4b`), 2개 역할 — **assist(`extract_text`=이미지 텍스트 추출)** + **verify(`verify_text`=OCR 교차검증)**.
- **현재**: `ENABLE_MULTIMODAL_LLM=true`+`ENABLE_MULTIMODAL_VERIFICATION=true`지만 **`MULTIMODAL_OCR_ASSIST_POLICY=disabled`** → **텍스트 추출(변환) 역할 OFF**. 즉 **Gemma는 라이브에서 이미지 텍스트를 변환하지 않음** — 실제 이미지→텍스트 변환기는 **CLOVA**이고, Gemma는 CLOVA 출력의 **검증만**, 그것도 **요청의 ~20%**(`MULTIMODAL_VERIFICATION_SAMPLE_RATE=0.2`)에서만.
- ⚠️ **명명 주의**: "Gemma 4"는 사용자 로컬 Ollama 커스텀 태그(`gemma4:*`)이며 공식 Google 패밀리는 Gemma 3. 설계의 "Gemma 4 Vision"은 로컬 태그 기준.

### 4. 모바일(Flutter) 환경별 빌드 — 부분
- **활성 앱 = `mobile/`**(패키지 `lemon_aid_mobile`); `mobile/flutter_app/`는 **레거시/중복 참조 프로젝트**(android/ios 없음, AppConfig 상이, 빌드 미포함) = 데드웨이트.
- 환경 주입 = **컴파일타임 `--dart-define`**(LEMON_API_BASE_URL/TOKEN/CERT_PINS) + `kReleaseMode` fail-closed. **.env·플레이버 아님**.
- Android `environment` 플레이버 3종(dev/staging/prod) 존재하나 **applicationId/version suffix만 변경 — 백엔드 URL/보안과 분리**(플레이버↔환경 수동 페어링 필요). **iOS는 환경별 스킴 없음**(Debug/Profile/Release만, bundle id 여전히 `com.example` 플레이스홀더, Android 같은 release-id 가드 없음).
- ✅ **릴리스 보안은 견고·테스트됨**(HTTPS-only·cert pin 필수·토큰 미임베드·cleartext 차단·Android release-id/keystore 가드; flutter analyze 클린, app_config/release_security 테스트 통과).
- ❌ **환경별 URL 미배선**: staging/prod URL 커밋 없음, 기본은 로컬(8000 loopback)뿐 → 실 빌드는 operator가 올바른 dart-define 수동 전달 의존(문서화 미흡). key.properties 부재(릴리스 서명 미구성, gitignore — 정상이나 미활성).

### 5. 백엔드/프론트/Docker/CI — 부분
- 백엔드 Docker 이미지 완전 정의(python:3.13-slim, non-root, healthcheck, OCR/vision build ARG 게이트), 라이브 컨테이너 healthy.
- ✅ **APP_ENV 보안 게이트 견고**: `config.validate_runtime_security`가 production서 insecure DB 기본값·AUTH_MODE=disabled·debug 로깅·외부 LLM·wildcard/non-https origin·기본/짧은 privacy secret 거부 + 실험 사인오프 게이트 강제 off. RLS Stage-2 fail-fast 기동 가드. (현 런타임은 `ENVIRONMENT=development`라 게이트 비활성=정상.)
- ❌ **CI가 Docker 이미지·프론트를 빌드하지 않음**: GitHub Actions는 백엔드 lint(black/ruff)+unit, 모바일 analyze/test, 시크릿 스캔, 의존성 audit만. **Dockerfile 빌드·`next build`/`tsc`·통합테스트(main job)·alembic 검증 없음**. 프론트 빌드는 Vercel에서만(GitHub CI 밖).
- ⚠️ **APP_ENV 명칭 불일치**: root .env `APP_ENV="local"`이나 백엔드 config 키는 `ENVIRONMENT` → APP_ENV는 백엔드에 무효(operator 함정).

## 권고 (우선순위)
1. **운영 의도 명확화 + 기본값 정렬**: 코드/`docker-compose.yml` 기본값을 실제 운영 의도(CLOVA primary)에 맞추거나, env override를 단일 진실원으로 문서화 — recreate drift 방지.
2. **YOLO 활성화 선결조건**: 학습된 섹션 검출기 weight 배포(현 제너릭 모델은 계약 거부) + `docs/17 §9 gate #2` 사인오프 + `OCR_ROI_PREPROCESSING_POLICY='crop_before_primary'`. (메모리상 운영자 205 bbox + A100 학습이 이 선결.)
3. **Paddle 재합류**: 재학습 완료 후 `ENABLE_LOCAL_OCR=true`(+필요 시 `OCR_SECONDARY_MERGE_POLICY`) — fallback/앙상블 복귀.
4. **Gemma 텍스트추출 활성 여부 결정**: 설계가 "Gemma가 텍스트 변환"이면 `MULTIMODAL_OCR_ASSIST_POLICY` 활성 필요(현 disabled=검증만). 모델 태그 명명도 정리.
5. **모바일 환경 배선**: 플레이버↔환경 URL/보안 결합(per-flavor dart-define 기본값 or buildConfig), iOS 환경 스킴 + 실 bundle id, staging/prod URL·cert-pin 문서화, `flutter_app/` 레거시 제거 검토.
6. **CI 보강**: Docker 이미지 빌드 + `next build`/`tsc` + 통합테스트 + `alembic check` 잡 추가(현재 미커버, 이미 알려진 0045 image-vs-DB head 불일치도 CI가 못 잡음).

## 참고
- 이 세션의 one-shot 융합 검증도 이 라이브 파이프라인(CLOVA 단독·전체 이미지·Gemma 검증 20%) 위에서 돌았음 → 실 사진 OCR 노이즈의 일부 배경.
- 전체 증거: 워크플로 결과(5 차원, file:line). 라이브 env는 `docker exec lemon-aid-backend-1 env` 기준(컨테이너 ≠ docker-compose 리터럴).
