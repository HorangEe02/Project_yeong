# AJIN Compliance — Phase 1 운영 단축 명령.
# 사용:
#   make setup      # Mac 호스트 Ollama 셋업 + .env.docker 복사
#   make up         # 컨테이너 빌드 + 시작 (background)
#   make logs       # tail
#   make ps         # 상태
#   make health     # /healthz curl
#   make test       # 호스트 .venv pytest
#   make test-docker # 컨테이너 pytest
#   make shell      # backend bash
#   make down       # 정지 (data 보존)
#   make clean      # 정지 + volume 제거 (data 영구 삭제)

VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_REQUIREMENTS_STAMP := $(VENV)/.requirements.stamp
UV_CACHE_DIR ?= .uv-cache
ALEMBIC_BIN := $(VENV)/bin/alembic
PYTEST_ARGS ?= tests/ -q
SUPABASE_PROJECT_REF ?= ycjuzwltwbeudanjykag
SUPABASE_COMPOSE_FILES ?= -f docker-compose.yml -f docker-compose.supabase.yml
FEATURE_C_RELEASE_LLM_PRIMARY ?= ollama
PGVECTOR_PREREQ_ARGS ?=
PGVECTOR_RELEASE_ARGS ?=

.PHONY: setup up down logs ps shell backend-venv test test-collect test-docker openapi-docs openapi-docs-check db-upgrade db-current supabase-env supabase-verify supabase-cutover-preflight supabase-cutover supabase-db-current supabase-db-upgrade supabase-advisors supabase-release-check pgvector-prereq-check pgvector-release-check pgvector-reindex-documents release-security-check feature-a-consistency-check feature-a-consistency-repair feature-a-doc-index-repair feature-b-release-check feature-c-release-check feature-d-release-check feature-e-release-check feature-f-release-check supabase-docker-config supabase-docker-up supabase-docker-ps supabase-docker-health build rebuild health clean lint help diagnose-equipment seed-equipment diagnose-compliance seed-compliance verify ingest-inspection migrate-inspection-synthetic demo-check demo-check-fast demo-check-json

help:
	@echo "AJIN Compliance — Phase 1 Docker"
	@echo ""
	@echo "주요 명령:"
	@echo "  make setup      Mac 호스트 Ollama 설치 + 모델 pull + .env.docker 복사"
	@echo "  make up         docker compose up -d --build"
	@echo "  make logs       tail -f 로그"
	@echo "  make ps         service 상태"
	@echo "  make health     /healthz curl"
	@echo "  make backend-venv 호스트 .venv 생성 + requirements 설치"
	@echo "  make test-collect pytest collection 재현"
	@echo "  make test       호스트 .venv pytest"
	@echo "  make test-docker 컨테이너 안 pytest"
	@echo "  make openapi-docs OpenAPI JSON + docs/API.md 재생성"
	@echo "  make openapi-docs-check OpenAPI 문서 stale 여부 확인"
	@echo "  make db-upgrade  DATABASE_URL 대상 Alembic migration 적용"
	@echo "  make db-current  DATABASE_URL 대상 Alembic 현재 revision 확인"
	@echo "  make supabase-env Brand-New-update/supabase-ajin.md에서 .env.supabase.local 생성"
	@echo "  make supabase-verify Supabase 원격 read-only 검증 보고서 생성"
	@echo "  make supabase-cutover-preflight Supabase 전환 env/secret 준비상태 점검"
	@echo "  make supabase-cutover Supabase login/link + Alembic + bucket + strict gate 실행"
	@echo "  make supabase-release-check Supabase strict gate + CLI dry-run/advisor"
	@echo "  make pgvector-prereq-check Supabase pgvector migration/local inventory prereq gate"
	@echo "  make pgvector-release-check Supabase pgvector remote schema/RLS gate"
	@echo "  make pgvector-reindex-documents Feature A 문서 인덱스를 Supabase pgvector로 적재"
	@echo "  make release-security-check frontend secret leak + Supabase RLS/Data API guard"
	@echo "  make feature-a-consistency-check Feature A SQLite/Chroma/Postgres index gate"
	@echo "  make feature-a-consistency-repair Feature A 직원 index 빠른 자동수리"
	@echo "  make feature-b-release-check Feature B attachment/mail/template release gate"
	@echo "  make feature-c-release-check Feature C endpoint/LLM/content release gate"
	@echo "  make feature-d-release-check Feature D live-source/citation/flag release gate"
	@echo "  make feature-e-release-check Feature E cookie/session/auth release gate"
	@echo "  make feature-f-release-check Feature F equipment/SPC release gate"
	@echo "  make supabase-docker-up Supabase override로 frontend/backend Docker 실행"
	@echo "  make shell      backend bash"
	@echo "  make down       정지 (data 보존)"
	@echo "  make clean      정지 + volume 제거"

