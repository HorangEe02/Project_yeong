# 보안 정책

## 보고 절차 (Vulnerability Reporting)

보안 취약점이나 secret 노출을 발견하시면, 공개 GitHub Issue 가 아닌 **GitHub Security Advisory** 또는 사적 채널로 보고해 주세요.

### 우선순위
- 🔴 **Critical**: secret 외부 노출, RCE, SQL injection — 24h 이내 대응
- 🟠 **High**: 인증 우회, 권한 상승 — 72h 이내
- 🟡 **Medium**: XSS, CSRF, DoS — 1주일 이내
- 🟢 **Low**: 정보 누설, deprecated lib — 다음 release

### 채널
1. GitHub Security Advisory — https://github.com/HorangEe02/Project_yeong/security/advisories/new
2. Email — `catlife9029@gmail.com` (subject prefix `[SECURITY]`)
3. 대학 졸업프로젝트 팀 채널 (Discord/Slack)

## Secret 관리

### 절대 commit 금지
| 항목 | 위치 |
|---|---|
| `GEMINI_API_KEY` | `.env`, GCP Secret Manager |
| `AJIN_OLLAMA_SECRET` | `~/.config/ajin/ollama-secret`, Cloud Run env |
| `AJIN_JWT_SECRET` | `.env`, GCP Secret Manager |
| `meili_master_key` | `secrets/meili_master_key` |
| `smtp_password` | `secrets/smtp_password` |
| Firebase Admin SDK key | `*-firebase-adminsdk-*.json` |
| GCP Service Account key | `gcp-sa-key.json` |
| `data/.jwt_secret` | `data/.jwt_secret` (자동 생성) |
| `~/.cloudflared/*.json` | Cloudflare Tunnel credentials |

### 자동 검증
- `.gitignore` 가 위 파일들을 모두 차단
- GitHub `Secret scanning` + `Push protection` 활성화 권장
- (선택) `gitleaks` 로 PR 시 자동 secret 검사

### Rotation 정책
- **즉시 rotation**: 채팅·로그·screenshot 등으로 외부 노출 의심 시
- **정기 rotation**: 90일마다 (관리자 책임)
- Rotation 절차: `~/.config/ajin/ollama-secret` 갱신 → Caddy reload → Cloud Run env update → 검증

## 사내 데이터 보호

- `data/employees.db` (직원 명단), `data/compliance.db` (법규), `data/equipment/*.db` 등은 **PUBLIC repo 절대 commit 금지**
- `.gitignore` 가 차단함 — `setup-demo-data.py` 가 가짜 데이터로 대체
- 실 사내 데이터 사용 시 사내 담당자에게 별도 받아 로컬 `data/` 에 배치

## RBAC (역할 기반 접근 제어)

| Level | 역할 | 권한 |
|---|---|---|
| L1 | 조회전용 | 본인 정보 조회 |
| L2 | 일반 사용자 | 채팅, 검색, 문서 작성 |
| L3 | 개발자 | + 시나리오 관리, 일부 admin |
| L4 | HR | + 인사 정보 관리 |
| L5 | 시스템관리자 | 전체 |

`backend/auth/` 의 dependency injection 으로 endpoint 별 최소 role 검증. Frontend 는 `useAuthStore().user.role_level` 로 UI 표시 분기.

## 의존성 보안

- Dependabot 활성화 (`.github/dependabot.yml`)
- 매월 `npm audit` + `pip-audit` 실행 권장
- Critical CVE 발견 시 24h 이내 패치

## 인프라 보안

- Cloud Run service 는 `--ingress=all` (Firebase Hosting 만 호출 가능하게 IAM 으로 추가 제한 가능)
- Mac Ollama 는 loopback (`127.0.0.1:11434`) 만 — Caddy `:8434` 가 단일 진입점
- Caddy access log 의 secret 헤더는 `format filter` 로 redact

## 사고 대응

1. 즉시 의심 secret rotation
2. PUBLIC repo 라면 즉시 Settings → Visibility → Make Private
3. `git filter-repo` 또는 BFG 로 history 에서 노출된 파일 영구 삭제
4. force push (rewrite history) — 단, 이미 clone 한 사람 영향 명시 공지
5. Post-mortem 작성 (Notion/Wiki) — 원인·영향·재발 방지 조치
