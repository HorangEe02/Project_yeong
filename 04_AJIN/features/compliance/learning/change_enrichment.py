"""규제 항목별 변경 이력 + 사내 영향 분석을 마크다운으로 렌더링.

Issue 3 통합 모듈 — change_detector(SQLite) + text_change_detector(diff) +
impact_analyzer(facility 매핑) 의 결과를 regulation_exporter 보고서에 합성한다.

데이터 흐름:
    regulation_type (예: "iso") + item_id
      ↓
    regulation_changes 테이블 쿼리 (before_text, after_text, impact_json)
      ↓
    TextChangeDetector → unified diff + 핵심 수치 변경
      ↓
    ImpactAnalyzer 결과(JSON 역직렬화) → 영향 사업장/공정/인원/위험도
      ↓
    마크다운 섹션
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional


def build_change_history_section(
    regulation_type: str,
    item_id: str = "",
    limit: int = 5,
    db_path: str | Path = "data/compliance_changes.db",
) -> list[str]:
    """regulation_changes 테이블에서 변경 이력을 조회해 마크다운 섹션을 반환한다.

    Args:
        regulation_type: 크롤러 타입 (예: "iso", "msds", "domestic_law")
        item_id: 특정 항목만 필터링 (빈 문자열이면 type 전체)
        limit: 최근 N건만
        db_path: regulation_changes SQLite 경로

    Returns:
        마크다운 라인 리스트. 변경 이력이 없으면 빈 리스트.
    """
    rows = _query_changes(regulation_type, item_id, limit, db_path)
    if not rows:
        return []

    lines: list[str] = []
    lines.append("")
    lines.append("#### 📊 규제 변경 이력 (과거 vs 현재)")
    lines.append("")

    for row in rows:
        change_type = row.get("change_type", "modified")
        detected_at = row.get("detected_at", "")
        diff_html = row.get("diff_html", "")
        before_text = row.get("before_text", "")
        after_text = row.get("after_text", "")

        lines.append(f"**{detected_at[:10]} · {_change_type_label(change_type)}**")

        if before_text or after_text:
            analysis = _analyze_text_diff(before_text, after_text)
            if analysis:
                lines.append("")
                lines.append(analysis)
        elif diff_html:
            lines.append("")
            lines.append("(상세 diff 는 웹 UI 에서 확인 가능)")
        else:
            old_v = row.get("old_value", "")
            new_v = row.get("new_value", "")
            if old_v or new_v:
                lines.append("")
                if old_v:
                    lines.append(f"- 이전: `{_truncate(old_v, 200)}`")
                if new_v:
                    lines.append(f"- 현재: `{_truncate(new_v, 200)}`")

        lines.append("")

    lines.append("---")
    return lines


def build_impact_section(
    regulation_type: str,
    item_id: str = "",
    db_path: str | Path = "data/compliance_changes.db",
) -> list[str]:
    """가장 최근 변경의 impact_json 을 풀어서 사내 영향 섹션을 만든다."""
    rows = _query_changes(regulation_type, item_id, limit=1, db_path=db_path)
    if not rows:
        return []

    impact_raw = rows[0].get("impact_json", "")
    impact = _parse_impact(impact_raw)
    if not impact:
        return []

    lines: list[str] = []
    lines.append("")
    lines.append("#### 🏭 아진산업 영향 분석")
    lines.append("")

    plants = impact.get("affected_plants") or []
    processes = impact.get("affected_processes") or []
    workers = impact.get("affected_workers")
    chemicals = impact.get("affected_chemicals") or []
    standards = impact.get("affected_standards") or []
    risk_score = impact.get("risk_score")
    severity = impact.get("severity")
    actions = impact.get("required_actions") or []
    deadline = impact.get("deadline")
    cost = impact.get("estimated_cost")

    if plants:
        lines.append(f"- **영향 사업장 ({len(plants)}개)**: {', '.join(plants)}")
    if processes:
        lines.append(f"- **영향 공정 ({len(processes)}개)**: {', '.join(processes)}")
    if workers is not None:
        lines.append(f"- **영향 작업자**: {workers}명")
    if chemicals:
        lines.append(f"- **관련 화학물질**: {', '.join(chemicals[:10])}")
    if standards:
        lines.append(f"- **관련 안전기준**: {', '.join(standards[:10])}")
    if risk_score is not None:
        try:
            score = float(risk_score)
            lines.append(f"- **위험 점수**: {score:.0f} / 100  ({_risk_grade(score)})")
        except (TypeError, ValueError):
            pass
    if severity:
        lines.append(f"- **심각도**: {severity}")
    if deadline:
        lines.append(f"- **시행/대응 마감일**: {deadline}")
    if cost:
        lines.append(f"- **예상 비용**: {cost}")

    if actions:
        lines.append("")
        lines.append("**권장 조치 사항**")
        for a in actions[:5]:
            lines.append(f"- {a}")

    lines.append("")
    lines.append("---")
    return lines


# ─────────────────────────────────────────────
# 내부 유틸
# ─────────────────────────────────────────────


def _query_changes(
    regulation_type: str,
    item_id: str,
    limit: int,
    db_path: str | Path,
) -> list[dict]:
    path = Path(db_path)
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        if item_id:
            rows = conn.execute(
                """SELECT * FROM regulation_changes
                   WHERE regulation_type = ? AND item_id = ?
                   ORDER BY detected_at DESC LIMIT ?""",
                (regulation_type, item_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM regulation_changes
                   WHERE regulation_type = ?
                   ORDER BY detected_at DESC LIMIT ?""",
                (regulation_type, limit),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []


def _analyze_text_diff(before_text: str, after_text: str) -> str:
    """TextChangeDetector 로 summary 한 줄 + 변경 단위 bullet 생성."""
    if not (before_text or after_text):
        return ""
    try:
        from features.compliance.alerts.text_change_detector import ChangeDetector

        detector = ChangeDetector()
        analysis = detector.detect(before_text, after_text)
    except Exception:
        return ""

    out = [analysis.summary] if analysis.summary else []
    for ch in analysis.changes[:6]:
        if ch.change_type == "modified":
            out.append(f"- 수정: `{_truncate(ch.before, 80)}` → `{_truncate(ch.after, 80)}`")
        elif ch.change_type == "added":
            out.append(f"- 추가: `{_truncate(ch.after, 120)}`")
        elif ch.change_type == "removed":
            out.append(f"- 삭제: `{_truncate(ch.before, 120)}`")
    if analysis.key_numbers_changed:
        out.append("")
        out.append("**핵심 수치 변경**")
        for kn in analysis.key_numbers_changed[:5]:
            out.append(f"- {kn['before']} → {kn['after']} ({kn['direction']})")
    return "\n".join(out)


def _parse_impact(raw: object) -> Optional[dict]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _change_type_label(change_type: str) -> str:
    return {
        "added": "신규 추가",
        "removed": "삭제",
        "modified": "변경 (수정)",
    }.get(change_type, change_type)


def _risk_grade(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def _truncate(text: str, max_chars: int) -> str:
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


__all__ = ["build_change_history_section", "build_impact_section"]
