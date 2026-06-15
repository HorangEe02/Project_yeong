"""D 컴플라이언스 알람 백엔드 신설을 위한 사전 진단 (v4.2 Phase 0).

목적: `regulation_changes` 테이블·`data/scenarios/` JSON 등 알람 5종 소스의
현재 가용 데이터를 측정해 Phase 1 endpoint 가 의미있는 알람을 반환할지 판정.

실행:
    python3 scripts/diagnose_compliance_alarms.py
출력:
    update_log/v4.2_d_alarms/diagnosis_<timestamp>.md
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "compliance_changes.db"
SCENARIOS_DIR = REPO / "data" / "scenarios"
OUT_DIR = REPO / "update_log" / "v4.2_d_alarms"

# 시행일 추출 휴리스틱 — new_value / summary_ko 텍스트에서 YYYY-MM-DD 패턴 검색.
DATE_RE = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")


def _extract_effective_date(text: str | None) -> date | None:
    if not text:
        return None
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return date(y, mo, d)
    except ValueError:
        return None


def _scan_regulation_changes() -> dict:
    if not DB_PATH.exists():
        return {"exists": False}
    out: dict = {"exists": True, "size_kb": round(DB_PATH.stat().st_size / 1024, 1)}
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        total = conn.execute("SELECT COUNT(*) FROM regulation_changes").fetchone()[0]
        out["total"] = total

        if total == 0:
            return out

        # 분포 — change_type, severity, status, grade
        for col in ("change_type", "severity", "status", "grade", "regulation_type"):
            rows = conn.execute(
                f"SELECT {col}, COUNT(*) FROM regulation_changes GROUP BY {col}"
            ).fetchall()
            out[f"{col}_dist"] = dict(rows)

        # ack 미완 수
        out["unacknowledged"] = conn.execute(
            "SELECT COUNT(*) FROM regulation_changes WHERE acknowledged=0"
        ).fetchone()[0]

        # action_required + 7일 초과 (소스 4)
        out["unresolved_7days"] = conn.execute(
            """SELECT COUNT(*) FROM regulation_changes
               WHERE status='action_required'
                 AND julianday('now') - julianday(detected_at) >= 7"""
        ).fetchone()[0]

        # 시행일 추출 가능 row 수 (소스 3)
        today = date.today()
        rows = conn.execute(
            "SELECT id, new_value, summary_ko, detected_at FROM regulation_changes"
        ).fetchall()
        dday_candidates: list[tuple[int, int]] = []  # (id, days_until)
        for rid, nv, summary, _ in rows:
            ed = _extract_effective_date(nv) or _extract_effective_date(summary)
            if ed is None:
                continue
            delta = (ed - today).days
            if 0 <= delta <= 30:
                dday_candidates.append((rid, delta))
        out["dday_candidates"] = len(dday_candidates)
        out["dday_sample"] = dday_candidates[:5]

        # detected_at 시간 범위
        rng = conn.execute(
            "SELECT MIN(detected_at), MAX(detected_at) FROM regulation_changes"
        ).fetchone()
        out["detected_range"] = rng
    finally:
        conn.close()
    return out


# NOTE: 아래 공식은 features/compliance/alarm_aggregator.py 의
# _compute_scenario_impact_score 와 1:1 동기화 — 변경 시 양쪽 함께 수정.
def _compute_score(sc: dict) -> int:
    sev = (sc.get("severity") or "").lower()
    score = {"high": 50, "medium": 30, "low": 15}.get(sev, 0)
    score += min(len(sc.get("affected_facility_ids") or []) * 8, 35)
    score += min(len(sc.get("impact_areas") or []) * 5, 25)
    cat = ((sc.get("regulation") or {}).get("category") or "").lower()
    if cat in {"safety", "environmental", "trade"}:
        score += 15
    return min(score, 100)


def _scan_scenarios() -> dict:
    if not SCENARIOS_DIR.exists():
        return {"exists": False}
    out: dict = {"exists": True}
    files = sorted(SCENARIOS_DIR.rglob("*.json"))
    out["json_count"] = len(files)
    if not files:
        return out

    scores: list[int] = []
    for f in files[:200]:  # 상한 — 무거운 디렉토리 보호
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # 시나리오 컨테이너 (us_trade_regulations 처럼 nested) 평탄화
        if isinstance(data, dict) and isinstance(data.get("scenarios"), list):
            items = data["scenarios"]
        elif isinstance(data, dict):
            items = [data]
        elif isinstance(data, list):
            items = data
        else:
            items = []
        for sc in items:
            if not isinstance(sc, dict):
                continue
            scores.append(_compute_score(sc))

    if scores:
        out["score_min"] = min(scores)
        out["score_max"] = max(scores)
        out["score_p80_plus"] = sum(1 for s in scores if s >= 80)
        out["score_p90_plus"] = sum(1 for s in scores if s >= 90)
        out["scenario_total"] = len(scores)
    return out


def _render_md(reg: dict, scen: dict) -> str:
    lines: list[str] = []
    lines.append("# D 컴플라이언스 알람 — 진단 보고서")
    lines.append("")
    lines.append(f"생성: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## 1. regulation_changes")
    lines.append("")
    if not reg.get("exists"):
        lines.append("- ❌ DB 파일 없음")
    elif reg.get("total", 0) == 0:
        lines.append("- ⚠️ 행 0건 — 시연용 seed 필요 (`seed_demo_compliance_alarm.py`)")
    else:
        lines.append(f"- 크기: {reg['size_kb']} KB · 행 {reg['total']}건 · 미ack {reg.get('unacknowledged', 0)}건")
        lines.append(f"- detected_at 범위: {reg.get('detected_range')}")
        for col in ("change_type", "severity", "status", "grade", "regulation_type"):
            dist = reg.get(f"{col}_dist", {})
            if dist:
                kv = ", ".join(f"{k}={v}" for k, v in dist.items())
                lines.append(f"- {col}: {kv}")
    lines.append("")

    lines.append("## 2. 5종 알람 소스별 자격 row 수")
    lines.append("")
    src1 = reg.get("unacknowledged", 0) if reg.get("exists") else 0
    src3 = reg.get("dday_candidates", 0) if reg.get("exists") else 0
    src4 = reg.get("unresolved_7days", 0) if reg.get("exists") else 0
    src2 = scen.get("score_p80_plus", 0) if scen.get("exists") else 0
    lines.append(f"- 소스 1 (law_change, 미ack): **{src1}**")
    lines.append(f"- 소스 2 (impact_score ≥80): **{src2}** (scenario JSON {scen.get('json_count', 0)}개 스캔)")
    lines.append(f"- 소스 3 (D-day ≤30일): **{src3}**")
    if reg.get("dday_sample"):
        lines.append(f"  - 샘플: {reg['dday_sample']}")
    lines.append(f"- 소스 4 (미해결 7일+): **{src4}**")
    lines.append("- 소스 5 (트렌드 2σ): change_detector.get_extended_trend() 실행 필요 (본 진단 미수행)")
    lines.append("")

    lines.append("## 3. 판정")
    lines.append("")
    total_phase1 = src1 + src3
    if total_phase1 == 0:
        lines.append("⚠️ **Phase 1 endpoint 가 빈 응답 반환 예정** — `python3 scripts/seed_demo_compliance_alarm.py` 로 시연 데이터 시드 권장.")
    elif total_phase1 < 3:
        lines.append(f"🟡 Phase 1 알람 {total_phase1}건 만 표시 가능. 더 다양한 시연을 위해 seed 추가 권장.")
    else:
        lines.append(f"✅ Phase 1 알람 {total_phase1}건 표시 가능. endpoint 즉시 의미있는 응답.")
    return "\n".join(lines) + "\n"


def main() -> int:
    print("[diagnose] regulation_changes …")
    reg = _scan_regulation_changes()
    if reg.get("exists"):
        print(f"  total={reg.get('total', 0)} · unacknowledged={reg.get('unacknowledged', 0)}")
        print(f"  dday_candidates={reg.get('dday_candidates', 0)} · unresolved_7days={reg.get('unresolved_7days', 0)}")
    else:
        print("  DB 없음")

    print("[diagnose] data/scenarios …")
    scen = _scan_scenarios()
    if scen.get("exists"):
        print(f"  json_count={scen.get('json_count', 0)} · p80+={scen.get('score_p80_plus', 0)}")
    else:
        print("  디렉토리 없음")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"diagnosis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(_render_md(reg, scen), encoding="utf-8")
    print(f"[diagnose] 보고서: {out_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
