"""Inject product-level v2 splits into a YOLO promote-template (split-carry fix).

The annotation template -> Label Studio -> export -> extract round-trip drops the
benchmark v2 product-level split, so promotion defaults every reviewed row to
``train`` (empty val/test). This re-attaches each row's split from the authoritative
v2 candidate manifests (keyed by ``fixture_id``), so ``promote`` materializes proper
product-level train/val/test (leakage-safe; same product never spans splits).

Writes the output JSONL beside the input template (pipeline path-safety guard).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

SUPPORTED_SPLITS = frozenset({"train", "val", "test"})


def _split_map(manifests: list[Path]) -> dict[str, str]:
    """Return ``fixture_id(candidate_id) -> v2_split`` from candidate manifests."""
    out: dict[str, str] = {}
    for m in manifests:
        for line in m.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            cid = rec.get("candidate_id")
            split = rec.get("v2_split")
            if cid and split in SUPPORTED_SPLITS:
                out[cid] = split
    return out


def build(*, template: Path, manifests: list[Path], output: Path, default_split: str) -> None:
    """Attach v2 splits to promote-template rows and write the result."""
    split_by_fixture = _split_map(manifests)
    rows = [
        json.loads(line)
        for line in template.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    counts: Counter[str] = Counter()
    matched = 0
    for row in rows:
        fid = row.get("fixture_id")
        split = split_by_fixture.get(fid, default_split)
        if fid in split_by_fixture:
            matched += 1
        row["split"] = split
        counts[split] += 1
    with output.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {"rows": len(rows), "split_map_matched": matched, "split_counts": dict(counts)},
            ensure_ascii=False,
        )
    )


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--template", required=True, type=Path, help="Promote-template JSONL (from extract)."
    )
    ap.add_argument(
        "--candidate-manifest",
        required=True,
        type=Path,
        action="append",
        help="v2 candidate manifest with candidate_id + v2_split (repeatable).",
    )
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--default-split", default="train", choices=sorted(SUPPORTED_SPLITS))
    a = ap.parse_args()
    build(
        template=a.template,
        manifests=a.candidate_manifest,
        output=a.output,
        default_split=a.default_split,
    )


if __name__ == "__main__":
    main()
