"""Inject CLOVA-teacher section bboxes as Label Studio predictions (bootstrap).

The annotation bundle's ``label-studio-tasks.json`` ships without predictions, so an
operator would draw every box from scratch. This pre-fills each task with the
teacher's section bboxes (mostly ingredient_amounts, ~90% coverage) as Label Studio
``predictions`` so the operator confirms/adjusts and adds the remaining sections
(intake_method etc.) — far faster than drawing all boxes manually.

The teacher boxes are per-token amount boxes (sparse), so they are a STARTING aid,
not final labels; the operator merges/tightens them into proper section regions.
Only normalized geometry + class labels are written (no raw OCR text).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# Detector class order (src.learning.retraining.SUPPLEMENT_SECTION_CLASS_NAMES).
CLASS_NAMES = (
    "product_identity",
    "supplement_facts",
    "ingredient_amounts",
    "precautions",
    "allergen_warning",
    "intake_method",
    "other_ingredients",
    "functional_claims",
)
MODEL_VERSION = "clova-teacher-bootstrap"
YOLO_LINE_FIELDS = 5


def _load_teacher(teacher_dirs: list[Path]) -> dict[str, dict[str, Any]]:
    """Return ``candidate_id -> teacher payload`` across teacher directories."""
    out: dict[str, dict[str, Any]] = {}
    for d in teacher_dirs:
        if not d.is_dir():
            continue
        for f in d.glob("*.json"):
            payload = json.loads(f.read_text(encoding="utf-8"))
            cid = payload.get("candidate_id")
            if cid:
                out[cid] = payload
    return out


def _yolo_to_ls(line: str, width: int, height: int) -> dict[str, Any] | None:
    """Convert a ``<cls> cx cy w h`` YOLO line to a Label Studio rectangle region."""
    parts = line.split()
    if len(parts) != YOLO_LINE_FIELDS:
        return None
    cls = int(parts[0])
    cx, cy, w, h = (float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]))
    if not 0 <= cls < len(CLASS_NAMES):
        return None
    return {
        "from_name": "label",
        "to_name": "image",
        "type": "rectanglelabels",
        "original_width": width,
        "original_height": height,
        "value": {
            "x": max(0.0, (cx - w / 2) * 100),
            "y": max(0.0, (cy - h / 2) * 100),
            "width": w * 100,
            "height": h * 100,
            "rotation": 0,
            "rectanglelabels": [CLASS_NAMES[cls]],
        },
    }


def build(*, bundle: Path, teacher_dirs: list[Path]) -> None:
    """Inject teacher predictions into the bundle's Label Studio tasks in place."""
    tasks_path = bundle / "label-studio-tasks.json"
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    teacher = _load_teacher(teacher_dirs)
    injected = boxes = 0
    for task in tasks:
        fid = task.get("data", {}).get("fixture_id")
        payload = teacher.get(fid)
        if not payload:
            continue
        regions = [
            r
            for line in payload.get("section_bboxes_yolo", [])
            if (r := _yolo_to_ls(line, payload.get("width", 0), payload.get("height", 0)))
        ]
        if not regions:
            continue
        task["predictions"] = [{"model_version": MODEL_VERSION, "result": regions}]
        injected += 1
        boxes += len(regions)
    tasks_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "tasks": len(tasks),
                "tasks_with_predictions": injected,
                "predicted_boxes": boxes,
                "teacher_payloads": len(teacher),
            },
            ensure_ascii=False,
        )
    )


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle", required=True, type=Path)
    ap.add_argument("--teacher-dir", required=True, type=Path, action="append")
    a = ap.parse_args()
    build(bundle=a.bundle, teacher_dirs=a.teacher_dir)


if __name__ == "__main__":
    main()
