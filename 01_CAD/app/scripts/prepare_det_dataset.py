#!/usr/bin/env python3
"""
YOLOv8-det 학습용 데이터셋 준비 스크립트

도면 이미지에서 영역 탐지(title_block, dimension_area, parts_table) 학습에 필요한
YOLO detection 데이터셋 구조를 생성한다.

사용법:
  python scripts/prepare_det_dataset.py --output ./data/det_dataset
  python scripts/prepare_det_dataset.py --output ./data/det_dataset --total 2000
  python scripts/prepare_det_dataset.py --output ./data/det_dataset --generate-heuristic
  python scripts/prepare_det_dataset.py --output ./data/det_dataset --export-cvat

디렉토리 구조 (YOLOv8-det 표준):
  data/det_dataset/
    images/train/  ← 학습 이미지
    images/val/    ← 검증 이미지
    labels/train/  ← YOLO 형식 라벨 (class_id cx cy w h)
    labels/val/    ← YOLO 형식 라벨
    dataset.yaml   ← 데이터셋 설정 파일

탐지 클래스 (3개):
  0: title_block      (표제란)
  1: dimension_area    (치수 영역)
  2: parts_table       (부품표)
"""

import argparse
import json
import random
import shutil
import sys
import xml.etree.ElementTree as ET
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

# 탐지 클래스 정의
DET_CLASSES = ["title_block", "dimension_area", "parts_table"]
DET_CLASS_MAP = {name: idx for idx, name in enumerate(DET_CLASSES)}


# ─────────────────────────────────────────────
# 이미지 수집 (카테고리 비례 샘플링)
# ─────────────────────────────────────────────

def collect_all_images(
    misumi_root: Path,
    bearing_root: Path,
) -> dict[str, list[Path]]:
    """소스 디렉토리에서 카테고리별 이미지 경로를 수집한다.

    Returns:
        {folder_name: [image_path, ...]}
    """
    category_images: dict[str, list[Path]] = {}

    for root_dir in [misumi_root, bearing_root]:
        if not root_dir.exists():
            print(f"  [WARNING] 소스 경로 없음: {root_dir}")
            continue
        for cat_dir in sorted(root_dir.iterdir()):
            if not cat_dir.is_dir():
                continue
            images = []
            for ext in IMAGE_EXTENSIONS:
                images.extend(cat_dir.glob(f"*{ext}"))
                images.extend(cat_dir.glob(f"*/*{ext}"))
            if images:
                category_images[cat_dir.name] = sorted(set(images))

    return category_images


def proportional_sample(
    category_images: dict[str, list[Path]],
    total: int,
    seed: int = 42,
) -> list[Path]:
    """카테고리 비례 샘플링으로 이미지를 선별한다.

    각 카테고리에서 전체 비율에 비례하여 이미지를 선택한다.
    최소 1장은 보장한다.

    Args:
        category_images: {category: [paths]}
        total: 총 샘플 수
        seed: 랜덤 시드

    Returns:
        list[Path]: 샘플링된 이미지 경로 리스트
    """
    random.seed(seed)

    all_count = sum(len(v) for v in category_images.values())
    if total >= all_count:
        # 전체 수보다 많으면 모든 이미지 사용
        all_images = []
        for imgs in category_images.values():
            all_images.extend(imgs)
        return all_images

    sampled: list[Path] = []
    remaining = total

    # 카테고리별 비례 할당
    allocations: dict[str, int] = {}
    for cat, imgs in category_images.items():
        n = max(1, int(len(imgs) / all_count * total))
        n = min(n, len(imgs))
        allocations[cat] = n
        remaining -= n

    # 잔여분 배분 (큰 카테고리 우선)
    sorted_cats = sorted(
        category_images.keys(),
        key=lambda c: len(category_images[c]),
        reverse=True,
    )
    idx = 0
    while remaining > 0:
        cat = sorted_cats[idx % len(sorted_cats)]
        if allocations[cat] < len(category_images[cat]):
            allocations[cat] += 1
            remaining -= 1
        idx += 1
        if idx > total * 2:
            break

    # 실제 샘플링
    for cat, n in allocations.items():
        imgs = category_images[cat]
        shuffled = imgs.copy()
        random.shuffle(shuffled)
        sampled.extend(shuffled[:n])

    return sampled


