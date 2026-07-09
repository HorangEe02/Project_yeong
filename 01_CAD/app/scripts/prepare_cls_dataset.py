#!/usr/bin/env python3
"""
YOLOv8-cls 학습용 데이터셋 준비 스크립트

73개 카테고리(MiSUMi 58 + Unit_bearing 15)의 이미지를
YOLOv8 분류 학습에 필요한 train/val 디렉토리 구조로 정리한다.

사용법:
  python scripts/prepare_cls_dataset.py --output ./data/cls_dataset
  python scripts/prepare_cls_dataset.py --output ./data/cls_dataset --val-ratio 0.15 --use-copy
  python scripts/prepare_cls_dataset.py --output ./data/cls_dataset --min-samples 5

디렉토리 구조 (YOLOv8-cls 표준):
  data/cls_dataset/
    train/
      Shafts/
        img001.png -> /원본/경로/img001.png  (심볼릭 링크)
      Gears/
      UCP/
      ...
    val/
      Shafts/
      Gears/
      ...
    class_names.json   ← {0: "Shafts", 1: "Gears", ...}
    dataset_stats.json ← 클래스별 통계
"""

import argparse
import json
import os
import random
import re
import shutil
import sys
import unicodedata
from collections import Counter
from pathlib import Path

# ─────────────────────────────────────────────
# 소스 경로 상수
# ─────────────────────────────────────────────

MISUMI_ROOT = Path(
    "<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/data/MiSUMi_png"
)
UNIT_BEARING_ROOT = Path(
    "<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/data/Unit_bearing_png"
)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif"}


# ─────────────────────────────────────────────
# 클래스명 정규화
# ─────────────────────────────────────────────

# MiSUMi 폴더 → 정규화된 클래스명 매핑
_MISUMI_NAME_MAP = {
    "00_new_products": "new_products",
    "04_Linear Bushings": "Linear_Bushings",
    "28_Simplified Adjustment Units": "Simplified_Adjustment_Units",
    "30_image processing": "image_processing",
    "46_Resin Plates": "Resin_Plates",
}

# Unit_bearing 폴더 → 정규화된 클래스명 매핑
_BEARING_NAME_MAP = {
    "1.UCP": "bearing_UCP",
    "2.UKP": "bearing_UKP",
    "3.UCF": "bearing_UCF",
    "5.UCFL": "bearing_UCFL",
    "6.UKFL": "bearing_UKFL",
    "7.UCFC": "bearing_UCFC",
    "8.UKFC": "bearing_UKFC",
    "9.UCFS": "bearing_UCFS",
    "10.UKFS": "bearing_UKFS",
    "11.UCT": "bearing_UCT",
    "12.UKT": "bearing_UKT",
    "13.SN(플러머블록)": "bearing_SN_Plummer_Block",
    "14.TAKEUP": "bearing_TAKEUP",
    "15.H-ADAPTER": "bearing_H_ADAPTER",
}


def normalize_misumi_name(folder_name: str) -> str:
    """MiSUMi 폴더명을 정규화된 클래스명으로 변환한다.

    예: "01_Shafts" → "Shafts"
        "04_Linear Bushings" → "Linear_Bushings"
        "23_Locating_&_Guide_Components" → "Locating_and_Guide_Components"
    """
    # 직접 매핑 확인
    if folder_name in _MISUMI_NAME_MAP:
        return _MISUMI_NAME_MAP[folder_name]

    # 번호 접두사 제거 (00_, 01_, ...)
    name = re.sub(r"^\d{2}_", "", folder_name)

    # 공백 → 언더스코어
    name = name.replace(" ", "_")

    # & → and
    name = name.replace("&", "and")

    # 연속 언더스코어 정리
    name = re.sub(r"_+", "_", name).strip("_")

    return name


def normalize_bearing_name(folder_name: str) -> str:
    """Unit_bearing 폴더명을 정규화된 클래스명으로 변환한다.

    예: "1.UCP" → "bearing_UCP"
        "13.SN(플러머블록)" → "bearing_SN_Plummer_Block"
    """
    if folder_name in _BEARING_NAME_MAP:
        return _BEARING_NAME_MAP[folder_name]

    # 번호. 접두사 제거
    name = re.sub(r"^\d+\.", "", folder_name)

    # 한글/괄호 제거
    name = re.sub(r"[가-힣()（）]", "", name)

    # 정리
    name = name.replace("-", "_").replace(" ", "_")
    name = re.sub(r"_+", "_", name).strip("_")

    return f"bearing_{name}"


