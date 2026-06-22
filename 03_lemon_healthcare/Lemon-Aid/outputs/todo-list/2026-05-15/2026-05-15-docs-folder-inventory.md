# yeong-Lemon-Aid docs 폴더별 Markdown 인벤토리

작성일: 2026-05-15  
대상 경로: `yeong-Lemon-Aid/docs`

## 1. 전체 확인 결과

| 구분 | 파일 수 | 성격 |
| --- | ---: | --- |
| `docs/` | 41 | 프로젝트 기획, 현재 상태, 후속 구현 플랜 |
| `docs/Nutrition-docs/dev-guides/` | 31 | 기능별 구현 가이드와 시연/운영/인수인계 가이드 |
| `docs/Nutrition-docs/previous-version/` | 15 | 과거 P1/PR 단위 설계안과 이전 예시 문서 |
| `docs/Nutrition-docs/templates/` | 1 | 반복 산출물 템플릿 |
| 전체 Markdown | 88 | 총 42,441 lines |

비 Markdown 파일도 확인했다. `docs/Nutrition-docs/pdf/`에는 01~10 문서 PDF와 `PR1_기능_상세_보고서.pdf`가 있고, `docs/Nutrition-docs/previous-version/`에는 일부 PDF/PPTX/HTML 산출물이 함께 있다. `docs/.DS_Store`와 `docs/Nutrition-docs/pdf/.omc/state/idle-notif-cooldown.json`은 macOS/도구 상태 파일이다.

## 2. `docs/` 루트 문서

### 2.1 기획과 기준선 문서

| 파일 | 내용 파악 | 분류 |
| --- | --- | --- |
| `01-project-overview.md` | 프로젝트 정체성, 입력 7종, 출력 5종, 회사 산출식, 범위, 일정, 성공 기준을 정의한다. | 최상위 개요 |
| `02-background-problem.md` | 헬스케어 AI 배경, 레몬헬스케어 맥락, 사용자/회사/산업 관점 문제 정의와 연구 질문을 정리한다. | 배경/문제정의 |
| `03-project-intent.md` | 프로젝트 의도, 서비스 지향점, 비의료 건강관리 방향, 발주처 협업 목적을 설명한다. | 제품 의도 |
| `04-market-research.md` | 시장, 경쟁 서비스, 사용자군, 포지셔닝, 차별화 요소를 조사한다. | 시장 조사 |
| `05-github-guidelines.md` | GitHub 협업 규칙, 브랜치/PR/커밋, CI, 폴더 구조 표준을 정의한다. 현재 `yeong-Lemon-Aid` 기준 구조와 데이터 폴더 표준이 반영되어 있다. | 협업/구조 표준 |
| `06-tech-stack.md` | 백엔드, 모바일, AI/OCR/LLM, DB, 보안, 배포 기술 스택을 정리한다. | 기술 스택 |
| `07-core-algorithm.md` | 활동점수, KDRIs, 체중 예측, 영양 분석 등 핵심 알고리즘을 가장 상세하게 설명한다. | 알고리즘 기준 |
| `08-implementation-plan.md` | 단계별 구현 계획, 일정, 책임 범위, MVP 진행 순서를 정리한다. | 구현 로드맵 |
| `09-data-catalog.md` | KDRIs, 식약처, 이미지/OCR, 사용자 입력 등 데이터 출처와 관리 방식을 정리한다. | 데이터 카탈로그 |
| `10-compliance-checklist.md` | 의료법/약사법 표현 제한, 개인정보, 동의, 보안, 운영 체크리스트를 정리한다. | 컴플라이언스 |
| `11-detailed-feature-implementation-plan.md` | 기능 단위 상세 구현 계획과 API/서비스/모바일 흐름을 연결한다. | 기능 상세 계획 |

### 2.2 보안, 로컬 LLM, 범위 통제 문서

| 파일 | 내용 파악 | 분류 |
| --- | --- | --- |
| `12-local-llm-ollama-migration.md` | 외부 LLM 대신 Ollama 로컬 LLM을 쓰는 방향, 보안/개인정보 이유, 전환 기준을 정리한다. | 로컬 LLM 전환 |
| `13-algorithm-literature-evidence.md` | 알고리즘 설계에 필요한 논문/근거와 공식 자료 연결을 정리한다. | 근거 문서 |
| `14-pre-implementation-scope-and-rules.md` | 구현 전 범위, 금지사항, feature flag, 운영 전제 조건을 정리한다. | 사전 범위 통제 |
| `15-regulated-feature-feasibility-and-compliance-plan.md` | 처방전/검사표 등 규제 민감 기능의 가능성과 컴플라이언스 조건을 검토한다. | 규제 기능 검토 |
| `16-implementation-settings-gap-review.md` | 문서와 실제 설정/feature flag 사이의 차이를 검토한다. | 설정 갭 리뷰 |
| `17-image-collection-consent-plan.md` | 이미지 수집 동의, 보관, 삭제, OCR/학습 사용 범위와 게이트를 정리한다. | 이미지 동의/수집 |
| `18-enhancement-brainstorm-notes.md` | 기존 전체 문서에 대한 갭 분석, 다관점 검토, 경쟁 매핑 브레인스토밍 모음이다. | 개선 아이디어 |