# ─────────────────────────────────────────────
# 휴리스틱 표제란 bbox 생성
# ─────────────────────────────────────────────

def generate_heuristic_title_block_label(image_path: Path) -> str | None:
    """CAD 도면의 표제란 위치를 휴리스틱으로 추정하여 YOLO 라벨 문자열을 반환한다.

    표제란은 대부분 우하단 약 20-30% 영역에 위치한다.
    이 라벨은 어노테이션 가속을 위한 초기값이며, 수작업 검수가 필요하다.

    Returns:
        YOLO 형식 라벨 문자열 "class_id cx cy w h" 또는 None
    """
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            w, h = img.size
    except Exception:
        return None

    # 휴리스틱: 우하단 영역 (정규화 좌표)
    # cx=0.875, cy=0.875, w=0.25, h=0.25 (이미지의 우하단 25%)
    # 가로가 긴 도면(A3/A4 횡)은 표제란이 더 우측에 있음
    aspect = w / h if h > 0 else 1.0

    if aspect > 1.3:
        # 가로 도면: 표제란이 좁고 우측에 치우침
        cx, cy, bw, bh = 0.90, 0.85, 0.20, 0.30
    else:
        # 세로 도면: 표제란이 하단 전체에 걸침
        cx, cy, bw, bh = 0.50, 0.92, 0.90, 0.16

    class_id = DET_CLASS_MAP["title_block"]
    return f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


# ─────────────────────────────────────────────
# 데이터셋 생성
# ─────────────────────────────────────────────

def create_det_dataset(
    output_dir: Path,
    images: list[Path],
    val_ratio: float = 0.15,
    seed: int = 42,
    use_symlinks: bool = True,
    generate_heuristic: bool = False,
) -> tuple[int, int]:
    """YOLO detection 데이터셋 구조를 생성한다.

    Args:
        output_dir: 출력 루트 디렉토리
        images: 이미지 경로 리스트
        val_ratio: 검증 세트 비율
        seed: 랜덤 시드
        use_symlinks: 심볼릭 링크 사용 여부
        generate_heuristic: 휴리스틱 title_block 라벨 생성 여부

    Returns:
        (n_train, n_val)
    """
    random.seed(seed)
    shuffled = images.copy()
    random.shuffle(shuffled)

    n_val = max(1, int(len(images) * val_ratio))
    val_images = shuffled[:n_val]
    train_images = shuffled[n_val:]

    # 디렉토리 생성
    for split in ["train", "val"]:
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    method = "symlink" if use_symlinks else "copy"
    print(f"\n  데이터셋 생성 ({method} 모드)...")

    heuristic_count = 0
    for split_name, split_images in [("train", train_images), ("val", val_images)]:
        img_dir = output_dir / "images" / split_name
        lbl_dir = output_dir / "labels" / split_name

        for img_path in split_images:
            dest = img_dir / img_path.name

            # 파일명 충돌 방지
            if dest.exists():
                stem = img_path.stem
                suffix = img_path.suffix
                counter = 1
                while dest.exists():
                    dest = img_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            # 이미지 링크/복사
            if use_symlinks:
                try:
                    dest.symlink_to(img_path.resolve())
                except OSError:
                    shutil.copy2(img_path, dest)
            else:
                shutil.copy2(img_path, dest)

            # 빈 라벨 파일 생성 (어노테이션 전)
            label_file = lbl_dir / dest.with_suffix(".txt").name

            if generate_heuristic:
                heuristic_label = generate_heuristic_title_block_label(img_path)
                if heuristic_label:
                    with open(label_file, "w") as f:
                        f.write(heuristic_label + "\n")
                    heuristic_count += 1
                else:
                    label_file.touch()
            else:
                label_file.touch()

        print(f"    {split_name}: {len(split_images):,}장")

    if generate_heuristic:
        print(f"    휴리스틱 title_block 라벨: {heuristic_count:,}장")

    return len(train_images), len(val_images)


def create_dataset_yaml(output_dir: Path) -> None:
    """dataset.yaml 파일을 생성한다."""
    yaml_content = f"""# YOLOv8-det 도면 영역 탐지 데이터셋
# 생성: scripts/prepare_det_dataset.py

path: {output_dir.resolve()}
train: images/train
val: images/val

# 탐지 클래스 (3개)
names:
  0: title_block       # 표제란 (도번, 재질, 척도, 날짜 등)
  1: dimension_area     # 치수 영역 (치수 주석 집중 영역)
  2: parts_table        # 부품표 (BOM 테이블)

nc: 3
"""
    yaml_path = output_dir / "dataset.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"  dataset.yaml 저장: {yaml_path}")


