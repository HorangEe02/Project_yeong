# 24. 병합 후 통합 계획 (Post-Merge Integration Blueprint)

> Status: draft → **rev.3** (2026-06-02 병합 전 history/root 게이트와 최신 상태 정정)
> 작성일: 2026-06-02
> 최종 수정: 2026-06-02 (rev.3 — 병합 전 merge-base/root 감사와 문서-코드 상태 정정)
> 기준: 전체 remote 44개 브랜치 최신 커밋 기반 (`git ls-remote --heads origin` 확인)
> 목적: 브랜치 병합 후 Agent/LLM 레이어를 빠르게 완성하기 위한 통합 지도

## 0. 이 문서의 역할

기존 25+ 문서에 없는 다음만 다룬다. 기존 문서 내용은 참조(`→`)로 연결하고 반복하지 않는다.

### 0.1 rev.2 수정 이력 (2026-06-02 원격 브랜치 감사 정정)

외부 리뷰에서 "누락 브랜치가 많다"는 피드백을 받아 원격 저장소를 재감사했다. rev.1에는
`git branch -r` 기준이 오래되었거나 누락되어 실제 원격과 다른 내용이 있었다. rev.2는
`git ls-remote --heads origin` 기준으로 정정한다.

| 리뷰 지적 | 검증 결과 |
|----------|----------|
| "exp08/exp09/exp10, docs-deliverables, docs-2026-05-31-backend-ocr-security 브랜치 누락" | ✅ 맞음 → 실제 원격에 모두 존재. §1.2와 §3.1에 반영 |
| "63클래스 확정이 너무 단정적" | ✅ 맞음 → exp06 63클래스는 현재 baseline. exp09/taxo62, exp10/taxo59 후속 실험 비교 후 최종 선택 |
| "docs/data-yolo-food-detection 누락" | ✅ 맞음 → §1.2에 추가 |
| "OCR fix/* 브랜치 누락" | ✅ 맞음 → §1.2 기타 브랜치 그룹에 추가 |
| "unknown_backlog 미구현 표현 부정확" | ✅ 맞음 → §4.3 정정 (로컬 구현 완료, 원격 미반영) |
| "로컬 workspace 이름 ≠ 실제 브랜치" | ✅ 맞음 → §1.3 신설 |

수정 방침: 원격에 존재하는 후속 실험 브랜치는 모두 병합 전 검토 대상으로 둔다. 다만 모든
브랜치를 본문에 길게 풀지는 않고, Agent/LLM 통합 결정에 영향을 주는 브랜치만 주요 표와
로드맵에 반영한다.

### 0.2 rev.3 수정 이력 (2026-06-02 병합 실행 전제 정정)

추가 검토에서 이 문서를 "그대로 병합 실행서"로 쓰기에는 위험한 전제가 확인됐다.

| 검토 지적 | 정정 |
|----------|------|
| 일부 핵심 브랜치가 `origin/develop`과 merge-base가 없음 | ✅ 맞음 → §1.4와 Phase 0 추가. unrelated history 처리 방식 확정 전 병합 금지 |
| `ai-agent-backend-integration` 최신 구현/문서 일부가 GitHub 원격에 없음 | ✅ 맞음 → §1.3에 "로컬-only/ahead 상태"를 병합 전 publish gate로 명시 |
| rate limit/log redaction `main.py` 등록 필요 표현 부정확 | ✅ 맞음 → OCR 강화 브랜치에서는 이미 등록됨. 병합 후 보존 검증으로 수정 |
| 최근 2주 커밋 수 표가 전체 원격 기준과 불일치 | ✅ 맞음 → `git shortlog -sne --since=2026-05-19 --remotes=origin` 기준으로 정정 |
| `feat/ai-agent-local-llm` 최신 커밋일 오기 | ✅ 맞음 → 2026-05-18로 정정 |
| `07-grounded-chatbot-todo.md`가 live smoke 미완료라고 남아 있음 | ✅ 맞음 → 최신 판정은 `09-grounded-chatbot-implementation-log.md` 기준으로 정정 필요 |

1. 팀 구성과 브랜치 현황 (§1) — GitHub 최신 활동 기반
2. 기획서와 구현의 괴리 (§2)
3. 브랜치 간 연결점 매핑 (§3) — 각 산출물의 **실제 완성도** 포함
4. Agent ↔ DB 런타임 접근 패턴 (§4)
5. RAG 데이터 소스 통합 인벤토리 (§5)
6. 남은 불확실 영역과 팀원 확인 질문 (§6)
7. 병합 후 작업 로드맵 (§7)

