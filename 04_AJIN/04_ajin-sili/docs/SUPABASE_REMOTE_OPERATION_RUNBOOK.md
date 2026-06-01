# Supabase Remote Operation Runbook

## 목적

AJIN backend의 운영 DB/Storage 기준을 Firebase fallback 또는 SQLite가 아니라 Supabase Postgres와 Supabase Storage로 전환하기 위한 검증 절차입니다. 대상 Supabase project ref는 `ycjuzwltwbeudanjykag`입니다.

이 문서는 secret 값을 저장하지 않습니다. `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY`는 로컬 shell, CI secret, 또는 Cloud Run Secret Manager로만 주입합니다.

## 공식 기준

- Supabase CLI login/link/init: https://supabase.com/docs/reference/cli/introduction
- Supabase 환경 분리: https://supabase.com/docs/guides/deployment/managing-environments
- Supabase API key 종류와 secret key 취급: https://supabase.com/docs/guides/getting-started/api-keys
- Supabase `db push --dry-run`: https://supabase.com/docs/reference/cli/supabase-db-push
- Google Cloud Billing 상태 확인: https://docs.cloud.google.com/billing/docs/how-to/verify-billing-enabled
- Google Cloud Billing 연결/복구: https://docs.cloud.google.com/billing/docs/how-to/modify-project
- Cloud Run 환경변수 설정: https://docs.cloud.google.com/run/docs/configuring/services/environment-variables
- Cloud Run Secret Manager 연동: https://docs.cloud.google.com/run/docs/configuring/services/secrets

## 로컬 CLI 정상화

현재 이 저장소는 `supabase init`으로 `supabase/config.toml`을 생성해 CLI project workdir을 갖습니다. 원격 연결은 유효한 personal access token과 DB password가 있어야 진행됩니다.

```bash
supabase login --token <sbp_...>
supabase link --project-ref ycjuzwltwbeudanjykag
supabase projects list -o json
supabase db push --dry-run --linked
supabase db advisors --linked --type security --level warn
```

CLI token은 `sbp_...` 형식이어야 합니다. `~/.supabase/access-token`이 존재하더라도 CLI가 `Invalid access token format`을 반환하면 원격 프로젝트 목록, link, advisor, dry-run 모두 신뢰 가능한 검증으로 볼 수 없습니다.

## 운영 환경 계약

운영 전환 profile은 실제 `.env` 파일에 커밋하지 않습니다. 아래 값은 Cloud Run/CI secret 또는 배포 환경 변수로만 주입합니다.

```bash
SUPABASE_PROJECT_REF=ycjuzwltwbeudanjykag
APP_DB_BACKEND=postgres
DATABASE_URL=<postgres connection string from Supabase>
SUPABASE_URL=https://ycjuzwltwbeudanjykag.supabase.co
SUPABASE_SECRET_KEY=<backend-only secret or service_role key>
SUPABASE_STORAGE_BUCKET_ATTACHMENTS=ajin-attachments
SUPABASE_STORAGE_BUCKET_DRAFT_EXPORTS=ajin-draft-exports
ENABLE_SUPABASE_REALTIME=false
FIREBASE_WRITE_ENABLED=false
FIREBASE_READ_FALLBACK_ENABLED=false
```

`SUPABASE_SECRET_KEY`는 backend-only secret입니다. Supabase 공식 문서 기준 secret key는 elevated access이며 RLS를 우회할 수 있으므로 frontend bundle, 모바일 앱, 공개 문서, URL query, 로그에 노출하면 안 됩니다.

## 자동 전환 Runner

반복 가능한 전환 절차는 `scripts/supabase_cutover.py`로 실행합니다. 기본값은 dry-run이며, secret 값은 출력하지 않습니다.

```bash
make supabase-env
# .env.supabase.local에 SUPABASE_ACCESS_TOKEN, SUPABASE_SECRET_KEY를 실제 Supabase/Cloud Run secret 기준으로 채운 뒤:

make supabase-cutover-preflight
make supabase-cutover
```

`make supabase-cutover`는 다음을 순서대로 수행합니다.

