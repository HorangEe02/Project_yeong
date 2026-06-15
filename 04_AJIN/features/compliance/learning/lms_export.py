"""P5 §5 — D15 학습경로 외부 LMS 이식용 표준 포맷 export.

외부 LMS (Moodle, Cornerstone, Workday Learn, ILT) 가 import 가능한 두 표준:

1. **SCORM 1.2** — `imsmanifest.xml` + HTML SCO 들 ZIP 패키지. 가장 광범위 호환.
2. **xAPI (Tin Can)** — 학습 활동 statements (JSON list). LRS (Learning Record Store)
   에 POST 가능. 진도/점수/완료 통계 추적용.

자격증명 무관 — 우리 DB 의 learning_paths/progress 만 읽어 직렬화.
"""
from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from features.compliance.alerts.legal_guard import COMPLIANCE_AI_DISCLAIMER


# ─────────────────────────────────────────────────────────────
# SCORM 1.2
# ─────────────────────────────────────────────────────────────


def _scorm_manifest(path: dict[str, Any], items: list[dict[str, Any]]) -> str:
    """SCORM 1.2 imsmanifest.xml 생성.

    각 change 를 SCO 1개로 매핑. organization 의 item 순서대로 학습.
    """
    name = escape(str(path.get("name") or "AJIN Compliance Learning Path"))
    items_xml: list[str] = []
    resources_xml: list[str] = []
    for it in items:
        sco_id = f"sco_{it['change_id']}"
        title = escape(it.get("title") or f"change_{it['change_id']}")
        items_xml.append(
            f'      <item identifier="item_{it["change_id"]}" identifierref="{sco_id}">'
            f'<title>Week {it.get("week",1)} · {title}</title></item>'
        )
        resources_xml.append(
            f'    <resource identifier="{sco_id}" type="webcontent" '
            f'adlcp:scormtype="sco" href="{sco_id}.html">'
            f'<file href="{sco_id}.html"/></resource>'
        )
    items_block = "\n".join(items_xml)
    resources_block = "\n".join(resources_xml)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<manifest identifier="ajin.compliance.path" version="1.0"\n'
        '  xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"\n'
        '  xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"\n'
        '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        '  <metadata>\n'
        '    <schema>ADL SCORM</schema>\n'
        '    <schemaversion>1.2</schemaversion>\n'
        '  </metadata>\n'
        '  <organizations default="ORG-1">\n'
        '    <organization identifier="ORG-1">\n'
        f'      <title>{name}</title>\n'
        f'{items_block}\n'
        '    </organization>\n'
        '  </organizations>\n'
        '  <resources>\n'
        f'{resources_block}\n'
        '  </resources>\n'
        '</manifest>\n'
    )


def _scorm_sco_html(change: dict[str, Any]) -> str:
    """SCO 1개 HTML — 변경 1건의 본문 + SCORM API stub (LMS 통신용)."""
    title = escape(str(change.get("item_title") or f"change_{change.get('id','?')}"))
    summary = escape(str(change.get("summary_ko") or ""))
    grade = escape(str(change.get("grade") or "MEDIUM"))
    body = escape(str(change.get("new_value") or "")[:2000])
    return (
        '<!DOCTYPE html>\n'
        '<html lang="ko"><head><meta charset="UTF-8">\n'
        f'<title>{title}</title>\n'
        '<script>\n'
        '// SCORM 1.2 API stub — LMS 가 부착\n'
        'function _scorm(){var w=window;while(w&&!w.API){if(w.parent===w)return null;w=w.parent}return w&&w.API?w.API:null}\n'
        'window.addEventListener("load", function(){var a=_scorm();if(a){a.LMSInitialize("");a.LMSSetValue("cmi.core.lesson_status","incomplete");a.LMSCommit("")}});\n'
        'function markCompleted(){var a=_scorm();if(a){a.LMSSetValue("cmi.core.lesson_status","completed");a.LMSCommit("");a.LMSFinish("")}}\n'
        '</script>\n'
        '</head><body>\n'
        f'<h1>{title}</h1>\n'
        f'<p><strong>등급:</strong> {grade}</p>\n'
        f'<p><strong>요약:</strong> {summary}</p>\n'
        f'<pre style="white-space:pre-wrap">{body}</pre>\n'
        '<button onclick="markCompleted()">학습 완료 표시</button>\n'
        f'<p style="color:#666;font-size:11px">{COMPLIANCE_AI_DISCLAIMER}</p>\n'
        '</body></html>\n'
    )