---

## 1. 팀 구성과 브랜치 현황 (GitHub 2026-06-02 기준)

### 1.1 팀원 → GitHub ID → 담당 영역

| 팀원 | GitHub ID | 최근 2주 커밋 | 주요 담당 | 핵심 브랜치 |
|------|-----------|-------------|----------|-----------|
| **태동** | HorangEe02 | **362건** | OCR 전체 + 백엔드 보안 + 모바일 카메라/분석 + DB RLS + CI + 알고리즘 확장 | `feat/backend-supplement-ocr-db-hardening`, `feat/mobile-ios-xcode-simulator-run` |
| **종필** | jongpil Mun | 24건 | 데이터 파이프라인 + CVAT 라벨링 + AI Hub 424클래스 재분리 | `docs/data-yolo-cvat-setup` |
| **bell** | bell-0925 | 35건 | YOLO 학습 실험 (exp01~10) + taxonomy/모델 비교 | `feat/data-yolo-exp06-taxonomy`, `feat/data-yolo-exp07-yolo26s`, `feat/data-yolo-exp09-taxo62`, `feat/data-yolo-exp10-taxo59` |
| **창민** | changmin5957-sys | 44건 | AI Agent + LLM + chatbot + 기획 문서 | `feat/ai-agent-backend-integration`, `changmin-aiagent` |
| **neong** | neong0819 | 6건 | 모바일 대시보드 UI + 데이터 통합 프로토콜 + 팀 협업 가이드 | `feat/mobile-dashboard-redesign`, `feat/data-integration-protocol-v1` |
| **성훈** | ParkSungHoon | 1건 | Food/not-food 이진 분류기 | `sunghoon-food-notfood-classification` |

> 커밋 수 산식: `git shortlog -sne --since=2026-05-19 --remotes=origin`.
> 이 값은 전체 원격 브랜치 기준 활동량 참고값이며, 병합 우선순위 자체를 의미하지 않는다.

### 1.2 브랜치별 최신 상태 (주요 활성 브랜치)

| 브랜치 | 최종 커밋일 | 담당자 | 상태 |
|--------|-----------|--------|------|
| `feat/backend-supplement-ocr-db-hardening` | 05-31 | HorangEe02 | **가장 활발** — OCR+DB+보안+CI |
| `docs/docs-2026-05-31-backend-ocr-security` | 06-02 | HorangEe02 | backend/OCR/security handoff와 local backend connectivity 보정 |
| `docs/docs-deliverables` | 06-02 | HorangEe02 | 산출물/문서 묶음 브랜치. 병합 대상 여부 별도 판단 필요 |
| `feat/data-yolo-exp10-taxo59` | 06-01 | bell-0925 | taxonomy v4(taxo59) + seed2 학습 산출물. exp06 baseline과 비교 필요 |
| `feat/data-yolo-exp09-taxo62` | 06-01 | bell-0925 | taxo62 per-class 검증 + exp07 비교 분석. 최종 taxonomy 후보 |
| `feat/data-yolo-exp08-yolo11s-b16` | 06-01 | bell-0925 | YOLO11s batch16/overnight runner 계열 후속 실험 |
| `feat/data-yolo-exp07-yolo26s` | 05-31 | bell-0925 | exp07 학습 진행 중 |
| `feat/data-yolo-exp06-taxonomy` | 05-31 | bell-0925 | 63클래스 taxonomy v2 + AP 검증 완료. 현재 기준선 |
| `sunghoon-food-notfood-classification` | 05-31 | ParkSungHoon | food/not-food gate 완성 |
| `feat/mobile-ios-xcode-simulator-run` | 05-31 | HorangEe02 | iOS 빌드 + 모바일 플로우 |
| `docs/data-yolo-food-detection` | 05-30 | bell-0925 | exp03~05 학습 산출물 + 50클래스 AP50 요약 CSV |
| `feat/ai-agent-backend-integration` | 05-29 | changmin5957-sys | Agent+chatbot 구현 (**로컬 5 commits ahead**) |
| `feat/ai-agent-local-llm` | 05-18 | changmin5957-sys | SGLang+Ollama 로컬 LLM 설정 문서 |
| `feat/taedong-agent-prototype-preview` | 05-29 | changmin5957-sys | agent chat UI 프로토타입 |
| `docs/data-yolo-cvat-setup` | 05-29 | jongpil Mun | CVAT + 424클래스 파이프라인 |
| `feat/data-integration-protocol-v1` | 05-28 | neong0819 | 데이터 통합 프로토콜 LOCKED |
| `feat/mobile-dashboard-redesign` | 05-25 | neong0819 | 대시보드 히어로카드 + 5탭 |
| `feat/db-internal-learning-pipeline` | — | HorangEe02 | DB 학습 파이프라인 + 모바일 보정 |
| `sunghoon-database` | — | ParkSungHoon | DB 작업 (kakao 연동 등) |