# ─────────────────────────────────────────────
# 이미지 수집
# ─────────────────────────────────────────────

def collect_images(
    misumi_root: Path,
    bearing_root: Path,
    min_samples: int = 1,
) -> dict[str, list[Path]]:
    """소스 디렉토리에서 카테고리별 이미지 경로를 수집한다.

    Args:
        misumi_root: MiSUMi 소스 디렉토리
        bearing_root: Unit_bearing 소스 디렉토리
        min_samples: 최소 이미지 수 (미달 시 경고)

    Returns:
        {class_name: [image_path, ...]}
    """
    class_images: dict[str, list[Path]] = {}

    # MiSUMi 58 카테고리
    if misumi_root.exists():
        for cat_dir in sorted(misumi_root.iterdir()):
            if not cat_dir.is_dir():
                continue
            class_name = normalize_misumi_name(cat_dir.name)

            images = []
            # 직접 이미지 + 서브폴더 내 이미지 (2단계까지)
            for ext in IMAGE_EXTENSIONS:
                images.extend(cat_dir.glob(f"*{ext}"))
                images.extend(cat_dir.glob(f"*/*{ext}"))

            if images:
                class_images[class_name] = sorted(set(images))
    else:
        print(f"  ⚠️  MiSUMi 경로 없음: {misumi_root}")

    # Unit_bearing 15 카테고리
    if bearing_root.exists():
        for cat_dir in sorted(bearing_root.iterdir()):
            if not cat_dir.is_dir():
                continue
            class_name = normalize_bearing_name(cat_dir.name)

            images = []
            for ext in IMAGE_EXTENSIONS:
                images.extend(cat_dir.glob(f"*{ext}"))
                images.extend(cat_dir.glob(f"*/*{ext}"))

            if images:
                class_images[class_name] = sorted(set(images))
    else:
        print(f"  ⚠️  Unit_bearing 경로 없음: {bearing_root}")

    # 최소 샘플 수 경고
    skipped = []
    for cls, imgs in list(class_images.items()):
        if len(imgs) < min_samples:
            skipped.append((cls, len(imgs)))

    if skipped:
        print(f"\n  ⚠️  최소 샘플 미달 카테고리 ({min_samples}장 기준):")
        for cls, cnt in skipped:
            print(f"    {cls}: {cnt}장")
        print(f"    → 이 카테고리들도 포함됩니다 (제외하려면 --min-samples 값을 높이세요)")

    return class_images


# ─────────────────────────────────────────────
# 데이터셋 분할
# ─────────────────────────────────────────────

def stratified_split(
    class_images: dict[str, list[Path]],
    val_ratio: float = 0.15,
    seed: int = 42,
) -> tuple[dict[str, list[Path]], dict[str, list[Path]]]:
    """Stratified train/val 분할을 수행한다.

    각 카테고리에서 val_ratio 비율만큼 검증 세트로 분리한다.
    최소 1장은 val에 포함되도록 보장한다.

    Args:
        class_images: {class_name: [paths]}
        val_ratio: 검증 세트 비율 (기본 15%)
        seed: 랜덤 시드

    Returns:
        (train_dict, val_dict)
    """
    random.seed(seed)

    train_dict: dict[str, list[Path]] = {}
    val_dict: dict[str, list[Path]] = {}

    for class_name, images in class_images.items():
        shuffled = images.copy()
        random.shuffle(shuffled)

        n_val = max(1, int(len(images) * val_ratio))
        # 이미지가 1장뿐이면 train에만 넣기
        if len(images) <= 1:
            train_dict[class_name] = shuffled
            val_dict[class_name] = []
            continue

        val_dict[class_name] = shuffled[:n_val]
        train_dict[class_name] = shuffled[n_val:]

    return train_dict, val_dict


# ─────────────────────────────────────────────
# 데이터셋 생성
# ─────────────────────────────────────────────

