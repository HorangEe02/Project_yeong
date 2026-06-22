# 03. AI Agent 안전 이식 계약

> Status: contract-first integration baseline
> 작성일: 2026-05-28
> 기준 브랜치: `feat/ai-agent-backend-integration`
> 기준 문서: [45-development-dependency-split.md](../Nutrition-docs/45-development-dependency-split.md)
> 상세 의료정보 DB 계약: [04-medical-source-db-contract.md](./04-medical-source-db-contract.md)

## 목적

이 문서는 팀원 브랜치의 AI Agent, Nutrition backend, DB, UI 변경을
`ai-agent-backend-integration`에 선별 이식할 때 지켜야 하는 최소 계약이다.
blind merge가 아니라 계약에 맞는 단위만 가져오는 것을 전제로 한다.

핵심 원칙은 다음과 같다.

- 의료/영양 판단과 안전 경계는 deterministic backend가 소유한다.
- LLM은 backend context를 한국어 제품 말투로 설명할 뿐, 새 의료 판단을 만들지 않는다.
- RAG는 reviewed source 보강 계층이며 safety boundary를 대체하지 않는다.
- DB는 실행 결과와 재현 가능한 version/source/audit metadata를 저장하고 계산식을 대신하지 않는다.
- UI는 backend 완성 전에도 같은 response fixture로 상태별 화면을 구현할 수 있어야 한다.

의료정보 DB의 source, claim, review, boundary, RAG 연결 schema는 별도 상세 계약인
[04-medical-source-db-contract.md](./04-medical-source-db-contract.md)를 따른다. 이
문서에는 세부 DB schema를 길게 넣지 않고, 이식 시 지켜야 할 상위 안전/응답/저장
경계만 유지한다.

## 표준 사용자 응답 계약

의료, 영양, 체중 예측, 영양제 주의, 챗봇 답변은 다음 사용자-facing 상태 중 하나로
내려간다.

| 상태 | 의미 | UI 기준 |
| --- | --- | --- |
| `normal` | 일반 분석 또는 낮은 위험도의 안내 | 요약과 다음 행동을 기본 표시 |
| `caution` | 진행 가능하지만 불확실성 또는 주의가 있음 | warning/source를 강조 |
| `blocked` | 제품이 답하면 안 되는 요청 | boundary message와 안전한 대안만 표시 |
| `needs_more_info` | 입력 부족 또는 OCR/추출 불확실 | 필요한 추가 입력을 표시 |
| `professional_review` | 전문가 확인이 필요한 건강 맥락 | 상담/측정/의료진 확인 CTA를 강조 |

필수 필드는 다음과 같다.

| 필드 | 타입 기준 | 계약 |
| --- | --- | --- |
| `status` | enum | 위 다섯 상태만 사용자-facing 상태로 사용한다. |
| `summary` | string | 현재 입력 기준으로 말할 수 있는 요약. 진단, 치료, 처방 단정 금지. |
| `warnings` | array | 주의, 불확실성, 입력 한계, safety boundary code/message. |
| `next_actions` | array | 낮은 위험도의 자기관리, 추가 입력, 측정, 전문가 상담 안내. |
| `sources` | array | reviewed source metadata 또는 source family card. draft 노출 금지. |
| `algorithm_version` | string | 계산, 판정, 정책 버전. DB result/history 저장 필수. |
| `confidence` | enum 또는 coarse string | `low`, `medium`, `high` 등 거친 신뢰도. 임상 확률처럼 표현하지 않는다. |
| `requires_professional_review` | boolean | UI 강조와 후속 CTA 기준. |

현재 backend 내부의 `completed`, `preview`, `failed`, `approval_status`,
`safety_warnings` 같은 값은 내부 실행 상태 또는 호환 필드로 유지할 수 있다. 다만
mobile과 사용자-facing API fixture는 위 다섯 상태와 필수 필드로 수렴해야 한다.

## 저장 금지 경계

다음 값은 DB, 사용자 응답, source card, agent memory, run log, RAG index에 저장하거나
노출하지 않는다.

