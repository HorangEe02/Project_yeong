#!/usr/bin/env python3
"""
CLIP v2 캡션 풍부화 스크립트.

category_details.py의 alias + feature + application 조합으로
다양한 캡션을 생성하여 CLIP 학습 신호를 개선한다.

기존 CSV 파일을 읽어 v2 CSV로 변환:
  train.csv → train_v2.csv
  val.csv   → val_v2.csv
  test.csv  → test_v2.csv

사용법:
  python training/enrich_captions.py
  python training/enrich_captions.py --verify  # 통계만 출력

입력: preprocessed_dataset/{train,val,test}.csv
출력: preprocessed_dataset/{train,val,test}_v2.csv
"""

import csv
import random
import argparse
from pathlib import Path
from collections import Counter

# category_details.py에서 메타데이터 import
from category_details import CATEGORY_DETAILS, get_aliases, get_features, get_applications

BASE_DIR = Path("<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD")
DATASET_DIR = BASE_DIR / "drawing-datasets" / "preprocessed_dataset"

# === 캡션 템플릿 (16개) ===

# 기본 템플릿 (v1 호환, alias 사용)
BASIC_TEMPLATES = [
    "an engineering drawing of {noun}",
    "a technical drawing of {noun}",
    "a mechanical drawing of {noun}",
    "a 2D technical illustration of {noun}",
    "industrial drawing showing {noun}",
    "engineering blueprint of {noun}",
    "technical specification drawing of {noun}",
    "a CAD blueprint showing {noun}",
]

# Feature-aware 템플릿
FEATURE_TEMPLATES = [
    "engineering drawing of {noun} showing {feature} detail",
    "technical illustration of {noun} with {feature}",
    "dimensional drawing of {noun} highlighting {feature}",
]

# Application-aware 템플릿
APPLICATION_TEMPLATES = [
    "CAD drawing of {noun} for {application}",
    "{noun} engineering drawing used in {application}",
]

# Feature + Application 조합 템플릿
COMBINED_TEMPLATES = [
    "technical drawing of {noun} with {feature} for {application}",
    "engineering drawing of {noun} showing {feature} used in {application}",
    "detailed CAD illustration of {noun} with {feature}",
]


def generate_caption(category: str, rng: random.Random) -> str:
    """
    카테고리에 대해 다양한 캡션을 확률적으로 생성한다.

    분포:
    - 50%: 기본 템플릿 + 랜덤 alias
    - 25%: Feature-aware 템플릿
    - 15%: Application-aware 템플릿
    - 10%: Combined 템플릿

    Args:
        category: 카테고리명 (e.g., "Gears", "bearing_UCP")
        rng: 시드된 Random 인스턴스
    Returns:
        생성된 캡션 문자열
    """
    aliases = get_aliases(category)
    features = get_features(category)
    applications = get_applications(category)

    noun = rng.choice(aliases)
    roll = rng.random()

    if roll < 0.50:
        # 기본 템플릿
        template = rng.choice(BASIC_TEMPLATES)
        return template.format(noun=noun)
    elif roll < 0.75:
        # Feature-aware
        feature = rng.choice(features)
        template = rng.choice(FEATURE_TEMPLATES)
        return template.format(noun=noun, feature=feature)
    elif roll < 0.90:
        # Application-aware
        application = rng.choice(applications)
        template = rng.choice(APPLICATION_TEMPLATES)
        return template.format(noun=noun, application=application)
    else:
        # Combined
        feature = rng.choice(features)
        application = rng.choice(applications)
        template = rng.choice(COMBINED_TEMPLATES)
        return template.format(noun=noun, feature=feature, application=application)


