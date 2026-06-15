"""Feature B Sprint 1 P0 — 단위/통합 테스트.

Coverage:
  - features/draft/mail_guard: 8 시나리오 (version, status, self_approval, external_ack,
    bcc, cap, invalid_email, rate_limit, allow)
  - features/draft/mail_audit: append + get_recent (격리 audit.db)
  - features/draft/watermark: compute_watermark_id + watermark_text
  - features/draft/template_exporter: HWPX 매핑 = .hwpx + ZIP 구조
  - docx/pdf/hwpx exporter 워터마크 부착 검증

격리된 임시 DB / 환경변수 reset 으로 운영 data 미오염.
"""

from __future__ import annotations

import io
import sqlite3
import zipfile
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace as N
from typing import Iterator

import pytest

from features.draft import mail_audit
from features.draft.mail_guard import (
    ALLOW,
    BLOCK_BCC_NOT_ALLOWED,
    BLOCK_INVALID_EMAIL,
    BLOCK_NOT_APPROVED,
    BLOCK_NO_VERSION,
    BLOCK_RATE_LIMIT,
    BLOCK_RECIPIENT_CAP,
    BLOCK_SELF_APPROVAL,
    BLOCK_WATERMARK_MISMATCH,
    DomainPolicy,
    MailSendGuard,
    NEEDS_EXTERNAL_ACK,
)
from features.draft.watermark import compute_watermark_id, watermark_text


# ─────────────────────────────────────────────────────────
# Fixtures — 격리된 version_db / audit.db
# ─────────────────────────────────────────────────────────


