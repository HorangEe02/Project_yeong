"""``src.config.Settings`` 단위 테스트 — D2/D3/D4 수리 검증 포함.

Reference:
    /Users/yeong/.claude/plans/ocr-yolo-sprightly-neumann.md §3.1 D2-D4
    /Users/yeong/.claude/plans/lemon-track-b/phase-00-bootstrap.md Step 6
"""

from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError
from src.config import Settings, get_settings


def test_settings_loads_with_required_env() -> None:
    """필수 env(DATABASE_URL)가 주어지면 정상 로드된다."""
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.environment == "development"
    assert s.llm_provider == "ollama"
    assert s.ollama_base_url == "http://127.0.0.1:11434"


def test_d2_no_allow_external_llm_field() -> None:
    """D2 수리: Settings에 ``allow_external_llm`` 필드가 더 이상 존재하지 않는다."""
    assert "allow_external_llm" not in Settings.model_fields


def test_d2_llm_provider_is_ollama_only() -> None:
    """D2 수리: ``llm_provider`` 는 ``Literal["ollama"]`` 단일값."""
    field = Settings.model_fields["llm_provider"]
    assert get_args(field.annotation) == ("ollama",)


def test_d3_extra_forbid_rejects_unknown_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D3 수리: 정의되지 않은 키워드 인자가 들어오면 ``ValidationError`` 로 거부."""
    del monkeypatch  # autouse 픽스처가 이미 안전 env를 주입했음
    with pytest.raises(ValidationError) as exc_info:
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            totally_unknown_field="x",
        )
    msg = str(exc_info.value)
    assert "totally_unknown_field" in msg.lower() or "extra_forbidden" in msg


def test_d4_retention_split_into_three_fields() -> None:
    """D4 수리: ``image_retention_*`` 가 3개로 분리되었고 단일 변수는 부재."""
    fields = Settings.model_fields
    assert "image_retention_temporary_hours" in fields
    assert "image_retention_history_days" in fields
    assert "image_retention_training_days" in fields
    assert "image_retention_days" not in fields


def test_d4_default_retention_values_match_policy() -> None:
    """D4 수리: 기본값이 docs/17 §5 정책(임시 0h / 히스토리 90d / 학습 0d)에 부합."""
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.image_retention_temporary_hours == 0
    assert s.image_retention_history_days == 90
    assert s.image_retention_training_days == 0


def test_gate_flags_default_false() -> None:
    """docs/17 §9: 모든 게이트 플래그는 기본 ``False``."""
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.enable_multimodal_llm is False
    assert s.enable_vision_classifier is False
    assert s.enable_image_learning_pipeline is False
    assert s.enable_pgvector_storage is False


def test_get_settings_is_cached() -> None:
    """``get_settings`` 는 ``lru_cache`` 로 동일 인스턴스를 반환한다."""
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