def process_csv(csv_in: Path, csv_out: Path, rng: random.Random) -> dict:
    """
    CSV 파일의 캡션을 풍부화된 버전으로 교체한다.

    Args:
        csv_in: 입력 CSV 경로
        csv_out: 출력 CSV 경로
        rng: 시드된 Random 인스턴스
    Returns:
        통계 딕셔너리 {total, unique_captions, categories}
    """
    rows = []
    with open(csv_in, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    caption_set = set()
    cat_counter = Counter()

    with open(csv_out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['filepath', 'caption', 'category'])
        writer.writeheader()

        for row in rows:
            category = row['category']
            new_caption = generate_caption(category, rng)
            caption_set.add(new_caption)
            cat_counter[category] += 1

            writer.writerow({
                'filepath': row['filepath'],
                'caption': new_caption,
                'category': category,
            })

    return {
        'total': len(rows),
        'unique_captions': len(caption_set),
        'categories': len(cat_counter),
    }


def verify_captions(csv_path: Path):
    """CSV 파일의 캡션 통계를 출력한다."""
    captions = []
    categories = Counter()

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            captions.append(row['caption'])
            categories[row['category']] += 1

    unique = set(captions)
    cap_counter = Counter(captions)

    print(f"\n  File: {csv_path.name}")
    print(f"  Total samples: {len(captions)}")
    print(f"  Unique captions: {len(unique)}")
    print(f"  Uniqueness ratio: {len(unique)/len(captions)*100:.1f}%")
    print(f"  Categories: {len(categories)}")

    # 가장 빈번한 캡션 top 5
    print(f"\n  Most common captions:")
    for cap, count in cap_counter.most_common(5):
        print(f"    [{count:4d}x] {cap[:80]}")

    # 가장 적은 캡션 카테고리
    print(f"\n  Categories with fewest unique captions:")
    cat_unique = {}
    for row_cap, row_cat in zip(captions, []):
        pass  # need to rebuild

    # 카테고리별 고유 캡션 수
    cat_caps = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat = row['category']
            if cat not in cat_caps:
                cat_caps[cat] = set()
            cat_caps[cat].add(row['caption'])

    cat_unique_counts = {cat: len(caps) for cat, caps in cat_caps.items()}
    sorted_cats = sorted(cat_unique_counts.items(), key=lambda x: x[1])

    for cat, count in sorted_cats[:5]:
        print(f"    {cat}: {count} unique captions")

    print(f"\n  Caption diversity per category:")
    for cat, count in sorted_cats[-5:]:
        print(f"    {cat}: {count} unique captions (top)")


def main():
    parser = argparse.ArgumentParser(description='CLIP v2 Caption Enrichment')
    parser.add_argument('--verify', action='store_true',
                        help='Only verify existing v2 CSVs (no generation)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    parser.add_argument('--dataset-dir', type=str, default=str(DATASET_DIR),
                        help='Dataset directory')
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir)

    if args.verify:
        print("=" * 60)
        print("  Caption Verification")
        print("=" * 60)
        for split in ['train', 'val', 'test']:
            v1_path = dataset_dir / f"{split}.csv"
            v2_path = dataset_dir / f"{split}_v2.csv"

            if v1_path.exists():
                print(f"\n  --- v1 ({split}) ---")
                verify_captions(v1_path)

            if v2_path.exists():
                print(f"\n  --- v2 ({split}) ---")
                verify_captions(v2_path)
        return

    print("=" * 60)
    print("  CLIP v2 Caption Enrichment")
    print("=" * 60)
    print(f"  Dataset: {dataset_dir}")
    print(f"  Categories in details: {len(CATEGORY_DETAILS)}")
    print(f"  Seed: {args.seed}")

    rng = random.Random(args.seed)

    for split in ['train', 'val', 'test']:
        csv_in = dataset_dir / f"{split}.csv"
        csv_out = dataset_dir / f"{split}_v2.csv"

        if not csv_in.exists():
            print(f"\n  [SKIP] {csv_in} not found")
            continue

        print(f"\n  Processing {split}...")

        # v1 통계
        v1_captions = set()
        with open(csv_in, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                v1_captions.add(row['caption'])
        print(f"    v1 unique captions: {len(v1_captions)}")

        # v2 생성
        stats = process_csv(csv_in, csv_out, rng)
        print(f"    v2 unique captions: {stats['unique_captions']}")
        print(f"    Improvement: {stats['unique_captions']/len(v1_captions):.1f}x")
        print(f"    Output: {csv_out}")

    print(f"\n{'='*60}")
    print("  Caption enrichment complete!")
    print(f"{'='*60}")

    # 자동 검증
    print("\n  Running verification...")
    for split in ['train', 'val', 'test']:
        v2_path = dataset_dir / f"{split}_v2.csv"
        if v2_path.exists():
            verify_captions(v2_path)


if __name__ == '__main__':
    main()