# ─────────────────────────────────────────────
# CVAT XML 내보내기
# ─────────────────────────────────────────────

def export_cvat_xml(
    output_dir: Path,
    split: str = "train",
) -> None:
    """CVAT 가져오기용 XML을 생성한다.

    CVAT의 "Upload annotations" → "CVAT for images 1.1" 형식으로
    가져갈 수 있는 XML 파일을 생성한다.

    Args:
        output_dir: 데이터셋 루트 디렉토리
        split: "train" 또는 "val"
    """
    img_dir = output_dir / "images" / split
    lbl_dir = output_dir / "labels" / split

    if not img_dir.exists():
        print(f"  [WARNING] 이미지 디렉토리 없음: {img_dir}")
        return

    # XML 구조 생성
    root = ET.Element("annotations")
    ET.SubElement(root, "version").text = "1.1"

    # 메타 정보
    meta = ET.SubElement(root, "meta")
    task = ET.SubElement(meta, "task")
    ET.SubElement(task, "name").text = f"drawing_det_{split}"
    labels_elem = ET.SubElement(task, "labels")
    for cls_name in DET_CLASSES:
        label = ET.SubElement(labels_elem, "label")
        ET.SubElement(label, "name").text = cls_name
        ET.SubElement(label, "type").text = "rectangle"

    # 이미지 + 라벨
    image_files = sorted(img_dir.iterdir())
    for idx, img_file in enumerate(image_files):
        if img_file.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        # 이미지 크기 가져오기
        try:
            from PIL import Image
            with Image.open(img_file) as img:
                w, h = img.size
        except Exception:
            w, h = 1000, 1000  # 기본값

        image_elem = ET.SubElement(root, "image", {
            "id": str(idx),
            "name": img_file.name,
            "width": str(w),
            "height": str(h),
        })

        # 라벨 파일에서 bbox 읽기
        label_file = lbl_dir / img_file.with_suffix(".txt").name
        if label_file.exists():
            with open(label_file, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) != 5:
                        continue
                    cls_id, cx, cy, bw, bh = (
                        int(parts[0]),
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3]),
                        float(parts[4]),
                    )
                    if cls_id < 0 or cls_id >= len(DET_CLASSES):
                        continue

                    # YOLO 정규화 → 픽셀 좌표
                    x1 = (cx - bw / 2) * w
                    y1 = (cy - bh / 2) * h
                    x2 = (cx + bw / 2) * w
                    y2 = (cy + bh / 2) * h

                    ET.SubElement(image_elem, "box", {
                        "label": DET_CLASSES[cls_id],
                        "xtl": f"{x1:.2f}",
                        "ytl": f"{y1:.2f}",
                        "xbr": f"{x2:.2f}",
                        "ybr": f"{y2:.2f}",
                        "occluded": "0",
                    })

    # XML 저장
    tree = ET.ElementTree(root)
    xml_path = output_dir / f"cvat_{split}.xml"
    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    print(f"  CVAT XML 저장: {xml_path} ({len(image_files)}장)")


# ─────────────────────────────────────────────
# 통계 출력
# ─────────────────────────────────────────────

