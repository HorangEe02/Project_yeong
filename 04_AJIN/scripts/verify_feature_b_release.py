#!/usr/bin/env python3
"""Verify Feature B draft release posture.

The verifier is secret-safe. It checks attachment ownership, mail guard
decisions, mail adapter sealing, and priority draft template renderability
without printing credentials or sending mail.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from typing import Any, Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOC_REFERENCES = (
    "https://supabase.com/docs/guides/storage/security/access-control",
    "https://supabase.com/docs/reference/python/storage-from-createsigneduploadurl",
    "https://jinja.palletsprojects.com/en/stable/api/#jinja2.Environment",
    "https://docs.python.org/3/library/smtplib.html",
    "https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse",
    "https://learn.microsoft.com/en-us/graph/api/driveitem-put-content?view=graph-rest-1.0",
    "https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession?view=graph-rest-1.0",
    "https://help.hancom.com/hoffice/multi/ko_kr/hwp/hwp/hwp.htm",
    "https://developer.hancom.com/opensources",
)

PRIORITY_TEMPLATE_IDS = (
    "kb_8d_report",
    "kb_ecn",
    "kb_oem_email",
    "kb_weekly_report",
    "catalog_8d_report",
    "catalog_ecn_notice",
    "catalog_oem_email",
    "catalog_meeting_note",
)


@dataclass(frozen=True)
class CheckResult:
    """Single Feature B release check result.

    Args:
        name: Stable machine-readable check name.
        status: One of pass, warn, fail, or skip.
        summary: Human-readable secret-safe summary.
        details: Optional secret-safe metadata.
    """

    name: str
    status: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable check.

        Returns:
            dict[str, Any]: Result fields for reports.
        """

        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class FeatureBConfig:
    """Runtime configuration for the Feature B verifier.

    Args:
        root: Repository root.
        strict: Whether fail checks should return a non-zero exit code.
        signoff_path: Optional business owner template review signoff file.
    """

    root: Path = ROOT
    strict: bool = False
    signoff_path: Path | None = None


def _display_path(root: Path, path: Path) -> str:
    """Return a repository-relative path when possible.

    Args:
        root: Repository root.
        path: Path to display.

    Returns:
        str: Secret-safe display path.
    """

    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


@contextmanager
def _temporary_env(updates: Mapping[str, str | None]) -> Iterator[None]:
    """Temporarily update environment variables.

    Args:
        updates: Environment variable updates. ``None`` unsets a variable.

    Yields:
        None: Control while the temporary environment is active.
    """

    old_values = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _user(employee_id: str, role: str = "EMPLOYEE") -> SimpleNamespace:
    """Create a minimal authenticated user object.

    Args:
        employee_id: Employee id.
        role: RBAC role.

    Returns:
        SimpleNamespace: User-like object for router/service checks.
    """

    return SimpleNamespace(
        employee_id=employee_id,
        user_id=employee_id,
        username=employee_id,
        role=role,
    )