#### 기타 브랜치 (그룹 요약)

| 그룹 | 브랜치 수 | 대표 브랜치 | 비고 |
|------|----------|-----------|------|
| **OCR fix/\*** | 11개 | `fix/ocr-v3-expected-matching`, `fix/ocr-ingredient-alias-matching` 등 | 태동의 OCR 강화 브랜치(`feat/backend-supplement-ocr-db-hardening`)에 통합 예정. 개별 리스트 불필요 |
| **OCR feat/\*** | 4개 | `feat/ocr-95-baseline-and-security-2026-05-20`, `feat/ocr-p1-5-followup`, `feat/ocr-quality-gates`, `feat/ocr-tampermonkey-category-labeling` | 초기 OCR 실험 브랜치. 현재 OCR 강화 브랜치가 이들을 대체 |
| **OCR test/\*** | 1개 | `test/ocr-kpi-readiness-gate` | OCR KPI 게이트 테스트 |
| **기타 docs/\*** | 2개 | `docs/team-collaboration-rules`, `docs/team-progress-guide` | 팀 협업 가이드 문서. data/산출물/보안 docs 브랜치는 주요 표에 별도 반영 |
| **기준 브랜치** | 2개 | `main`, `develop` | 현재 둘 다 `2f94102` 동일 커밋. 병합 기준 초기화 필요 |
| **개인/초기** | 5개 | `changmin-aiagent`, `changmin-plan`, `jongpil-tech`, `taedong-design`, `yeong-tech` | 초기 개인 작업 브랜치. 병합 대상 여부는 별도 판단 |

> 📊 **전체 원격 브랜치: 44개** (2026-06-02 `git ls-remote --heads origin` 기준)

### 1.3 로컬 Workspace 구조 (병합 시 주의사항)

`lemon_aid/` 디렉토리는 하나의 메인 클론 + 여러 **git worktree**로 구성되어 있다. 디렉토리 이름과 실제 체크아웃된 브랜치가 다르므로 주의.

| 디렉토리 | 실체 | 현재 브랜치 | 주의 |
|----------|------|------------|------|
| `lemon_aid/main/` | 메인 클론 | `docs/team-progress-guide` | ⚠️ 이름이 main이지만 **main 브랜치가 아님** |
| `lemon_aid/ai-agent-backend-integration/` | worktree | `feat/ai-agent-backend-integration` | origin보다 **5 commits ahead**, `23/24` 문서 포함 untracked 다수 |
| `lemon_aid/develop/` | worktree | `docs/team-collaboration-rules` | ⚠️ 이름이 develop이지만 **develop 브랜치가 아님** |

**⚠️ `origin/main`과 `origin/develop`은 현재 동일 커밋(`2f94102`)을 가리킨다.**
병합 순서(§7 Phase A) 실행 전, develop 브랜치를 main에서 분기하여 실제 통합 브랜치로 초기화해야 한다.

### 1.4 병합 전 Git history/root 감사

단순히 브랜치가 원격에 존재한다고 해서 바로 `develop`에 순차 merge할 수 있는 것은 아니다.
현재 일부 핵심 브랜치는 서로 다른 root commit에서 시작했다.

| 브랜치 그룹 | root commit | `origin/develop`과 관계 | 병합 전 판단 |
|-------------|-------------|-------------------------|--------------|
| `origin/develop`, `origin/main`, data/YOLO, food gate, data protocol, agent integration | `a9e4ea9` | merge-base 있음 | 일반 3-way merge 가능 |
| `feat/backend-supplement-ocr-db-hardening`, `feat/mobile-ios-xcode-simulator-run`, `docs/docs-2026-05-31-backend-ocr-security` | `f9613a1` | `origin/develop`과 merge-base 없음 | unrelated history 처리 방식 확정 필요 |

병합 담당자는 Phase A 전에 아래 명령으로 전체 원격 ref와 merge-base를 확인한다.

```powershell
git -C main fetch origin '+refs/heads/*:refs/remotes/origin/*' --prune
git -C main ls-remote --heads origin
git -C main merge-base origin/develop origin/feat/backend-supplement-ocr-db-hardening
git -C main merge-base origin/develop origin/feat/ai-agent-backend-integration
```