def create_dataset(
    output_dir: Path,
    train_dict: dict[str, list[Path]],
    val_dict: dict[str, list[Path]],
    use_symlinks: bool = True,
) -> None:
    """train/val 디렉토리 구조를 생성한다.

    Args:
        output_dir: 출력 루트 디렉토리
        train_dict: {class_name: [paths]} 학습 세트
        val_dict: {class_name: [paths]} 검증 세트
        use_symlinks: True면 심볼릭 링크, False면 파일 복사
    """
    method = "symlink" if use_symlinks else "copy"
    print(f"\n  데이터셋 생성 중 ({method} 모드)...")

    for split_name, split_dict in [("train", train_dict), ("val", val_dict)]:
        split_dir = output_dir / split_name
        total_count = 0

        for class_name, images in sorted(split_dict.items()):
            class_dir = split_dir / class_name
            class_dir.mkdir(parents=True, exist_ok=True)

            for img_path in images:
                dest = class_dir / img_path.name

                # 파일명 충돌 방지
                if dest.exists():
                    stem = img_path.stem
                    suffix = img_path.suffix
                    counter = 1
                    while dest.exists():
                        dest = class_dir / f"{stem}_{counter}{suffix}"
                        counter += 1

                if use_symlinks:
                    try:
                        dest.symlink_to(img_path.resolve())
                    except OSError:
                        # 심볼릭 링크 실패 시 복사로 폴백
                        shutil.copy2(img_path, dest)
                else:
                    shutil.copy2(img_path, dest)

                total_count += 1

        print(f"    {split_name}: {total_count:,}장 ({len(split_dict)}클래스)")


# ─────────────────────────────────────────────
# 메타데이터 저장
# ─────────────────────────────────────────────

def save_class_mapping(
    output_dir: Path,
    class_names: list[str],
) -> None:
    """class_names.json 저장 (인덱스 → 클래스명 매핑)"""
    mapping = {i: name for i, name in enumerate(sorted(class_names))}
    path = output_dir / "class_names.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"  class_names.json 저장: {path} ({len(mapping)}클래스)")


def save_dataset_stats(
    output_dir: Path,
    train_dict: dict[str, list[Path]],
    val_dict: dict[str, list[Path]],
) -> None:
    """dataset_stats.json 저장 (클래스별 통계)"""
    stats = {
        "total_classes": len(train_dict),
        "total_train": sum(len(v) for v in train_dict.values()),
        "total_val": sum(len(v) for v in val_dict.values()),
        "per_class": {},
    }

    for cls in sorted(train_dict.keys()):
        n_train = len(train_dict.get(cls, []))
        n_val = len(val_dict.get(cls, []))
        stats["per_class"][cls] = {
            "train": n_train,
            "val": n_val,
            "total": n_train + n_val,
        }

    path = output_dir / "dataset_stats.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  dataset_stats.json 저장: {path}")


# ─────────────────────────────────────────────
# 통계 출력
# ─────────────────────────────────────────────