setup:
	@echo "[setup] Mac 호스트 Ollama 셋업…"
	@bash scripts/setup_host_ollama.sh
	@if [ ! -f .env ]; then \
		echo "ERROR: .env 가 없습니다 — 먼저 .env 를 작성하세요"; exit 1; \
	fi
	@if [ ! -f .env.docker ]; then \
		cp .env.docker.example .env.docker; \
		echo "[setup] .env.docker 생성 (.env.docker.example 복사) — 필요 시 편집"; \
	else \
		echo "[setup] .env.docker 이미 존재 — skip"; \
	fi
	@echo "[setup] 완료. 다음: make up"

up:
	docker compose up -d --build
	@echo ""
	@echo "✓ 시작 완료 — http://localhost:8080"
	@echo "  health: make health"
	@echo "  logs:   make logs"

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

health:
	@echo "[health] /healthz …"
	@curl -fsS http://localhost:8080/healthz || echo "rp 가 아직 준비 중"
	@echo ""
	@echo "[health] backend /api/health …"
	@curl -fsS http://localhost:8080/api/health | python3 -m json.tool || true

shell:
	docker compose exec backend bash

backend-venv:
	@# 호스트 pytest 재현 환경. Python 3.13+ 는 기본 테스트 런타임에서 제외한다.
	@if [ ! -x "$(VENV_PYTHON)" ]; then \
		if command -v uv >/dev/null 2>&1; then \
			UV_CACHE_DIR="$(UV_CACHE_DIR)" uv venv --python 3.12 "$(VENV)"; \
		elif command -v python3.12 >/dev/null 2>&1; then \
			python3.12 -m venv "$(VENV)"; \
		elif command -v python3.11 >/dev/null 2>&1; then \
			python3.11 -m venv "$(VENV)"; \
		else \
			echo "ERROR: Python 3.12 또는 3.11 런타임이 필요합니다. Python 3.13은 기본 pytest 런타임으로 사용하지 않습니다."; \
			exit 1; \
		fi; \
	fi
	@VENV_PY_VERSION=$$($(VENV_PYTHON) -c 'import sys; print(".".join(map(str, sys.version_info[:2])))'); \
	case "$$VENV_PY_VERSION" in \
		3.11|3.12) ;; \
		*) echo "ERROR: $(VENV) Python $$VENV_PY_VERSION 감지. .venv는 Python 3.11 또는 3.12로 재생성하세요."; exit 1 ;; \
	esac
	@if [ ! -f "$(VENV_REQUIREMENTS_STAMP)" ] || [ requirements.txt -nt "$(VENV_REQUIREMENTS_STAMP)" ]; then \
		set -e; \
		if $(VENV_PYTHON) -m pip --version >/dev/null 2>&1; then \
			$(VENV_PYTHON) -m pip install --upgrade pip; \
			$(VENV_PYTHON) -m pip install -r requirements.txt; \
		elif command -v uv >/dev/null 2>&1; then \
			UV_CACHE_DIR="$(UV_CACHE_DIR)" uv pip install --python "$(VENV_PYTHON)" -r requirements.txt; \
		else \
			echo "ERROR: $(VENV) 안에 pip가 없고 uv도 사용할 수 없습니다."; \
			exit 1; \
		fi; \
		touch "$(VENV_REQUIREMENTS_STAMP)"; \
	else \
		echo "[backend-venv] requirements.txt 변경 없음 — 설치 생략"; \
	fi

test: backend-venv
	@# 호스트 .venv 기준 pytest. 사용: make test PYTEST_ARGS="tests/test_x.py -q"
	$(VENV_PYTHON) -m pytest $(PYTEST_ARGS)

test-collect: backend-venv
	@# collection/import 실패를 먼저 재현한다.
	$(VENV_PYTHON) -m pytest --collect-only $(PYTEST_ARGS)

openapi-docs: backend-venv
	@# FastAPI app.openapi() 기준으로 문서 산출물을 재생성한다.
	$(VENV_PYTHON) scripts/generate_openapi_docs.py

openapi-docs-check: backend-venv
	@# 생성 결과와 커밋된 문서 산출물이 같은지 확인한다.
	$(VENV_PYTHON) scripts/generate_openapi_docs.py --check