`feat/backend-supplement-ocr-db-hardening` 계열처럼 merge-base가 없는 브랜치는 다음 중 하나를
명시적으로 선택한 뒤 병합한다.

1. `--allow-unrelated-histories`로 통합하고 전체 파일 충돌을 수동 해결한다.
2. 새 통합 기준 브랜치를 OCR/backend root에서 만들고 data/agent 쪽을 반대로 이식한다.
3. 브랜치 전체 merge 대신 필요한 디렉토리/커밋 단위로 cherry-pick 또는 파일 이식한다.

이 선택 전에는 §7의 병합 순서를 실행하지 않는다.

---

## 2. 기획과 구현의 괴리 (Plan vs Reality)

기획서(`planning/guide/06-ai-agents.md`)는 초기에 작성. 구현이 진행되면서 변경된 사항:

| 항목 | 기획서 | 실제 구현 | 비고 |
|------|-------|-----------|------|
| **LLM Provider** | Claude API + GPT 백업 | SGLang + Ollama 로컬 LLM | 개인정보 보호 + 비용 |
| **Agent 구조** | 3개 (개인화/평가/챗봇) | 6 Agent + 3 Engine + SafetyGuard + Orchestrator | 세분화 |
| **답변 프레임** | 없음 | AnswerCard + 6 answerability + 7 renderer | 신규 |
| **Knowledge** | 없음 | knowledge.py (74KB) + Source Governance 3-tier | 신규 |
| **Safety** | check_forbidden_terms | SafetyGuard (금지 표현 + UL + 상호작용 + trace sanitize + 한국어 injection 차단) | 대폭 강화 |
| **OCR** | 기본 Adapter | %DV 보존 + 부형제 필터 + 단위 allowlist + prompt injection 차단 | HorangEe02 대폭 강화 |
| **보안** | 미정의 | Rate limit + 감사 해시 pepper + 로그 레다크션 + detect-secrets + RLS 설계 | 신규 |
| **CI/CD** | 미정의 | GitHub Actions (lint/test/build/security/deps) | HorangEe02 신설 |
| **알고리즘** | v1~v4 + BMR + 7-step | + 허리둘레 복부비만 + 흡연자 비타민C + 음주 BMI 안내 | HorangEe02 확장 |

현재 Agent 구성은 → [23-agent-llm-pipeline-flow.md](./23-agent-llm-pipeline-flow.md) 참조.

---

## 3. 브랜치 간 연결점 매핑 (GitHub 최신 기준)

### 3.1 음식 이미지 분류 파이프라인 — **상당 부분 완성됨**

기존 문서에서 "불확실"로 표시했으나, GitHub 확인 결과 다음이 이미 완성:

| 구성 요소 | 담당자 | 상태 | 상세 |
|----------|--------|------|------|
| **Food/not-food 이진 게이트** | 성훈 | **완성** | CLIP ViT-L/14 + Logistic Regression. threshold 0.6 권장. Streamlit 데모 포함 |
| **YOLO 63클래스 탐지** | bell | **exp06 baseline 완성** | YOLOv11s, AP50: 0.70~0.99. 40+ 클래스 AP50 ≥ 0.80 |
| **taxonomy v2 (50→63)** | bell | **기준선** | `exp06_taxonomy_v2_mapping.csv`. 최종 확정 전 exp09/taxo62, exp10/taxo59와 비교 필요 |
| **YOLO 후속 실험** | bell | **exp07~10 존재** | exp07(YOLO26s), exp08(YOLO11s-b16), exp09(taxo62), exp10(taxo59). 모델/taxonomy 선택 게이트 필요 |
| **424클래스 재분리** | 종필 | **파이프라인 완성** | AI Hub 원본 코드 복구 (val: 402/430 코드 회수 가능) |
| **데이터 통합 프로토콜** | neong | **LOCKED** | 13-case 분류 자동화, `nutrition_map_enriched.json` single source of truth |
| **평가 메트릭 v2** | neong | **LOCKED** | E2E Top-3 acc ≥0.80 목표, 7개 리스크 대응 계획 |
| **음식 YOLO 후보 endpoint** | 태동 | **완성** | `POST /meals/analyze-image` (458행 구현 + 168 테스트) |
| **식단 이미지 확인 저장** | 태동 | **완성** | `POST /meals/{id}/confirm` + 모바일 연동 |

