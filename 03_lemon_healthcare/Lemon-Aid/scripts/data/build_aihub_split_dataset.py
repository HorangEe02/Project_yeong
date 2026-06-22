"""원본 AI Hub 코드 단위로 50클래스 YOLO 데이터셋을 재분리(re-split)한다.

이미지는 ``--src-root`` 로 지정한 기존 ``aihub_yolo_50`` 산출물을 하드링크로
재사용하고, 실패하면 복사로 폴백한다. 라벨의 클래스 인덱스만 코드별 새
인덱스로 치환하여 ``aihub_yolo_split`` 를 생성한다.
원본 데이터셋은 건드리지 않는다.

Reference:
    docs/superpowers/plans/2026-05-29-aihub-class-split-recovery-handoff.md
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NAME_CSV = REPO_ROOT / "data/food_images/manifests/aihub_code_korean_names.csv"
DEFAULT_SRC_ROOTS = (
    REPO_ROOT / "data/food_images/aihub_yolo_50",
    REPO_ROOT / "data/food_images/processed/aihub_yolo_50",
)
DEFAULT_OUT = REPO_ROOT / "data/food_images/processed/aihub_yolo_split"
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


def _has_files(path: Path) -> bool:
    """디렉터리가 존재하고 파일을 1개 이상 포함하는지 확인한다.

    Args:
        path: 검사할 디렉터리 경로.

    Returns:
        디렉터리에 파일 또는 하위 항목이 있으면 True.
    """
    return path.is_dir() and any(path.iterdir())


def _first_existing_split_dir(source_roots: list[Path], split: str, leaf: str) -> Path:
    """소스 루트 후보에서 사용 가능한 split 하위 디렉터리를 고른다.

    Args:
        source_roots: ``aihub_yolo_50`` 루트 후보 목록.
        split: ``train`` 또는 ``val``.
        leaf: ``images`` 또는 ``labels``.

    Returns:
        첫 번째 non-empty 디렉터리.

    Raises:
        FileNotFoundError: 모든 후보 루트에서 해당 디렉터리를 찾지 못한 경우.
    """
    checked: list[str] = []
    for root in source_roots:
        candidate = root / split / leaf
        checked.append(str(candidate))
        if _has_files(candidate):
            return candidate
    raise FileNotFoundError(
        f"사용 가능한 {split}/{leaf} 디렉터리를 찾지 못했습니다: {checked}"
    )


def _find_index_json(source_roots: list[Path]) -> Path:
    """소스 루트 후보에서 ``yolo_class_index_50.json`` 을 찾는다.

    Args:
        source_roots: ``aihub_yolo_50`` 루트 후보 목록.

    Returns:
        발견된 index JSON 경로.

    Raises:
        FileNotFoundError: 후보 경로 어디에도 파일이 없는 경우.
    """
    checked: list[str] = []
    for root in source_roots:
        candidate = root / "yolo_class_index_50.json"
        checked.append(str(candidate))
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"yolo_class_index_50.json 을 찾지 못했습니다: {checked}")


def load_mapping(csv_path: Path) -> tuple[dict[str, str], list[str]]:
    """코드→한글명 매핑과 드롭 코드를 읽는다.

    Args:
        csv_path: ``aihub_code_korean_names.csv`` 경로.

    Returns:
        (code→korean_name, drop_codes) 튜플. status==DROP 또는 빈 이름은 드롭.
    """
    code_to_name: dict[str, str] = {}
    drop: list[str] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = row["code"].strip()
            name = row["korean_name"].strip()
            status = row.get("status", "").strip().upper()
            if status == "DROP" or not name:
                drop.append(code)
                continue
            code_to_name[code] = name
    return code_to_name, drop


def build_classes(code_to_name: dict[str, str], idx_json: dict) -> tuple[list[str], dict[str, int]]:
    """유니크 한글명을 클래스로 만들고 코드→새 인덱스 맵을 만든다.

    Args:
        code_to_name: 코드→한글명.
        idx_json: 원본 yolo_class_index_50.json 의 aihub_to_yolo (정렬 기준용).

    Returns:
        (names, code_to_new_index). names 는 (원본클래스, 한글명) 정렬 순.
    """
    a2y = idx_json["aihub_to_yolo"]
    # 한글명별 대표 원본 roboflow_class (정렬·가독성용)
    name_to_rfc: dict[str, str] = {}
    for code, name in code_to_name.items():
        rfc = a2y.get(code, {}).get("roboflow_class", "zzz")
        name_to_rfc.setdefault(name, rfc)
    names = sorted(set(code_to_name.values()), key=lambda n: (name_to_rfc[n], n))
    name_to_idx = {n: i for i, n in enumerate(names)}
    code_to_new = {c: name_to_idx[n] for c, n in code_to_name.items()}
    return names, code_to_new


def link_or_copy(src: Path, dst: Path) -> str:
    """이미지를 하드링크하고 실패하면 복사한다.

    Args:
        src: 원본 이미지 경로.
        dst: 대상 이미지 경로.

    Returns:
        ``link``, ``copy``, ``skip``, ``miss`` 중 하나.
    """
    if not src.exists():
        return "miss"
    if dst.exists():
        return "skip"
    try:
        os.link(src, dst)
        return "link"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def process_split(
    split: str,
    out_root: Path,
    source_roots: list[Path],
    code_to_new: dict[str, int],
    drop: set[str],
) -> dict:
    """한 split 의 라벨 재작성 + 이미지 하드링크.

    Args:
        split: 'train' | 'val'.
        out_root: 출력 데이터셋 루트.
        source_roots: 원본 ``aihub_yolo_50`` 루트 후보 목록.
        code_to_new: 코드→새 인덱스.
        drop: 드롭 코드 집합.

    Returns:
        처리 통계 dict.

    Raises:
        FileNotFoundError: 사용 가능한 이미지 또는 라벨 소스 디렉터리가 없는 경우.
    """
    label_src = _first_existing_split_dir(source_roots, split, "labels")
    image_src = _first_existing_split_dir(source_roots, split, "images")

    out_img = out_root / split / "images"
    out_lab = out_root / split / "labels"
    out_img.mkdir(parents=True, exist_ok=True)
    out_lab.mkdir(parents=True, exist_ok=True)

    stats: Counter[str] = Counter()
    per_class: Counter[int] = Counter()
    img_ops: Counter[str] = Counter()
    bad_code: set[str] = set()

    for entry in os.scandir(label_src):
        if not entry.name.endswith(".txt"):
            continue
        match = CODE_RE.match(entry.name)
        if not match:
            stats["no_code"] += 1
            continue
        code = match.group(1)
        if code in drop:
            stats["dropped"] += 1
            continue
        new_idx = code_to_new.get(code)
        if new_idx is None:
            bad_code.add(code)
            stats["unmapped"] += 1
            continue

        # 라벨 재작성 (bbox 유지, 클래스 인덱스만 치환). 파일당 1줄 가정이나 다중행도 처리.
        lines_out: list[str] = []
        for line in Path(entry.path).read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            lines_out.append(f"{new_idx} {parts[1]} {parts[2]} {parts[3]} {parts[4]}")
        if not lines_out:
            stats["empty_label"] += 1
            continue
        (out_lab / entry.name).write_text("\n".join(lines_out) + "\n", encoding="utf-8")

        # 이미지 하드링크
        stem = entry.name[:-4]
        op = link_or_copy(image_src / f"{stem}.jpg", out_img / f"{stem}.jpg")
        img_ops[op] += 1
        if op == "miss":
            stats["img_missing"] += 1
            # 이미지 없으면 라벨도 제거하여 정합성 유지
            (out_lab / entry.name).unlink(missing_ok=True)
            continue

        stats["written"] += 1
        per_class[new_idx] += 1

    return {
        "split": split,
        "label_src": str(label_src),
        "stats": dict(stats),
        "img_ops": dict(img_ops),
        "per_class": dict(per_class),
        "unmapped_codes": sorted(bad_code),
    }


def write_dataset_files(
    out_root: Path,
    names: list[str],
    code_to_name: dict[str, str],
    code_to_new: dict[str, int],
    idx_json: dict,
    per_class_total: Counter,
    per_class_val: Counter,
) -> None:
    """data.yaml, yolo_class_index, class_counts.csv 를 생성한다.

    Args:
        out_root: 출력 데이터셋 루트.
        names: 새 클래스명 목록.
        code_to_name: AI Hub 코드→한글명 매핑.
        code_to_new: AI Hub 코드→새 클래스 인덱스 매핑.
        idx_json: 기존 ``yolo_class_index_50.json`` payload.
        per_class_total: train+val 합산 클래스별 샘플 수.
        per_class_val: val 클래스별 샘플 수.
    """
    # data.yaml — path 를 상대(.)로 두어 드라이브 문자 변화에 안전
    lines = [
        "# AI Hub food YOLO dataset — re-split to original per-code classes",
        "path: .",
        "train: train/images",
        "val: val/images",
        "",
        f"nc: {len(names)}",
        "names:",
    ]
    lines += [f"  - {n}" for n in names]
    (out_root / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    a2y = idx_json["aihub_to_yolo"]
    payload = {
        "class_names": names,
        "aihub_to_class": {
            code: {"new_index": code_to_new[code], "korean_name": code_to_name[code],
                   "orig_roboflow_class": a2y.get(code, {}).get("roboflow_class")}
            for code in sorted(code_to_new)
        },
    }
    (out_root / "yolo_class_index_split.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    audit = out_root / "_audit"
    audit.mkdir(exist_ok=True)
    with (audit / "class_counts.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["class_id", "class_name", "train_count", "val_count"])
        for i, name in enumerate(names):
            writer.writerow([i, name, per_class_total.get(i, 0), per_class_val.get(i, 0)])


def main() -> None:
    """CLI 엔트리포인트."""
    parser = argparse.ArgumentParser(
        description="AI Hub 50클래스 YOLO 데이터셋을 코드 단위 클래스로 재분리합니다."
    )
    parser.add_argument(
        "--src-root",
        type=Path,
        action="append",
        dest="src_roots",
        help=(
            "원본 aihub_yolo_50 데이터셋 루트. 여러 번 지정하면 순서대로 후보를 "
            "검사합니다. 기본값은 repo 내부 data/food_images 경로 후보입니다."
        ),
    )
    parser.add_argument("--name-csv", type=Path, default=DEFAULT_NAME_CSV)
    parser.add_argument("--index-json", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true", help="기존 출력 디렉터리 있어도 진행")
    args = parser.parse_args()

    source_roots = [
        resolve_repo_path(path) for path in (args.src_roots or list(DEFAULT_SRC_ROOTS))
    ]
    name_csv = resolve_repo_path(args.name_csv)
    index_json_path = (
        resolve_repo_path(args.index_json)
        if args.index_json is not None
        else _find_index_json(source_roots)
    )
    out_root = resolve_repo_path(args.out)
    if out_root.exists() and any(out_root.iterdir()) and not args.force:
        raise SystemExit(f"출력 디렉터리가 비어있지 않음(중단): {out_root}  (--force 로 강제)")

    code_to_name, drop = load_mapping(name_csv)
    idx_json = json.loads(index_json_path.read_text(encoding="utf-8"))
    names, code_to_new = build_classes(code_to_name, idx_json)
    print(f"[plan] 클래스(유니크 한글명) 수: {len(names)} | 매핑 코드: {len(code_to_new)} | 드롭: {drop}", flush=True)

    out_root.mkdir(parents=True, exist_ok=True)
    reports = [
        process_split(s, out_root, source_roots, code_to_new, set(drop))
        for s in ("train", "val")
    ]

    per_class_total: Counter = Counter()
    per_class_val: Counter = Counter()
    for rep in reports:
        if rep["split"] == "val":
            per_class_val.update(rep["per_class"])
        per_class_total.update(rep["per_class"])

    write_dataset_files(out_root, names, code_to_name, code_to_new, idx_json,
                        per_class_total, per_class_val)

    # 검증
    zero_val = [names[i] for i in range(len(names)) if per_class_val.get(i, 0) == 0]
    report = {
        "out_root": str(out_root),
        "num_classes": len(names),
        "num_codes_mapped": len(code_to_new),
        "dropped_codes": drop,
        "splits": reports,
        "train_total": sum(per_class_total.values()),
        "val_total": sum(per_class_val.values()),
        "classes_with_zero_val": zero_val,
        "num_classes_zero_val": len(zero_val),
    }
    (out_root / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "splits"}, ensure_ascii=False, indent=2), flush=True)
    for rep in reports:
        print(f"[{rep['split']}] stats={rep['stats']} img_ops={rep['img_ops']}", flush=True)


if __name__ == "__main__":
    main()
