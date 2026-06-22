"""Tests for the WIKI embedding model -> storage/prompt registry."""

from __future__ import annotations

import pytest
from src.services import wiki_embedding_targets as targets


def test_bge_m3_target_is_raw_1024_dim() -> None:
    """bge-m3 stores 1024-dim vectors in the base table and embeds raw text."""
    target = targets.get_target("bge-m3")
    assert target.table == "wiki_chunk_embeddings"
    assert target.dimensions == 1024
    assert target.query_prompt_prefix == ""
    assert target.document_prompt_prefix == ""
    assert target.format_query("마그네슘") == "마그네슘"
    assert target.format_document("본문") == "본문"


def test_embeddinggemma_target_is_prompted_768_dim() -> None:
    """embeddinggemma stores 768-dim vectors in its own table with asymmetric prompts."""
    target = targets.get_target("embeddinggemma")
    assert target.table == "wiki_chunk_embeddings_gemma"
    assert target.dimensions == 768
    assert target.format_query("마그네슘") == "task: search result | query: 마그네슘"
    assert target.format_document("본문") == "title: none | text: 본문"


def test_get_target_unknown_model_raises_keyerror() -> None:
    """An unregistered model raises KeyError listing the known models."""
    with pytest.raises(KeyError) as excinfo:
        targets.get_target("does-not-exist")
    message = str(excinfo.value)
    assert "does-not-exist" in message
    assert "bge-m3" in message


def test_known_models_and_table_allowlist_are_consistent() -> None:
    """Every known model contributes exactly one allowlisted table."""
    models = targets.known_models()
    assert set(models) == {"bge-m3", "embeddinggemma"}
    tables = {targets.get_target(model).table for model in models}
    assert tables == set(targets.EMBEDDING_TABLES)
    assert targets.DEFAULT_EMBEDDING_MODEL == "bge-m3"
