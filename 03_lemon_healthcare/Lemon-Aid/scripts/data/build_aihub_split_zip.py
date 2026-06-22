"""원본 AI Hub 코드 단위 재분리 데이터셋을 단일 ZIP으로 스트리밍 생성한다.

12만 개 파일을 디스크에 만드는 대신(파일 생성 지연 회피), 이미지는 ``--src-root`` 에서
읽어 zip에 넣고 라벨은 메모리에서 새 인덱스로 재작성하여 zip에 직접 기록한다.
ZIP_STORED(무압축: JPEG는 압축 이득 없음, 빠름). 결과물은 학습 컴퓨터에서 풀어 사용.

Reference:
    docs/superpowers/plans/2026-05-29-aihub-split-training-setup.md
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import time
import zipfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NAME_CSV = REPO_ROOT / "data/food_images/manifests/aihub_code_korean_names.csv"
DEFAULT_SRC_ROOT = REPO_ROOT / "data/food_images/aihub_yolo_50"
DEFAULT_ZIP = REPO_ROOT / "data/food_images/processed/aihub_yolo_split.zip"
DEFAULT_ZIP_ROOT = "aihub_yolo_split"
CODE_RE = re.compile(r"^(?:train|val)_([ABC][0-9]{5})_")


def resolve_repo_path(path: Path) -> Path:
    """CLI 경로를 repo 기준 절대경로로 정규화한다.

    Args:
        path: CLI에서 전달된 경로. 상대경로면 repo root 기준으로 해석한다.

    Returns:
        정규화된 절대경로.
    """
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return (REPO_ROOT / expanded).resolve()


def load_mapping(csv_path: Path) -> tuple[dict[str, str], list[str]]:
    """코드→한글명과 드롭 코드를 읽는다.

    Args:
        csv_path: ``aihub_code_korean_names.csv`` 경로.

    Returns:
        (code→korean_name, drop_codes) 튜플.
    """
    code_to_name: dict[str, str] = {}
    drop: list[str] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = row["korean_name"].strip()
            if row.get("status", "").strip().upper() == "DROP" or not name:
                drop.append(row["code"].strip())
            else:
                code_to_name[row["code"].strip()] = name
    return code_to_name, drop


def build_classes(code_to_name: dict[str, str], a2y: dict) -> tuple[list[str], dict[str, int]]:
    """유니크 한글명을 (원본클래스, 한글명) 순으로 정렬해 클래스/코드→인덱스를 만든다.

    Args:
        code_to_name: AI Hub 코드→한글명 매핑.
        a2y: 기존 ``yolo_class_index_50.json`` 의 ``aihub_to_yolo`` 매핑.

    Returns:
        (class_names, code_to_new_index) 튜플.
    """
    name_to_rfc: dict[str, str] = {}
    for code, name in code_to_name.items():
        name_to_rfc.setdefault(name, a2y.get(code, {}).get("roboflow_class", "zzz"))
    names = sorted(set(code_to_name.values()), key=lambda n: (name_to_rfc[n], n))
    name_to_idx = {n: i for i, n in enumerate(names)}
    return names, {c: name_to_idx[n] for c, n in code_to_name.items()}


def rewrite_label(text: str, new_idx: int) -> str:
    """라벨 텍스트의 각 줄 첫 토큰(클래스)을 새 인덱스로 치환한다.

    Args:
        text: 원본 YOLO 라벨 텍스트.
        new_idx: 치환할 새 클래스 인덱스.

    Returns:
        bbox 값은 유지하고 클래스 인덱스만 치환한 라벨 텍스트.
    """
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 5:
            out.append(f"{new_idx} {parts[1]} {parts[2]} {parts[3]} {parts[4]}")
    return "\n".join(out) + "\n" if out else ""


def main() -> None:
    """CLI 엔트리포인트."""
    parser = argparse.ArgumentParser(
        description="AI Hub 코드 단위 재분리 YOLO 데이터셋을 zip으로 생성합니다."
    )
    parser.add_argument("--src-root", type=Path, default=DEFAULT_SRC_ROOT)
    parser.add_argument("--name-csv", type=Path, default=DEFAULT_NAME_CSV)
    parser.add_argument("--zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--zip-root", default=DEFAULT_ZIP_ROOT)
    parser.add_argument("--force", action="store_true", help="기존 zip을 덮어쓰기")
    args = parser.parse_args()
    src_root = resolve_repo_path(args.src_root)
    name_csv = resolve_repo_path(args.name_csv)
    zip_path = resolve_repo_path(args.zip)

    code_to_name, drop = load_mapping(name_csv)
    a2y = json.loads((src_root / "yolo_class_index_50.json").read_text(encoding="utf-8"))["aihub_to_yolo"]
    names, code_to_new = build_classes(code_to_name, a2y)
    print(f"[plan] classes={len(names)} codes={len(code_to_new)} drop={drop}", flush=True)

    per_total: Counter[int] = Counter()
    per_val: Counter[int] = Counter()
    stats: Counter[str] = Counter()
    started = time.time()

    if zip_path.exists() and not args.force:
        raise SystemExit(f"출력 zip이 이미 있습니다(중단): {zip_path}  (--force 로 강제)")
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        for split in ("train", "val"):
            label_dir = src_root / split / "labels"
            image_dir = src_root / split / "images"
            n = 0
            for entry in os.scandir(label_dir):
                if not entry.name.endswith(".txt"):
                    continue
                m = CODE_RE.match(entry.name)
                if not m:
                    stats["no_code"] += 1
                    continue
                code = m.group(1)
                if code in drop:
                    stats["dropped"] += 1
                    continue
                new_idx = code_to_new.get(code)
                if new_idx is None:
                    stats["unmapped"] += 1
                    continue
                stem = entry.name[:-4]
                img_src = image_dir / f"{stem}.jpg"
                if not img_src.exists():
                    stats["img_missing"] += 1
                    continue
                label_txt = rewrite_label(Path(entry.path).read_text(encoding="utf-8"), new_idx)
                if not label_txt:
                    stats["empty_label"] += 1
                    continue
                zf.writestr(f"{args.zip_root}/{split}/labels/{entry.name}", label_txt)
                zf.write(img_src, f"{args.zip_root}/{split}/images/{stem}.jpg")
                per_total[new_idx] += 1
                if split == "val":
                    per_val[new_idx] += 1
                stats["written"] += 1
                n += 1
                if n % 10000 == 0:
                    print(f"[{split}] {n} written, {time.time()-started:.0f}s", flush=True)
            print(f"[{split}] done: {n}", flush=True)

        # 메타데이터 (zip 내부)
        yaml_lines = [
            "# AI Hub food YOLO dataset - re-split to original per-code classes",
            "path: .", "train: train/images", "val: val/images", "",
            f"nc: {len(names)}", "names:",
        ] + [f"  - {n}" for n in names]
        zf.writestr(f"{args.zip_root}/data.yaml", "\n".join(yaml_lines) + "\n")

        index_payload = {
            "class_names": names,
            "aihub_to_class": {
                code: {"new_index": code_to_new[code], "korean_name": code_to_name[code],
                       "orig_roboflow_class": a2y.get(code, {}).get("roboflow_class")}
                for code in sorted(code_to_new)
            },
        }
        zf.writestr(f"{args.zip_root}/yolo_class_index_split.json",
                    json.dumps(index_payload, ensure_ascii=False, indent=2))

        # per_total 은 train+val 합산이므로 train = total - val
        cc = io.StringIO()
        writer = csv.writer(cc)
        writer.writerow(["class_id", "class_name", "train_count", "val_count"])
        for i, name in enumerate(names):
            writer.writerow([i, name, per_total.get(i, 0) - per_val.get(i, 0), per_val.get(i, 0)])
        zf.writestr(f"{args.zip_root}/_audit/class_counts.csv", cc.getvalue())

        zero_val = [names[i] for i in range(len(names)) if per_val.get(i, 0) == 0]
        report = {
            "num_classes": len(names),
            "num_codes_mapped": len(code_to_new),
            "dropped_codes": drop,
            "stats": dict(stats),
            "train_total": sum(per_total.values()) - sum(per_val.values()),
            "val_total": sum(per_val.values()),
            "num_classes_zero_val": len(zero_val),
            "classes_with_zero_val": zero_val,
        }
        zf.writestr(f"{args.zip_root}/build_report.json", json.dumps(report, ensure_ascii=False, indent=2))

    size_gb = zip_path.stat().st_size / 1e9
    print(json.dumps({k: v for k, v in report.items() if k != "classes_with_zero_val"},
                     ensure_ascii=False, indent=2), flush=True)
    print(f"[zip] {zip_path}  {size_gb:.2f} GB  elapsed={time.time()-started:.0f}s", flush=True)
    # 사이드카로 report 도 디스크에 (검증용)
    zip_path.with_suffix(".report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
