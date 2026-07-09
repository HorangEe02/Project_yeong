#!/usr/bin/env python3
"""
Step 5-A: CLIP Fine-tuning 데이터셋 구성
- 기존 MiSUMi/Bearing + 신규 staged 이미지를 활용
- Image-Text 쌍 생성 (contrastive learning)
- 카테고리별 다양한 텍스트 템플릿 적용
- OpenCLIP 학습 포맷 (CSV: filepath, caption)

출력: drawing-datasets/clip_finetune_dataset/
  ├── train.csv         (학습 image-text 쌍)
  ├── val.csv           (검증 image-text 쌍)
  ├── dataset_config.json (학습 하이퍼파라미터)
  └── dataset_stats.json  (통계)
"""

import csv
import json
import random
import time
from pathlib import Path
from collections import defaultdict

RANDOM_SEED = 42
VAL_RATIO = 0.15

# === 경로 설정 ===
BASE_DIR = Path("<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD")
STAGED_DIR = BASE_DIR / "drawing-datasets" / "staged"
OUTPUT_DIR = BASE_DIR / "drawing-datasets" / "clip_finetune_dataset"

MISUMI_PNG_DIR = BASE_DIR / "CAD_etc" / "data" / "MiSUMi_png"
BEARING_PNG_DIR = BASE_DIR / "CAD_etc" / "data" / "Unit_bearing_png"
CLASS_NAMES_FILE = BASE_DIR / "drawing-datasets" / "unified_class_names.json"

IMAGE_EXTS = {'.png', '.jpg', '.jpeg'}

# === 학습 제외 카테고리 ===
EXCLUDE_CATEGORIES = {"image_processing", "new_products"}

# === MiSUMi/Bearing 디렉토리 매핑 (실제 디렉토리명 기준) ===
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


