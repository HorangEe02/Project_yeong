"""Feature C repo-local content CMS validation tests."""

from __future__ import annotations

from pathlib import Path

from features.onboarding.content_cms import (
    archive_content,
    get_content,
    list_content,
    upsert_content,
    validate_content_store,
)


def _kb_root(root: Path) -> Path:
    path = root / "data" / "knowledge_base"
    for name in ("sops", "glossary", "glossary_aliases"):
        (path / name).mkdir(parents=True, exist_ok=True)
    (path / "glossary_aliases" / "aliases.json").write_text("{}", encoding="utf-8")
    return path


def _published_sop() -> dict:
    return {
        "sop_id": "SOP-TEST",
        "title": "테스트 SOP",
        "department": "품질보증팀",
        "category": "품질",
        "citation_id": "SOP-TEST",
        "owner_department": "품질보증팀",
        "reviewed_at": "2026-05-21",
        "effective_date": "2026-05-21",
        "version": "1.0",
        "status": "published",
        "steps": [
            {
                "step_number": 1,
                "title": "확인",
                "description": "확인한다.",
                "checklist": ["확인 완료"],
            }
        ],
    }


def test_validate_content_store_requires_published_metadata(tmp_path: Path) -> None:
    """Published SOP/Glossary items fail validation when metadata is missing."""

    kb_root = _kb_root(tmp_path)
    (kb_root / "sops" / "SOP-BAD.json").write_text(
        '{"sop_id":"SOP-BAD","title":"bad","status":"published"}',
        encoding="utf-8",
    )

    result = validate_content_store(tmp_path)

    assert result["ok"] is False
    assert any("missing_published_metadata" in issue["detail"] for issue in result["issues"])


def test_upsert_list_get_and_archive_content(tmp_path: Path) -> None:
    """Admin CMS helpers can create, read, list, and archive content safely."""

    _kb_root(tmp_path)

    saved = upsert_content("sops", "SOP-TEST", _published_sop(), root=tmp_path)
    loaded = get_content("sops", "SOP-TEST", root=tmp_path)

    assert saved["object_id"] == "SOP-TEST"
    assert loaded["payload"]["status"] == "published"
    assert len(list_content("sops", include_unpublished=False, root=tmp_path)) == 1

    archived = archive_content("sops", "SOP-TEST", root=tmp_path)

    assert archived["status"] == "archived"
    assert list_content("sops", include_unpublished=False, root=tmp_path) == []
    assert len(list_content("sops", include_unpublished=True, root=tmp_path)) == 1


def test_upsert_rejects_unsafe_object_id(tmp_path: Path) -> None:
    """CMS writes reject path traversal object ids."""

    _kb_root(tmp_path)

    try:
        upsert_content("sops", "../escape", _published_sop(), root=tmp_path)
    except ValueError as exc:
        assert "unsafe" in str(exc) or "escape" in str(exc)
    else:
        raise AssertionError("unsafe object id should fail")