1. `.env.supabase.local`과 `.env`에서 누락된 환경변수를 로드합니다.
2. `SUPABASE_PROJECT_REF`, `SUPABASE_URL`, `APP_DB_BACKEND`, Firebase fallback 차단 상태, key prefix를 fail-closed로 검증합니다.
3. `supabase login --token`, `supabase link --project-ref`, `supabase projects list -o json`을 실행합니다.
4. Alembic `upgrade head`와 `current`를 실행합니다.
5. `ajin-attachments`, `ajin-draft-exports` bucket을 생성하거나 private으로 보정합니다.
6. strict verifier, `supabase db push --dry-run --linked`, security advisor를 실행합니다.

원격 환경변수가 준비되지 않은 상태에서는 runner가 exit code `2`로 중단되어야 합니다. 이 상태는 정상적인 차단이며, secret을 채우기 전에는 원격 DB/Storage를 변경하지 않습니다.

## 로컬 Docker에서 원격 Supabase 연결

기본 `docker-compose.yml`은 기존 로컬 Docker 경로를 유지합니다. 원격 Supabase 연결은 `docker-compose.supabase.yml` override를 명시했을 때만 활성화합니다.

```bash
make supabase-docker-config
make supabase-docker-up
make supabase-docker-ps
make supabase-docker-health
```

이 override는 backend에만 `.env.supabase.local`을 주입합니다. Frontend는 계속 `/api`로 FastAPI를 호출하고, `SUPABASE_SECRET_KEY` 또는 legacy `service_role` key를 브라우저 bundle에 넣지 않습니다.

## Read-only 원격 검증

검증 스크립트는 기본적으로 read-only입니다. DB 연결은 `SELECT` 기반 metadata 조회만 수행하고, Storage는 bucket 목록 조회만 수행합니다.
`--strict`에서는 Supabase CLI 실행 가능 여부, `sbp_...` access token 형식, `supabase projects list -o json`의 대상 project 포함 여부, 로컬 `supabase link` project ref까지 함께 확인합니다.

```bash
APP_DB_BACKEND=postgres \
DATABASE_URL=<redacted> \
SUPABASE_URL=https://ycjuzwltwbeudanjykag.supabase.co \
SUPABASE_SECRET_KEY=<redacted> \
FIREBASE_WRITE_ENABLED=false \
FIREBASE_READ_FALLBACK_ENABLED=false \
.venv/bin/python scripts/verify_supabase_remote.py --strict --project-ref ycjuzwltwbeudanjykag
```

팀 공유용 보고서가 필요하면 다음처럼 생성합니다.

```bash
.venv/bin/python scripts/verify_supabase_remote.py \
  --strict \
  --project-ref ycjuzwltwbeudanjykag \
  --markdown outputs/supabase-verification/$(date +%Y-%m-%d)-remote-check.md
```

검증 실패 기준은 다음과 같습니다.

- `SUPABASE_URL`이 `https://ycjuzwltwbeudanjykag.supabase.co`와 불일치
- Supabase CLI 미설치, `SUPABASE_ACCESS_TOKEN`/CLI token 형식 오류, target project 미노출, local link ref 불일치
- `APP_DB_BACKEND=postgres`가 아님
- `DATABASE_URL` 누락 또는 read-only DB 연결 실패
- `alembic_version` 누락 또는 head revision 불일치
- 필수 테이블 `users`, `attachments`, `live_alarms`, `feedback_events`, `audit_logs` 누락
- 필수 테이블 RLS 비활성
- 민감 테이블에 `anon` 또는 `authenticated` role 권한 존재
- Storage bucket `ajin-attachments`, `ajin-draft-exports` 누락 또는 public bucket
- `SUPABASE_SECRET_KEY` 누락
- `FIREBASE_WRITE_ENABLED=true`
- `--strict`에서 `FIREBASE_READ_FALLBACK_ENABLED=true`

## Migration 적용 순서

Supabase CLI migration을 앱 schema의 단일 기준으로 사용하지 않습니다. 앱 DB schema 기준은 이 저장소의 Alembic migration입니다. Supabase CLI는 project link, remote state 조회, dry-run, security advisor 용도로만 사용합니다.

