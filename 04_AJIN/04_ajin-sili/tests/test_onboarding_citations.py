"""Feature C onboarding citation enforcement tests."""

from __future__ import annotations

from features.onboarding.citations import SourceRef, enforce_citations, source_ref_from_kb_context


def test_enforce_citations_verifies_existing_source_marker() -> None:
    """Answers with required source markers stay verified."""

    source = SourceRef(
        citation_id="KB-HR-001",
        source_path="department_guides/hr.md",
        source_type="kb_markdown",
        reviewed_at="2026-05-21",
    )

    result = enforce_citations("복리후생은 인사팀 기준을 따릅니다. [출처:KB-HR-001]", [source])

    assert result.citation_status == "verified"
    assert result.footer == ""
    assert result.sources[0]["citation_id"] == "KB-HR-001"


def test_enforce_citations_appends_missing_source_footer() -> None:
    """Missing source markers are corrected by a server-side footer."""

    source = SourceRef(
        citation_id="SOP-8D",
        source_path="data/knowledge_base/sops/SOP-8D.json",
        source_type="sop",
        title="8D 절차",
    )

    result = enforce_citations("8D는 팀 구성 후 원인 분석을 진행합니다.", [source])

    assert result.citation_status == "corrected"
    assert "[출처:SOP-8D]" in result.footer
    assert result.text.endswith(result.footer)


def test_enforce_citations_marks_model_only_without_sources() -> None:
    """Answers without retrieved sources get a low-trust model-only notice."""

    result = enforce_citations("담당 부서에 확인해 주세요.", [])

    assert result.citation_status == "model_only"
    assert "사내 자료에서 확인된 출처 없음" in result.footer


def test_source_ref_from_kb_context_requires_citation_id() -> None:
    """KB context conversion is fail-closed when citation metadata is absent."""

    try:
        source_ref_from_kb_context({"source_path": "x.md"})
    except ValueError as exc:
        assert "citation_id" in str(exc)
    else:
        raise AssertionError("missing citation_id should fail")