db-upgrade: backend-venv
	@# 사용: APP_DB_BACKEND=postgres DATABASE_URL=postgresql://... make db-upgrade
	$(ALEMBIC_BIN) upgrade head

db-current: backend-venv
	@# 사용: APP_DB_BACKEND=postgres DATABASE_URL=postgresql://... make db-current
	$(ALEMBIC_BIN) current

supabase-verify: backend-venv
	@# 사용: APP_DB_BACKEND=postgres DATABASE_URL=... SUPABASE_URL=... SUPABASE_SECRET_KEY=... make supabase-verify
	$(VENV_PYTHON) scripts/verify_supabase_remote.py --project-ref "$(SUPABASE_PROJECT_REF)" --markdown "outputs/supabase-verification/$$(date +%F)-remote-check.md"

supabase-env: backend-venv
	@# Brand-New-update/supabase-ajin.md 에서 gitignored .env.supabase.local 을 생성한다. secret 값은 출력하지 않는다.
	$(VENV_PYTHON) scripts/import_supabase_ajin_env.py ../Brand-New-update/supabase-ajin.md --output .env.supabase.local

supabase-cutover-preflight: backend-venv
	@# 사용: make supabase-cutover-preflight [SUPABASE_CUTOVER_ARGS="--env-file .env.supabase.local"]
	$(VENV_PYTHON) scripts/supabase_cutover.py --project-ref "$(SUPABASE_PROJECT_REF)" $(SUPABASE_CUTOVER_ARGS)

supabase-cutover: backend-venv
	@# 사용: make supabase-cutover [SUPABASE_CUTOVER_ARGS="--env-file .env.supabase.local"]
	$(VENV_PYTHON) scripts/supabase_cutover.py --apply --project-ref "$(SUPABASE_PROJECT_REF)" $(SUPABASE_CUTOVER_ARGS)

supabase-db-current: db-current
	@# Supabase/Postgres DATABASE_URL 대상 Alembic 현재 revision 확인 alias.

supabase-db-upgrade: db-upgrade
	@# Supabase/Postgres DATABASE_URL 대상 Alembic migration 적용 alias.

supabase-advisors:
	@# Supabase CLI link/token 필요. 민감 권한과 보안 advisor를 배포 전 확인한다.
	supabase db advisors --linked --type security --level warn

supabase-release-check: backend-venv
	@# 운영 전환 gate: read-only verifier 통과 후 Supabase CLI dry-run/advisor 확인.
	$(VENV_PYTHON) scripts/verify_supabase_remote.py --strict --project-ref "$(SUPABASE_PROJECT_REF)"
	supabase db push --dry-run --linked
	supabase db advisors --linked --type security --level warn

pgvector-prereq-check: backend-venv
	@# Chroma/Postgres 전환 1단계: local pgvector migration + Chroma/BM25 inventory 확인.
	$(VENV_PYTHON) scripts/verify_pgvector_prereq.py --strict --skip-remote --markdown "outputs/supabase-verification/$$(date +%F)-pgvector-prereq.md" $(PGVECTOR_PREREQ_ARGS)

pgvector-release-check: backend-venv
	@# Chroma/Postgres 전환 release gate: remote pgvector schema/RLS/client grant 상태 확인.
	$(VENV_PYTHON) scripts/verify_pgvector_prereq.py --strict --require-remote --markdown "outputs/supabase-verification/$$(date +%F)-pgvector-release.md" $(PGVECTOR_RELEASE_ARGS)

pgvector-reindex-documents: backend-venv
	@# DATABASE_URL + APP_DB_BACKEND=postgres + Ollama embedding backend 필요.
	VECTOR_WRITE_MODE=postgres $(VENV_PYTHON) -m features.search.indexer

release-security-check: backend-venv
	@# Firebase 제거 전 운영 보안 gate: frontend secret 노출 + Supabase RLS/Data API 상태 확인.
	$(VENV_PYTHON) scripts/verify_release_security.py --include-supabase-remote --strict --project-ref "$(SUPABASE_PROJECT_REF)"

feature-a-consistency-check: backend-venv
	@# Feature A release gate: SQLite employees / FTS5 / Chroma / Postgres mirror / BM25 일관성 확인.
	$(VENV_PYTHON) scripts/verify_feature_a_consistency.py --strict --markdown "outputs/feature-a-consistency/$$(date +%F)-feature-a-consistency.md"