### 2.3 현재 상태와 P1 안정화 문서

| 파일 | 내용 파악 | 분류 |
| --- | --- | --- |
| `20-backend-file-structure-plan.md` | 백엔드 파일 구조 확장 원칙, 반영 구조, 구현 게이트를 짧게 정리한다. | 백엔드 구조 계획 |
| `21-backend-file-structure-guide.md` | 백엔드 디렉터리/모듈 책임, API/service/model/test 배치를 상세히 설명한다. | 백엔드 구조 가이드 |
| `22-current-implementation-status-map.md` | 현재 구현 상태를 코드/테스트/문서 관점으로 매핑한다. 현재 상태를 볼 때 우선 확인할 문서다. | 현재 상태 맵 |
| `23-p1-stabilization-plan.md` | P1 안정화를 위한 테스트, CI, 데이터, 보안, feature flag 작업 계획을 정리한다. | P1 안정화 |
| `24-postgresql-transition-plan.md` | SQLite/개발 DB에서 PostgreSQL 전환 가능성, SQLAlchemy 유지 전략, 검증 계획을 설명한다. | DB 전환 |

### 2.4 OCR, LLM, 이미지 분석 문서

| 파일 | 내용 파악 | 분류 |
| --- | --- | --- |
| `25-ocr-text-supplement-analysis-plan.md` | OCR 텍스트를 영양제 성분/함량/섭취 방법으로 분석하는 흐름을 계획한다. | OCR 텍스트 분석 |
| `26-ot-s2-ocr-provider-adapter-implementation-plan.md` | OCR provider adapter 구조, CLOVA/외부 provider 게이트, service 연결 계획을 정리한다. | OCR adapter 계획 |
| `27-ot-s2b-google-vision-ocr-review-plan.md` | Google Vision OCR 도입/검토 방향과 리뷰 기준을 정리한다. | Google Vision 검토 |
| `28-ollama-local-llm-connection-implementation-plan.md` | Ollama 로컬 LLM 연결 구현, health check, adapter, 오류 처리 계획을 정리한다. | Ollama 연결 |
| `30-multimodal-yolo-experiment-plan.md` | YOLO/멀티모달 이미지 실험, ROI detection, OCR 보조 가능성을 검토한다. | YOLO 실험 |
| `32-paddleocr-local-fallback-plan.md` | PaddleOCR를 로컬 OCR fallback으로 도입하는 비용/리스크/구현 계획을 정리한다. | PaddleOCR fallback |
| `33-three-tier-ocr-pipeline-implementation-guide.md` | Google Vision, YOLO ROI, Ollama/Paddle/CLOVA fallback을 묶는 3-tier OCR 파이프라인 가이드다. | 3-tier OCR |
| `35-google-vision-ocr-provider-implementation-plan.md` | Google Vision provider 구현 계획, API key 방식, 테스트, smoke gate를 정리한다. | Google Vision 구현 |
| `40-ocr-3-tier-expansion-design-plan.md` | 3-tier OCR 확장 상세 설계와 구현 반영 상태를 정리한다. 현재 fixture manifest 경로는 `data/supplement_images/manifests/fixtures/...` 기준이다. | OCR 확장 설계 |

### 2.5 모델, 학습, 규제 intake, 운영 플랜

