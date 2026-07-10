# 04_AJIN 문서 인덱스

## 운영·배포 가이드 (현행)

| 문서 | 내용 |
|------|------|
| [API.md](./API.md) | 전체 API 레퍼런스 (scripts/generate_openapi_docs.py 자동 생성) |
| [DOCKER.md](./DOCKER.md) | Docker 로컬 실행 가이드 |
| [BACKEND_DEPLOY.md](./BACKEND_DEPLOY.md) | 백엔드(Cloud Run) 배포 가이드 |
| [FULL_MODE_DEPLOY.md](./FULL_MODE_DEPLOY.md) | 전체 모드 배포 가이드 |
| [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) | 10분 시연 시나리오 (Cloud Run 기준) |
| [SUPABASE_REMOTE_OPERATION_RUNBOOK.md](./SUPABASE_REMOTE_OPERATION_RUNBOOK.md) | Supabase 운영 런북 |
| [IDP_SETUP_GUIDE.md](./IDP_SETUP_GUIDE.md) | IdP(인증) 설정 가이드 |
| `openapi.json` / `openapi-summary.json` | OpenAPI 스펙 원본 / 요약 |

## 기능 문서 (Feature A~F)

[FEATURE_A_SEARCH.md](./FEATURE_A_SEARCH.md) · [FEATURE_B_DRAFT.md](./FEATURE_B_DRAFT.md) · [FEATURE_C_ONBOARDING.md](./FEATURE_C_ONBOARDING.md) · [FEATURE_D_COMPLIANCE.md](./FEATURE_D_COMPLIANCE.md) · [FEATURE_E_ADMIN.md](./FEATURE_E_ADMIN.md) · [FEATURE_F_EQUIPMENT.md](./FEATURE_F_EQUIPMENT.md) — 상세 스펙은 [features/](./features/)

## 설계·계획 문서

| 위치 | 내용 |
|------|------|
| [design/](./design/) | 웹 디자인 스펙, 작업 계획 |
| [features/](./features/) | 기능 상세 명세 |
| [migration/](./migration/) | DB 마이그레이션 설계 (compliance_db → Postgres 등) |
| [RAG_ENHANCEMENT_PLAN.md](./RAG_ENHANCEMENT_PLAN.md) | RAG 고도화 계획 |
| [UI_REDESIGN_PLAN.md](./UI_REDESIGN_PLAN.md) | UI 리디자인 계획 |
| [FIREBASE_TO_SUPABASE_POSTGRES.md](./FIREBASE_TO_SUPABASE_POSTGRES.md) | Firebase → Supabase/Postgres 전환 설계 |
| [INSPECTION_CSV_SCHEMA.md](./INSPECTION_CSV_SCHEMA.md) · [PHASE_B_AB_VALIDATION.md](./PHASE_B_AB_VALIDATION.md) | 데이터 스키마 · 검증 기록 |
| `SLACK_APP_MANIFEST.yaml` | Slack 앱 매니페스트 |

## 이력·스냅샷 (개발 과정 기록 — 당시 시점 기준)

| 위치 | 내용 |
|------|------|
| [reports/](./reports/) | 버전별 업데이트 리포트 |
| [reviews/](./reviews/) | 종합 평가·포스트모템 |
| [roadmaps/](./roadmaps/) | 로드맵 스냅샷 |
| [HANDOFF_2026-05-27_v3.10.md](./HANDOFF_2026-05-27_v3.10.md) | v3.10 시점 핸드오프 문서 |
| [legacy/](./legacy/) | 구버전(Streamlit UI 등) 관련 문서 |
| [generated/](./generated/) · [demo-video/](./demo-video/) · [wwdc-techstack/](./wwdc-techstack/) | 생성 산출물 · 데모 관련 자료 |

> 이력·스냅샷 문서는 작성 시점의 구조(예: 구 Streamlit `ui/*.py`)를 서술하므로 현행 코드와 다를 수 있습니다.