feature-a-consistency-repair: backend-venv
	@# Feature A 빠른 수리: FTS5 rebuild + real active 직원 Chroma/Postgres upsert.
	$(VENV_PYTHON) scripts/verify_feature_a_consistency.py --strict --repair --markdown "outputs/feature-a-consistency/$$(date +%F)-feature-a-consistency.md"

feature-a-doc-index-repair: backend-venv
	@# Feature A 문서 Chroma/BM25 full rebuild 허용. 임베딩 backend 가용성 필요.
	$(VENV_PYTHON) scripts/verify_feature_a_consistency.py --strict --repair --repair-documents --markdown "outputs/feature-a-consistency/$$(date +%F)-feature-a-consistency.md"

feature-b-release-check: backend-venv
	@# Feature B release gate: attachment ownership + mail guard + priority template review posture.
	$(VENV_PYTHON) scripts/verify_feature_b_release.py --strict --markdown "outputs/feature-b-verification/$$(date +%F)-feature-b-release.md"

feature-c-release-check: backend-venv
	@# Feature C release gate: endpoint surface + LLM cost/failure posture + content review posture.
	LLM_ROUTER_PRIMARY="$(FEATURE_C_RELEASE_LLM_PRIMARY)" $(VENV_PYTHON) scripts/verify_feature_c_release.py --strict --markdown "outputs/feature-c-verification/$$(date +%F)-feature-c-release.md"

feature-d-release-check: backend-venv
	@# Feature D release gate: D1 surface + official live probes + citation/flag/scheduler posture.
	$(VENV_PYTHON) scripts/verify_feature_d_release.py --strict --markdown "outputs/feature-d-verification/$$(date +%F)-feature-d-release.md"

feature-e-release-check: backend-venv
	@# Feature E release gate: cookie auth + CSRF + production session/default-account posture.
	$(VENV_PYTHON) scripts/verify_feature_e_release.py --strict --markdown "outputs/feature-e-verification/$$(date +%F)-feature-e-release.md"

feature-f-release-check: backend-venv
	@# Feature F release gate: equipment RBAC + PLC stream contract + offline field queue posture.
	$(VENV_PYTHON) scripts/verify_feature_f_release.py --strict --markdown "outputs/feature-f-verification/$$(date +%F)-feature-f-release.md"

supabase-docker-config:
	@# secret 출력 방지를 위해 config 내용은 출력하지 않고 유효성만 검사한다.
	docker compose $(SUPABASE_COMPOSE_FILES) config -q
	@echo "✓ Supabase Docker compose config valid"

supabase-docker-up:
	docker compose $(SUPABASE_COMPOSE_FILES) up -d --build
	@echo ""
	@echo "✓ Supabase Docker 시작 완료 — http://localhost:8080"
	@echo "  health: make supabase-docker-health"
	@echo "  ps:     make supabase-docker-ps"

supabase-docker-ps:
	docker compose $(SUPABASE_COMPOSE_FILES) ps

supabase-docker-health:
	@echo "[health] /healthz …"
	@curl -fsS http://localhost:8080/healthz || echo "rp 가 아직 준비 중"
	@echo ""
	@echo "[health] backend /api/health …"
	@curl -fsS http://localhost:8080/api/health | python3 -m json.tool || true

test-docker:
	@# 컨테이너(Python 3.11+) 안에서 pytest. prod 이미지는 그대로 두고 run 컨테이너에 테스트 의존성만 설치한다.
	@# 사용: make test-docker [ARGS="-k compliance_alarm -v"]
	docker compose run --rm \
		-v $(PWD)/backend:/app/backend:ro \
		-v $(PWD)/core:/app/core:ro \
		-v $(PWD)/features:/app/features:ro \
		-v $(PWD)/config:/app/config:ro \
		-v $(PWD)/config.py:/app/config.py:ro \
		-v $(PWD)/tests:/app/tests:ro \
		-v $(PWD)/scripts:/app/scripts:ro \
		-v $(PWD)/requirements.txt:/app/requirements.txt:ro \
		--no-deps backend \
		sh -lc 'if ! python -c "import pytest" >/dev/null 2>&1; then python -m pip install --no-cache-dir -r requirements.txt; fi; python -m pytest tests/ -q $(ARGS)'