**Agent 연결을 위해 아직 필요한 것**:
1. YOLO 모델 → 모바일 배포 (ONNX → TFLite/CoreML 변환 **미검증**)
2. exp06/07/08/09/10 비교 후 최종 taxonomy/model 선택
3. 선택된 taxonomy → 식약처 식품성분 DB 매핑 (영양소 연결)
4. 실제 사용자 사진으로 domain shift 테스트 (**미실행**, AI Hub 크롭만 검증)
5. IntakeAgent에 `FoodClassificationResult` 입력 연결

**약한 클래스 (AP50 < 0.70)** — 마라탕(0.21), 탕수육(0.35), 제육볶음(0.51) 등 8개

> ⚠️ **모델/taxonomy 선택 미확정**: exp06 63클래스는 현재 가장 명확한 기준선이지만,
> 원격에는 exp08(YOLO11s-b16), exp09(taxo62), exp10(taxo59) 후속 실험 브랜치가 존재한다.
> 병합 후에는 exp06을 그대로 확정하지 말고 per-class AP, 모바일 배포 가능성, 식품성분 DB 매핑
> 가능성을 함께 비교해 최종 taxonomy/model을 선택한다.

### 3.2 OCR + 백엔드 보안 — **대부분 완성됨**

태동(HorangEe02)이 `feat/backend-supplement-ocr-db-hardening` 브랜치에서 대규모 작업 완료:

| 구성 요소 | 상태 | 상세 |
|----------|------|------|
| **OCR %DV 보존** | **완성** | `daily_value_percent` 컬럼 추가 (migration 0020) |
| **부형제 필터링** | **완성** | gelatin, glycerin 등 자동 제외 |
| **단위 allowlist** | **완성** | 8/8 악성 차단, 14/14 정상 통과 테스트 |
| **한국어 prompt injection 차단** | **완성** | NFKC 정규화 + 패턴 탐지 |
| **Rate limit** | **완성** (코드) | Token bucket, 추론 동시성 캡. OCR 강화 브랜치 `main.py`에는 등록됨. 병합 후 보존 검증 필요 |
| **감사 해시 pepper** | **완성** | audit_logs용 별도 HMAC 키 |
| **로그 레다크션** | **완성** (코드) | extra/traceback/DB자격증명 마스킹. OCR 강화 브랜치 `main.py`에서 `setup_logging()` 호출됨. 병합 후 보존 검증 필요 |
| **detect-secrets** | **완성** | `.secrets.baseline` + pre-commit 훅 |
| **FORCE RLS 설계** | **설계+PoC 완료** | 32테이블 정책, migration 0023a/b/c 작성. **라이브 미적용** |
| **CI 게이트** | **완성** | GitHub Actions: lint/test/build/security/deps |

**Agent에 미치는 영향**:
- RLS 라이브 적용 시 Agent 서비스 계정(`lemon_app`)에 적절한 권한 필요
- 현재는 `lemon` superuser로 동작 → RLS bypass. 역할 마이그레이션 선행 필요
- OCR migration (0020/0021) 아직 라이브 DB 미적용

### 3.3 모바일 UI — **핵심 플로우 작동 중**

| 구성 요소 | 담당자 | 상태 | 상세 |
|----------|--------|------|------|
| **카메라 프로토타입** | 태동 | **완성** | 카메라+갤러리 (603행), 분석결과 화면 (293행) |
| **영양제 확인+저장** | 태동 | **완성** | evidence_spans 추적, 타임아웃/동의 재진입 처리 |
| **식단 이미지 확인+저장** | 태동 | **완성** | YOLO 후보 → 사용자 확인 → DB 저장 |
| **대시보드** | neong | **P0 완성** | 히어로카드 + 날짜 네비 + 마스코트 15포즈 + FAB 빠른 액션 |
| **5탭 쉘** | neong | **완성** | 카메라/분석결과/챗/점수/설정 |
| **iOS 시뮬레이터** | 태동 | **완성** | Xcode 26.5 타깃 + signing 정리 |

**Agent 연결을 위해 아직 필요한 것**:
- Agent API Response (`DailyCoachingResult`, `ChatbotResponse`) → 대시보드/채팅 UI 매핑
- `sources[]` 출처 귀속 표시 방식 미확정
- `answerability` 상태별 UI 표현 미확정
- iOS HEIC 이미지 MIME allowlist 누락 (jpeg/png/webp만 허용 → 415 에러 가능)

### 3.4 알고리즘 확장 — **완성됨**

태동(HorangEe02)이 추가 구현 완료:

| 확장 | 상태 | 커밋 |
|------|------|------|
| 허리둘레 복부비만 flag (KSSO 기준) | **완성** | `beec93f` |
| 흡연자 비타민C 카드 보정 | **완성** | `da17171` |
| 음주 BMI/허리둘레 안내 | **완성** | `6aae49b` |