```bash
supabase db push --dry-run --linked
APP_DB_BACKEND=postgres DATABASE_URL=<redacted> make db-upgrade
APP_DB_BACKEND=postgres DATABASE_URL=<redacted> make db-current
APP_DB_BACKEND=postgres DATABASE_URL=<redacted> .venv/bin/python scripts/verify_supabase_remote.py --strict
```

## 배포 전 Gate

기존 Cloud Run canary 흐름은 유지합니다. 운영 전환 시에는 `--require-supabase`를 추가해 strict verifier 통과 전 no-traffic revision 배포도 막습니다.
이 모드에서는 no-traffic revision의 `/api/admin/system/health-extended`를 `SMOKE_ADMIN_JWT`로 호출해 실제 Cloud Run runtime이 Supabase DB/Storage secret을 받은 상태인지 확인합니다.

```bash
APP_DB_BACKEND=postgres \
DATABASE_URL=<redacted> \
SUPABASE_URL=https://ycjuzwltwbeudanjykag.supabase.co \
SUPABASE_SECRET_KEY=<redacted> \
SMOKE_ADMIN_JWT=<redacted admin JWT> \
FIREBASE_WRITE_ENABLED=false \
FIREBASE_READ_FALLBACK_ENABLED=false \
bash scripts/deploy-backend.sh --require-supabase --skip-canary
```

`SMOKE_ADMIN_JWT`가 없으면 `--require-supabase` 배포는 실패해야 합니다. 공개 `/api/health`에는 Supabase 상세 상태를 추가하지 않고, 관리자 전용 health만 사용합니다.

### Smoke Credential Contract

`Demo!2026`은 frontend mock seed와 데모 chip 전용 값입니다. Supabase/Postgres 전환 gate, Cloud Run no-traffic smoke, Firebase read fallback 제거 검증에서는 이 값을 release smoke credential로 사용하지 않습니다.

릴리즈 smoke의 인증 경로는 다음 둘 중 하나로 고정합니다.

- 로컬: gitignored bootstrap admin password file 또는 bootstrap workflow로 발급된 실제 credential 사용
- Cloud Run/tag/canary: `scripts/mint_smoke_admin_jwt.py`가 생성한 short-lived `SMOKE_ADMIN_JWT` 사용

따라서 `SYS-0001/Demo!2026`, `PE-0019/Demo!2026`의 `401`은 Supabase gate 실패로 분류하지 않고, mock/demo UX가 실제 Supabase auth와 섞이지 않도록 분리하는 신호로 취급합니다.

### Cloud Run Supabase Runtime Unblock

현재 production unblock의 선행 조건은 `ajin-cb` billing 복구입니다. Billing이 꺼져 있으면 Secret Manager API도 `BILLING_DISABLED`로 막히므로, secret/env 주입이나 runtime smoke를 진행하지 않습니다.

```bash
gcloud beta billing projects describe ajin-cb --format='json(projectId,billingEnabled,billingAccountName)'
gcloud secrets list --project ajin-cb --format='value(name)'
```

`billingEnabled=true`가 확인되면 `AJIN_JWT_SECRET`을 운영 source of truth로 고정합니다. 기존 Secret Manager 값을 복구할 수 있으면 보존하고, 없으면 새 32-byte 이상 값을 생성합니다. 새 값을 만들면 기존 로그인 세션과 기존 JWT는 무효화될 수 있습니다.

```bash
mkdir -p secrets
gcloud secrets versions access latest \
  --secret=AJIN_JWT_SECRET \
  --project=ajin-cb > secrets/ajin-jwt-secret.txt
chmod 600 secrets/ajin-jwt-secret.txt
```

Secret Manager에 기존 `AJIN_JWT_SECRET`이 없다면 아래처럼 로컬 파일을 만들고, 이후 helper가 Secret Manager에 버전을 추가하게 합니다.

```bash
mkdir -p secrets
openssl rand -hex 32 > secrets/ajin-jwt-secret.txt
chmod 600 secrets/ajin-jwt-secret.txt
```

Cloud Run runtime secret은 backend-only 값만 사용합니다. Supabase core secret은 필수이고, Feature D 공식 API secret은 존재하는 항목만 주입합니다.

