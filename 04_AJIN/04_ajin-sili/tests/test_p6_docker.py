"""P6 Phase 1 — Docker 컨테이너화 정합성 테스트.

런타임 docker daemon 없이 파일 존재 + 정합성만 검증.
컨테이너 실 실행 검증은 docs/DOCKER.md 의 'make up + make health' 수동.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─────────────────────────────────────────────────────────────
# 파일 존재
# ─────────────────────────────────────────────────────────────


class TestFiles:
    @pytest.mark.parametrize("path", [
        "Dockerfile",
        "frontend/Dockerfile",
        ".dockerignore",
        "docker-compose.yml",
        "docker-compose.cloud.yml",
        "nginx/rp.conf",
        ".env.docker.example",
        "Makefile",
        "scripts/setup_host_ollama.sh",
        "docs/DOCKER.md",
    ])
    def test_phase1_file_present(self, path):
        assert (PROJECT_ROOT / path).exists(), f"missing: {path}"


# ─────────────────────────────────────────────────────────────
# Dockerfile lint
# ─────────────────────────────────────────────────────────────


class TestDockerfile:
    def test_multistage_targets_exist(self):
        text = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert re.search(r"FROM\s+\S+\s+AS\s+slim", text), "slim stage 없음"
        assert re.search(r"FROM\s+\S+\s+AS\s+full", text), "full stage 없음"

    def test_exposes_port(self):
        text = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "EXPOSE 8080" in text

    def test_copies_features_and_backend(self):
        text = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "COPY backend/" in text
        assert "COPY features/" in text


# ─────────────────────────────────────────────────────────────
# docker-compose.yml 정합성 (PyYAML)
# ─────────────────────────────────────────────────────────────


class TestCompose:
    @pytest.fixture
    def compose(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML 미설치 — 정합성 lint skip")
        return yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    def test_required_services(self, compose):
        services = compose.get("services") or {}
        for required in ("backend", "frontend", "redis", "rp"):
            assert required in services, f"service 누락: {required}"

    def test_backend_uses_host_ollama(self, compose):
        be = compose["services"]["backend"]
        env = be.get("environment") or {}
        assert env.get("OLLAMA_BASE_URL", "").endswith(":11434")
        assert "host.docker.internal" in env.get("OLLAMA_BASE_URL", "") or "ollama" in env.get("OLLAMA_BASE_URL", "")

    def test_rp_exposes_8080(self, compose):
        rp = compose["services"]["rp"]
        ports = rp.get("ports") or []
        assert any("8080:80" in p for p in ports), f"rp port 매핑 누락: {ports}"

    def test_redis_has_healthcheck(self, compose):
        r = compose["services"]["redis"]
        assert "healthcheck" in r

    def test_extra_hosts_for_linux_compat(self, compose):
        be = compose["services"]["backend"]
        eh = be.get("extra_hosts") or []
        assert any("host.docker.internal:host-gateway" in str(h) for h in eh)

    def test_env_file_optional(self, compose):
        """env_file required:false — 파일 없어도 시작 가능."""
        be = compose["services"]["backend"]
        envs = be.get("env_file") or []
        # env_file 가 list of dict (long form) 인지 확인
        if envs and isinstance(envs[0], dict):
            assert all(e.get("required") is False for e in envs)


class TestCloudOverride:
    @pytest.fixture
    def cloud(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML 미설치")
        return yaml.safe_load(
            (PROJECT_ROOT / "docker-compose.cloud.yml").read_text(encoding="utf-8"),
        )

    def test_ollama_service_active(self, cloud):
        """Phase 2 — ollama-large + ollama-fast 분리, 둘 다 NVIDIA 자원 reservation."""
        services = cloud.get("services") or {}
        for svc_name in ("ollama-large", "ollama-fast"):
            assert svc_name in services, f"{svc_name} service 누락"
            svc = services[svc_name]
            deploy = svc.get("deploy") or {}
            resources = deploy.get("resources") or {}
            reservations = resources.get("reservations") or {}
            devices = reservations.get("devices") or []
            assert any(d.get("driver") == "nvidia" for d in devices), \
                f"{svc_name} NVIDIA reservation 누락"

    def test_backend_swaps_ollama_url(self, cloud):
        """Phase 2 — backend 가 LARGE/FAST 두 endpoint 모두 설정 + OLLAMA_BASE_URL 폴백."""
        be = (cloud.get("services") or {}).get("backend") or {}
        env = be.get("environment") or {}
        assert env.get("OLLAMA_BASE_URL_LARGE") == "http://ollama-large:11434"
        assert env.get("OLLAMA_BASE_URL_FAST") == "http://ollama-fast:11434"
        # Phase 1 호환 — OLLAMA_BASE_URL 도 LARGE 로 폴백
        assert env.get("OLLAMA_BASE_URL") == "http://ollama-large:11434"


# ─────────────────────────────────────────────────────────────
# .dockerignore — 핵심 항목 검증
# ─────────────────────────────────────────────────────────────


class TestDockerignore:
    def test_excludes_pycache_and_git(self):
        text = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
        assert "__pycache__/" in text
        assert ".git/" in text


# ─────────────────────────────────────────────────────────────
# nginx rp.conf
# ─────────────────────────────────────────────────────────────


class TestNginxRp:
    def test_routes_api_to_backend(self):
        text = (PROJECT_ROOT / "nginx/rp.conf").read_text(encoding="utf-8")
        assert "location /api/" in text
        assert "backend_upstream" in text or "backend:8080" in text

    def test_routes_root_to_frontend(self):
        text = (PROJECT_ROOT / "nginx/rp.conf").read_text(encoding="utf-8")
        assert "frontend_upstream" in text or "frontend:80" in text

    def test_healthz_aliases_backend(self):
        text = (PROJECT_ROOT / "nginx/rp.conf").read_text(encoding="utf-8")
        assert "/healthz" in text
        assert "/api/health" in text


# ─────────────────────────────────────────────────────────────
# setup_host_ollama.sh syntax
# ─────────────────────────────────────────────────────────────


class TestSetupScript:
    def test_bash_syntax_valid(self):
        import subprocess
        path = PROJECT_ROOT / "scripts" / "setup_host_ollama.sh"
        result = subprocess.run(
            ["bash", "-n", str(path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"syntax 오류:\n{result.stderr}"

    def test_executable(self):
        import os
        path = PROJECT_ROOT / "scripts" / "setup_host_ollama.sh"
        assert os.access(path, os.X_OK), "+x 권한 누락"


# ─────────────────────────────────────────────────────────────
# Makefile — 핵심 target 존재
# ─────────────────────────────────────────────────────────────


class TestMakefile:
    def test_required_targets(self):
        text = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
        for target in ("setup", "up", "down", "logs", "ps", "test", "health", "shell"):
            assert re.search(rf"^{target}:", text, re.MULTILINE), f"target 누락: {target}"