def verify_storage_ownership() -> CheckResult:
    """Verify Storage attachment ownership and missing-object gates.

    Returns:
        CheckResult: Storage ownership check result.
    """

    from fastapi import HTTPException

    from backend.routers import storage as storage_router
    from backend.services.supabase_storage import get_attachment, record_attachment

    with tempfile.TemporaryDirectory(prefix="feature-b-storage-") as tmp:
        db_url = f"sqlite:///{Path(tmp) / 'attachments.db'}"
        with _temporary_env({"APP_DB_BACKEND": "sqlite", "DATABASE_URL": db_url}):
            attachment_id = record_attachment(
                employee_id="B-OWNER",
                bucket="ajin-attachments",
                object_path="uploads/B-OWNER/2026/05/20/sample.txt",
                content_type="text/plain",
                size_bytes=12,
                metadata={"original_name": "sample.txt", "bucket_type": "attachments"},
            )
            row = get_attachment(attachment_id)
            if not row:
                return CheckResult(
                    "storage_ownership_smoke",
                    "fail",
                    "attachment metadata could not be recorded",
                )

            outcomes: dict[str, str] = {}
            try:
                storage_router._assert_attachment_access(row, _user("B-OWNER"))
                outcomes["owner"] = "allow"
                storage_router._assert_attachment_access(row, _user("SYS-0001", "SYS_ADMIN"))
                outcomes["admin"] = "allow"
            except HTTPException as exc:
                return CheckResult(
                    "storage_ownership_smoke",
                    "fail",
                    "owner/admin attachment access did not allow as expected",
                    {"status_code": exc.status_code},
                )

            try:
                storage_router._assert_attachment_access(row, _user("B-OTHER"))
                outcomes["other"] = "unexpected_allow"
            except HTTPException as exc:
                outcomes["other"] = f"deny_{exc.status_code}"

            original_exists = storage_router.storage_object_exists
            try:
                storage_router.storage_object_exists = lambda **_: False
                try:
                    storage_router._assert_storage_object_exists(
                        row,
                        missing_status=409,
                        missing_detail="upload_not_found",
                    )
                    outcomes["missing_object"] = "unexpected_allow"
                except HTTPException as exc:
                    outcomes["missing_object"] = f"deny_{exc.status_code}"
            finally:
                storage_router.storage_object_exists = original_exists

    expected = {
        "owner": "allow",
        "admin": "allow",
        "other": "deny_403",
        "missing_object": "deny_409",
    }
    if outcomes != expected:
        return CheckResult(
            "storage_ownership_smoke",
            "fail",
            "Storage attachment ownership smoke had unexpected outcomes",
            {"outcomes": outcomes},
        )
    return CheckResult(
        "storage_ownership_smoke",
        "pass",
        "owner/admin allow, other-user deny, and missing object deny are enforced",
        {"outcomes": outcomes},
    )