---

## 4. Agent ↔ DB 런타임 접근 패턴

(이전 버전과 동일 — §3.1~3.4 내용 유지)

### 4.1 접근 계층

```
Agent → Service → Repository → SQLAlchemy AsyncSession → PostgreSQL
```

### 4.2 읽기/쓰기 패턴

→ 이전 버전의 §3.2, §3.3 테이블 참조 (변경 없음)

### 4.3 현재 미연결 부분

| 패턴 | 현재 상태 | 필요 작업 |
|------|-----------|----------|
| `AgentRunLogger` | InMemory (메모리) | DB 연결 구현 |
| `AgentMemoryWriter` | Protocol 정의만 | DB 연결 구현 |
| `ChatbotEvidenceRepository` | DB 쿼리 구현됨 | migration + 시드 데이터 |
| `unknown_backlog` | **로컬 구현 완료** (원격 미반영) | migration 3개(0010/0013/0017) + service 2개 + test 2개 + script 3개. 병합 전 재검증 필요 |
| Meal YOLO → IntakeAgent | endpoint 있으나 Agent 미연결 | FoodClassificationResult → IntakeAgent 입력 매핑 |

---

## 5. RAG 데이터 소스 통합 인벤토리

| # | 소스 | 현재 상태 | Agent 연결 | 변경사항 (GitHub 기준) |
|---|------|-----------|-----------|---------------------|
| 1 | **KDRIs 2025** (1,795 rows) | **완료** | NutritionEngine | 변경 없음 |
| 2 | **식약처 기능성 인정 원료** | 구조 준비 | SupplementEngine | 변경 없음 |
| 3 | **약물-영양소 상호작용** | P0 ~10쌍 | SupplementEngine + SafetyGuard | 변경 없음 |
| 4 | **KDCA 건강정보** | knowledge.py 내장 | ChatbotAgent | 변경 없음 |
| 5 | **식품성분 DB** | 구조 준비 | IntakeAgent | **`nutrition_map_enriched.json` 프로토콜 LOCKED** (neong) |
| 6 | **회사 가이드 알고리즘** | **완료** | 분석 레이어 | **허리둘레/흡연/음주 확장 완료** (태동) |
| 7 | **LLM-WIKI** | 참고용 | 직접 사용 안 함 | 변경 없음 |
| 8 | **영양제 제품 DB** | 일부 구축 | SupplementParser | **%DV 컬럼 추가, 부형제 필터** (태동) |
| 9 | **음식 분류 모델** (신규) | **exp06 baseline + exp07~10 후속 실험** | IntakeAgent (미연결) | **food/not-food gate + exp06/07/08/09/10 비교 후 선택** |
| 10 | **데이터 통합 프로토콜** (신규) | **LOCKED** | 데이터 품질 관리 | **13-case 분류 + 평가 메트릭 v2** |

---

## 6. 남은 불확실 영역과 확인 질문

GitHub 확인으로 해소된 질문과 아직 남은 질문을 구분:

### 6.1 해소된 질문 (GitHub에서 답 확인됨)

| 기존 질문 | 답 |
|----------|-----|
| 클래스 체계 몇 개? | **최종 미확정**. exp06 63클래스가 baseline이고 exp09 62클래스, exp10 59클래스 후속 후보가 존재 |
| confidence threshold? | food/not-food gate: **0.6** (성훈 모델 metadata) |
| 음식 YOLO endpoint 있나? | **있음** (`POST /meals/analyze-image`, 태동 구현) |
| CI/CD 있나? | **있음** (GitHub Actions, 태동 구현) |
| 모바일 카메라/확인 플로우? | **작동 중** (카메라+식단+영양제 확인 저장, 태동) |
| 대시보드 구성? | **P0 완성** (히어로카드+5탭+FAB, neong) |
| 데이터 통합 프로세스? | **LOCKED** (13-case 프로토콜 + eval metrics v2, neong) |

### 6.2 아직 확인 필요한 질문