- `DATABASE_URL` ← Secret Manager `AJIN_DATABASE_URL:latest`
- `SUPABASE_SECRET_KEY` ← Secret Manager `AJIN_SUPABASE_SECRET_KEY:latest`
- `AJIN_JWT_SECRET` ← Secret Manager `AJIN_JWT_SECRET:latest`
- `LAW_GO_KR_OC` ← Secret Manager `law-oc:latest`
- `CUSTOMS_API_KEY` ← Secret Manager `customs-api-key:latest`
- `DART_API_KEY` ← Secret Manager `dart-api-key:latest`

`CUSTOMS_API_KEY`를 아직 발급하지 않은 경우 `customs-api-key`는 만들지 않고 배포할 수 있습니다. 이때 Feature D global trade crawler는 curated fallback 상태로 동작하고, `make feature-d-release-check` strict gate는 `global_trade:missing_CUSTOMS_API_KEY`를 release blocker로 유지합니다.

`SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `SMOKE_ADMIN_JWT`는 deploy/local-only 값이므로 Cloud Run runtime에 넣지 않습니다.

```bash
set -a
source .env.supabase.local
set +a

.venv/bin/python scripts/configure_cloudrun_supabase_runtime.py \
  --jwt-secret-file secrets/ajin-jwt-secret.txt

.venv/bin/python scripts/configure_cloudrun_supabase_runtime.py \
  --jwt-secret-file secrets/ajin-jwt-secret.txt \
  --apply
```

`scripts/configure_cloudrun_supabase_runtime.py`는 기본 dry-run입니다. `--apply`에서만 다음 작업을 수행합니다.

1. `ajin-cb` billing enabled 상태 확인
2. Secret Manager secret `AJIN_DATABASE_URL`, `AJIN_SUPABASE_SECRET_KEY`, `AJIN_JWT_SECRET` 생성 또는 확인
3. 값이 있는 Feature D official API secret `law-oc`, `customs-api-key`, `dart-api-key` 생성 또는 확인
4. 각 secret에 새 version 추가
5. Cloud Run service account에 각 secret 단위 `roles/secretmanager.secretAccessor` 부여
6. 현재 Cloud Run service에 deploy-only/local-only env가 잘못 들어가 있지 않은지 확인

그 다음 short-lived smoke token을 생성하고 no-traffic revision deploy를 실행합니다.

```bash
.venv/bin/python scripts/mint_smoke_admin_jwt.py \
  --jwt-secret-file secrets/ajin-jwt-secret.txt \
  --overwrite

SMOKE_ADMIN_JWT="$(cat secrets/smoke-admin.jwt)" \
bash scripts/deploy-backend.sh --mode slim --require-supabase --skip-canary
```

`--mode slim --require-supabase`는 `gcloud run deploy --source=.`에 `--update-env-vars`와 `--update-secrets`를 붙여 no-traffic revision에 Supabase runtime config를 주입합니다. `--mode full --require-supabase`는 Cloud Build secret/env 전달 설계가 별도로 끝날 때까지 차단합니다.

배포 후 현재 Cloud Run revision이 기대 mapping을 갖는지 별도 확인하려면 다음을 실행합니다.

```bash
.venv/bin/python scripts/configure_cloudrun_supabase_runtime.py \
  --jwt-secret-file secrets/ajin-jwt-secret.txt \
  --verify-existing-mapping
```

권장 전환 순서는 다음과 같습니다.

1. Supabase CLI access token 정상화
2. 원격 read-only 검증
3. `supabase db push --dry-run --linked`
4. Alembic upgrade
5. remote strict verification
6. Cloud Run no-traffic deploy with `--require-supabase`
7. tag URL smoke test
8. canary
9. production promote
10. Firebase read fallback off

## Admin Health 확인

`/api/admin/system/health-extended`의 `external.supabase`는 secret 없는 상태만 노출합니다.

- `project_ref_configured`
- `url_matches_project_ref`
- `db_backend`
- `database_connected`
- `alembic_current`
- `storage_configured`
- `storage_buckets_present`

응답에는 raw `DATABASE_URL`, password, `SUPABASE_SECRET_KEY`, access token이 포함되면 안 됩니다.
