"""AI Hub YOLO 50 클래스 train 다운샘플링.

원본 train의 클래스당 이미지 수를 상한(기본 500)으로 자르고,
이미지+라벨을 새 폴더로 복사한다. val은 원본 전체를 복사한다.

샘플링은 spec §3.1대로 seed 고정 랜덤(random.sample on sorted stems).

Reference:
    docs/superpowers/specs/2026-05-27-aihub-yolo-balanced500-yolo11s-design.md
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.data._dataset_audit import collect_stems_by_class
from scripts.data._manifest_models import ClassManifest, TrainManifest


def select_stems_per_class(
    stems_by_class: dict[int, list[str]],
    cap_per_class: int,
    seed: int,
) -> dict[int, list[str]]:
    """클래스별로 시드 고정 랜덤 샘플링을 적용한다.

    클래스의 원본 개수가 cap_per_class 초과면 cap만큼 sample,
    이하면 전체를 그대로 유지한다. 결과는 정렬된 stem 리스트로 반환한다.

    재현성: 같은 seed + 같은 입력(stems_by_class의 각 리스트가 동일 set)이면
    출력이 비트 단위로 동일하다. 입력 순서는 sorted()로 정규화하므로 무관.

    Args:
        stems_by_class: class_id → 원본 stem 리스트.
        cap_per_class: 클래스당 상한.
        seed: random.seed에 사용할 정수.

    Returns:
        class_id → 선택된 stem 리스트 (정렬됨). 입력의 모든 키 보존.

    Examples:
        >>> result = select_stems_per_class({0: ["a", "b", "c", "d"]}, cap_per_class=2, seed=42)
        >>> len(result[0])
        2
    """
    rng = random.Random(seed)
    output: dict[int, list[str]] = {}
    for cid in sorted(stems_by_class.keys()):
        canonical = sorted(stems_by_class[cid])
        if len(canonical) <= cap_per_class:
            output[cid] = list(canonical)
        else:
            picked = rng.sample(canonical, cap_per_class)
            output[cid] = sorted(picked)
    return output


def copy_selected_pairs(src_split: Path, dst_split: Path, selected_stems: list[str]) -> int:
    """src의 images/labels에서 stem 짝을 dst로 복사한다.

    Args:
        src_split: 원본 split 루트 (예: aihub_yolo_50/train).
        dst_split: 대상 split 루트 (예: aihub_yolo_50_balanced_500/train).
        selected_stems: 복사할 파일 stem 리스트 (확장자 제외).

    Returns:
        복사된 짝 개수.

    Raises:
        FileNotFoundError: stem의 jpg가 src에 없는 경우.
    """
    (dst_split / "images").mkdir(parents=True, exist_ok=True)
    (dst_split / "labels").mkdir(parents=True, exist_ok=True)

    count = 0
    for stem in selected_stems:
        src_img = src_split / "images" / f"{stem}.jpg"
        src_lbl = src_split / "labels" / f"{stem}.txt"
        if not src_img.exists():
            raise FileNotFoundError(f"missing image: {src_img.name}")
        shutil.copy2(src_img, dst_split / "images" / src_img.name)
        shutil.copy2(src_lbl, dst_split / "labels" / src_lbl.name)
        count += 1
    return count


def copy_full_split(src_split: Path, dst_split: Path) -> int:
    """split 전체(images + labels)를 dst로 복사한다.

    val을 다운샘플 없이 전체 그대로 옮길 때 사용한다.

    Args:
        src_split: 원본 split 루트.
        dst_split: 대상 split 루트.

    Returns:
        복사된 이미지 개수.
    """
    stems = sorted(p.stem for p in (src_split / "images").glob("*.jpg"))
    return copy_selected_pairs(src_split, dst_split, selected_stems=stems)


def write_dataset_yaml(dst_root: Path, names: list[str]) -> Path:
    """다운샘플 결과 폴더에 data.yaml을 작성한다.

    Args:
        dst_root: aihub_yolo_50_balanced_500 폴더 절대 경로.
        names: 클래스 이름 리스트 (순서 = class_id).

    Returns:
        생성된 data.yaml 경로.
    """
    yaml_path = dst_root / "data.yaml"
    lines = [
        "# YOLO dataset config - balanced_500 subset (train downsampled to <=500/class)",
        f"path: {dst_root.as_posix()}",
        "train: train/images",
        "val: val/images",
        "",
        f"nc: {len(names)}",
        "names:",
        *[f"  - {n}" for n in names],
        "",
    ]
    yaml_path.write_text("\n".join(lines), encoding="utf-8")
    return yaml_path


@dataclass(frozen=True)
class DownsampleResult:
    """run_downsample 결과 요약."""

    train_copied: int
    val_copied: int
    manifest_path: Path


def _write_class_counts_csv(path: Path, counts: dict[int, int], names: list[str]) -> None:
    """class_id, class_name, count 3-열 CSV로 분포를 기록한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["class_id", "class_name", "count"])
        for cid in sorted(counts.keys()):
            writer.writerow([cid, names[cid], counts[cid]])