| 파일 | 내용 파악 | 분류 |
| --- | --- | --- |
| `29-hall-lite-weight-prediction-implementation-plan.md` | Hall-lite 동적 체중 예측 모델 구현 계획, API 호환성, 검증 기준을 정리한다. | 체중 예측 |
| `31-backend-feature-specifications.md` | 백엔드 기능별 상세 스펙을 모아 둔 계획성 문서다. 실제 구현 여부는 코드/테스트와 대조가 필요하다. | 백엔드 기능 스펙 |
| `34-llm-serving-engines-multi-environment-setup-guide.md` | Ollama, MLX, vLLM 등 LLM serving engine을 환경별로 연결하는 설정 가이드다. | LLM serving |
| `36-post-p1-execution-plan.md` | P1 이후 CI, PR gate, OCR, 학습, regulated intake 우선순위를 정리한다. | Post-P1 실행계획 |
| `37-ci-hardening-design-plan.md` | CI path filter, backend/mobile/docs 검증, 데이터/설정 gate 강화를 설계한다. | CI 강화 |
| `38-stabilization-pr-gate-design-plan.md` | PR 안정화 게이트, 승인 조건, checklist와 sign-off 흐름을 설계한다. | PR gate |
| `39-commit-unit-splitting-design-plan.md` | 큰 변경을 Conventional Commits 단위로 나누는 staging/commit 전략을 설계한다. | 커밋 분리 |
| `41-learning-vector-db-implementation-design-plan.md` | 학습 벡터 DB, embedding, object storage, consent gate, retention을 설계한다. | 학습/vector DB |
| `42-prescription-lab-ocr-intake-design-plan.md` | 처방전/검사표 OCR intake, 사용자 확인, 직접 복용량 변경 안내 금지, DB/API 설계를 정리한다. | 규제 OCR intake |

루트 문서에는 `19-*.md`가 없다. 번호 체계상 의도적 결번인지 과거 문서 누락인지 별도 확인 가능하다.

## 3. `docs/Nutrition-docs/dev-guides/` 문서

`dev-guides`는 구현자가 바로 따라갈 수 있는 기능별 작업 지시서 성격이다. 일부 문서는 계획/예시 수준이고, 일부는 실제 구현과 연결된 현재 가이드다.

| 파일 | 내용 파악 | 분류 |
| --- | --- | --- |
| `00-setup-environment.md` | Python/Flutter/DB/Ollama 등 개발 환경 설정과 검증 명령을 안내한다. | 환경 설정 |
| `01-bmi-and-v1-algorithm.md` | BMI와 v1 활동점수 알고리즘 구현, 테스트, 검증 기준을 안내한다. | 알고리즘 |
| `02-v2-v3-v4-algorithms.md` | 활동점수 v2~v4 확장, 질환/심박/백분위 분기를 설명한다. | 알고리즘 |
| `03-bmr-tdee.md` | BMR/TDEE 계산, 활동계수, 대사량 산출 테스트를 안내한다. | 알고리즘 |
| `04-weight-prediction-7step.md` | 회사 7-step 체중 예측 흐름과 구현/테스트 기준을 설명한다. | 체중 예측 |
| `05-kdris-lookup.md` | KDRIs lookup, 데이터 스키마, 연령/성별/영양소 매칭을 안내한다. | KDRIs |
| `06-deficient-nutrient-diagnosis.md` | 부족 영양소 진단, 단위 변환, 상태 분류, 금지 표현 검증을 상세히 안내한다. | 영양 진단 |
| `07-ocr-pipeline.md` | 현행 OCR intake/API/provider 연결 상태를 요약한 짧은 가이드다. | OCR |
| `08-llm-supplement-parsing.md` | Ollama 기반 영양제 OCR 텍스트 파싱 구현 상태와 진입점을 요약한다. | LLM 파싱 |
| `09-supplement-registration-api.md` | 영양제 등록 API, matching, 사용자 확인 흐름을 요약한다. | 영양제 등록 |
| `10-mobile-flutter-setup.md` | Flutter 프로젝트 생성, 패키지, 환경 설정, 빌드 검증을 안내한다. | 모바일 |
| `11-mobile-camera-screen.md` | 카메라 화면, 이미지 촬영/업로드, 권한 처리 UI를 안내한다. | 모바일 |
| `12-mobile-healthkit-integration.md` | HealthKit/Health Connect 연동, 데이터 권한, sync 흐름을 안내한다. | 모바일/건강데이터 |
| `13-mobile-dashboard.md` | 모바일 대시보드 화면, 카드/차트/상태 표시 UI 구현을 안내한다. | 모바일 |
| `14-hall-dynamic-model.md` | Hall-lite 동적 체중 모델의 단위, 상수, baseline-preserving 설계를 정리한다. | 체중 모델 |
| `15-goal-based-analysis.md` | 건강 목적 기반 영양 분석과 목표별 메시지/우선순위를 안내한다. | 목적 분석 |
| `16-meal-recognition.md` | 음식 이미지 인식, 음식 분류, 영양 매핑 흐름을 안내한다. | 음식 분석 |
| `17-feedback-and-notifications.md` | 피드백 루프, 알림, 사용자 행동 유도 흐름을 안내한다. | 피드백/알림 |
| `18-mobile-deficient-screen.md` | 부족 영양소 결과 화면 UI 구현을 안내한다. | 모바일 UI |
| `19-mobile-goal-analysis-screen.md` | 목적별 분석 화면 UI 구현을 안내한다. | 모바일 UI |
| `20-mobile-meal-input-screen.md` | 식단 입력 화면, 사진/수동 입력, 결과 표시 UI를 안내한다. | 모바일 UI |
| `21-mobile-feedback-ui.md` | 피드백과 알림 UI, CTA, 상태 표현을 안내한다. | 모바일 UI |
| `22-demo-scenarios.md` | 페르소나 A/B 시연 흐름, 시연 데이터, 당일 체크리스트를 정리한다. | 시연 |
| `23-presentation-deck.md` | 발표자료 구성, 메시지 구조, 슬라이드 기획을 안내한다. | 발표 |
| `24-demo-day-rehearsal.md` | 데모 리허설, 시간표, 비상 대응, 최종 점검을 안내한다. | 시연 준비 |
| `25-handover-checklist.md` | 코드/문서/데이터/운영/지원 인수인계 checklist를 정리한다. | 인수인계 |
| `26-operations-manual.md` | 운영 매뉴얼, 배포/모니터링/일상 점검을 안내한다. | 운영 |
| `27-incident-runbook.md` | 장애 유형별 대응 절차, escalation, 복구 기준을 정리한다. | 장애 대응 |
| `28-retrospective.md` | 프로젝트 회고, 학습 내용, 개선점 기록 템플릿을 제공한다. | 회고 |
| `29-final-deliverables-index.md` | 최종 산출물 목록, 검증 체크리스트, 인계 패키지를 정리한다. | 최종 산출물 |
| `30-post-p1-execution-checklist.md` | P1 이후 실행 항목과 검증 명령을 체크리스트화한다. | Post-P1 체크리스트 |