def save_dataset_stats(
    output_dir: Path,
    total_images: int,
    n_train: int,
    n_val: int,
    n_categories_sampled: int,
) -> None:
    """dataset_stats.json 저장"""
    stats = {
        "task": "detection",
        "classes": DET_CLASSES,
        "num_classes": len(DET_CLASSES),
        "total_images": total_images,
        "train_images": n_train,
        "val_images": n_val,
        "categories_sampled_from": n_categories_sampled,
        "note": "labels require manual annotation (CVAT/LabelImg)",
    }
    path = output_dir / "dataset_stats.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  dataset_stats.json 저장: {path}")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="YOLOv8-det 학습용 데이터셋 준비 (표제란/치수/부품표 탐지)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python scripts/prepare_det_dataset.py --output ./data/det_dataset --total 2000
  python scripts/prepare_det_dataset.py --output ./data/det_dataset --generate-heuristic
  python scripts/prepare_det_dataset.py --output ./data/det_dataset --export-cvat
        """,
    )
    parser.add_argument(
        "--output", type=str, default="./data/det_dataset",
        help="출력 디렉토리 (기본: ./data/det_dataset)",
    )
    parser.add_argument(
        "--total", type=int, default=2000,
        help="총 샘플 수 (기본: 2000)",
    )
    parser.add_argument(
        "--val-ratio", type=float, default=0.15,
        help="검증 세트 비율 (기본: 0.15)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="랜덤 시드 (기본: 42)",
    )
    parser.add_argument(
        "--use-copy", action="store_true",
        help="심볼릭 링크 대신 파일 복사",
    )
    parser.add_argument(
        "--generate-heuristic", action="store_true",
        help="휴리스틱 title_block 라벨 자동 생성 (초기 어노테이션용)",
    )
    parser.add_argument(
        "--export-cvat", action="store_true",
        help="CVAT 가져오기용 XML 내보내기",
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
    print("  YOLOv8-det 데이터셋 준비 (영역 탐지)")
    print("=" * 65)
    print(f"  탐지 클래스: {DET_CLASSES}")
    print(f"  목표 샘플 수: {args.total:,}장")

    # 기존 디렉토리 처리
    if output_dir.exists():
        if args.clean:
            print(f"\n  기존 디렉토리 삭제: {output_dir}")
            shutil.rmtree(output_dir)
        else:
            print(f"\n  [WARNING] 디렉토리 이미 존재: {output_dir}")
            print(f"      --clean 옵션으로 재생성하거나 다른 경로를 지정하세요.")
            sys.exit(1)

    # Step 1: 이미지 수집
    print(f"\n  Step 1: 이미지 수집...")
    category_images = collect_all_images(
        misumi_root=Path(args.misumi_root),
        bearing_root=Path(args.bearing_root),
    )

    if not category_images:
        print("  [ERROR] 이미지를 찾을 수 없습니다. 소스 경로를 확인하세요.")
        sys.exit(1)

    all_count = sum(len(v) for v in category_images.values())
    print(f"    수집 완료: {len(category_images)}카테고리, {all_count:,}장")

    # Step 2: 비례 샘플링
    print(f"\n  Step 2: 카테고리 비례 샘플링 ({args.total:,}장)...")
    sampled = proportional_sample(category_images, args.total, seed=args.seed)
    print(f"    샘플링 완료: {len(sampled):,}장")

    # Step 3: 데이터셋 생성
    print(f"\n  Step 3: YOLO 데이터셋 생성 → {output_dir}")
    n_train, n_val = create_det_dataset(
        output_dir,
        sampled,
        val_ratio=args.val_ratio,
        seed=args.seed,
        use_symlinks=not args.use_copy,
        generate_heuristic=args.generate_heuristic,
    )

    # Step 4: dataset.yaml + 메타데이터
    print(f"\n  Step 4: 설정 파일 생성...")
    create_dataset_yaml(output_dir)
    save_dataset_stats(output_dir, len(sampled), n_train, n_val, len(category_images))

    # Step 5: CVAT 내보내기 (옵션)
    if args.export_cvat:
        print(f"\n  Step 5: CVAT XML 내보내기...")
        export_cvat_xml(output_dir, split="train")
        export_cvat_xml(output_dir, split="val")

    # 결과 요약
    print(f"\n{'=' * 65}")
    print(f"  데이터셋 준비 완료")
    print(f"{'=' * 65}")
    print(f"  이미지: {len(sampled):,}장 (train: {n_train:,}, val: {n_val:,})")
    print(f"  라벨: {'휴리스틱 title_block 생성' if args.generate_heuristic else '빈 파일 (어노테이션 필요)'}")
    print(f"  출력: {output_dir}")

    print(f"\n  다음 단계:")
    if not args.generate_heuristic:
        print(f"    1. 어노테이션 도구로 bbox 라벨링 (CVAT / LabelImg)")
        print(f"       → CVAT: python scripts/prepare_det_dataset.py --export-cvat 후 가져오기")
    else:
        print(f"    1. 휴리스틱 라벨 검수 + dimension_area/parts_table 추가 라벨링")
    print(f"    2. python scripts/train_yolo_det.py --data {output_dir}")


if __name__ == "__main__":
    main()