def run_downsample(
    src_root: Path,
    dst_root: Path,
    class_names: list[str],
    cap_per_class: int,
    seed: int,
    val_cap_per_class: int | None = None,
) -> DownsampleResult:
    """다운샘플 파이프라인 전체를 실행한다.

    1) 원본 train 라벨 스캔 → 클래스별 stem 맵
    2) seed 고정 랜덤 샘플링으로 클래스당 cap 적용
    3) 선택된 train 짝과 val(전체 또는 cap) 을 dst로 복사
    4) data.yaml + train 매니페스트 JSON + 분포 CSV 작성
    5) val_cap_per_class 가 주어지면 val 매니페스트/분포 CSV도 함께 작성

    Args:
        src_root: 원본 데이터셋 루트 (aihub_yolo_50).
        dst_root: 대상 데이터셋 루트 (없으면 생성).
        class_names: 클래스 이름 리스트 (순서 = class_id).
        cap_per_class: train 클래스당 상한.
        seed: random seed (train과 val에 동일 시드 사용, 별도 Random 인스턴스).
        val_cap_per_class: val 클래스당 상한. None이면 val 전체 복사(기본값).

    Returns:
        DownsampleResult (train/val 복사 개수, train 매니페스트 경로).

    Raises:
        FileNotFoundError: 라벨에 짝꿍 이미지가 없는 경우.
        ValueError: 라벨에 범위 밖 class_id가 있는 경우.
    """
    num_classes = len(class_names)

    # --- train 처리 ---
    src_train_labels = src_root / "train" / "labels"
    stems_by_class = collect_stems_by_class(src_train_labels, num_classes=num_classes)
    original_counts = {cid: len(stems) for cid, stems in stems_by_class.items()}

    selected = select_stems_per_class(stems_by_class, cap_per_class=cap_per_class, seed=seed)
    balanced_counts = {cid: len(stems) for cid, stems in selected.items()}

    flat_selected: list[str] = []
    for cid in sorted(selected.keys()):
        flat_selected.extend(selected[cid])

    train_copied = copy_selected_pairs(
        src_root / "train", dst_root / "train", selected_stems=flat_selected
    )

    # --- val 처리 ---
    if val_cap_per_class is None:
        val_copied = copy_full_split(src_root / "val", dst_root / "val")
        val_stems_by_class: dict[int, list[str]] | None = None
        val_selected: dict[int, list[str]] | None = None
    else:
        src_val_labels = src_root / "val" / "labels"
        val_stems_by_class = collect_stems_by_class(src_val_labels, num_classes=num_classes)
        val_selected = select_stems_per_class(
            val_stems_by_class, cap_per_class=val_cap_per_class, seed=seed
        )
        flat_val_selected: list[str] = []
        for cid in sorted(val_selected.keys()):
            flat_val_selected.extend(val_selected[cid])
        val_copied = copy_selected_pairs(
            src_root / "val", dst_root / "val", selected_stems=flat_val_selected
        )

    write_dataset_yaml(dst_root, names=class_names)

    # --- train 매니페스트 + CSV ---
    manifest = TrainManifest(
        seed=seed,
        cap_per_class=cap_per_class,
        classes=[
            ClassManifest(class_id=cid, class_name=class_names[cid], stems=selected[cid])
            for cid in sorted(selected.keys())
        ],
    )
    manifest_path = dst_root / "_manifest" / "train_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    _write_class_counts_csv(
        dst_root / "_manifest" / "class_counts_original.csv", original_counts, class_names
    )
    _write_class_counts_csv(
        dst_root / "_manifest" / "class_counts_balanced.csv", balanced_counts, class_names
    )

    # --- val 매니페스트 + CSV (val_cap_per_class 적용 시만) ---
    if (
        val_cap_per_class is not None
        and val_selected is not None
        and val_stems_by_class is not None
    ):
        val_original_counts = {cid: len(s) for cid, s in val_stems_by_class.items()}
        val_balanced_counts = {cid: len(s) for cid, s in val_selected.items()}
        val_manifest = TrainManifest(
            seed=seed,
            cap_per_class=val_cap_per_class,
            classes=[
                ClassManifest(class_id=cid, class_name=class_names[cid], stems=val_selected[cid])
                for cid in sorted(val_selected.keys())
            ],
        )
        val_manifest_path = dst_root / "_manifest" / "val_manifest.json"
        val_manifest_path.write_text(val_manifest.model_dump_json(indent=2), encoding="utf-8")
        _write_class_counts_csv(
            dst_root / "_manifest" / "val_class_counts_original.csv",
            val_original_counts,
            class_names,
        )
        _write_class_counts_csv(
            dst_root / "_manifest" / "val_class_counts_balanced.csv",
            val_balanced_counts,
            class_names,
        )

    return DownsampleResult(
        train_copied=train_copied, val_copied=val_copied, manifest_path=manifest_path
    )