def _seed_mail_version_db(path: Path) -> None:
    """Create a minimal draft version DB for mail guard checks.

    Args:
        path: SQLite DB path to create.
    """

    conn = sqlite3.connect(str(path))
    conn.executescript(
        dedent(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                author TEXT DEFAULT '',
                department TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                version_num INTEGER NOT NULL DEFAULT 1,
                template_vars_json TEXT DEFAULT '{}',
                rendered_text TEXT DEFAULT '',
                change_summary TEXT DEFAULT '',
                created_at TEXT,
                created_by TEXT,
                status TEXT DEFAULT 'draft',
                reviewer_id TEXT DEFAULT '',
                reviewed_at TEXT DEFAULT '',
                review_note TEXT DEFAULT ''
            );
            INSERT INTO documents (id, doc_type, title, author) VALUES
                (1, 'oem_email', 'approved mail', 'B-SENDER'),
                (2, 'oem_email', 'self approved mail', 'B-SELF');
            INSERT INTO versions (id, document_id, status, reviewer_id) VALUES
                (10, 1, 'draft', ''),
                (30, 1, 'approved', 'B-REVIEWER'),
                (50, 2, 'approved', 'B-SELF');
            """
        )
    )
    conn.commit()
    conn.close()


def _mail_req(
    *,
    version_id: int = 30,
    to: Sequence[str] = (),
    cc: Sequence[str] = (),
    bcc: Sequence[str] = (),
    acknowledged_external: bool = False,
    watermark_id: str = "WMK-00000000",
) -> SimpleNamespace:
    """Create a minimal mail send request object.

    Args:
        version_id: Draft version id.
        to: To-recipient emails.
        cc: CC-recipient emails.
        bcc: BCC-recipient emails.
        acknowledged_external: Whether external send was acknowledged.
        watermark_id: Expected watermark for the approved version.

    Returns:
        SimpleNamespace: Request-like object for ``MailSendGuard``.
    """

    return SimpleNamespace(
        version_id=version_id,
        to=[SimpleNamespace(email=email, name="") for email in to],
        cc=[SimpleNamespace(email=email, name="") for email in cc],
        bcc=[SimpleNamespace(email=email, name="") for email in bcc],
        acknowledged_external=acknowledged_external,
        watermark_id=watermark_id,
    )


def verify_mail_guard() -> CheckResult:
    """Verify mail guard decisions and adapter sealing.

    Returns:
        CheckResult: Mail guard check result.
    """

    from features.draft.mail_guard import (
        ALLOW,
        BLOCK_NOT_APPROVED,
        BLOCK_RATE_LIMIT,
        BLOCK_SELF_APPROVAL,
        DomainPolicy,
        MailSendGuard,
        NEEDS_EXTERNAL_ACK,
    )
    from features.draft.mail_sender import MockMailAdapter, get_mail_adapter, reset_mail_adapter

    with tempfile.TemporaryDirectory(prefix="feature-b-mail-") as tmp:
        db_path = Path(tmp) / "draft_versions.db"
        _seed_mail_version_db(db_path)
        guard = MailSendGuard(
            policy=DomainPolicy(
                internal_domains={"ajin.co.kr"},
                trusted_oem_domains={"hkmc.com"},
            ),
            version_db_path=db_path,
            rate_limit_per_min=2,
        )

        decisions = {
            "draft_block": guard.validate(
                _mail_req(version_id=10, to=["a@ajin.co.kr"]),
                _user("B-SENDER"),
            ).decision,
            "external_ack_required": guard.validate(
                _mail_req(to=["buyer@example.com"]),
                _user("B-SENDER"),
            ).decision,
            "external_ack_allow": guard.validate(
                _mail_req(to=["buyer@example.com"], acknowledged_external=True),
                _user("B-SENDER"),
            ).decision,
            "self_approval_block": guard.validate(
                _mail_req(version_id=50, to=["a@ajin.co.kr"]),
                _user("B-SELF"),
            ).decision,
        }

        rate_guard = MailSendGuard(
            policy=DomainPolicy(internal_domains={"ajin.co.kr"}, trusted_oem_domains=set()),
            version_db_path=db_path,
            rate_limit_per_min=2,
        )
        rate_req = _mail_req(to=["a@ajin.co.kr"])
        rate_user = _user("B-RATE")
        rate_guard.validate(rate_req, rate_user)
        rate_guard.validate(rate_req, rate_user)
        decisions["rate_limit_block"] = rate_guard.validate(rate_req, rate_user).decision

    expected = {
        "draft_block": BLOCK_NOT_APPROVED,
        "external_ack_required": NEEDS_EXTERNAL_ACK,
        "external_ack_allow": ALLOW,
        "self_approval_block": BLOCK_SELF_APPROVAL,
        "rate_limit_block": BLOCK_RATE_LIMIT,
    }
    if decisions != expected:
        return CheckResult(
            "mail_guard_operational_smoke",
            "fail",
            "mail guard decisions differ from release policy",
            {"decisions": decisions},
        )

    adapter_outcomes: dict[str, str] = {}
    with _temporary_env({"AJIN_MAIL_MODE": None, "AJIN_MAIL_REAL_ENABLED": None}):
        reset_mail_adapter()
        adapter_outcomes["default"] = type(get_mail_adapter()).__name__
    with _temporary_env({"AJIN_MAIL_MODE": "real", "AJIN_MAIL_REAL_ENABLED": None}):
        reset_mail_adapter()
        try:
            get_mail_adapter()
            adapter_outcomes["real_without_enable"] = "unexpected_allow"
        except RuntimeError:
            adapter_outcomes["real_without_enable"] = "blocked"
    reset_mail_adapter()

    current_mode = os.getenv("AJIN_MAIL_MODE", "mock").strip().lower() or "mock"
    real_enabled = os.getenv("AJIN_MAIL_REAL_ENABLED", "").strip()
    if current_mode == "real" and real_enabled == "1":
        return CheckResult(
            "mail_guard_operational_smoke",
            "fail",
            "real mail mode is enabled but RealSmtpAdapter.send is not implemented",
            {"decisions": decisions, "adapter_outcomes": adapter_outcomes},
        )
    if adapter_outcomes != {"default": MockMailAdapter.__name__, "real_without_enable": "blocked"}:
        return CheckResult(
            "mail_guard_operational_smoke",
            "fail",
            "mail adapter sealing did not match release policy",
            {"adapter_outcomes": adapter_outcomes},
        )
    return CheckResult(
        "mail_guard_operational_smoke",
        "pass",
        "mail guard decisions pass and real adapter remains sealed by default",
        {"decisions": decisions, "current_mode": current_mode},
    )


def _sample_contexts() -> dict[str, dict[str, Any]]:
    """Return representative sample contexts for priority templates.

    Returns:
        dict[str, dict[str, Any]]: Template id to render context.
    """

    return {
        "kb_8d_report": {
            "title": "EWP housing leak response",
            "report_id": "8D-2026-001",
            "date": "2026-05-20",
            "plant": "Gyeongsan Plant",
            "customer": "Hyundai Motor",
            "part_name": "EWP Housing",
            "part_no": "26410-TEST",
            "severity": "High",
            "status": "D3",
            "d0_description": "Initial containment started.",
            "team_members": [{"role": "Leader", "name": "Kim", "department": "QA"}],
            "d2_problem_description": "Leak detected during end-of-line inspection.",
            "d3_containment_actions": ["Hold suspect lot", "Run 100% inspection"],
            "d4_root_cause": "Seal seating variation.",
            "d5_corrective_actions": ["Revise fixture stop", "Update work instruction"],
            "d6_validation": "Pilot run passed.",
            "d7_prevention": ["Control plan update", "Operator retraining"],
            "d8_recognition": "Team acknowledged.",
        },
        "kb_ecn": {
            "title": "EWP diode change",
            "ecn_number": "ECN-2026-A-014",
            "change_reason": "Field return prevention.",
            "effective_date": "2026-06-01",
            "affected_parts": "EWP-001, EWP-001A",
            "recipient": "Hyundai Motor Quality",
            "originator": "AJIN Engineering",
            "impact_analysis": "No dimensional impact.",
            "approval_chain": "",
            "attachments": "",
        },
        "kb_oem_email": {
            "recipient": "Hyundai Motor Quality Team",
            "subject": "PPAP Level 3 Submission for Part EWP-001",
            "sender_name": "Jun Park",
            "sender_title": "Quality Assurance Manager",
            "sender_email": "jun.park@ajin.co.kr",
            "sender_phone": "+82-53-000-0000",
            "main_content": "Please find the attached PPAP package for review.",
            "action_required": "Please review and approve the package.",
            "due_date": "2026-06-10",
            "attachments": "PSW.pdf, FMEA.xlsx",
        },
        "kb_weekly_report": {
            "week": "2026 W21",
            "summary": "Quality containment and ECN follow-up are on schedule.",
            "author": "Kim",
            "team": "Quality Assurance",
            "achievements": "- Closed EWP containment",
            "issues": "- Waiting customer approval",
            "next_week_plan": "- Submit validation report",
        },
        "catalog_8d_report": {
            "doc_number": "8D-2026-001",
            "created_date": "2026-05-20",
            "department": "Quality Assurance",
            "author": "Kim",
            "part_name": "EWP Housing",
            "part_number": "26410-TEST",
            "customer": "Hyundai Motor",
            "claim_date": "2026-05-19",
            "defect_summary": "Leak during inspection",
            "defect_quantity": "3EA",
            "d1_team": [{"role": "Leader", "name": "Kim", "department": "QA"}],
            "d2_problem": "Leak detected at final inspection.",
            "d2_5w1h": None,
            "d3_containment": "Hold lot and inspect 100%.",
            "d3_actions": [{"description": "Hold", "owner": "QA", "due_date": "2026-05-20", "status": "done"}],
            "d4_root_cause": "Seal seating variation.",
            "d5_corrective": "Fixture stop revision.",
            "d6_implementation": "Pilot run validation.",
            "d6_schedule": [{"action": "Pilot", "owner": "QA", "start": "2026-05-21", "end": "2026-05-22", "status": "planned"}],
            "d7_prevention": "Control plan update.",
            "d8_closure": "Close after customer confirmation.",
        },
        "catalog_ecn_notice": {
            "doc_number": "ECN-2026-A-014",
            "issue_date": "2026-05-20",
            "part_name": "EWP Housing",
            "part_number": "26410-TEST",
            "change_type": "Process change",
            "vehicle_model": "EV platform",
            "change_origin": "Quality improvement",
            "before_description": "Fixture stop A",
            "after_description": "Fixture stop B",
            "change_reason": "Improve seal seating consistency.",
            "impact_scope": "Gyeongsan line 1",
            "schedule": [{"phase": "Pilot", "date": "2026-05-25", "note": "QA hold point"}],
            "department_actions": [{"department": "QA", "action": "Validate first lot"}],
            "author": "Kim",
            "reviewer": "Park",
            "approver": "Lee",
        },
        "catalog_oem_email": {
            "customer_name": "Hyundai Motor",
            "department": "Quality",
            "recipient_name": "John Smith",
            "recipient_title": "Manager",
            "sender_department": "Quality Assurance",
            "sender_name": "Kim",
            "sender_title": "Manager",
            "date": "2026-05-20",
            "subject": "EWP containment update",
            "opening_paragraph": "We are sharing the containment status.",
            "structured_items": [{"label": "Lot", "value": "LOT-2026-0520"}],
            "main_body": "The suspect lot is on hold and inspection is complete.",
            "action_items": ["Please confirm receipt."],
            "closing_paragraph": "We will send validation data separately.",
            "sender_phone": "054-000-0000",
            "sender_email": "kim@ajin.co.kr",
        },
        "catalog_meeting_note": {
            "doc_number": "MTG-2026-001",
            "meeting_title": "EWP quality review",
            "meeting_date": "2026-05-20",
            "meeting_time": "10:00",
            "meeting_place": "Gyeongsan Plant",
            "author": "Kim",
            "attendees": [{"department": "QA", "name": "Kim", "title": "Manager"}],
            "agenda_items": [{"title": "Containment", "content": "Review lot hold."}],
            "decisions": [{"content": "Run pilot validation", "owner": "QA", "deadline": "2026-05-22"}],
            "next_steps": "Send validation report.",
        },
    }


def verify_priority_templates(config: FeatureBConfig) -> CheckResult:
    """Verify priority Draft templates render and carry review metadata.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Template verification result.
    """

    from jinja2 import Environment, StrictUndefined

    from features.draft.template_metadata import parse_template_metadata

    templates = {
        "kb_8d_report": config.root / "data/knowledge_base/templates/8d_report_template.j2",
        "kb_ecn": config.root / "data/knowledge_base/templates/ecn_template.j2",
        "kb_oem_email": config.root / "data/knowledge_base/templates/oem_email_template.j2",
        "kb_weekly_report": config.root / "data/knowledge_base/templates/weekly_report_template.j2",
        "catalog_8d_report": config.root / "data/templates/report/8d_report.j2",
        "catalog_ecn_notice": config.root / "data/templates/report/ecn_notice.j2",
        "catalog_oem_email": config.root / "data/templates/email/to_oem.j2",
        "catalog_meeting_note": config.root / "data/templates/report/meeting_note.j2",
    }
    expected_markers = {
        "kb_8d_report": ["D1", "D8"],
        "kb_ecn": ["Engineering Change Notice", "ECN"],
        "kb_oem_email": ["Subject:", "AJIN Industry"],
        "kb_weekly_report": ["주간 보고서", "KPI"],
        "catalog_8d_report": ["8D REPORT", "D1"],
        "catalog_ecn_notice": ["설계변경통보서", "ECN"],
        "catalog_oem_email": ["아진산업", "제목:"],
        "catalog_meeting_note": ["회의록", "결정 사항"],
    }
    contexts = _sample_contexts()
    env = Environment(undefined=StrictUndefined, autoescape=False)
    rendered: list[str] = []
    failures: list[str] = []
    metadata_missing: list[str] = []

    for key, path in templates.items():
        if not path.exists():
            failures.append(f"{key}:missing")
            continue
        try:
            output = env.from_string(path.read_text(encoding="utf-8")).render(**contexts[key])
        except Exception as exc:
            failures.append(f"{key}:{type(exc).__name__}")
            continue
        if len(output.strip()) < 80:
            failures.append(f"{key}:too_short")
            continue
        missing_markers = [marker for marker in expected_markers[key] if marker not in output]
        if missing_markers:
            failures.append(f"{key}:missing_markers={','.join(missing_markers)}")
            continue
        rendered.append(key)

        if key.startswith("kb_"):
            metadata = parse_template_metadata(path)
            if not metadata.get("usage_hint") or not metadata.get("required_vars"):
                metadata_missing.append(key)

    if failures:
        return CheckResult(
            "draft_template_render_smoke",
            "fail",
            "priority Draft templates failed deterministic render checks",
            {"failures": failures, "rendered": rendered},
        )
    if metadata_missing:
        return CheckResult(
            "draft_template_render_smoke",
            "fail",
            "priority knowledge-base templates are missing review metadata",
            {"metadata_missing": metadata_missing, "rendered": rendered},
        )
    return CheckResult(
        "draft_template_render_smoke",
        "pass",
        "priority Draft templates render with strict sample contexts and review metadata",
        {"rendered_count": len(rendered), "templates": rendered},
    )


def verify_template_business_signoff(config: FeatureBConfig) -> CheckResult:
    """Check whether a business-owner template review signoff exists.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Business signoff posture.
    """

    if not config.signoff_path:
        return CheckResult(
            "template_business_signoff",
            "fail",
            "business-owner template signoff file is required for release",
            {"required_template_ids": list(PRIORITY_TEMPLATE_IDS)},
        )
    if not config.signoff_path.exists():
        return CheckResult(
            "template_business_signoff",
            "fail",
            "business-owner template signoff file does not exist",
            {"path": _display_path(config.root, config.signoff_path)},
        )

    try:
        signoff = json.loads(config.signoff_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CheckResult(
            "template_business_signoff",
            "fail",
            "business-owner template signoff must be valid JSON",
            {"path": _display_path(config.root, config.signoff_path), "error": str(exc)},
        )

    templates = signoff.get("templates", [])
    if not isinstance(templates, list):
        return CheckResult(
            "template_business_signoff",
            "fail",
            "business-owner template signoff JSON must contain a templates list",
            {"path": _display_path(config.root, config.signoff_path)},
        )

    required_fields = {"template_id", "owner_department", "reviewer", "approved_at", "version", "doc_types"}
    missing_fields: dict[str, list[str]] = {}
    signed_ids: set[str] = set()
    for item in templates:
        if not isinstance(item, Mapping):
            missing_fields["<invalid_item>"] = sorted(required_fields)
            continue
        template_id = str(item.get("template_id", "")).strip()
        missing = sorted(field for field in required_fields if not item.get(field))
        if missing:
            missing_fields[template_id or "<missing_template_id>"] = missing
        if template_id:
            signed_ids.add(template_id)

    missing_templates = sorted(set(PRIORITY_TEMPLATE_IDS) - signed_ids)
    if missing_fields or missing_templates:
        return CheckResult(
            "template_business_signoff",
            "fail",
            "business-owner template signoff is incomplete",
            {
                "missing_templates": missing_templates,
                "missing_fields": missing_fields,
                "path": _display_path(config.root, config.signoff_path),
            },
        )

    doc_types = sorted({
        str(doc_type)
        for item in templates
        if isinstance(item, Mapping)
        for doc_type in (item.get("doc_types") or [])
    })
    if config.signoff_path and config.signoff_path.exists():
        return CheckResult(
            "template_business_signoff",
            "pass",
            "business-owner template signoff covers all priority templates",
            {
                "path": _display_path(config.root, config.signoff_path),
                "template_count": len(signed_ids),
                "doc_types": doc_types,
            },
        )


def verify_export_compatibility() -> CheckResult:
    """Verify local HWPX and Microsoft Graph request-shape compatibility.

    Returns:
        CheckResult: Export compatibility gate result.
    """

    from features.draft.hwpx_exporter import HwpxExporter
    from features.draft.hwpx_validator import validate_hwpx_bytes
    from features.draft.sharepoint_compat import plan_sharepoint_upload
    from features.draft.watermark import compute_watermark_id

    md = "# Feature B compatibility\n\nAI assisted export validation."
    watermark_id = compute_watermark_id(md)
    hwpx_bytes = HwpxExporter().export_bytes(md, doc_title="compat", author="release")
    hwpx_result = validate_hwpx_bytes(hwpx_bytes, expected_watermark_id=watermark_id)

    outcomes: dict[str, str] = {
        "hwpx": "pass" if hwpx_result.ok else "fail",
    }

    try:
        small = plan_sharepoint_upload(
            drive_id="drive123",
            parent_id="parent123",
            filename="draft.hwpx",
            size_bytes=len(hwpx_bytes),
            content_type="application/vnd.hancom.hwpx",
        )
        outcomes["sharepoint_small"] = f"{small.method}:{small.mode}"
    except Exception as exc:
        outcomes["sharepoint_small"] = f"fail:{type(exc).__name__}"

    try:
        large = plan_sharepoint_upload(
            drive_id="drive123",
            parent_id="parent123",
            filename="large-draft.hwpx",
            size_bytes=251 * 1024 * 1024,
            content_type="application/vnd.hancom.hwpx",
            chunk_size_bytes=10 * 1024 * 1024,
        )
        outcomes["sharepoint_large"] = f"{large.method}:{large.mode}:{large.chunk_size_bytes}"
    except Exception as exc:
        outcomes["sharepoint_large"] = f"fail:{type(exc).__name__}"

    try:
        plan_sharepoint_upload(
            drive_id="drive123",
            parent_id="parent123",
            filename="bad-chunk.hwpx",
            size_bytes=251 * 1024 * 1024,
            content_type="application/vnd.hancom.hwpx",
            chunk_size_bytes=123,
        )
        outcomes["sharepoint_bad_chunk"] = "unexpected_allow"
    except ValueError as exc:
        outcomes["sharepoint_bad_chunk"] = str(exc)

    expected = {
        "hwpx": "pass",
        "sharepoint_small": "PUT:single_put",
        "sharepoint_large": f"POST:upload_session:{10 * 1024 * 1024}",
        "sharepoint_bad_chunk": "chunk_size_must_be_320kib_multiple",
    }
    if outcomes != expected:
        return CheckResult(
            "draft_export_compatibility",
            "fail",
            "HWPX or SharePoint compatibility checks failed",
            {"outcomes": outcomes, "hwpx_errors": hwpx_result.errors},
        )
    return CheckResult(
        "draft_export_compatibility",
        "pass",
        "HWPX package and SharePoint request-shape checks passed",
        {"outcomes": outcomes},
    )


def summarize(checks: Sequence[CheckResult]) -> dict[str, Any]:
    """Summarize check statuses.

    Args:
        checks: Check results.

    Returns:
        dict[str, Any]: Summary payload.
    """

    counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    return {"status": status, "counts": counts, "checked_at": datetime.now(timezone.utc).isoformat()}


def run_verification(config: FeatureBConfig) -> dict[str, Any]:
    """Run all Feature B release checks.

    Args:
        config: Verifier config.

    Returns:
        dict[str, Any]: Secret-safe report payload.
    """

    checks = [
        verify_storage_ownership(),
        verify_mail_guard(),
        verify_priority_templates(config),
        verify_template_business_signoff(config),
        verify_export_compatibility(),
    ]
    return {
        "summary": summarize(checks),
        "config": {
            "strict": config.strict,
            "signoff_path": str(config.signoff_path.relative_to(config.root))
            if config.signoff_path and config.signoff_path.is_relative_to(config.root)
            else str(config.signoff_path or ""),
            "mail_mode": os.getenv("AJIN_MAIL_MODE", "mock").strip() or "mock",
        },
        "references": list(DOC_REFERENCES),
        "checks": [check.to_dict() for check in checks],
    }


def write_markdown_report(report: Mapping[str, Any], path: Path) -> None:
    """Write a Markdown verification report.

    Args:
        report: Report payload.
        path: Destination path.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    lines = [
        "# Feature B Release Check",
        "",
        f"- Status: `{summary['status']}`",
        f"- Checked at: `{summary['checked_at']}`",
        f"- Counts: `{json.dumps(summary['counts'], ensure_ascii=False)}`",
        f"- AJIN_MAIL_MODE: `{report['config']['mail_mode']}`",
        f"- Business signoff path: `{report['config']['signoff_path']}`",
        "",
        "## Checks",
        "",
        "| Status | Check | Summary | Details |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        details = json.dumps(check.get("details", {}), ensure_ascii=False)
        lines.append(
            f"| `{check['status']}` | `{check['name']}` | {check['summary']} | `{details}` |"
        )
    lines.extend(
        [
            "",
            "## Business Review Checklist",
            "",
            "- 8D Report: confirm required fields, customer-response wording, D1-D8 section order, and attachment labels.",
            "- ECN: confirm approval chain, effective-date wording, affected part scope, and validation plan language.",
            "- Mail: confirm OEM/internal greeting, confidentiality footer, CC policy, and attachment recommendation labels.",
            "- Reports: confirm weekly/meeting report headers, KPI wording, action-owner fields, and review cadence.",
            "",
            "## References",
            "",
        ]
    )
    for ref in report["references"]:
        lines.append(f"- {ref}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_text_report(report: Mapping[str, Any]) -> None:
    """Print a compact text report.

    Args:
        report: Report payload.
    """

    summary = report["summary"]
    print(
        "Feature B release: "
        f"{summary['status']} "
        f"(pass={summary['counts']['pass']}, warn={summary['counts']['warn']}, "
        f"fail={summary['counts']['fail']}, skip={summary['counts']['skip']})"
    )
    for check in report["checks"]:
        print(f"[{check['status'].upper()}] {check['name']}: {check['summary']}")
        if check.get("details"):
            print(f"  details={json.dumps(check['details'], ensure_ascii=False)}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list.

    Returns:
        argparse.Namespace: Parsed arguments.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when fail checks remain.")
    parser.add_argument("--markdown", default="", help="Write a Markdown report to this path.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument(
        "--business-signoff",
        default="",
        help="Optional business-owner template review signoff file.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Optional argument list.

    Returns:
        int: Process exit code.
    """

    args = parse_args(argv)
    signoff_path = (ROOT / args.business_signoff).resolve() if args.business_signoff else None
    config = FeatureBConfig(root=ROOT, strict=bool(args.strict), signoff_path=signoff_path)
    report = run_verification(config)
    if args.markdown:
        markdown_path = Path(args.markdown)
        if not markdown_path.is_absolute():
            markdown_path = ROOT / markdown_path
        write_markdown_report(report, markdown_path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text_report(report)
    if config.strict and report["summary"]["status"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