# === 카테고리별 텍스트 설명 ===
# CLIP 학습에 사용할 카테고리-텍스트 매핑
CATEGORY_DESCRIPTIONS = {
    # MiSUMi 기계 부품
    "Accessories": ["mechanical accessories", "machine accessories and parts"],
    "Actuator": ["actuator mechanism", "linear actuator assembly", "pneumatic actuator"],
    "Aluminum_Frames": ["aluminum extrusion frame", "aluminum structural frame profile"],
    "Angles": ["angle bracket", "metal angle piece", "L-shaped angle"],
    "Antivibration": ["anti-vibration mount", "vibration damper", "rubber anti-vibration pad"],
    "Ball_Screws": ["ball screw assembly", "ball screw with nut", "precision ball screw"],
    "Ball_Splines": ["ball spline shaft", "ball spline bearing assembly"],
    "Bearings_with_Holder": ["bearing unit with housing", "pillow block bearing", "mounted bearing assembly"],
    "Brackets": ["mounting bracket", "structural bracket", "support bracket"],
    "Casters": ["caster wheel", "industrial caster", "swivel caster with brake"],
    "Clamps": ["mechanical clamp", "toggle clamp", "pipe clamp"],
    "Contact_Probes": ["spring contact probe", "test probe pin", "pogo pin"],
    "Conveyors": ["conveyor system", "belt conveyor assembly", "roller conveyor"],
    "Couplings": ["shaft coupling", "flexible coupling", "rigid coupling joint"],
    "Cover_Panels": ["cover panel", "protective cover plate", "enclosure panel"],
    "Cylinders": ["pneumatic cylinder", "hydraulic cylinder", "air cylinder actuator"],
    "Fitting_and_Nozzles": ["pipe fitting", "nozzle connector", "tube fitting"],
    "Flat_Belts_and_Round_Belts": ["flat drive belt", "round belt pulley system"],
    "Gears": ["gear wheel", "spur gear mechanism", "gear assembly"],
    "Heaters": ["industrial heater", "cartridge heater element"],
    "Hinge_Pins": ["hinge pin", "pivot pin", "hinge joint pin"],
    "Holders_for_Shaft": ["shaft holder", "shaft support block", "shaft mounting holder"],
    "Inspections": ["inspection tool", "measurement device", "gauging instrument"],
    "Led_Lighting": ["LED light fixture", "LED illumination module"],
    "Levers": ["mechanical lever", "lever handle", "lever arm mechanism"],
    "Linear_Bushings": ["linear bushing", "linear motion bearing", "slide bushing"],
    "Linear_Guides": ["linear guide rail", "linear motion guide", "precision linear guide"],
    "Locating_Pins": ["locating pin", "dowel pin", "precision locating pin"],
    "Locating_and_Guide_Components": ["guide component", "locating and guide mechanism"],
    "Manifolds": ["manifold block", "pneumatic manifold", "hydraulic manifold"],
    "Misc": ["miscellaneous mechanical part", "various mechanical component"],
    "Oil_Free_Bushings": ["oil-free bushing", "self-lubricating bushing", "dry bushing"],
    "Pipe_Frames": ["pipe frame structure", "tubular frame assembly"],
    "Pipes_Fitting_Valves": ["pipe valve assembly", "pipe fitting and valve", "plumbing valve"],
    "Plungers": ["spring plunger", "ball plunger", "indexing plunger"],
    "Posts": ["support post", "mounting post", "pillar post"],
    "Pulls": ["handle pull", "drawer pull", "cabinet pull handle"],
    "Resin_Plates": ["resin plate", "plastic plate", "polymer sheet"],
    "Ribs_and_Angle_Plates": ["rib plate", "angle plate", "reinforcement rib"],
    "Rods": ["metal rod", "support rod", "guide rod"],
    "Rollers": ["roller", "conveyor roller", "guide roller"],
    "Rotary_Shafts": ["rotary shaft", "rotating shaft", "drive shaft"],
    "Sanitary_Vacuum_Tanks": ["sanitary tank", "vacuum tank vessel", "stainless tank"],
    "Screws": ["machine screw", "fastener screw", "precision screw"],
    "Sensors": ["sensor device", "proximity sensor", "industrial sensor"],
    "Set_Collars": ["set collar", "shaft collar", "clamping collar ring"],
    "Shafts": ["precision shaft", "machine shaft", "drive shaft"],
    "Simplified_Adjustment_Units": ["adjustment unit", "positioning adjustment mechanism"],
    "Slide_Rails": ["slide rail", "drawer slide rail", "linear slide"],
    "Slide_Screws": ["slide screw", "lead screw assembly"],
    "Springs": ["compression spring", "mechanical spring", "coil spring"],
    "Sprockets_and_Chains": ["sprocket wheel", "chain drive sprocket", "roller chain"],
    "Stages": ["positioning stage", "XY stage", "linear stage platform"],
    "Timing_Pulleys": ["timing belt pulley", "synchronous pulley", "toothed pulley"],
    "Urethanes": ["urethane component", "polyurethane part", "urethane rubber"],
    "Washers": ["flat washer", "spring washer", "lock washer"],
    # Bearing 유닛
    "bearing_UCP": ["UCP pillow block bearing", "UCP pedestal bearing unit"],
    "bearing_UKP": ["UKP pillow block bearing", "UKP adapter sleeve bearing"],
    "bearing_UCF": ["UCF square flange bearing", "UCF 4-bolt flange bearing"],
    "bearing_UCFL": ["UCFL two-bolt flange bearing", "UCFL oval flange bearing"],
    "bearing_UKFL": ["UKFL two-bolt flange bearing", "UKFL oval flange adapter"],
    "bearing_UCFC": ["UCFC piloted flange bearing", "UCFC round cartridge bearing"],
    "bearing_UKFC": ["UKFC piloted flange bearing", "UKFC round cartridge adapter"],
    "bearing_UCFS": ["UCFS piloted flange bearing", "UCFS square cartridge bearing"],
    "bearing_UKFS": ["UKFS piloted flange bearing", "UKFS square cartridge adapter"],
    "bearing_UCT": ["UCT take-up bearing", "UCT sliding block bearing"],
    "bearing_UKT": ["UKT take-up bearing", "UKT sliding block adapter"],
    "bearing_SN플러머블록": ["SN plummer block bearing", "SN split bearing housing"],
    "bearing_TAKEUP": ["take-up bearing unit", "conveyor take-up bearing"],
    "bearing_H_ADAPTER": ["H adapter sleeve", "bearing adapter sleeve"],
    # 신규 카테고리
    "Wheels": ["wheel rim", "vehicle wheel", "automotive wheel"],
    "Tires": ["tire cross-section", "rubber tire", "vehicle tire"],
    "Suspension": ["suspension system", "vehicle suspension assembly", "shock absorber"],
    "Brakes": ["brake assembly", "disc brake system", "brake caliper"],
    "Powertrain": ["powertrain component", "transmission system", "drivetrain assembly"],
    "Clutches": ["clutch mechanism", "friction clutch assembly", "clutch plate"],
    "Pistons": ["engine piston", "piston assembly", "cylinder piston"],
    "Differential": ["differential gear", "differential mechanism", "axle differential"],
    "Bolts_and_Nuts": ["bolt and nut", "hex bolt fastener", "threaded fastener"],
    "Flanges": ["pipe flange", "flange connection", "mounting flange"],
    "Housing": ["mechanical housing", "bearing housing", "gear housing enclosure"],
    "Airbag_Module": ["airbag module", "airbag inflator assembly", "vehicle airbag unit"],
}