def print_summary(
    class_images: dict[str, list[Path]],
    train_dict: dict[str, list[Path]],
    val_dict: dict[str, list[Path]],
) -> None:
    """데이터셋 통계를 출력한다."""
    total = sum(len(v) for v in class_images.values())
    n_train = sum(len(v) for v in train_dict.values())
    n_val = sum(len(v) for v in val_dict.values())

    print(f"\n{'=' * 65}")
    print(f"  📊 데이터셋 통계")
    print(f"{'=' * 65}")
    print(f"  전체 클래스: {len(class_images)}개")
    print(f"  전체 이미지: {total:,}장")
    print(f"  학습 세트:   {n_train:,}장 ({n_train / total * 100:.1f}%)")
    print(f"  검증 세트:   {n_val:,}장 ({n_val / total * 100:.1f}%)")

    # Top-10 / Bottom-10
    sorted_classes = sorted(
        class_images.items(), key=lambda x: len(x[1]), reverse=True
    )

    print(f"\n  📈 이미지 수 상위 10:")
    for cls, imgs in sorted_classes[:10]:
        n_tr = len(train_dict.get(cls, []))
        n_va = len(val_dict.get(cls, []))
        print(f"    {cls:<40} {len(imgs):>5}장 (train:{n_tr}, val:{n_va})")

    print(f"\n  📉 이미지 수 하위 10:")
    for cls, imgs in sorted_classes[-10:]:
        n_tr = len(train_dict.get(cls, []))
        n_va = len(val_dict.get(cls, []))
        print(f"    {cls:<40} {len(imgs):>5}장 (train:{n_tr}, val:{n_va})")

    # 불균형 경고
    max_count = len(sorted_classes[0][1])
    min_count = len(sorted_classes[-1][1])
    ratio = max_count / min_count if min_count > 0 else float("inf")
    if ratio > 50:
        print(f"\n  ⚠️  클래스 불균형 심각: {max_count}:{min_count} (비율 {ratio:.0f}:1)")
        print(f"      → 학습 시 augmentation/oversampling 권장")

    print(f"{'=' * 65}")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="YOLOv8-cls 학습용 데이터셋 준비 (73카테고리)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/prepare_cls_dataset.py --output ./data/cls_dataset
  python scripts/prepare_cls_dataset.py --output ./data/cls_dataset --val-ratio 0.2 --use-copy
        """,
    )
    parser.add_argument(
        "--output", type=str, default="./data/cls_dataset",
        help="출력 디렉토리 (기본: ./data/cls_dataset)",
    )
    parser.add_argument(
        "--val-ratio", type=float, default=0.15,
        help="검증 세트 비율 (기본: 0.15)",
    )
    parser.add_argument(
        "--min-samples", type=int, default=1,
        help="최소 이미지 수 경고 임계값 (기본: 1)",
    )
    parser.add_argument(
        "--use-copy", action="store_true",
        help="심볼릭 링크 대신 파일 복사 (Docker 환경용)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="랜덤 시드 (기본: 42)",
    )
    parser.add_argument(
        "--misumi-root", type=str, default=str(MISUMI_ROOT),
        help=f"MiSUMi 소스 디렉토리 (기본: {MISUMI_ROOT})",
    )
    parser.add_argument(
        "--bearing-root", type=str, default=str(UNIT_BEARING_ROOT),
        help=f"Unit_bearing 소스 디렉토리 (기본: {UNIT_BEARING_ROOT})",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="기존 출력 디렉토리 삭제 후 재생성",
    )

    args = parser.parse_args()
    output_dir = Path(args.output)

    print("=" * 65)
    print("  YOLOv8-cls 데이터셋 준비")
    print("=" * 65)

    # 기존 디렉토리 처리
    if output_dir.exists():
        if args.clean:
            print(f"\n  기존 디렉토리 삭제: {output_dir}")
            shutil.rmtree(output_dir)
        else:
            print(f"\n  ⚠️  디렉토리 이미 존재: {output_dir}")
            print(f"      --clean 옵션으로 재생성하거나 다른 경로를 지정하세요.")
            sys.exit(1)

    # Step 1: 이미지 수집
    print(f"\n  Step 1: 이미지 수집...")
    print(f"    MiSUMi:       {args.misumi_root}")
    print(f"    Unit_bearing: {args.bearing_root}")

    class_images = collect_images(
        misumi_root=Path(args.misumi_root),
        bearing_root=Path(args.bearing_root),
        min_samples=args.min_samples,
    )

    if not class_images:
        print("  [ERROR] 이미지를 찾을 수 없습니다. 소스 경로를 확인하세요.")
        sys.exit(1)

    total = sum(len(v) for v in class_images.values())
    print(f"\n    수집 완료: {len(class_images)}클래스, {total:,}장")

    # Step 2: Train/Val 분할
    print(f"\n  Step 2: Stratified 분할 (val_ratio={args.val_ratio}, seed={args.seed})...")
    train_dict, val_dict = stratified_split(
        class_images,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )

    # Step 3: 디렉토리 생성
    print(f"\n  Step 3: 데이터셋 생성 → {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    create_dataset(
        output_dir,
        train_dict,
        val_dict,
        use_symlinks=not args.use_copy,
    )

    # Step 4: 메타데이터 저장
    print(f"\n  Step 4: 메타데이터 저장...")
    save_class_mapping(output_dir, list(class_images.keys()))
    save_dataset_stats(output_dir, train_dict, val_dict)

    # 통계 출력
    print_summary(class_images, train_dict, val_dict)

    print(f"\n  ✅ 데이터셋 준비 완료: {output_dir}")
    print(f"\n  다음 단계:")
    print(f"    python scripts/train_yolo_cls.py --data {output_dir}")


if __name__ == "__main__":
    main()