def _load_class_names_from_yaml(yaml_path: Path) -> list[str]:
    """원본 data.yaml에서 'names:' 블록을 읽는다.

    PyYAML 없이 단순 파싱: '- ' 접두사 라인을 클래스로 본다.

    Args:
        yaml_path: data.yaml 경로.

    Returns:
        클래스 이름 리스트 (순서 = class_id).
    """
    names: list[str] = []
    in_names = False
    for raw in yaml_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("names:"):
            in_names = True
            continue
        if in_names:
            stripped = line.lstrip()
            if stripped.startswith("- "):
                names.append(stripped[2:].strip())
            elif line and not line.startswith(" "):
                break
    return names


def _main(argv: list[str] | None = None) -> int:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="AI Hub YOLO 50 train 다운샘플 (클래스당 상한 적용)"
    )
    parser.add_argument("--src", type=Path, required=True, help="원본 데이터셋 루트")
    parser.add_argument("--dst", type=Path, required=True, help="대상 데이터셋 루트")
    parser.add_argument("--cap", type=int, default=500, help="train 클래스당 상한 (기본 500)")
    parser.add_argument(
        "--val-cap",
        type=int,
        default=None,
        help="val 클래스당 상한 (기본 None = val 전체 복사)",
    )
    parser.add_argument("--seed", type=int, default=42, help="random seed (기본 42)")
    args = parser.parse_args(argv)

    src_yaml = args.src / "data.yaml"
    names = _load_class_names_from_yaml(src_yaml)
    if not names:
        print(f"ERROR: failed to load class names from {src_yaml}", file=sys.stderr)
        return 2

    result = run_downsample(
        src_root=args.src,
        dst_root=args.dst,
        class_names=names,
        cap_per_class=args.cap,
        seed=args.seed,
        val_cap_per_class=args.val_cap,
    )
    print(f"train_copied={result.train_copied} val_copied={result.val_copied}")
    print(f"manifest={result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