- raw prompt 또는 full prompt
- raw LLM response, provider payload 전문
- raw OCR text
- raw image bytes, base64 image, EXIF, 원본 파일명
- internal trace, guard name, policy 내부 문자열
- `draft`, `paper_candidate`, 내부 조사 snippet
- 개인정보, 시크릿, provider key, service-account JSON

허용되는 저장 대상은 확인된 입력과 재현 가능한 결과 metadata다.

- user profile, consent state
- confirmed meal/activity/supplement/health record
- algorithm input snapshot과 output snapshot
- `algorithm_version`
- warning code와 reviewed source metadata
- source review status, reviewed date, expiry
- audit trail과 deletion evidence

## LLM 계약

LLM은 판단자가 아니라 설명자다.

- LLM 호출 전 backend safety classifier가 먼저 위험 의도를 분류한다.
- LLM prompt에는 sanitized findings, recommendations, reviewed source family, response contract만 넣는다.
- LLM은 listed source family 밖의 건강 사실, 수치 약속, 복약 변경, 진단/치료 판단을 만들 수 없다.
- LLM 결과가 금지 표현, unsupported medical fact, unsupported numeric medical claim을 포함하면 fallback으로 내려간다.
- 일반 식사 질문은 공식 출처 기반 조정 안내를 우선하고, 약물/진단/검사/응급/자해 등 고위험 의도에서만 강한 전문가 경계를 적용한다.

## RAG 계약

RAG는 마지막 보강 계층이다.

- reviewed source만 index와 사용자 source card에 들어간다.
- `draft`, `paper_candidate`, 내부 조사 문서는 prompt grounding과 사용자 source에서 제외한다.
- retrieval 실패 시 deterministic answer와 safety boundary가 유지된다.
- source에는 최소한 `source_id`, `source_family`, `review_status`, `reviewed_at` 또는 expiry 기준을 포함한다.
- live web search는 사용자-facing 의료 답변에 직접 연결하지 않는다.

## 팀 브랜치 read-only 스캔

2026-05-28 fetch 후 확인한 원격 기준이다. 이 표는 merge 결정이 아니라 이식 후보
분류다.

| 브랜치 | 최신 head | 확인 범위 | 이식 후보 | 보류/주의 |
| --- | --- | --- | --- | --- |
| `origin/main` | `2f94102 docs: add research evidence usage guide` | 최신 통합 기준 | 기준 diff 비교용 | 로컬 `main/`은 dirty 상태라 직접 수정 금지 |
| `origin/develop` | `2f94102 docs: add research evidence usage guide` | 팀 통합 기준 | 새 feature/docs 브랜치 base | 로컬 `develop/` worktree는 `63ffbee`로 오래된 별도 docs 브랜치 |
| `origin/changmin-aiagent` | `efe231c Add reviewed medical source registry` | `ai-agent/src`, `knowledge.py`, `SafetyGuard`, LLM clients, tests | reviewed source registry, response policy, trace/prompt sanitizer, SGLang/OpenAI-compatible client | standalone package 경로와 backend API schema를 그대로 merge하지 않는다 |
| `origin/feat/ai-agent-local-llm` | `a0416dd docs(ai): clarify pull request branch notes` | 초기 local LLM agent package | basic app adapter, Ollama/OpenAI-compatible client, safety trace sanitizer | `changmin-aiagent`가 더 최신이므로 중복 단위는 최신 브랜치 우선 |
| `origin/yeong-tech` | `86d0198 docs(report): 2026-05-19 Claude Code multi-session summary` | Nutrition backend, KDRIs, OCR, privacy, learning/vector DB | KDRIs 2025 approved row/manifest, consent gate, raw image/OCR 비저장 테스트, regulated OCR schema | 대형 backend 전체 merge 금지. 현재 backend 모델/마이그레이션과 충돌 검토 후 파일 단위 이식 |
| `origin/sunghoon-database` | `c6149b3 kakao ver3` | auth/profile/consent DB 초안 | Kakao/social login, profile, consent table 초안 | audit/history/result 계약이 부족하다. 기존 Nutrition backend privacy/result 모델과 비교 필요 |
| `origin/taedong-design` | `7d1dfa8 feat(mobile): 메인 대시보드 본문 + 카메라/분석결과/챗/점수/설정 + 부가화면` | Flutter model/screen/widget | `AnalysisResult`, confidence/source rendering, warning UI, chat/dashboard screen 참고 | 사용자-facing 상태 enum과 source array 계약에 맞게 재모델링 필요 |
| `origin/feat/mobile-dashboard-redesign` | `e50114c docs(team): 팀 협업 가이드 추가 (브랜치·커밋·PR·CI 규칙)` | Flutter dashboard redesign | dashboard/card/widget 참고 | 원격 head가 협업 문서 커밋이므로 실제 UI diff는 `taedong-design`과 비교 필요 |
| local `feat/mobile-chat-prototype` | `7d1dfa8 feat(mobile): 메인 대시보드 본문 + 카메라/분석결과/챗/점수/설정 + 부가화면` | local worktree only | chat prototype 참고 | 원격 `origin/feat/mobile-chat-prototype`는 없음. 이식 전 원격 반영 여부 확인 |