def export_scorm_package(path_id: int) -> bytes | None:
    """learning_paths.id → SCORM 1.2 ZIP 바이트. path 미존재 시 None."""
    from features.compliance.learning.learning_path import _conn
    c = _conn()
    p = c.execute(
        "SELECT * FROM learning_paths WHERE id = ?", (path_id,),
    ).fetchone()
    if p is None:
        c.close()
        return None
    try:
        curriculum = json.loads(p["curriculum_json"] or "[]")
    except json.JSONDecodeError:
        curriculum = []
    # 모든 change_id 평탄화 + 메타 fetch
    items: list[dict[str, Any]] = []
    change_meta: dict[int, dict[str, Any]] = {}
    flat_ids: list[int] = []
    for week in curriculum:
        for cid in week.get("change_ids") or []:
            cid = int(cid)
            flat_ids.append(cid)
            items.append({
                "change_id": cid,
                "week": int(week.get("week", 1)),
                "title": "",
            })
    if flat_ids:
        placeholders = ",".join(["?"] * len(flat_ids))
        rows = c.execute(
            f"""SELECT id, item_title, summary_ko, grade, new_value
                FROM regulation_changes WHERE id IN ({placeholders})""",
            flat_ids,
        ).fetchall()
        for r in rows:
            change_meta[int(r["id"])] = dict(r)
    c.close()

    # items 에 title 채움
    for it in items:
        meta = change_meta.get(it["change_id"], {})
        it["title"] = meta.get("item_title") or f"change {it['change_id']}"

    manifest = _scorm_manifest(dict(p), items)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("imsmanifest.xml", manifest)
        for it in items:
            cid = it["change_id"]
            html = _scorm_sco_html(change_meta.get(cid, {"id": cid}))
            zf.writestr(f"sco_{cid}.html", html)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# xAPI (Tin Can)
# ─────────────────────────────────────────────────────────────


_XAPI_VERB_MAP = {
    "pending": ("attempted", "http://adlnet.gov/expapi/verbs/attempted"),
    "in_progress": ("attempted", "http://adlnet.gov/expapi/verbs/attempted"),
    "pass": ("passed", "http://adlnet.gov/expapi/verbs/passed"),
    "pass_with_comment": ("passed", "http://adlnet.gov/expapi/verbs/passed"),
    "redo": ("failed", "http://adlnet.gov/expapi/verbs/failed"),
}


def export_xapi_statements(path_id: int) -> list[dict[str, Any]] | None:
    """learning_progress → xAPI statements list. path 미존재 시 None."""
    from features.compliance.learning.learning_path import _conn
    c = _conn()
    p = c.execute(
        "SELECT * FROM learning_paths WHERE id = ?", (path_id,),
    ).fetchone()
    if p is None:
        c.close()
        return None
    progs = c.execute(
        "SELECT * FROM learning_progress WHERE path_id = ? ORDER BY week, id",
        (path_id,),
    ).fetchall()
    c.close()

    actor_email = (
        p["assignee_employee_id"]
        if "@" in (p["assignee_employee_id"] or "")
        else f"mailto:{p['assignee_employee_id']}@ajin.local"
    )
    statements: list[dict[str, Any]] = []
    for r in progs:
        verb_name, verb_id = _XAPI_VERB_MAP.get(
            (r["mentor_review"] or "pending"),
            ("attempted", "http://adlnet.gov/expapi/verbs/attempted"),
        )
        ts = (r["updated_at"] or datetime.now(timezone.utc).isoformat())
        score = r["quiz_score"]
        score_obj = (
            {"raw": int(score), "min": 0, "max": 100,
             "scaled": round(int(score) / 100, 2)}
            if score is not None and int(score) >= 0 else None
        )
        st: dict[str, Any] = {
            "actor": {"mbox": actor_email if actor_email.startswith("mailto:")
                       else f"mailto:{actor_email}"},
            "verb": {"id": verb_id, "display": {"en-US": verb_name}},
            "object": {
                "id": f"http://ajin.local/compliance/change/{r['change_id']}",
                "definition": {
                    "name": {"ko": f"규제 변경 {r['change_id']}"},
                    "type": "http://adlnet.gov/expapi/activities/lesson",
                },
            },
            "timestamp": ts,
            "context": {
                "extensions": {
                    "http://ajin.local/x/path_id": path_id,
                    "http://ajin.local/x/week": int(r["week"]),
                    "http://ajin.local/x/quiz_attempts": int(r["quiz_attempts"] or 0),
                },
            },
        }
        if score_obj:
            st["result"] = {"score": score_obj,
                             "completion": verb_name == "passed",
                             "success": verb_name == "passed"}
        statements.append(st)
    return statements