| # | 영역 | 질문 | 담당자 | 우선순위 |
|---|------|------|--------|---------|
| Q1 | **모바일 모델 배포** | YOLOv11s → TFLite/CoreML 변환 가능한가? 정확도 하락은? 모델 크기는 30MB 이하인가? | bell + 태동 | **높음 (블로커)** |
| Q2 | **Domain shift** | AI Hub 크롭 vs 실제 사용자 사진 정확도 차이는? (목표: ≤15%p) | bell | **높음** |
| Q3 | **taxonomy → 영양소** | exp06 63 / exp09 62 / exp10 59 중 어떤 taxonomy가 식약처 식품성분 DB `food_code`에 가장 잘 매핑되는가? `nutrition_map_enriched.json`에 영양소 데이터 있는가? | neong + 종필 + bell | **높음** |
| Q4 | **RLS 역할 마이그레이션** | `lemon` → `lemon_app` 전환 시점은? Agent 서비스 계정 권한은? | 태동 | 중간 |
| Q5 | **Agent 응답 → UI 매핑** | `findings[]`, `sources[]`, `safety_warnings` 를 어떤 위젯으로 표시? | 태동 + neong | 중간 |
| Q6 | **answerability UI** | `unknown_no_reviewed_source`, `medical_decision_boundary` 상태의 UI 표현은? | 태동 + neong | 중간 |
| Q7 | **iOS HEIC** | HEIC MIME 지원 추가 필요 (현재 jpeg/png/webp만 → 415 에러) | 태동 | 중간 |
| Q8 | **Startup 등록 보존** | OCR 강화 브랜치에는 rate limit 미들웨어와 로그 레다크션 필터가 등록되어 있음. unrelated-history 병합 후 `main.py`에서 사라지지 않았는가? | 태동 | 중간 |
| Q9 | **LLM 스트리밍** | 채팅 응답 SSE 스트리밍 vs 완성 후 전송? | 팀 전체 | 낮음 |

### 6.3 Agent 측 독립 작업 (다른 브랜치 무관)

| 작업 | 이유 |
|------|------|
| `AgentRunLogger` DB 연결 | Protocol 확정됨 |
| `AgentMemoryWriter` DB 연결 | Protocol 확정됨 |
| `unknown_backlog` 원격 반영 + 병합 전 재검증 | 로컬 구현 완료 (migration 0010/0013/0017 + service + test). push 후 동작 검증 필요 |
| `medical_sources` 시드 데이터 | knowledge.py에 데이터 존재 |
| ChatbotAgent renderer 분리 | 내부 리팩토링 |
| P0 상호작용 boundary 확장 | 데이터 추가 |

---

## 7. 병합 후 작업 로드맵 (수정된 버전)

GitHub 현황 반영으로 기존보다 **Phase C(브랜치 통합)가 축소**되지만, 음식 모델/taxonomy는
exp06 기준선을 바로 확정하지 않고 exp07~10 결과 비교 게이트를 먼저 통과한다.

### Phase 0: 병합 기준 브랜치와 history/root 정리 (0.5~1일)

```
1. 전체 remote refs를 명시적으로 fetch
   git -C main fetch origin '+refs/heads/*:refs/remotes/origin/*' --prune
2. `origin/develop` 기준 merge-base 표 작성
   - 일반 3-way merge 가능 브랜치
   - unrelated history 브랜치
3. OCR/backend root(`f9613a1`) 계열 처리 방식 선택
   - allow-unrelated-histories merge
   - OCR/backend root를 통합 기준으로 재선정
   - 디렉토리/커밋 단위 이식
4. `feat/ai-agent-backend-integration`의 로컬 5 commits ahead와 untracked 문서를 원격 반영할지 결정
5. 병합 전 보호 규칙 확인
   - main/develop 직접 push 금지
   - 통합 feature 브랜치 + PR
   - explicit staging
```

### Phase A: 병합 및 안정화 (1~2일, Phase 0 통과 후)

```
1. develop에 순차 병합
   순서: OCR 강화(태동) → data/YOLO(bell+종필) → food gate(성훈)
        → data protocol(neong) → mobile(태동+neong) → agent(창민)
2. 충돌 해결 + CI 게이트 통과 (태동이 이미 구축한 GitHub Actions)
3. 전체 테스트: pytest 390+ 통과
4. Alembic 마이그레이션 적용
   - 0020/0021 (OCR %DV) + medical_sources 3-tier
   - 0023a/b/c (FORCE RLS)는 Phase D로 별도 진행
5. main.py에 rate limit 미들웨어 + 로그 레다크션 필터가 병합 후에도 남아 있는지 확인
```

### Phase B: DB 연동 + Agent 내부 연결 (2~3일)

```
1. AgentRunLogger → DB (InMemory 교체)
2. AgentMemoryWriter → DB
3. medical_sources + evidence_items 시드 데이터 (knowledge.py → DB)
4. unknown_backlog 원격 반영 + 동작 검증 (로컬 구현 완료 — migration/service/test 존재)
5. ChatbotAgent renderer 분리 (CardAnswer/Unknown/Boundary)
```

