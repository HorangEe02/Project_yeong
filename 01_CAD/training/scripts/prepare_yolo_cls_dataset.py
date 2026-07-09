#!/usr/bin/env python3
"""
Step 5-B: YOLOv8-cls 확장 학습 데이터셋 구성
- 기존 MiSUMi/Bearing 데이터 (61,841장, 72 카테고리)
- 신규 staged 데이터 (7,921장, 24 카테고리 → 12 기존 매핑 + 12 신규)
- 통합 85 카테고리 train/val 분할 (85:15 비율)
- 심볼릭 링크 대신 실제 파일 경로 참조 (YOLO가 직접 읽음)

출력: drawing-datasets/yolo_cls_dataset/
  ├── train/{카테고리명}/  (심볼릭 링크)
  ├── val/{카테고리명}/    (심볼릭 링크)
  ├── dataset.yaml         (YOLO 학습 설정)
  └── dataset_stats.json   (통계)
"""

import os
import json
import random
import time
from pathlib import Path
from collections import defaultdict

RANDOM_SEED = 42
VAL_RATIO = 0.15  # 15% validation

# === 경로 설정 ===
BASE_DIR = Path("<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD")
STAGED_DIR = BASE_DIR / "drawing-datasets" / "staged"
OUTPUT_DIR = BASE_DIR / "drawing-datasets" / "yolo_cls_dataset"

# 기존 MiSUMi 데이터 경로
MISUMI_PNG_DIR = BASE_DIR / "CAD_etc" / "data" / "MiSUMi_png"
BEARING_PNG_DIR = BASE_DIR / "CAD_etc" / "data" / "Unit_bearing_png"

# 통합 카테고리 파일
CLASS_NAMES_FILE = BASE_DIR / "drawing-datasets" / "unified_class_names.json"

# 이미지 확장자
IMAGE_EXTS = {'.png', '.jpg', '.jpeg'}

# MiSUMi 디렉토리명 → 카테고리명 매핑 (실제 디렉토리명 기준)
MISUMI_DIR_MAP = {
    "00_new_products": "new_products",
    "01_Shafts": "Shafts",
    "02_Holders_for_Shaft": "Holders_for_Shaft",
    "03_Set_Collars": "Set_Collars",
    "04_Linear Bushings": "Linear_Bushings",
    "05_Ball_Splines": "Ball_Splines",
    "06_Oil_Free_Bushings": "Oil_Free_Bushings",
    "07_Actuator": "Actuator",
    "08_Linear_Guides": "Linear_Guides",
    "09_Slide_Rails": "Slide_Rails",
    "10_Ball_Screws": "Ball_Screws",
    "11_Slide_Screws": "Slide_Screws",
    "12_Rotary_Shafts": "Rotary_Shafts",
    "13_Hinge_Pins": "Hinge_Pins",
    "14_Bearings_with_Holder": "Bearings_with_Holder",
    "15_Couplings": "Couplings",
    "16_Rollers": "Rollers",
    "17_Conveyors": "Conveyors",
    "18_Flat_Belts_and_Round_Belts": "Flat_Belts_and_Round_Belts",
    "19_Timing_Pulleys": "Timing_Pulleys",
    "20_Gears": "Gears",
    "21_Sprockets_and_Chains": "Sprockets_and_Chains",
    "22_Locating_Pins": "Locating_Pins",
    "23_Locating_&_Guide_Components": "Locating_and_Guide_Components",
    "24_Plungers": "Plungers",
    "25_Clamps": "Clamps",
    "26_Inspections": "Inspections",
    "27_Contact_Probes": "Contact_Probes",
    "28_Simplified Adjustment Units": "Simplified_Adjustment_Units",
    "29_Stages": "Stages",
    "30_image processing": "image_processing",
    "31_Sensors": "Sensors",
    "32_Posts": "Posts",
    "33_Ribs_and_Angle_Plates": "Ribs_and_Angle_Plates",
    "34_Washers": "Washers",
    "35_Screws": "Screws",
    "36_Misc": "Misc",
    "37_Rods": "Rods",
    "38_Springs": "Springs",
    "39_Urethanes": "Urethanes",
    "40_Antivibration": "Antivibration",
    "41_Aluminum_Frames": "Aluminum_Frames",
    "42_Accessories": "Accessories",
    "44_Pipe_Frames": "Pipe_Frames",
    "45_Cover_Panels": "Cover_Panels",
    "46_Resin Plates": "Resin_Plates",
    "47_Led_Lighting": "Led_Lighting",
    "48_Casters": "Casters",
    "49_Levers": "Levers",
    "50_Pulls": "Pulls",
    "51_Manifolds": "Manifolds",
    "52_Pipes_Fitting_Valves": "Pipes_Fitting_Valves",
    "53_Sanitary_Vacuum_Tanks": "Sanitary_Vacuum_Tanks",
    "54_Fitting_and_Nozzles": "Fitting_and_Nozzles",
    "55_Cylinders": "Cylinders",
    "56_Heaters": "Heaters",
    "58_Angles": "Angles",
    "59_Brackets": "Brackets",
}

