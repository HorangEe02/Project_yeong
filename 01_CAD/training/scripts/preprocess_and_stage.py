#!/usr/bin/env python3
"""
Step 4: 전처리 파이프라인
- 카테고리 매핑 기반 이미지 정리
- 대형 이미지 리사이즈 (최대 2000px)
- Kaggle Airbag 언더샘플링
- ChromaDB 등록 및 YOLO-cls 학습용 스테이징 디렉토리 생성
"""

import os
import json
import random
import shutil
import time
from pathlib import Path
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# === 설정 ===
BASE_DIR = Path("<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/drawing-datasets")
STAGED_DIR = BASE_DIR / "staged"  # 전처리 완료 이미지 출력
QUALITY_DIR = BASE_DIR / "quality_report"

MAX_DIMENSION = 2000  # 최대 해상도 (긴 변 기준)
AIRBAG_SAMPLE_SIZE = 1000  # Airbag 언더샘플링 수
RANDOM_SEED = 42

# 매핑 파일 로드
MAPPING_FILE = BASE_DIR / "category_mapping.json"

# 스킵할 카테고리 (소량으로 학습 효과 없음)
SKIP_CATEGORIES = {"Turbocharger"}  # 2장뿐


def load_valid_images(source_key: str) -> set:
    """Step 1에서 생성한 유효 이미지 목록 로드"""
    list_file = QUALITY_DIR / f"valid_{source_key}.txt"
    if not list_file.exists():
        return set()
    with open(list_file, 'r') as f:
        return {line.strip() for line in f if line.strip()}


def resize_if_needed(img: Image.Image, max_dim: int) -> Image.Image:
    """긴 변이 max_dim 초과 시 비율 유지하며 리사이즈"""
    w, h = img.size
    if max(w, h) <= max_dim:
        return img

    if w >= h:
        new_w = max_dim
        new_h = int(h * max_dim / w)
    else:
        new_h = max_dim
        new_w = int(w * max_dim / h)

    return img.resize((new_w, new_h), Image.LANCZOS)


def process_and_copy(src_path: str, dst_path: str, max_dim: int) -> bool:
    """이미지 리사이즈 후 PNG로 저장"""
    try:
        with Image.open(src_path) as img:
            img = img.convert("RGB")
            img = resize_if_needed(img, max_dim)
            img.save(dst_path, "PNG", optimize=True)
        return True
    except Exception as e:
        print(f"    ✗ 처리 실패: {os.path.basename(src_path)} - {e}")
        return False


def process_source(source_key: str, source_mappings: dict, valid_images: set) -> dict:
    """하나의 데이터 소스 전처리"""
    stats = {"processed": 0, "skipped": 0, "failed": 0, "categories": {}}

    if not source_mappings.get("mappings"):
        print(f"  → 매핑 없음 (스킵)")
        return stats

    for src_cat, mapping in source_mappings["mappings"].items():
        target = mapping["target"]
        target_id = mapping["target_id"]

        if target in SKIP_CATEGORIES:
            print(f"  → {src_cat} → {target}: 스킵 (소량 카테고리)")
            stats["skipped"] += mapping.get("images", 0)
            continue

        # 출력 디렉토리 생성
        cat_dir = STAGED_DIR / target
        cat_dir.mkdir(parents=True, exist_ok=True)

        # 해당 소스-카테고리의 유효 이미지 필터링
        matching_images = []
        for img_path in valid_images:
            # 경로에 소스 카테고리 이름이 포함되는지 확인
            path_parts = Path(img_path).parts
            if src_cat in path_parts:
                matching_images.append(img_path)

        # 소스 카테고리가 디렉토리 이름과 다른 경우 (airbag 등)
        if not matching_images and src_cat == "60k_png_1200x900":
            matching_images = list(valid_images)  # 전부 사용 후 샘플링

        if not matching_images:
            print(f"  → {src_cat}: 이미지 없음")
            continue

        # Airbag 언더샘플링
        if source_key == "kaggle_airbag":
            random.seed(RANDOM_SEED)
            matching_images = random.sample(matching_images, min(AIRBAG_SAMPLE_SIZE, len(matching_images)))
            print(f"  → {src_cat} → {target}: {len(matching_images)}장 (언더샘플링)")
        else:
            print(f"  → {src_cat} → {target}: {len(matching_images)}장")

        cat_processed = 0
        for img_path in matching_images:
            src_name = Path(img_path).stem
            # 출력 파일명: {source}_{원본이름}.png
            dst_name = f"{source_key}_{src_name}.png"
            dst_path = str(cat_dir / dst_name)

            if os.path.exists(dst_path):
                cat_processed += 1
                continue

            if process_and_copy(img_path, dst_path, MAX_DIMENSION):
                cat_processed += 1
            else:
                stats["failed"] += 1

        stats["processed"] += cat_processed
        stats["categories"][target] = stats["categories"].get(target, 0) + cat_processed

    return stats


def main():
    print("=" * 60)
    print("  Step 4: 전처리 파이프라인 (D→B→A 공용)")
    print(f"  최대 해상도: {MAX_DIMENSION}px")
    print(f"  Airbag 샘플링: {AIRBAG_SAMPLE_SIZE}장")
    print(f"  출력: {STAGED_DIR}")
    print("=" * 60)

    # 매핑 파일 로드
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)

    source_mappings = mapping_data["source_mappings"]

    # 스테이징 디렉토리 생성
    STAGED_DIR.mkdir(exist_ok=True)

    grand_stats = {"total_processed": 0, "total_skipped": 0, "total_failed": 0}
    all_category_counts = {}

    # 소스별 처리 (D 경로에서 사용할 라벨링된 소스만)
    labeled_sources = [
        "uspto_ppubs", "google_patents", "grabcad",
        "kaggle_airbag",
        "synthetic_basic", "synthetic_enhanced"
    ]

    for source_key in labeled_sources:
        if source_key not in source_mappings:
            continue

        src_cfg = source_mappings[source_key]
        print(f"\n{'='*60}")
        print(f"처리 중: {src_cfg.get('description', source_key)}")

        # 유효 이미지 목록 로드
        valid_images = load_valid_images(source_key)
        print(f"  유효 이미지: {len(valid_images)}장")

        if not valid_images:
            print(f"  ⚠ 유효 이미지 목록 없음")
            continue

        stats = process_source(source_key, src_cfg, valid_images)

        grand_stats["total_processed"] += stats["processed"]
        grand_stats["total_skipped"] += stats["skipped"]
        grand_stats["total_failed"] += stats["failed"]

        for cat, cnt in stats["categories"].items():
            all_category_counts[cat] = all_category_counts.get(cat, 0) + cnt

    # === 최종 요약 ===
    print(f"\n{'='*60}")
    print("  전처리 완료 요약")
    print(f"{'='*60}")
    print(f"  처리 완료: {grand_stats['total_processed']}장")
    print(f"  스킵: {grand_stats['total_skipped']}장")
    print(f"  실패: {grand_stats['total_failed']}장")
    print(f"\n  카테고리별 이미지 수:")

    for cat, cnt in sorted(all_category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {cat:30s}: {cnt:>5d}장")

    # 결과 저장
    result = {
        "preprocess_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "staged_dir": str(STAGED_DIR),
        "max_dimension": MAX_DIMENSION,
        "airbag_sample_size": AIRBAG_SAMPLE_SIZE,
        "stats": grand_stats,
        "category_counts": all_category_counts,
        "total_categories": len(all_category_counts),
    }

    result_path = STAGED_DIR / "preprocess_result.json"
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  결과 저장: {result_path}")

    return result


if __name__ == "__main__":
    main()