# CLIP 학습용 텍스트 템플릿
TEXT_TEMPLATES = [
    "a technical drawing of {}",
    "an engineering drawing of {}",
    "a CAD blueprint showing {}",
    "a mechanical drawing of {}",
    "a 2D technical illustration of {}",
    "engineering blueprint of {}",
    "industrial drawing showing {}",
    "technical specification drawing of {}",
]


def collect_images_from_dir(base_dir: Path, dir_map: dict) -> dict:
    """디렉토리 구조에서 이미지 수집"""
    category_images = defaultdict(list)
    if not base_dir.exists():
        print(f"  Warning: directory not found: {base_dir}")
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


def generate_caption(category: str, seed_val: int) -> str:
    """카테고리에 대한 텍스트 캡션 생성 (랜덤 템플릿 + 랜덤 설명)"""
    rng = random.Random(seed_val)

    descriptions = CATEGORY_DESCRIPTIONS.get(category)
    if not descriptions:
        # fallback: 카테고리 이름을 공백으로 변환
        desc = category.replace("_", " ").lower()
    else:
        desc = rng.choice(descriptions)

    template = rng.choice(TEXT_TEMPLATES)
    return template.format(desc)


def split_train_val(images: list, val_ratio: float, seed: int) -> tuple:
    """train/val 분할"""
    random.seed(seed)
    shuffled = images.copy()
    random.shuffle(shuffled)
    val_count = max(1, int(len(shuffled) * val_ratio))
    if val_count >= len(shuffled):
        val_count = max(0, len(shuffled) - 1)
    return shuffled[val_count:], shuffled[:val_count]