# Bearing 디렉토리명 → 카테고리명 매핑
BEARING_DIR_MAP = {
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
    "13.SN(플러머블록)": "bearing_SN플러머블록",
    "14.TAKEUP": "bearing_TAKEUP",
    "15.H-ADAPTER": "bearing_H_ADAPTER",
}

# 학습 제외 카테고리 (메타 카테고리)
EXCLUDE_CATEGORIES = {"image_processing", "new_products"}


def collect_images_from_dir(base_dir: Path, dir_map: dict) -> dict:
    """디렉토리 구조에서 이미지 수집"""
    category_images = defaultdict(list)

    if not base_dir.exists():
        print(f"  ⚠ 디렉토리 없음: {base_dir}")
        return category_images

    for dir_name, cat_name in dir_map.items():
        if cat_name in EXCLUDE_CATEGORIES:
            continue

        cat_dir = base_dir / dir_name
        if not cat_dir.exists():
            continue

        for f in cat_dir.iterdir():
            if f.suffix.lower() in IMAGE_EXTS and not f.name.startswith('.'):
                category_images[cat_name].append(str(f))

    return category_images


def collect_staged_images() -> dict:
    """staged 디렉토리에서 이미지 수집"""
    category_images = defaultdict(list)

    if not STAGED_DIR.exists():
        print("  ⚠ staged 디렉토리 없음")
        return category_images

    for cat_dir in STAGED_DIR.iterdir():
        if not cat_dir.is_dir():
            continue

        cat_name = cat_dir.name
        if cat_name in EXCLUDE_CATEGORIES:
            continue

        for f in cat_dir.iterdir():
            if f.suffix.lower() in IMAGE_EXTS and not f.name.startswith('.'):
                category_images[cat_name].append(str(f))

    return category_images


def split_train_val(images: list, val_ratio: float, seed: int) -> tuple:
    """train/val 분할"""
    random.seed(seed)
    shuffled = images.copy()
    random.shuffle(shuffled)

    val_count = max(1, int(len(shuffled) * val_ratio))
    # 최소 1장은 train에 유지
    if val_count >= len(shuffled):
        val_count = max(0, len(shuffled) - 1)

    val = shuffled[:val_count]
    train = shuffled[val_count:]
    return train, val


def create_symlinks(images: list, target_dir: Path):
    """이미지 파일에 대한 심볼릭 링크 생성"""
    target_dir.mkdir(parents=True, exist_ok=True)

    for img_path in images:
        src = Path(img_path)
        dst = target_dir / src.name

        # 이름 충돌 방지
        if dst.exists() or dst.is_symlink():
            stem = src.stem
            suffix = src.suffix
            counter = 1
            while dst.exists() or dst.is_symlink():
                dst = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        try:
            os.symlink(str(src.resolve()), str(dst))
        except OSError as e:
            print(f"    ✗ 링크 실패: {src.name} - {e}")