### Phase C: 음식 파이프라인 ↔ Agent 연결 (2~3일)

```
이미 완성된 것:
  ✅ food/not-food gate (성훈)
  ✅ YOLO exp06 63클래스 baseline (bell)
  ✅ YOLO exp07/08/09/10 후속 실험 브랜치 존재 (bell)
  ✅ /meals/analyze-image endpoint (태동)
  ✅ 식단 확인+저장 플로우 (태동)
  ✅ 데이터 통합 프로토콜 (neong)

남은 작업:
1. exp06/07/08/09/10 결과 비교
   - per-class AP, 약한 클래스, taxonomy 크기(63/62/59), 모바일 배포 가능성, 식품성분 DB 매핑성을 함께 비교
2. 최종 taxonomy/model 선택 후 식약처 식품성분 DB 영양소 매핑
   - nutrition_map_enriched.json 활용
3. FoodClassificationResult → IntakeAgent.normalize() 입력 연결
4. 모바일 모델 배포 검증 (TFLite/CoreML 변환 + 정확도/크기 측정)
   - 실패 시 Plan B: FastAPI 서버사이드 추론
5. 실사용자 사진 domain shift 테스트 (100+장)
```

### Phase D: Agent 마무리 + 보안 적용 (3~4일)

```
1. PersonalizationAgent — agent_memory DB 읽기/쓰기
2. ChatbotAgent — DB-backed ChatbotEvidenceRepository 실연결
3. SGLang structured output 안정화
4. P0 상호작용 boundary 확장 (10쌍 → 50쌍)
5. RLS 역할 마이그레이션 (lemon → lemon_app) — 태동 설계 기반
6. Agent 서비스 계정 권한 설정
```

### Phase E: E2E 통합 테스트 + 데모 (2~3일)

```
1. 페르소나 시나리오:
   - 김건강 (52세): 영양제 사진 → OCR → 코칭 → 채팅 Q&A
   - 박직장 (38세): 음식 사진 → YOLO 분류 → 식단 평가 → 체중 예측
2. Safety: 금지 표현, 응급, boundary, prompt injection
3. 성능: LLM < 5초, YOLO 추론 < 1초 (모바일)
4. 데모 시나리오 + fallback 시연
```

---

## 8. 기술 결정 동기화

| 항목 | 기획 | 현재 구현 | 확정 |
|------|------|-----------|------|
| LLM | Claude API | SGLang + Ollama | **확정** |
| Agent | 3개 | 6 Agent + 3 Engine + SafetyGuard | **확정** |
| 검색 | 미정의 | SQL Phase 1 | Phase 1 **확정** |
| DB | PostgreSQL + TimescaleDB + Redis | + pgvector (선택적) + FORCE RLS (설계 완료) | **확정** |
| 모바일 | Flutter | Flutter 3.24+ | **확정** |
| CI/CD | 미정의 | GitHub Actions (lint/test/build/security/deps) | **확정** (태동) |
| 음식 분류 | 미정의 | CLIP gate + YOLO exp06 baseline + exp07~10 후속 후보 + 13-case 통합 프로토콜 | **선택 게이트 필요** |
| OCR 보안 | 기본 | %DV + allowlist + injection 차단 + 부형제 필터 | **확정** (태동) |

---

## 부록: 관련 문서 빠른 참조

| 주제 | 문서 | 위치 |
|------|------|------|
| 파이프라인 전체 흐름 | 23-agent-llm-pipeline-flow.md | Integration-docs/ |
| 챗봇 PRD/TDD/TRD | 05/06/08 시리즈 | Integration-docs/ |
| 의료 소스 DB | 04-medical-source-db-contract.md | Integration-docs/ |
| DB 스키마 | 05-data-model.md | planning/guide/ |
| 알고리즘 | 07-core-algorithm.md | Nutrition-docs/ |
| 데이터 통합 프로토콜 | INTEGRATION_PROTOCOL.md | docs/ (data-integration-protocol-v1) |
| 평가 메트릭 | EVAL_METRICS.md | docs/ (data-integration-protocol-v1) |
| FORCE RLS 설계 | 2026-05-31-force-rls-rollout-design.md | docs/ (ocr-db-hardening) |
| OCR/보안 핸드오프 | 2026-05-30-ocr-yolo-ollama-security-db-audit-handoff.md | docs/ (ocr-db-hardening) |
| 구현 로그 | 09, 16~22 시리즈 | Integration-docs/ |
| 갭 리뷰 | 10, 15 | Integration-docs/ |
