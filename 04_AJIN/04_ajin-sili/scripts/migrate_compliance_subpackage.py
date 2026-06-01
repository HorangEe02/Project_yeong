"""Rewrite internal imports across features/compliance/<sub>/*.py to point at new sub-paths.

After Phase 1 (git mv), each moved file still contains:
    from features.compliance.X import ...
    from features.compliance import X  (rarer, e.g. `from features.compliance import jira_sync`)

This script rewrites both into the new sub-path form:
    from features.compliance.<sub_for_X>.X import ...
    from features.compliance.<sub_for_X> import X

Usage:
  python3 scripts/migrate_compliance_subpackage.py --dry-run
  python3 scripts/migrate_compliance_subpackage.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPL = ROOT / "features" / "compliance"

SUBS = ["crawlers", "rag", "alerts", "supply", "learning", "infra"]

CLUSTER_MAP: dict[str, str] = {
    # crawlers
    "iso_crawler": "crawlers", "apqp_crawler": "crawlers", "msds_crawler": "crawlers",
    "domestic_law_crawler": "crawlers", "eu_regulation_crawler": "crawlers",
    "oem_quality_crawler": "crawlers", "carbon_esg_crawler": "crawlers",
    "ev_battery_crawler": "crawlers", "global_trade_crawler": "crawlers",
    "us_trade_crawler": "crawlers", "base_crawler": "crawlers", "crawler": "crawlers",
    # rag
    "regulation_qa": "rag", "whatif_engine": "rag", "cost_simulator": "rag",
    "tariff_simulator": "rag", "financial_baseline": "rag",
    "accounting_trace": "rag", "demo_scenario_engine": "rag",
    "regulation_context": "rag",
    # alerts
    "change_detector": "alerts", "change_classifier": "alerts",
    "text_change_detector": "alerts", "regulation_classifier": "alerts",
    "legal_classifier": "alerts", "notify": "alerts", "notify_slack": "alerts",
    "notify_sms": "alerts", "alert_generator": "alerts", "alarm_aggregator": "alerts",
    # supply
    "supplier_compliance": "supply", "supplier_discovery": "supply",
    "supplier_graph": "supply", "supplier_recommender": "supply",
    "industry_trend": "supply",
    # learning
    "learning_path": "learning", "regulation_exporter": "learning",
    "exec_report": "learning", "lms_export": "learning",
    # infra
    "_http": "infra", "compliance_db": "infra", "risk_scorer": "infra",
    "impact_analyzer": "infra", "impact_network": "infra",
    "plant_regulation_mapper": "infra", "facility_db": "infra",
    "timeline_builder": "infra", "feedback_loop": "infra",
    "regulation_indexer": "infra", "case_law_indexer": "infra",
    "contract_indexer": "infra", "jira_sync": "infra",
    "approval_workflow": "infra", "collab_ticket": "infra",
    "compliance_checker": "infra", "sop_diff": "infra",
    "delegation_rules": "infra", "version_manager": "infra",
}

# Pattern A: `from features.compliance.X import ...`
RE_FROM_DOT = re.compile(r"from\s+features\.compliance\.([A-Za-z_][A-Za-z0-9_]*)\s+import\b")
# Pattern B: `from features.compliance import a, b, c`  (handles symbols/modules at top level)
RE_FROM_TOP = re.compile(r"^(\s*)from\s+features\.compliance\s+import\s+(.+)$", re.MULTILINE)


def rewrite_text(src: str) -> tuple[str, int]:
    """Rewrite imports. Returns (new_text, change_count)."""
    changes = 0

    def repl_dot(m: re.Match[str]) -> str:
        nonlocal changes
        mod = m.group(1)
        sub = CLUSTER_MAP.get(mod)
        if sub is None:
            # Could be `_common`/`_backlog`/already-prefixed sub — leave it
            if mod in SUBS or mod in ("_common", "_backlog"):
                return m.group(0)
            return m.group(0)
        changes += 1
        return f"from features.compliance.{sub}.{mod} import"

    new_src = RE_FROM_DOT.sub(repl_dot, src)

    def repl_top(m: re.Match[str]) -> str:
        nonlocal changes
        indent = m.group(1)
        rest = m.group(2).rstrip()
        # Strip optional trailing comment
        body = rest
        comment = ""
        if "#" in body:
            ix = body.index("#")
            comment = " " + body[ix:]
            body = body[:ix].rstrip()
        # Handle parenthesized multi-line: not in oneline -- only single-line
        if body.endswith("\\"):
            return m.group(0)
        names_part = body.strip().rstrip(",")
        # Skip parenthesized
        if names_part.startswith("("):
            return m.group(0)
        parts = [p.strip() for p in names_part.split(",") if p.strip()]
        # Decide: if every name is a CLUSTER_MAP module, we can rewrite per-sub.
        # If any name is a sub-package (crawlers/rag/...) or unknown symbol, keep top-level import.
        if not parts:
            return m.group(0)
        out_lines: list[str] = []
        unknown: list[str] = []
        sub_to_mods: dict[str, list[str]] = {}
        for p in parts:
            # Handle `X as Y`
            name = p.split(" as ")[0].strip()
            sub = CLUSTER_MAP.get(name)
            if sub is None:
                unknown.append(p)
            else:
                sub_to_mods.setdefault(sub, []).append(p)
        if unknown:
            # leave entirely — we cannot safely partial-rewrite
            return m.group(0)
        for sub, mods in sub_to_mods.items():
            out_lines.append(f"{indent}from features.compliance.{sub} import {', '.join(mods)}")
        changes += 1
        result = "\n".join(out_lines) + comment
        return result

    new_src = RE_FROM_TOP.sub(repl_top, new_src)
    return new_src, changes


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--sub", choices=SUBS, help="Limit to one sub-package")
    args = ap.parse_args()

    targets: list[Path] = []
    subs = [args.sub] if args.sub else SUBS
    for s in subs:
        targets.extend(sorted((COMPL / s).glob("*.py")))

    total_changes = 0
    changed_files: list[str] = []
    for p in targets:
        src = p.read_text(encoding="utf-8")
        new_src, n = rewrite_text(src)
        if n > 0:
            total_changes += n
            changed_files.append(f"{p.relative_to(ROOT)}: {n}")
            if args.apply:
                p.write_text(new_src, encoding="utf-8")
    print(f"changes={total_changes} files={len(changed_files)}")
    for line in changed_files:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