## 선별 이식 순서

1. Contract fixture를 먼저 만든다.
   - 다섯 상태와 필수 필드가 backend response, DB result model, Flutter fixture에서 동일하게 해석되어야 한다.
2. Safety boundary를 고정한다.
   - 복약 변경, 치료 판단, 검사수치 해석, 혈당 급강하 기대, 영양제 병용, 응급/자해 위험은 LLM 호출 전 boundary 응답으로 내려간다.
3. 저장 책임을 고정한다.
   - result/history에는 input/output snapshot, `algorithm_version`, warning/source metadata를 저장한다.
   - raw prompt, raw OCR text, raw image는 저장 금지 테스트를 둔다.
4. UI fixture를 고정한다.
   - `normal`, `caution`, `blocked`, `needs_more_info`, `professional_review` mock을 먼저 만들고 rendering rule을 고정한다.
5. RAG는 reviewed source governance 테스트가 통과한 뒤 연결한다.
   - RAG 실패가 safety boundary를 우회하지 않아야 한다.

## 이식 금지 조건

다음 조건이 하나라도 있으면 해당 코드는 보류한다.

- 사용자-facing 응답에 raw trace, raw prompt, raw OCR text, raw image metadata가 섞인다.
- `draft` 또는 `paper_candidate` source가 prompt 근거나 사용자 source card에 들어간다.
- LLM이 복약 변경, 치료 판단, 질환 확정, 혈당/체중 수치 약속을 직접 생성한다.
- DB migration이 기존 result/history/consent/audit 책임을 덮어쓴다.
- mobile fixture가 내부 상태명 또는 guard 문자열에 의존한다.
- 코드 단위 테스트 없이 대형 branch merge만으로 기능을 가져오려 한다.

## 검증 기준

| 영역 | 최소 검증 |
| --- | --- |
| Contract | backend response와 Flutter fixture shape 비교 테스트 |
| Safety | 위험 질문이 LLM 없이 boundary 응답으로 내려가는 테스트 |
| Answer quality | 대표 golden set이 금지 표현 없이 측정/낮은 위험 행동/상담 안내를 포함하는지 확인 |
| DB/privacy | consent, audit, history, deletion flow와 raw field 비저장 테스트 |
| Evidence/RAG | reviewed source만 검색/노출되고 draft source가 제외되는 테스트 |
| UI | 다섯 상태 fixture rendering과 raw trace/internal policy 문자열 비노출 확인 |

## 다음 구현 PR 기준

다음 PR은 문서가 아니라 코드 이식 단계다. PR 시작 전 현재
`ai-agent-backend-integration`의 미커밋 변경을 먼저 분리하고, 새 feature/docs 브랜치는
`origin/develop`에서 만든다. 팀 브랜치 코드는 merge가 아니라 `git show`/`git diff`로
파일 단위 비교 후 가져온다.
