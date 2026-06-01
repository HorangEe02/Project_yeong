#!/usr/bin/env python3
"""기존 seed_documents.json (합성 30건 보존) + 신규 real_documents seed JSON 들 병합.

사용:
    python3 scripts/merge_real_documents.py
        --base data/demo_documents/seed_documents.json
        --add data/real_documents/kosha_real_seed.json
        --out data/demo_documents/seed_documents.json

기본 동작: 기존 doc_id 와 충돌 없는 신규 entry 만 추가.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="data/demo_documents/seed_documents.json")
    p.add_argument("--add", action="append", required=True,
                   help="추가할 seed JSON 경로 (반복 지정 가능)")
    p.add_argument("--out", default="data/demo_documents/seed_documents.json")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    base_path = Path(args.base)
    out_path = Path(args.out)

    base_docs: list[dict] = json.loads(base_path.read_text(encoding="utf-8"))
    base_ids = {d["doc_id"] for d in base_docs}
    print(f"BASE: {base_path} → {len(base_docs)} docs ({len(base_ids)} unique ids)")

    new_docs: list[dict] = []
    for add_path in args.add:
        ap = Path(add_path)
        docs = json.loads(ap.read_text(encoding="utf-8"))
        added = 0
        skipped = 0
        for d in docs:
            if d["doc_id"] in base_ids:
                skipped += 1
                continue
            new_docs.append(d)
            base_ids.add(d["doc_id"])
            added += 1
        print(f"ADD : {ap} → +{added}, skip {skipped} (id 충돌)")

    if not new_docs:
        print("→ 추가할 신규 문서가 없음. 종료.")
        return 0

    merged = base_docs + new_docs
    print(f"\nMERGED total: {len(merged)} (기존 {len(base_docs)} + 신규 {len(new_docs)})")

    types: dict[str, int] = {}
    for d in merged:
        types[d.get("doc_type", "unknown")] = types.get(d.get("doc_type", "unknown"), 0) + 1
    print(f"doc_type 분포: {types}")

    if args.dry_run:
        print("→ --dry-run 이므로 파일 저장 안 함")
        return 0

    # 백업
    if out_path.exists():
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = out_path.with_suffix(f".{ts}.bak.json")
        shutil.copy2(out_path, backup)
        print(f"BACKUP: {backup}")

    out_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"WROTE : {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
