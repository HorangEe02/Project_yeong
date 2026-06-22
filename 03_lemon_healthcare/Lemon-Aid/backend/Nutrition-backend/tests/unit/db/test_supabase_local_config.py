"""Supabase MCP and local CLI configuration tests."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]


def test_supabase_mcp_config_is_project_scoped_and_env_driven() -> None:
    """Verify MCP config uses project scoping without committed tokens."""
    config = json.loads((PROJECT_ROOT / ".mcp.json").read_text(encoding="utf-8"))

    server = config["mcpServers"]["supabase"]
    assert server["type"] == "http"
    assert server["url"].startswith("https://mcp.supabase.com/mcp?")
    assert "project_ref=${SUPABASE_PROJECT_REF}" in server["url"]
    assert "read_only=${SUPABASE_MCP_READ_ONLY}" in server["url"]
    assert "features=${SUPABASE_MCP_FEATURES}" in server["url"]
    assert "Authorization" not in server
    assert "SUPABASE_ACCESS_TOKEN" not in json.dumps(config)


def test_supabase_local_ports_avoid_default_cli_port_block() -> None:
    """Verify local Supabase ports do not collide with common 5432x projects."""
    config = tomllib.loads((PROJECT_ROOT / "supabase" / "config.toml").read_text(encoding="utf-8"))

    assert config["project_id"] == "lemon-aid-nutrition-local"
    assert config["api"]["port"] == 56321
    assert config["db"]["port"] == 56322
    assert config["db"]["shadow_port"] == 56320
    assert config["db"]["pooler"]["port"] == 56329
    assert config["studio"]["port"] == 56323
    assert config["inbucket"]["port"] == 56324


def test_supabase_learning_storage_bucket_is_private() -> None:
    """Verify local Supabase learning-image bucket is private by default."""
    config = tomllib.loads((PROJECT_ROOT / "supabase" / "config.toml").read_text(encoding="utf-8"))

    bucket = config["storage"]["buckets"]["learning-images"]
    assert bucket["public"] is False
    assert bucket["file_size_limit"] == "20MiB"
    assert bucket["allowed_mime_types"] == ["image/png", "image/jpeg", "image/webp"]
    assert bucket["objects_path"] == "./storage/learning-images"
