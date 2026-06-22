"""Local LLM-WIKI retrieval tests."""

from __future__ import annotations

from pathlib import Path

from src.config import Settings
from src.services.llm_wiki_retrieval import retrieve_llm_wiki_context


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    """Return settings pointing at a temporary WIKI root.

    Args:
        tmp_path: Temporary WIKI root.
        overrides: Optional Settings field overrides.

    Returns:
        Settings object for file-based retrieval tests.
    """
    values = {
        "llm_wiki_path": tmp_path,
        "llm_wiki_retrieval_enabled": True,
        "llm_wiki_max_sources": 2,
        "llm_wiki_excerpt_chars": 180,
        **overrides,
    }
    return Settings(_env_file=None, **values)


def test_retrieve_llm_wiki_context_returns_relative_markdown_citations(tmp_path: Path) -> None:
    """Verify Markdown retrieval exposes bounded relative citations only."""
    wiki_dir = tmp_path / "supplements"
    wiki_dir.mkdir()
    (wiki_dir / "vitamin-d.md").write_text(
        "# 비타민 D\n\n"
        "## 상담 권고\n"
        "비타민 D는 혈중 수치와 복용 중인 약을 함께 확인하는 보충제 정보입니다.",
        encoding="utf-8",
    )
    (tmp_path / "ignore.txt").write_text("비타민 D", encoding="utf-8")

    result = retrieve_llm_wiki_context("비타민 D 상담 권고", _settings(tmp_path))

    assert result.query == "비타민 D 상담 권고"
    assert len(result.citations) == 1
    citation = result.citations[0]
    assert citation.title == "비타민 D"
    assert citation.source_path == "supplements/vitamin-d.md"
    assert citation.heading == "비타민 D"
    assert "혈중 수치" in citation.excerpt
    assert str(tmp_path) not in citation.source_path
    assert citation.score > 0


def test_retrieve_llm_wiki_context_ignores_hidden_and_non_markdown_files(tmp_path: Path) -> None:
    """Verify hidden files and non-Markdown files cannot become public citations."""
    hidden_dir = tmp_path / ".private"
    hidden_dir.mkdir()
    (hidden_dir / "vitamin-d.md").write_text("# 비타민 D\n숨김 문서", encoding="utf-8")
    (tmp_path / "vitamin-d.txt").write_text("# 비타민 D\n텍스트 문서", encoding="utf-8")

    result = retrieve_llm_wiki_context("비타민 D", _settings(tmp_path))

    assert result.citations == ()


def test_retrieve_llm_wiki_context_returns_empty_when_disabled_or_missing(tmp_path: Path) -> None:
    """Verify retrieval is fail-closed when WIKI config is unavailable."""
    disabled = retrieve_llm_wiki_context(
        "비타민 D",
        _settings(tmp_path, llm_wiki_retrieval_enabled=False),
    )
    missing = retrieve_llm_wiki_context(
        "비타민 D",
        _settings(tmp_path / "missing"),
    )

    assert disabled.citations == ()
    assert missing.citations == ()