test-e2e:
	@# 컨테이너 E2E — 인증 불필요 endpoint 만 (실 endpoint 는 RBAC 정상 동작)
	@echo "[1/3] /healthz (rp + backend)"
	@curl -fsS http://localhost:8080/healthz | python3 -m json.tool
	@echo ""
	@echo "[2/3] / (frontend SPA)"
	@curl -fsS -o /dev/null -w "  HTTP %{http_code} | size %{size_download}B\n" http://localhost:8080/
	@echo ""
	@echo "[3/3] /api/compliance/scenarios (인증 401 기대 — RBAC 정상 동작 검증)"
	@curl -sS -o /dev/null -w "  HTTP %{http_code} (401 expected)\n" http://localhost:8080/api/compliance/scenarios

build:
	docker compose build

rebuild:
	docker compose build --no-cache

lint:
	@docker compose config -q && echo "✓ docker-compose.yml 유효"
	@nginx -t -c $(PWD)/nginx/rp.conf 2>/dev/null || echo "(nginx 호스트 미설치 — 컨테이너 안에서 lint 됨)"

clean:
	docker compose down -v
	@echo "✓ volume 제거 완료 (data 디렉토리는 bind mount 라 보존됨)"

diagnose-equipment:
	@echo "[diagnose] Feature F endpoint + DB 진단…"
	@python3 scripts/diagnose_equipment.py --base-url $${AJIN_BASE_URL:-http://localhost:8000}

seed-equipment:
	@echo "[seed] Feature F 데이터 시드 6종…"
	@python3 scripts/seed_molds_db.py
	@python3 scripts/seed_error_history.py
	@python3 scripts/generate_spc_ml_data.py
	@python3 scripts/generate_mold_ml_data.py
	@python3 scripts/seed_spc_demo.py
	@python3 scripts/seed_inspection_logs.py
	@echo "✓ seed 완료 — 다음: make diagnose-equipment"

diagnose-compliance:
	@echo "[diagnose] Feature D 컴플라이언스 알람 진단…"
	@python3 scripts/diagnose_compliance_alarms.py

seed-compliance:
	@echo "[seed] Feature D 알람 시연 데이터 시드…"
	@python3 scripts/seed_demo_compliance_alarm.py --reset
	@echo "✓ seed 완료 — 다음: make diagnose-compliance"

verify:
	@# v4.1+v4.2+v4.3 자동 검증 — JWT 환경변수 필요
	@# 사용: JWT=$$(cat /tmp/jwt) make verify
	@bash scripts/verify_v41_p41.sh

ingest-inspection:
	@# 사용: make ingest-inspection FILE=path/to/file.csv [DRY=1]
	@if [ -z "$(FILE)" ]; then echo "FILE 인자 필요: make ingest-inspection FILE=path.csv"; exit 1; fi
	@python3 scripts/ingest_inspection_csv.py "$(FILE)" $(if $(DRY),--dry-run,)

migrate-inspection-synthetic:
	@# Phase 4 — 합성 inspection_logs 삭제 + 자연키 unique index. 백업 자동.
	@# 사용: make migrate-inspection-synthetic                # dry-run 보고
	@#       make migrate-inspection-synthetic APPLY=1         # 실 삭제
	@python3 scripts/migrate_inspection_drop_synthetic.py $(if $(APPLY),--apply,)

migrate-data-lineage:
	@# P1 — A/E/F synthetic/demo 출처 라벨링. 삭제 없음, 기본은 dry-run.
	@# 사용: make migrate-data-lineage            # dry-run
	@#       make migrate-data-lineage APPLY=1    # 컬럼/backfill/CSV sidecar 적용
	@python3 scripts/migrate_data_lineage.py $(if $(APPLY),--apply,)

demo-check:
	@# 시연 E2E 자동 검증 — 4 영역 19 체크 (5~7분).
	@# 사용: make demo-check                        # strict (WARN도 FAIL)
	@#       make demo-check DEMO_ARGS="--soft"     # soft (WARN 허용)
	python3 scripts/demo_check.py --strict $(DEMO_ARGS)

demo-check-fast:
	@# 시연 D-Day T-120 빠른 점검 — 영역 A+B만 (1~2분).
	@# Vercel 체크 생략 (오프라인 시연 환경).
	python3 scripts/demo_check.py --fast --no-vercel $(DEMO_ARGS)

demo-check-json:
	@# CI 통합 JSON 출력 → /tmp/demo_check.json
	python3 scripts/demo_check.py --strict --json > /tmp/demo_check.json
	@echo "[demo-check-json] 결과 저장: /tmp/demo_check.json"
	@python3 -c "import json,sys; r=json.load(open('/tmp/demo_check.json')); s=r['summary']; print(f\"  결과: {s['verdict']}  PASS={s['passed']} WARN={s['warned']} FAIL={s['failed']}\")"