def main():
    print("=" * 60)
    print("  Step 5-B: YOLOv8-cls 확장 학습 데이터셋 구성")
    print(f"  Val 비율: {VAL_RATIO*100:.0f}%")
    print(f"  출력: {OUTPUT_DIR}")
    print("=" * 60)

    # 카테고리 이름 로드
    with open(CLASS_NAMES_FILE, 'r', encoding='utf-8') as f:
        class_names = json.load(f)

    # === 1. 이미지 수집 ===
    print("\n[1/4] 이미지 수집 중...")

    # 기존 MiSUMi 데이터
    print(f"  MiSUMi: {MISUMI_PNG_DIR}")
    misumi_images = collect_images_from_dir(MISUMI_PNG_DIR, MISUMI_DIR_MAP)
    misumi_total = sum(len(v) for v in misumi_images.values())
    print(f"    → {len(misumi_images)}개 카테고리, {misumi_total}장")

    # 기존 Bearing 데이터
    print(f"  Bearing: {BEARING_PNG_DIR}")
    bearing_images = collect_images_from_dir(BEARING_PNG_DIR, BEARING_DIR_MAP)
    bearing_total = sum(len(v) for v in bearing_images.values())
    print(f"    → {len(bearing_images)}개 카테고리, {bearing_total}장")

    # 신규 staged 데이터
    print(f"  Staged: {STAGED_DIR}")
    staged_images = collect_staged_images()
    staged_total = sum(len(v) for v in staged_images.values())
    print(f"    → {len(staged_images)}개 카테고리, {staged_total}장")

    # === 2. 통합 ===
    print("\n[2/4] 카테고리 통합 중...")
    all_images = defaultdict(list)

    for cat, imgs in misumi_images.items():
        all_images[cat].extend(imgs)
    for cat, imgs in bearing_images.items():
        all_images[cat].extend(imgs)
    for cat, imgs in staged_images.items():
        all_images[cat].extend(imgs)

    total_categories = len(all_images)
    total_images = sum(len(v) for v in all_images.values())
    print(f"  통합 결과: {total_categories}개 카테고리, {total_images}장")

    # === 3. Train/Val 분할 및 심볼릭 링크 생성 ===
    print("\n[3/4] Train/Val 분할 및 링크 생성 중...")

    # 기존 출력 정리
    if OUTPUT_DIR.exists():
        import shutil
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    train_dir = OUTPUT_DIR / "train"
    val_dir = OUTPUT_DIR / "val"

    stats = {}
    total_train = 0
    total_val = 0

    for cat_name in sorted(all_images.keys()):
        imgs = all_images[cat_name]
        train_imgs, val_imgs = split_train_val(imgs, VAL_RATIO, RANDOM_SEED)

        create_symlinks(train_imgs, train_dir / cat_name)
        create_symlinks(val_imgs, val_dir / cat_name)

        stats[cat_name] = {
            "train": len(train_imgs),
            "val": len(val_imgs),
            "total": len(imgs),
        }
        total_train += len(train_imgs)
        total_val += len(val_imgs)

        print(f"  {cat_name:35s}: {len(imgs):>5d} (train {len(train_imgs):>5d} / val {len(val_imgs):>4d})")

    # === 4. YOLO 설정 파일 생성 ===
    print("\n[4/4] YOLO 설정 파일 생성 중...")

    # dataset.yaml for YOLOv8-cls
    yaml_content = f"""# YOLOv8-cls 확장 학습 데이터셋
# 생성일: {time.strftime("%Y-%m-%d %H:%M:%S")}
# 카테고리: {total_categories}개
# 이미지: {total_images}장 (train {total_train} / val {total_val})

path: {OUTPUT_DIR}
train: train
val: val

# 카테고리 목록 ({total_categories}개)
names:
"""
    # 카테고리를 ID 순서로 정렬
    id_to_name = {}
    for id_str, name in class_names.items():
        if name in all_images:
            id_to_name[int(id_str)] = name

    # class_names에 없는 카테고리 확인 (이론상 없어야 함)
    name_to_id = {v: int(k) for k, v in class_names.items()}

    for cat_id in sorted(id_to_name.keys()):
        cat_name = id_to_name[cat_id]
        yaml_content += f"  {cat_id}: {cat_name}\n"

    yaml_path = OUTPUT_DIR / "dataset.yaml"
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)

    # dataset_stats.json
    dataset_stats = {
        "creation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_classes": total_categories,
        "total_train": total_train,
        "total_val": total_val,
        "total_images": total_images,
        "val_ratio": VAL_RATIO,
        "sources": {
            "misumi": {"categories": len(misumi_images), "images": misumi_total},
            "bearing": {"categories": len(bearing_images), "images": bearing_total},
            "staged_new": {"categories": len(staged_images), "images": staged_total},
        },
        "per_class": stats,
    }

    stats_path = OUTPUT_DIR / "dataset_stats.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(dataset_stats, f, ensure_ascii=False, indent=2)

    # unified class names 복사
    import shutil
    shutil.copy2(CLASS_NAMES_FILE, OUTPUT_DIR / "class_names.json")

    # === 최종 요약 ===
    print(f"\n{'='*60}")
    print("  YOLOv8-cls 데이터셋 구성 완료")
    print(f"{'='*60}")
    print(f"  카테고리: {total_categories}개")
    print(f"  Train: {total_train}장")
    print(f"  Val: {total_val}장")
    print(f"  합계: {total_images}장")
    print(f"\n  출력 디렉토리: {OUTPUT_DIR}")
    print(f"  YOLO 설정: {yaml_path}")
    print(f"  통계: {stats_path}")
    print(f"\n  학습 명령어:")
    print(f"  yolo classify train data={yaml_path} model=yolov8s-cls.pt epochs=100 imgsz=224")


if __name__ == "__main__":
    main()