## 4. `docs/Nutrition-docs/previous-version/` 문서

이 폴더는 현재 기준 문서라기보다 과거 PR/P1 단위 설계안과 예시 문서를 보관하는 archive 성격이다. 현재 구현 상태 판단에는 루트 문서와 실제 코드/테스트를 우선해야 한다.

| 파일 | 내용 파악 | 분류 |
| --- | --- | --- |
| `README.md` | previous-version 폴더의 용도를 짧게 설명한다. | 폴더 안내 |
| `17-api-paper-algorithm-rationale.md` | API와 알고리즘 근거를 논문/문헌 중심으로 정리한 이전 문서다. | 과거 근거 |
| `18-p1-0-api-security-contract.md` | P1 API 보안 계약, 인증/권한, contract 기준을 정리한 과거 설계안이다. | P1 보안 |
| `19-p1-1-db-alembic-extension.md` | DB/Alembic 확장 계획을 정리한 과거 설계안이다. | P1 DB |
| `20-p1-2-ocr-image-intake.md` | OCR 이미지 intake 설계를 정리한 과거 설계안이다. | P1 OCR intake |
| `21-p1-3-ollama-structured-parser.md` | Ollama 구조화 파서 설계를 정리한 과거 설계안이다. | P1 LLM parser |
| `22-p1-4-supplement-registration-matching.md` | 영양제 등록/matching 흐름을 정리한 과거 설계안이다. | P1 등록 |
| `23-p1-5-deficiency-dashboard-api.md` | 부족 영양소 dashboard API 설계를 정리한 과거 설계안이다. | P1 dashboard |
| `24-p1-6-healthkit-health-connect-sync.md` | HealthKit/Health Connect sync 설계를 정리한 과거 설계안이다. | P1 health sync |
| `25-p1-7-mobile-mvp-capture-yolov8-plan.md` | 모바일 MVP 캡처와 YOLOv8 계획을 정리한 과거 문서다. | P1 mobile/YOLO |
| `26-algorithm-modification-paper-rationale.md` | 알고리즘 수정 근거를 문헌 중심으로 정리한 과거 문서다. | 과거 알고리즘 근거 |
| `dev-guide-07-ocr-pipeline-design-example.md` | OCR pipeline 설계 예시 버전이다. | 예시 가이드 |
| `dev-guide-08-llm-supplement-parsing-design-example.md` | LLM 영양제 파싱 설계 예시 버전이다. | 예시 가이드 |
| `dev-guide-09-supplement-registration-api-design-example.md` | 영양제 등록 API 설계 예시 버전이다. | 예시 가이드 |
| `root-copy-17-api-paper-algorithm-rationale.md` | `17-api-paper-algorithm-rationale.md`의 root-copy 계열 보관본이다. | 중복/보관 |