def main():
    print("=" * 60)
    print("  Step 5-A: CLIP Fine-tuning Dataset")
    print(f"  Val ratio: {VAL_RATIO*100:.0f}%")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)

    # === 1. 이미지 수집 ===
    print("\n[1/4] Collecting images...")

    misumi_images = collect_images_from_dir(MISUMI_PNG_DIR, MISUMI_DIR_MAP)
    misumi_total = sum(len(v) for v in misumi_images.values())
    print(f"  MiSUMi: {len(misumi_images)} categories, {misumi_total} images")

    bearing_images = collect_images_from_dir(BEARING_PNG_DIR, BEARING_DIR_MAP)
    bearing_total = sum(len(v) for v in bearing_images.values())
    print(f"  Bearing: {len(bearing_images)} categories, {bearing_total} images")

    staged_images = collect_staged_images()
    staged_total = sum(len(v) for v in staged_images.values())
    print(f"  Staged: {len(staged_images)} categories, {staged_total} images")

    # === 2. 통합 ===
    print("\n[2/4] Merging categories...")
    all_images = defaultdict(list)
    for cat, imgs in misumi_images.items():
        all_images[cat].extend(imgs)
    for cat, imgs in bearing_images.items():
        all_images[cat].extend(imgs)
    for cat, imgs in staged_images.items():
        all_images[cat].extend(imgs)

    total_categories = len(all_images)
    total_images = sum(len(v) for v in all_images.values())
    print(f"  Merged: {total_categories} categories, {total_images} images")

    # === 3. Train/Val 분할 + CSV 생성 ===
    print("\n[3/4] Creating train/val CSV files...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    train_csv = OUTPUT_DIR / "train.csv"
    val_csv = OUTPUT_DIR / "val.csv"

    stats = {}
    total_train_pairs = 0
    total_val_pairs = 0

    train_rows = []
    val_rows = []

    for cat_name in sorted(all_images.keys()):
        imgs = all_images[cat_name]
        train_imgs, val_imgs = split_train_val(imgs, VAL_RATIO, RANDOM_SEED)

        # 각 이미지에 대해 caption 생성
        for i, img_path in enumerate(train_imgs):
            caption = generate_caption(cat_name, RANDOM_SEED + hash(img_path) % 100000)
            train_rows.append((img_path, caption, cat_name))

        for i, img_path in enumerate(val_imgs):
            caption = generate_caption(cat_name, RANDOM_SEED + hash(img_path) % 100000)
            val_rows.append((img_path, caption, cat_name))

        stats[cat_name] = {
            "train": len(train_imgs),
            "val": len(val_imgs),
            "total": len(imgs),
        }
        total_train_pairs += len(train_imgs)
        total_val_pairs += len(val_imgs)

        print(f"  {cat_name:35s}: {len(imgs):>5d} (train {len(train_imgs):>5d} / val {len(val_imgs):>4d})")

    # CSV 파일 쓰기
    random.seed(RANDOM_SEED)
    random.shuffle(train_rows)
    random.shuffle(val_rows)

    with open(train_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["filepath", "caption", "category"])
        writer.writerows(train_rows)

    with open(val_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["filepath", "caption", "category"])
        writer.writerows(val_rows)

    # === 4. 설정 및 통계 파일 생성 ===
    print("\n[4/4] Writing config and stats...")

    # 학습 설정
    config = {
        "model": "ViT-B/32",
        "pretrained": "openai",
        "embedding_dim": 512,
        "batch_size": 64,
        "epochs": 30,
        "lr": 1e-5,
        "warmup_steps": 500,
        "weight_decay": 0.1,
        "precision": "amp",
        "lock_image_tower_epochs": 5,
        "dataset": {
            "train_csv": str(train_csv),
            "val_csv": str(val_csv),
            "total_train": total_train_pairs,
            "total_val": total_val_pairs,
        },
        "notes": [
            "Fine-tune OpenAI CLIP ViT-B/32 for engineering drawing classification",
            "Image tower locked for first 5 epochs (warm up text encoder first)",
            "Low learning rate to preserve pre-trained knowledge",
            "AMP (mixed precision) for M4 Pro MPS acceleration",
        ],
    }

    config_path = OUTPUT_DIR / "dataset_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # 통계
    dataset_stats = {
        "creation_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_classes": total_categories,
        "total_train_pairs": total_train_pairs,
        "total_val_pairs": total_val_pairs,
        "total_images": total_images,
        "val_ratio": VAL_RATIO,
        "text_templates": len(TEXT_TEMPLATES),
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

    # 카테고리 이름 복사
    import shutil
    shutil.copy2(CLASS_NAMES_FILE, OUTPUT_DIR / "class_names.json")

    # === 최종 요약 ===
    print(f"\n{'='*60}")
    print("  CLIP Fine-tuning Dataset Ready")
    print(f"{'='*60}")
    print(f"  Categories: {total_categories}")
    print(f"  Train pairs: {total_train_pairs}")
    print(f"  Val pairs:   {total_val_pairs}")
    print(f"  Total:       {total_images}")
    print(f"\n  Output:  {OUTPUT_DIR}")
    print(f"  Train:   {train_csv}")
    print(f"  Val:     {val_csv}")
    print(f"  Config:  {config_path}")

    # 샘플 출력
    print(f"\n  Sample train pairs:")
    for row in train_rows[:5]:
        fname = Path(row[0]).name
        print(f"    {fname:40s} -> {row[1]}")


if __name__ == "__main__":
    main()
