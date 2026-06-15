"""Feature F (Equipment) endpoint + DB 진단 — Mock 제거 작업 Phase 0.

사용:
    python3 scripts/diagnose_equipment.py
    python3 scripts/diagnose_equipment.py --base-url http://localhost:8000
    python3 scripts/diagnose_equipment.py --token <JWT>

출력:
    - 콘솔 요약
    - update_log/v4.1_mock_removal/equipment_diagnosis_<date>.md
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "equipment"
SPC_ML_DIR = REPO_ROOT / "data" / "spc_ml"
OUT_DIR = REPO_ROOT / "update_log" / "v4.1_mock_removal"

# (method, path, body, label) — equipment.py 13 endpoint 전부.
ENDPOINTS: list[tuple[str, str, dict[str, Any] | None, str]] = [
    ("GET", "/api/equipment/dashboard/overview", None, "overview"),
    ("GET", "/api/equipment/headline", None, "headline"),
    ("GET", "/api/equipment/spc/cch", None, "spc(cch)"),
    ("GET", "/api/equipment/spc/violations/recent", None, "spc/violations"),
    ("POST", "/api/equipment/error/search", {"query": "베어링 마모", "top_k": 5}, "error/search"),
    ("GET", "/api/equipment/error/categories", None, "error/categories"),
    ("GET", "/api/equipment/markov/E-101", None, "markov(E-101)"),
    ("GET", "/api/equipment/molds", None, "molds"),
    ("GET", "/api/equipment/mtbf", None, "mtbf"),
    ("GET", "/api/equipment/ml-engines/status", None, "ml-engines/status"),
    ("POST", "/api/equipment/manual/search", {"query": "프레스 가이드 핀 교체", "top_k": 3}, "manual/search"),
    ("GET", "/api/equipment/inspection/checklist/press", None, "inspection(press)"),
]

# DB 파일과 핵심 테이블 후보 — 테이블 존재 여부 확인 후 row count.
DB_TARGETS = [
    ("error_codes.db", ["error_codes", "errors"]),
    ("error_history.db", ["error_history", "history"]),
    ("inspection.db", ["inspection_logs", "checklists", "inspections"]),
    ("maintenance.db", ["maintenance_history", "maintenance", "maintenance_cost"]),
    ("mold_lifecycle.db", ["mold_maintenance_logs", "mold_shot_logs", "molds", "mold_lifecycle"]),
    ("molds.db", ["molds", "mold_master"]),
    ("drawings.db", ["drawings"]),
]


def _request(base_url: str, method: str, path: str, body: dict[str, Any] | None, token: str | None) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urlrequest.Request(url, data=data, method=method, headers=headers)
    started = time.perf_counter()
    try:
        with urlrequest.urlopen(req, timeout=15) as resp:
            payload = resp.read()
            elapsed_ms = (time.perf_counter() - started) * 1000
            return {
                "ok": True,
                "status": resp.status,
                "bytes": len(payload),
                "ms": round(elapsed_ms, 1),
                "preview": _preview(payload),
            }
    except urlerror.HTTPError as e:
        elapsed_ms = (time.perf_counter() - started) * 1000
        body_bytes = b""
        try:
            body_bytes = e.read()
        except Exception:
            pass
        return {
            "ok": False,
            "status": e.code,
            "bytes": len(body_bytes),
            "ms": round(elapsed_ms, 1),
            "preview": _preview(body_bytes),
        }
    except (urlerror.URLError, TimeoutError, OSError) as e:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {"ok": False, "status": 0, "bytes": 0, "ms": round(elapsed_ms, 1), "error": str(e)}


def _preview(payload: bytes) -> str:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return f"<binary {len(payload)}B>"
    return (text[:160] + "…") if len(text) > 160 else text


def _db_rowcount(db_path: Path, table_candidates: list[str]) -> dict[str, Any]:
    if not db_path.exists():
        return {"exists": False}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            counts: dict[str, int] = {}
            for tbl in table_candidates:
                if tbl in tables:
                    counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            return {
                "exists": True,
                "size_kb": round(db_path.stat().st_size / 1024, 1),
                "tables": sorted(tables),
                "counts": counts,
            }
        finally:
            conn.close()
    except sqlite3.Error as e:
        return {"exists": True, "error": str(e)}


def _csv_rowcounts(csv_dir: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if not csv_dir.exists():
        return out
    for csv in sorted(csv_dir.glob("*.csv")):
        try:
            with csv.open("r", encoding="utf-8") as f:
                out[csv.name] = sum(1 for _ in f) - 1  # header 제외
        except OSError as e:
            out[csv.name] = -1
            print(f"[warn] {csv.name} read 실패: {e}", file=sys.stderr)
    return out


def _render_markdown(endpoint_results: list[dict[str, Any]], db_results: dict[str, dict], csv_counts: dict[str, int], base_url: str) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append(f"# Feature F 진단 보고서")
    lines.append("")
    lines.append(f"- 생성: {now}")
    lines.append(f"- Base URL: {base_url}")
    lines.append("")

    lines.append("## 1. Endpoint 상태")
    lines.append("")
    lines.append("| Endpoint | Method | Status | Bytes | ms | OK |")
    lines.append("|---|---|---|---|---|---|")
    for r in endpoint_results:
        ok_mark = "✅" if r["ok"] else "❌"
        lines.append(f"| `{r['path']}` | {r['method']} | {r['status']} | {r['bytes']} | {r['ms']} | {ok_mark} |")
    lines.append("")

    lines.append("## 2. SQLite DB 상태")
    lines.append("")
    for db_name, info in db_results.items():
        lines.append(f"### `{db_name}`")
        if not info.get("exists"):
            lines.append("- ❌ 파일 없음")
            lines.append("")
            continue
        if "error" in info:
            lines.append(f"- ⚠️ 에러: {info['error']}")
            lines.append("")
            continue
        lines.append(f"- 크기: {info['size_kb']} KB")
        lines.append(f"- 전체 테이블: {', '.join(info['tables']) or '(없음)'}")
        if info["counts"]:
            for tbl, cnt in info["counts"].items():
                mark = "✅" if cnt > 0 else "⚠️ (비어있음)"
                lines.append(f"- `{tbl}`: {cnt} rows {mark}")
        else:
            lines.append("- ⚠️ 후보 테이블 매칭 없음 — 스키마 확인 필요")
        lines.append("")

    lines.append("## 3. SPC CSV 행수")
    lines.append("")
    if not csv_counts:
        lines.append("- ❌ `data/spc_ml/` 비어있음 — `make seed-equipment` 실행 필요")
    else:
        for name, cnt in csv_counts.items():
            mark = "✅" if cnt > 100 else "⚠️"
            lines.append(f"- `{name}`: {cnt} rows {mark}")
    lines.append("")

    # 판정
    lines.append("## 4. 판정")
    lines.append("")
    failed_endpoints = [r for r in endpoint_results if not r["ok"]]
    empty_dbs = [n for n, info in db_results.items() if info.get("exists") and info.get("counts") and all(c == 0 for c in info["counts"].values())]
    missing_dbs = [n for n, info in db_results.items() if not info.get("exists")]
    empty_csv = [n for n, c in csv_counts.items() if c <= 100]

    if not failed_endpoints and not empty_dbs and not missing_dbs and not empty_csv:
        lines.append("✅ **Phase 1로 직행 가능** — 모든 endpoint 정상 + DB·CSV 충분")
    else:
        lines.append("⚠️ **Phase 0.2 seed 필요**:")
        if failed_endpoints:
            lines.append(f"- 실패 endpoint {len(failed_endpoints)}개: {', '.join(r['label'] for r in failed_endpoints)}")
        if missing_dbs:
            lines.append(f"- 누락 DB: {', '.join(missing_dbs)}")
        if empty_dbs:
            lines.append(f"- 비어있는 DB: {', '.join(empty_dbs)}")
        if empty_csv:
            lines.append(f"- 부족한 CSV: {', '.join(empty_csv)}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Feature F endpoint + DB 진단")
    parser.add_argument("--base-url", default=os.environ.get("AJIN_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.environ.get("AJIN_TOKEN"), help="JWT (생략 시 인증 없이 호출)")
    parser.add_argument("--skip-http", action="store_true", help="endpoint 호출 건너뛰기 (DB만)")
    args = parser.parse_args()

    print(f"[diagnose] base={args.base_url}")

    endpoint_results: list[dict[str, Any]] = []
    if not args.skip_http:
        for method, path, body, label in ENDPOINTS:
            r = _request(args.base_url, method, path, body, args.token)
            r.update({"method": method, "path": path, "label": label})
            endpoint_results.append(r)
            mark = "✅" if r["ok"] else "❌"
            print(f"  {mark} {method:4s} {path:60s} {r['status']:>3} {r['bytes']:>6}B {r['ms']:>6}ms")

    print("[diagnose] DB row counts…")
    db_results: dict[str, dict] = {}
    for db_name, candidates in DB_TARGETS:
        info = _db_rowcount(DATA_DIR / db_name, candidates)
        db_results[db_name] = info
        if info.get("exists"):
            counts = info.get("counts", {})
            summary = ", ".join(f"{k}={v}" for k, v in counts.items()) or "(매칭 없음)"
            print(f"  ✅ {db_name:25s} {summary}")
        else:
            print(f"  ❌ {db_name:25s} 파일 없음")

    print("[diagnose] CSV…")
    csv_counts = _csv_rowcounts(SPC_ML_DIR)
    for name, cnt in csv_counts.items():
        print(f"  {'✅' if cnt > 100 else '⚠️'} {name:35s} {cnt} rows")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"equipment_diagnosis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(_render_markdown(endpoint_results, db_results, csv_counts, args.base_url), encoding="utf-8")
    print(f"[diagnose] 보고서: {out_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