비 Markdown 보관물:

| 파일 | 내용 파악 |
| --- | --- |
| `17-api-paper-algorithm-rationale.pdf` | 17번 근거 문서 PDF 산출물 |
| `26-algorithm-modification-paper-rationale.pdf` | 26번 근거 문서 PDF 산출물 |
| `26-algorithm-modification-paper-rationale.pptx` | 26번 관련 발표자료 |
| `dev-planning-review-report.html` | 개발 계획 리뷰 HTML 산출물 |
| `root-copy-17-api-paper-algorithm-rationale.pdf` | 17번 root-copy PDF 산출물 |

## 5. `docs/Nutrition-docs/templates/` 문서

| 파일 | 내용 파악 | 분류 |
| --- | --- | --- |
| `ocr-three-tier-evaluation-report.md` | OCR 3-tier fixture 평가 결과를 기록하는 반복 템플릿이다. 실행 정보, provider metrics, review notes 구성을 가진다. | 평가 템플릿 |

## 6. `docs/Nutrition-docs/pdf/` 산출물

`docs/Nutrition-docs/pdf/`는 Markdown 기준 문서의 PDF 산출물을 보관한다.

| 파일 | 대응 문서 |
| --- | --- |
| `01-project-overview.pdf` | `01-project-overview.md` |
| `02-background-problem.pdf` | `02-background-problem.md` |
| `03-project-intent.pdf` | `03-project-intent.md` |
| `04-market-research.pdf` | `04-market-research.md` |
| `05-github-guidelines.pdf` | `05-github-guidelines.md` |
| `06-tech-stack.pdf` | `06-tech-stack.md` |
| `07-core-algorithm.pdf` | `07-core-algorithm.md` |
| `08-implementation-plan.pdf` | `08-implementation-plan.md` |
| `09-data-catalog.pdf` | `09-data-catalog.md` |
| `10-compliance-checklist.pdf` | `10-compliance-checklist.md` |
| `PR1_기능_상세_보고서.pdf` | PR1 기능 상세 보고서 PDF 산출물 |

## 7. 폴더별 정리 판단

| 폴더 | 현재 역할 | 정리 판단 |
| --- | --- | --- |
| `docs/` | 현재 기준 문서와 후속 계획 문서가 같이 있다. | 번호 순 관리가 되어 있어 유지 가능하다. 다만 `22`, `23`은 current-state 성격이고 `31`~`42`는 대부분 계획/확장 문서라 구현 사실로 오해하지 않게 표시가 필요하다. |
| `docs/Nutrition-docs/dev-guides/` | 구현자용 가이드가 기능 순서대로 정리되어 있다. | 유지 가능하다. 모바일/시연/운영/인수인계 문서까지 포함하므로 "개발 가이드"보다 넓은 실행 가이드 폴더다. |
| `docs/Nutrition-docs/previous-version/` | 과거 설계와 예시 문서를 보관한다. | archive 성격이 명확하다. 현재 문서와 중복되는 이름이 있으므로 현재 구현 판단 시 제외하는 규칙이 필요하다. |
| `docs/Nutrition-docs/templates/` | 반복 산출물 양식 보관소다. | 유지 가능하다. 향후 sign-off, PR gate, evaluation report 템플릿을 이곳에 모으면 좋다. |
| `docs/Nutrition-docs/pdf/` | PDF 산출물 보관소다. | Markdown 원본과 동기화가 필요하다. 현재 01~10 PDF 중심이라 11 이후 문서는 PDF가 없다. |

## 8. 후속 정리 제안

1. `docs/Nutrition-docs/22-current-implementation-status-map.md`를 현재 상태 확인 진입점으로 명시한다.
2. `docs/31`~`docs/42`는 "구현 완료", "부분 구현", "설계/계획" 상태 라벨을 각 문서 상단에 통일한다.
3. `docs/Nutrition-docs/previous-version/`의 PDF/PPTX/HTML은 유지하되, README에 "현재 구현 판단에는 사용하지 않음"을 명시한다.
4. `docs/Nutrition-docs/pdf/`는 01~10만 PDF가 있으므로 최신 Markdown과 재동기화할지 결정한다.
5. `docs/.DS_Store`와 `docs/Nutrition-docs/pdf/.omc/state/idle-notif-cooldown.json`은 문서 산출물이 아니므로 커밋 대상에서 제외하는 것이 좋다.
