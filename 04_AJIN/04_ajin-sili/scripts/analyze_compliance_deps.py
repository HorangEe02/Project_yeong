"""AST-based dependency analyzer for features/compliance/ → 6 subpackage migration (v4.7 D mv).

Outputs:
- update_log/v4.7_d_mv/dep_graph.md (Mermaid)
- update_log/v4.7_d_mv/import_baseline.json (per-file dependency list)

Detects:
- Cross-cluster imports
- Circular imports (DFS)
"""

from __future__ import annotations

import ast
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPL = ROOT / "features" / "compliance"
OUT_DIR = ROOT / "update_log" / "v4.7_d_mv"

# 6-cluster classification (v4.7 plan §2.2 + 2.2.1)
CLUSTER_MAP: dict[str, str] = {
    # crawlers (12)
    "iso_crawler": "crawlers",
    "apqp_crawler": "crawlers",
    "msds_crawler": "crawlers",
    "domestic_law_crawler": "crawlers",
    "eu_regulation_crawler": "crawlers",
    "oem_quality_crawler": "crawlers",
    "carbon_esg_crawler": "crawlers",
    "ev_battery_crawler": "crawlers",
    "global_trade_crawler": "crawlers",
    "us_trade_crawler": "crawlers",
    "base_crawler": "crawlers",
    "crawler": "crawlers",
    # rag (8)
    "regulation_qa": "rag",
    "whatif_engine": "rag",
    "cost_simulator": "rag",
    "tariff_simulator": "rag",
    "financial_baseline": "rag",
    "accounting_trace": "rag",
    "demo_scenario_engine": "rag",
    "regulation_context": "rag",
    # alerts (10)
    "change_detector": "alerts",
    "change_classifier": "alerts",
    "text_change_detector": "alerts",
    "regulation_classifier": "alerts",
    "legal_classifier": "alerts",
    "notify": "alerts",
    "notify_slack": "alerts",
    "notify_sms": "alerts",
    "alert_generator": "alerts",
    "alarm_aggregator": "alerts",
    # supply (5)
    "supplier_compliance": "supply",
    "supplier_discovery": "supply",
    "supplier_graph": "supply",
    "supplier_recommender": "supply",
    "industry_trend": "supply",
    # learning (4)
    "learning_path": "learning",
    "regulation_exporter": "learning",
    "exec_report": "learning",
    "lms_export": "learning",
    # infra (19) — plan listed 15 + 4 extras (sop_diff/delegation_rules/version_manager/_http)
    "compliance_db": "infra",
    "risk_scorer": "infra",
    "impact_analyzer": "infra",
    "impact_network": "infra",
    "plant_regulation_mapper": "infra",
    "facility_db": "infra",
    "timeline_builder": "infra",
    "feedback_loop": "infra",
    "regulation_indexer": "infra",
    "case_law_indexer": "infra",
    "contract_indexer": "infra",
    "jira_sync": "infra",
    "approval_workflow": "infra",
    "collab_ticket": "infra",
    "compliance_checker": "infra",
    "_http": "infra",
    "sop_diff": "infra",
    "delegation_rules": "infra",
    "version_manager": "infra",
}


def collect_imports(py_file: Path) -> set[str]:
    """Return set of features.compliance.<X> imported by py_file."""
    deps: set[str] = set()
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return deps
    for node in ast.walk(tree):
        # `from features.compliance.X import ...`
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "features.compliance":
                # `from features.compliance import X` — each name is module-or-symbol
                for alias in node.names:
                    if alias.name in CLUSTER_MAP:
                        deps.add(alias.name)
            elif node.module.startswith("features.compliance."):
                tail = node.module.removeprefix("features.compliance.")
                head = tail.split(".")[0]
                if head in CLUSTER_MAP:
                    deps.add(head)
        # `import features.compliance.X`
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("features.compliance."):
                    tail = alias.name.removeprefix("features.compliance.")
                    head = tail.split(".")[0]
                    if head in CLUSTER_MAP:
                        deps.add(head)
    return deps


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """DFS-based cycle detection. Returns list of cycle paths."""
    cycles: list[list[str]] = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    stack: list[str] = []

    def dfs(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for nxt in graph.get(node, ()):
            if nxt not in color:
                continue
            if color[nxt] == GRAY:
                # cycle: from nxt back to nxt in stack
                idx = stack.index(nxt)
                cycles.append(stack[idx:] + [nxt])
            elif color[nxt] == WHITE:
                dfs(nxt)
        stack.pop()
        color[node] = BLACK

    for n in list(graph):
        if color[n] == WHITE:
            dfs(n)
    return cycles


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph: dict[str, set[str]] = {}
    cluster_xref: dict[tuple[str, str], int] = defaultdict(int)

    for py_file in sorted(COMPL.glob("*.py")):
        mod = py_file.stem
        if mod == "__init__":
            continue
        deps = collect_imports(py_file)
        deps.discard(mod)  # self
        graph[mod] = deps
        src_cluster = CLUSTER_MAP.get(mod, "?")
        for dep in deps:
            tgt_cluster = CLUSTER_MAP.get(dep, "?")
            if src_cluster != tgt_cluster:
                cluster_xref[(src_cluster, tgt_cluster)] += 1

    # baseline JSON
    baseline = {mod: sorted(deps) for mod, deps in graph.items()}
    (OUT_DIR / "import_baseline.json").write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    cycles = find_cycles(graph)

    # cluster summary
    cluster_files: dict[str, list[str]] = defaultdict(list)
    for mod in graph:
        cluster_files[CLUSTER_MAP.get(mod, "?")].append(mod)

    # Mermaid graph
    lines: list[str] = [
        "# features/compliance/ dependency graph (v4.7 D mv baseline)",
        "",
        f"Total modules: {len(graph)}",
        f"Total edges: {sum(len(d) for d in graph.values())}",
        f"Cycles: {len(cycles)}",
        "",
        "## Cluster sizes",
        "",
        "| cluster | count | files |",
        "|---|---|---|",
    ]
    for cl in ["crawlers", "rag", "alerts", "supply", "learning", "infra", "?"]:
        files = sorted(cluster_files.get(cl, []))
        if files:
            lines.append(f"| {cl} | {len(files)} | {', '.join(files)} |")
    lines += [
        "",
        "## Cross-cluster import counts",
        "",
        "| from | to | count |",
        "|---|---|---|",
    ]
    for (a, b), c in sorted(cluster_xref.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {a} | {b} | {c} |")
    lines += ["", "## Cycles (DFS)", ""]
    if cycles:
        for cyc in cycles:
            lines.append(f"- {' → '.join(cyc)}")
    else:
        lines.append("(none)")

    lines += [
        "",
        "## Mermaid cluster graph",
        "",
        "```mermaid",
        "flowchart LR",
    ]
    seen_edges: set[tuple[str, str]] = set()
    for (a, b), c in cluster_xref.items():
        if (a, b) in seen_edges:
            continue
        seen_edges.add((a, b))
        lines.append(f"  {a} -->|{c}| {b}")
    lines.append("```")

    (OUT_DIR / "dep_graph.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: wrote {OUT_DIR/'dep_graph.md'} and {OUT_DIR/'import_baseline.json'}")
    print(f"modules={len(graph)} cycles={len(cycles)}")


if __name__ == "__main__":
    main()