def _make_version_db(tmp_path: Path) -> Path:
    """draft_versions.db — 실 스키마 (documents JOIN versions, B4 v4.0 columns)."""
    db = tmp_path / "draft_versions.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(dedent(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            author TEXT DEFAULT '',
            department TEXT DEFAULT '',
            created_at TEXT, updated_at TEXT
        );
        CREATE TABLE versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            version_num INTEGER NOT NULL DEFAULT 1,
            template_vars_json TEXT DEFAULT '{}',
            rendered_text TEXT DEFAULT '',
            change_summary TEXT DEFAULT '',
            created_at TEXT, created_by TEXT,
            status TEXT DEFAULT 'draft',
            reviewer_id TEXT DEFAULT '',
            reviewed_at TEXT DEFAULT '',
            review_note TEXT DEFAULT ''
        );
        -- documents:
        INSERT INTO documents (id, doc_type, title, author) VALUES
            (1, 'oem_email', 'doc-kim', 'kim'),
            (2, 'oem_email', 'doc-self', 'self_kim');
        -- versions:
        INSERT INTO versions (id, document_id, status, reviewer_id) VALUES
            (10, 1, 'draft',        ''),
            (20, 1, 'under_review', 'park'),
            (30, 1, 'approved',     'park'),
            (40, 1, 'rejected',     'park'),
            (50, 2, 'approved',     'self_kim');
        """
    ))
    conn.commit()
    conn.close()
    return db


def _make_audit_db(tmp_path: Path) -> Path:
    db = tmp_path / "audit.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(dedent(
        """
        CREATE TABLE mail_audit_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts TEXT NOT NULL DEFAULT (datetime('now')),
          user_id INTEGER, sender_email TEXT,
          version_id INTEGER, version_status TEXT,
          adapter TEXT, ok INTEGER, message_id TEXT,
          to_count INTEGER, cc_count INTEGER, bcc_count INTEGER,
          external_domains TEXT, guard_decision TEXT,
          watermark_id TEXT, detail TEXT
        );
        """
    ))
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def guard(tmp_path: Path, monkeypatch) -> Iterator[MailSendGuard]:
    """격리 version_db + 신선한 rate-limiter."""
    db = _make_version_db(tmp_path)
    # 사내 도메인 명시 (env override 와 무관하게 결정론적)
    policy = DomainPolicy(
        internal_domains={"ajin.co.kr"},
        trusted_oem_domains={"hkmc.com"},
    )
    yield MailSendGuard(policy=policy, version_db_path=db, rate_limit_per_min=100)


def _make_req(version_id=30, to=None, cc=None, bcc=None, ack=False, watermark_id=None):
    return N(
        version_id=version_id,
        to=[N(email=e, name="") for e in (to or [])],
        cc=[N(email=e, name="") for e in (cc or [])],
        bcc=[N(email=e, name="") for e in (bcc or [])],
        acknowledged_external=ack,
        watermark_id=compute_watermark_id("") if watermark_id is None else watermark_id,
    )


# ─────────────────────────────────────────────────────────
# 8 시나리오 — mail_guard
# ─────────────────────────────────────────────────────────


def test_guard_block_no_version(guard):
    req = _make_req(version_id=0, to=["a@ajin.co.kr"])
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == BLOCK_NO_VERSION
    assert not rep.ok


def test_guard_block_version_not_found(guard):
    req = _make_req(version_id=99999, to=["a@ajin.co.kr"])
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == BLOCK_NO_VERSION


def test_guard_block_not_approved_draft(guard):
    req = _make_req(version_id=10, to=["a@ajin.co.kr"])  # draft
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == BLOCK_NOT_APPROVED
    assert rep.version_status == "draft"


def test_guard_block_not_approved_rejected(guard):
    req = _make_req(version_id=40, to=["a@ajin.co.kr"])  # rejected
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == BLOCK_NOT_APPROVED


def test_guard_block_self_approval(guard):
    # version 50: author == reviewer == self_kim
    req = _make_req(version_id=50, to=["a@ajin.co.kr"])
    rep = guard.validate(req, N(employee_id="self_kim"))
    assert rep.decision == BLOCK_SELF_APPROVAL


def test_guard_block_watermark_mismatch(guard):
    req = _make_req(version_id=30, to=["a@ajin.co.kr"], watermark_id="WMK-deadbeef")
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == BLOCK_WATERMARK_MISMATCH


def test_guard_block_invalid_email(guard):
    req = _make_req(version_id=30, to=["malformed-no-at"])
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == BLOCK_INVALID_EMAIL


def test_guard_needs_external_ack(guard):
    req = _make_req(version_id=30, to=["x@external.com"], ack=False)
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == NEEDS_EXTERNAL_ACK
    # classified["external"] 는 이메일 전체 리스트 ("x@external.com" 형태).
    assert "x@external.com" in rep.classified["external"]


def test_guard_external_with_ack_passes(guard):
    req = _make_req(version_id=30, to=["x@external.com"], ack=True)
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == ALLOW


def test_guard_bcc_blocked_when_external(guard):
    req = _make_req(
        version_id=30,
        to=["x@external.com"],
        bcc=["b@ajin.co.kr"],
        ack=True,
    )
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == BLOCK_BCC_NOT_ALLOWED


def test_guard_oem_domain_classified_as_oem(guard):
    # hkmc.com 은 trusted OEM — external ack 불필요
    req = _make_req(version_id=30, to=["hong@hkmc.com"], ack=False)
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == ALLOW
    assert "hkmc.com" in [e.split("@")[-1] for e in rep.classified["oem"]]


def test_guard_recipient_cap_total(guard):
    too_many_to = [f"u{i}@ajin.co.kr" for i in range(60)]
    req = _make_req(version_id=30, to=too_many_to)
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == BLOCK_RECIPIENT_CAP


def test_guard_external_to_cap(guard):
    too_many_external = [f"u{i}@external.com" for i in range(25)]
    req = _make_req(version_id=30, to=too_many_external, ack=True)
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == BLOCK_RECIPIENT_CAP


def test_guard_rate_limit(tmp_path, monkeypatch):
    """rate limit 3/min — 4번째 차단."""
    db = _make_version_db(tmp_path)
    g = MailSendGuard(
        policy=DomainPolicy(internal_domains={"ajin.co.kr"}, trusted_oem_domains=set()),
        version_db_path=db,
        rate_limit_per_min=3,
    )
    req = _make_req(version_id=30, to=["a@ajin.co.kr"])
    user = N(employee_id="kim")
    assert g.validate(req, user).decision == ALLOW
    assert g.validate(req, user).decision == ALLOW
    assert g.validate(req, user).decision == ALLOW
    assert g.validate(req, user).decision == BLOCK_RATE_LIMIT


def test_guard_allow_internal_only(guard):
    req = _make_req(version_id=30, to=["a@ajin.co.kr"], cc=["b@ajin.co.kr"])
    rep = guard.validate(req, N(employee_id="kim"))
    assert rep.decision == ALLOW
    assert rep.classified["external"] == []


# ─────────────────────────────────────────────────────────
# mail_audit
# ─────────────────────────────────────────────────────────


def test_audit_append_and_get_recent(tmp_path):
    db = _make_audit_db(tmp_path)
    rid = mail_audit.append(
        user_id=7, sender_email="kim@ajin.co.kr",
        version_id=30, version_status="approved",
        adapter="mock", ok=True, message_id="msg-1",
        to_recipients=["a@hkmc.com"],
        cc_recipients=["b@ajin.co.kr"],
        bcc_recipients=[],
        guard_decision="allow",
        watermark_id="WMK-abc12345",
        detail="ok",
        db_path=db,
    )
    assert rid and rid >= 1
    rows = mail_audit.get_recent(10, db_path=db)
    assert len(rows) == 1
    row = rows[0]
    assert row["ok"] == 1
    assert row["guard_decision"] == "allow"
    # external_domains 는 to+cc+bcc 의 모든 도메인을 합산 (자동 분류 안 함 — 가드가 분류해 전달).
    # 본 테스트는 external_domains=None 으로 호출했으므로 ajin/hkmc 둘 다 포함됨이 정상.
    import json
    parsed = json.loads(row["external_domains"])
    assert "hkmc.com" in parsed
    assert "ajin.co.kr" in parsed


def test_audit_append_failed_send(tmp_path):
    db = _make_audit_db(tmp_path)
    rid = mail_audit.append(
        sender_email="kim@ajin.co.kr",
        version_id=10, version_status="draft",
        adapter="", ok=False, message_id="",
        to_recipients=["x@external.com"],
        guard_decision="block_not_approved",
        detail="status=draft",
        db_path=db,
    )
    assert rid
    row = mail_audit.get_recent(1, db_path=db)[0]
    assert row["ok"] == 0
    assert row["guard_decision"] == "block_not_approved"


# ─────────────────────────────────────────────────────────
# watermark utility
# ─────────────────────────────────────────────────────────


def test_watermark_id_deterministic():
    assert compute_watermark_id("hello") == compute_watermark_id("hello")
    assert compute_watermark_id("a") != compute_watermark_id("b")
    assert compute_watermark_id("").startswith("WMK-")


def test_watermark_text_with_and_without_reviewer():
    wid = "WMK-abc12345"
    assert "검토: park" in watermark_text(wid, "park")
    assert "검토 미완" in watermark_text(wid, "")
    assert "AI 보조 작성" in watermark_text(wid)
    assert wid in watermark_text(wid)


# ─────────────────────────────────────────────────────────
# HWPX export — 매핑 복구 + 워터마크 부착
# ─────────────────────────────────────────────────────────


def test_template_exporter_hwpx_extension_restored():
    """template_exporter.py:365 mapping 복구 검증 (plan §15)."""
    from features.draft.template_exporter import text_to_hwpx_bytes
    b = text_to_hwpx_bytes("# Test\n\n본문", "샘플")
    assert len(b) > 100
    zf = zipfile.ZipFile(io.BytesIO(b))
    names = zf.namelist()
    assert names[0] == "mimetype"
    assert zf.read("mimetype").decode().strip() == "application/hwp+zip"
    assert "Contents/content.hpf" in names
    assert "Contents/section0.xml" in names


def test_hwpx_exporter_includes_watermark():
    from features.draft.hwpx_exporter import HwpxExporter
    md = "# 워터마크 테스트\n\n본문"
    b = HwpxExporter().export_bytes(markdown_text=md, doc_title="t", author="park")
    section = zipfile.ZipFile(io.BytesIO(b)).read("Contents/section0.xml").decode()
    expected = compute_watermark_id(md)
    assert expected in section
    assert "AI 보조 작성" in section
    assert "park" in section


# ─────────────────────────────────────────────────────────
# DOCX export 워터마크
# ─────────────────────────────────────────────────────────


def test_docx_export_includes_watermark():
    from features.draft.docx_exporter import DocxExporter
    md = "# DocX 워터마크\n\n본문 한 줄"
    b = DocxExporter().export_bytes(markdown_text=md, doc_title="t", author="kim")
    xml = zipfile.ZipFile(io.BytesIO(b)).read("word/document.xml").decode("utf-8")
    expected = compute_watermark_id(md)
    assert expected in xml, "watermark id 가 docx XML 에 부착되지 않음"
    assert "AI 보조 작성" in xml


def test_docx_watermark_id_changes_with_content():
    from features.draft.docx_exporter import DocxExporter
    a = DocxExporter().export_bytes("first content", "t", author="kim")
    b = DocxExporter().export_bytes("different content", "t", author="kim")
    # 두 docx의 워터마크 ID는 컨텐츠가 다르므로 달라야 함
    xml_a = zipfile.ZipFile(io.BytesIO(a)).read("word/document.xml").decode()
    xml_b = zipfile.ZipFile(io.BytesIO(b)).read("word/document.xml").decode()
    wid_a = compute_watermark_id("first content")
    wid_b = compute_watermark_id("different content")
    assert wid_a != wid_b
    assert wid_a in xml_a
    assert wid_b in xml_b
    assert wid_a not in xml_b


# ─────────────────────────────────────────────────────────
# PDF export 워터마크 — PDF 바이너리는 텍스트 직접 검색 어려움.
# 최소 검증: bytes 길이 + magic header.
# ─────────────────────────────────────────────────────────


def test_pdf_export_runs_with_author():
    from features.draft.pdf_exporter import PdfExporter
    md = "# PDF 워터마크\n\n본문"
    b = PdfExporter().export_bytes(markdown_text=md, doc_title="t", author="kim")
    assert b.startswith(b"%PDF")
    assert len(b) > 500


# ─────────────────────────────────────────────────────────
# mail_sender env 봉인
# ─────────────────────────────────────────────────────────


def test_mail_sender_default_mock(monkeypatch):
    monkeypatch.delenv("AJIN_MAIL_MODE", raising=False)
    monkeypatch.delenv("AJIN_MAIL_REAL_ENABLED", raising=False)
    from features.draft.mail_sender import get_mail_adapter, reset_mail_adapter, MockMailAdapter
    reset_mail_adapter()
    a = get_mail_adapter()
    assert isinstance(a, MockMailAdapter)


def test_mail_sender_real_blocked_without_enable(monkeypatch):
    monkeypatch.setenv("AJIN_MAIL_MODE", "real")
    monkeypatch.delenv("AJIN_MAIL_REAL_ENABLED", raising=False)
    from features.draft.mail_sender import get_mail_adapter, reset_mail_adapter
    reset_mail_adapter()
    with pytest.raises(RuntimeError):
        get_mail_adapter()


def test_mail_sender_real_skeleton_blocks_send(monkeypatch):
    monkeypatch.setenv("AJIN_MAIL_MODE", "real")
    monkeypatch.setenv("AJIN_MAIL_REAL_ENABLED", "1")
    from features.draft.mail_sender import (
        get_mail_adapter, reset_mail_adapter, MailMessage, MailRecipient,
    )
    reset_mail_adapter()
    a = get_mail_adapter()
    with pytest.raises(NotImplementedError):
        a.send(MailMessage(subject="t", body="b", to=[MailRecipient(email="x@y.com")]))
    reset_mail_adapter()


def test_mail_sender_unknown_mode_rejected(monkeypatch):
    monkeypatch.setenv("AJIN_MAIL_MODE", "graph")
    from features.draft.mail_sender import get_mail_adapter, reset_mail_adapter
    reset_mail_adapter()
    with pytest.raises(ValueError):
        get_mail_adapter()
    reset_mail_adapter()
