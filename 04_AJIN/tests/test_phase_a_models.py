"""v3.3 Phase A — LLM 멀티 프로바이더 셀렉터 테스트.

검증 대상:
1. _VISIBLE_FAMILIES 에 exaone 추가 (qwen / gemma / exaone)
2. _ollama_family() 매칭 정확성
3. LLMOption 스키마가 family='exaone' 허용
4. _build_llm_options(feature='onboarding') 의 응답 구조
5. Gemini 차단 정책 — feature='draft' 만 차단, 'onboarding' 은 허용

이 테스트는 Ollama 서버 가동을 요구하지 않는다 — 모든 외부 호출을 monkeypatch 로 대체.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.routers.models import (
    _VISIBLE_FAMILIES,
    _ollama_family,
    _build_llm_options,
    _feature_b_blocks_gemini,
)
from backend.schemas.draft import LLMOption, LLMOptionsResponse


# ──────────────────────────────────────────────
# 1. _VISIBLE_FAMILIES — exaone 추가 검증
# ──────────────────────────────────────────────


def test_visible_families_includes_exaone():
    """exaone3.5 / exaone-deep 가 노출 패밀리에 등록되어야 한다."""
    assert "exaone3.5" in _VISIBLE_FAMILIES
    assert "exaone-deep" in _VISIBLE_FAMILIES
    assert _VISIBLE_FAMILIES["exaone3.5"] == "exaone"
    assert _VISIBLE_FAMILIES["exaone-deep"] == "exaone"


def test_visible_families_keeps_qwen_gemma():
    """기존 qwen3.5/gemma4 매핑이 보존되어야 한다 (회귀 방지)."""
    assert _VISIBLE_FAMILIES["qwen3.5"] == "qwen"
    assert _VISIBLE_FAMILIES["gemma4"] == "gemma"


# ──────────────────────────────────────────────
# 2. _ollama_family() — 모델 ID → 패밀리 매칭
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "model_id,expected",
    [
        ("qwen3.5:9b", "qwen"),
        ("qwen3.5:4b", "qwen"),
        ("qwen3:latest", "qwen"),
        ("gemma4:e4b", "gemma"),
        ("gemma4:e2b", "gemma"),
        ("gemma3:1b", "gemma"),
        ("exaone3.5:latest", "exaone"),
        ("exaone-deep:latest", "exaone"),
        # 미허용 패밀리 — None 반환
        ("llama3.2:1b", None),
        ("mistral:7b", None),
        ("phi3:mini", None),
    ],
)
def test_ollama_family_matching(model_id: str, expected: str | None):
    assert _ollama_family(model_id) == expected


# ──────────────────────────────────────────────
# 3. LLMOption 스키마 — family Literal 확장
# ──────────────────────────────────────────────


def test_llm_option_accepts_exaone_family():
    """family='exaone' 이 Pydantic 검증을 통과해야 한다."""
    opt = LLMOption(
        provider="ollama",
        id="exaone3.5:latest",
        label="EXAONE 3.5 7.8B (한국어 특화)",
        family="exaone",
    )
    assert opt.family == "exaone"
    assert opt.provider == "ollama"


def test_llm_option_rejects_invalid_family():
    """미허용 family 는 Pydantic ValidationError 가 발생해야 한다."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LLMOption(
            provider="ollama",
            id="llama3.2:1b",
            label="Llama 3.2",
            family="llama",  # type: ignore[arg-type]
        )


# ──────────────────────────────────────────────
# 4. _build_llm_options() — 응답 구조
# ──────────────────────────────────────────────


def _patch_installed(models: list[str]):
    """get_installed_models 패치 — Ollama 서버 호출 회피."""
    return patch("backend.routers.models.get_installed_models", return_value=models)


def test_build_llm_options_onboarding_with_full_lineup():
    """exaone 가 설치되어 있으면 옵션에 노출되어야 한다."""
    installed = [
        "qwen3.5:9b",
        "qwen3.5:4b",
        "gemma4:e4b",
        "exaone3.5:latest",
        "llama3.2:1b",  # 미허용 — 노출 X
    ]
    with _patch_installed(installed):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            res = _build_llm_options("onboarding")

    assert isinstance(res, LLMOptionsResponse)
    ollama_ids = [o.id for o in res.options if o.provider == "ollama"]
    # 허용 패밀리만 노출
    assert "qwen3.5:9b" in ollama_ids
    assert "exaone3.5:latest" in ollama_ids
    assert "gemma4:e4b" in ollama_ids
    assert "llama3.2:1b" not in ollama_ids


def test_build_llm_options_default_is_qwen_9b():
    """기본값은 qwen3.5:9b (priority 리스트 첫 번째)."""
    installed = ["qwen3.5:9b", "exaone3.5:latest", "gemma4:e4b"]
    with _patch_installed(installed):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            res = _build_llm_options("onboarding")

    assert res.default_provider == "ollama"
    assert res.default_id == "qwen3.5:9b"


def test_build_llm_options_gemini_blocked_in_draft_only():
    """Gemini 는 feature='draft' 에서만 차단, 'onboarding' 에서는 허용."""
    with _patch_installed(["qwen3.5:9b"]):
        with patch.dict(
            os.environ,
            {"GEMINI_API_KEY": "test-key", "FEATURE_B_BLOCK_GEMINI": "true"},
        ):
            draft_res = _build_llm_options("draft")
            onb_res = _build_llm_options("onboarding")

    draft_gemini = [o for o in draft_res.options if o.provider == "gemini"]
    onb_gemini = [o for o in onb_res.options if o.provider == "gemini"]

    assert len(draft_gemini) == 1
    assert draft_gemini[0].blocked is True
    assert "보안 정책" in draft_gemini[0].blocked_reason

    assert len(onb_gemini) == 1
    assert onb_gemini[0].blocked is False
    assert onb_gemini[0].available is True


def test_build_llm_options_gemini_unavailable_when_key_missing():
    """GEMINI_API_KEY 부재 → available=False + 안내 메시지."""
    with _patch_installed(["qwen3.5:9b"]):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            res = _build_llm_options("onboarding")

    gemini = [o for o in res.options if o.provider == "gemini"]
    assert len(gemini) == 1
    assert gemini[0].available is False
    assert "GEMINI_API_KEY" in gemini[0].blocked_reason


# ──────────────────────────────────────────────
# 5. _feature_b_blocks_gemini() — env 파싱
# ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False),
        ("anything-else", False),
    ],
)
def test_feature_b_blocks_gemini_env_parse(value: str, expected: bool):
    with patch.dict(os.environ, {"FEATURE_B_BLOCK_GEMINI": value}):
        assert _feature_b_blocks_gemini() is expected


def test_feature_b_blocks_gemini_default_true():
    """env 미설정 시 기본값 True (보수적 차단)."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("FEATURE_B_BLOCK_GEMINI", None)
        assert _feature_b_blocks_gemini() is True
