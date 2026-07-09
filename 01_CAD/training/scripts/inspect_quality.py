#!/usr/bin/env python3
"""
Step 1: 데이터 품질 검수 스크립트
- 모든 데이터셋 소스에서 이미지 파일 스캔
- 이미지 유효성 검사 (PIL로 열 수 있는지)
- 크기 제한 필터링 (너무 큰 이미지 스킵)
- 소스별 통계 및 사용 가능 이미지 리스트 생성
"""

import os
import json
import sys
import time
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

# PIL import
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 큰 이미지도 열 수 있도록

# === 설정 ===
BASE_DIR = Path("<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/drawing-datasets")
OUTPUT_DIR = BASE_DIR / "quality_report"

# 크기 제한: 파일 크기 50MB 이상 또는 해상도 15000px 이상이면 "too_large"
MAX_FILE_SIZE_MB = 50
MAX_DIMENSION_PX = 15000

# 이미지 확장자
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp', '.gif'}

# 데이터셋 소스 정의
DATASET_SOURCES = {
    "uspto_ppubs": {
        "path": "patents/collected_drawings/uspto_ppubs",
        "description": "USPTO PPUBS 특허 도면",
        "expected": 3254,
    },
    "google_patents": {
        "path": "patents/collected_drawings/google_patents",
        "description": "Google Patents 도면",
        "expected": 510,
    },
    "grabcad": {
        "path": "grabcad/collected_images/grabcad",
        "description": "GrabCAD 커뮤니티 도면",
        "expected": 799,
    },
    "kaggle_airbag": {
        "path": "kaggle/collected_datasets/airbag-cad",
        "description": "Kaggle Airbag CAD Drawing",
        "expected": 60000,
    },
    "kaggle_2d": {
        "path": "kaggle/collected_datasets/two-dimensional-engineering-drawings",
        "description": "Kaggle 2D Engineering Drawings",
        "expected": 7,
    },
    "archive_org": {
        "path": "archive_org/extracted_drawings",
        "description": "미군 기술 매뉴얼 도면 (Archive.org)",
        "expected": 5825,
    },
    "synthetic_basic": {
        "path": "synthetic/generated_drawings",
        "description": "합성 도면 (기본)",
        "expected": 1000,
    },
    "synthetic_enhanced": {
        "path": "synthetic/enhanced_drawings",
        "description": "합성 도면 (향상된 버전)",
        "expected": 1332,
    },
    "google_images": {
        "path": "google_images/collected_images",
        "description": "Wikimedia Commons CC 이미지",
        "expected": 3,
    },
}


def find_images(directory: Path) -> list:
    """디렉토리에서 모든 이미지 파일 경로를 찾음"""
    images = []
    if not directory.exists():
        return images
    for root, dirs, files in os.walk(directory):
        # .DS_Store, __pycache__ 등 제외
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in files:
            if f.startswith('.'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in IMAGE_EXTS:
                images.append(os.path.join(root, f))
    return images


def inspect_single_image(filepath: str) -> dict:
    """단일 이미지 검사"""
    result = {
        "path": filepath,
        "filename": os.path.basename(filepath),
        "status": "unknown",
        "file_size_bytes": 0,
        "file_size_mb": 0.0,
        "width": 0,
        "height": 0,
        "format": "",
        "mode": "",
        "error": None,
        "category": "",  # 상위 디렉토리에서 추출
    }

    try:
        # 파일 크기 확인
        file_size = os.path.getsize(filepath)
        result["file_size_bytes"] = file_size
        result["file_size_mb"] = round(file_size / (1024 * 1024), 2)

        # 파일 크기 제한 체크
        if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            result["status"] = "too_large_filesize"
            result["error"] = f"File size {result['file_size_mb']}MB exceeds {MAX_FILE_SIZE_MB}MB limit"
            return result

        # PIL로 이미지 열기 (메타데이터만)
        with Image.open(filepath) as img:
            result["width"] = img.width
            result["height"] = img.height
            result["format"] = img.format or ""
            result["mode"] = img.mode

            # 해상도 제한 체크
            if img.width > MAX_DIMENSION_PX or img.height > MAX_DIMENSION_PX:
                result["status"] = "too_large_dimension"
                result["error"] = f"Dimension {img.width}x{img.height} exceeds {MAX_DIMENSION_PX}px limit"
                return result

            # 유효한 이미지 (실제 로드 시도)
            img.load()
            result["status"] = "valid"

    except (IOError, OSError, Image.DecompressionBombError) as e:
        result["status"] = "corrupted"
        result["error"] = str(e)[:200]
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:200]

    return result


def extract_category(filepath: str, source_key: str) -> str:
    """파일 경로에서 카테고리 추출"""
    parts = Path(filepath).parts
    source_cfg = DATASET_SOURCES.get(source_key, {})
    source_path = source_cfg.get("path", "")
    source_parts = Path(source_path).parts

    # source path 이후의 첫 번째 디렉토리를 카테고리로
    try:
        # 전체 경로에서 source_path에 해당하는 부분 이후를 찾음
        for i, part in enumerate(parts):
            if i + len(source_parts) <= len(parts):
                match = all(parts[i + j] == source_parts[j] for j in range(len(source_parts)))
                if match:
                    remaining = parts[i + len(source_parts):]
                    if len(remaining) >= 2:
                        return remaining[0]
                    elif len(remaining) == 1:
                        return ""  # 파일이 source 바로 아래에 있음
    except Exception:
        pass
    return ""


def inspect_source(source_key: str, source_cfg: dict) -> dict:
    """하나의 데이터셋 소스 전체 검수"""
    source_dir = BASE_DIR / source_cfg["path"]
    print(f"\n{'='*60}")
    print(f"검수 중: {source_cfg['description']} ({source_key})")
    print(f"경로: {source_dir}")

    if not source_dir.exists():
        print(f"  ⚠ 디렉토리 없음!")
        return {
            "source_key": source_key,
            "description": source_cfg["description"],
            "path": str(source_dir),
            "exists": False,
            "total_found": 0,
            "results": [],
        }

    # 이미지 파일 찾기
    image_files = find_images(source_dir)
    total = len(image_files)
    print(f"  발견된 이미지: {total}장 (예상: {source_cfg['expected']}장)")

    results = []
    stats = defaultdict(int)
    size_stats = {"min_mb": float('inf'), "max_mb": 0, "total_mb": 0}
    dim_stats = {"min_w": float('inf'), "max_w": 0, "min_h": float('inf'), "max_h": 0}
    category_counts = defaultdict(lambda: {"valid": 0, "invalid": 0, "total": 0})
    format_counts = defaultdict(int)

    start_time = time.time()

    for i, fpath in enumerate(image_files):
        if (i + 1) % 500 == 0 or i == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (total - i - 1) / rate if rate > 0 else 0
            print(f"  진행: {i+1}/{total} ({rate:.0f} img/s, ~{remaining:.0f}s 남음)")

        result = inspect_single_image(fpath)
        category = extract_category(fpath, source_key)
        result["category"] = category

        stats[result["status"]] += 1
        format_counts[result["format"]] += 1

        if result["file_size_mb"] > 0:
            size_stats["min_mb"] = min(size_stats["min_mb"], result["file_size_mb"])
            size_stats["max_mb"] = max(size_stats["max_mb"], result["file_size_mb"])
            size_stats["total_mb"] += result["file_size_mb"]

        if result["width"] > 0:
            dim_stats["min_w"] = min(dim_stats["min_w"], result["width"])
            dim_stats["max_w"] = max(dim_stats["max_w"], result["width"])
            dim_stats["min_h"] = min(dim_stats["min_h"], result["height"])
            dim_stats["max_h"] = max(dim_stats["max_h"], result["height"])

        cat_key = category if category else "(root)"
        category_counts[cat_key]["total"] += 1
        if result["status"] == "valid":
            category_counts[cat_key]["valid"] += 1
        else:
            category_counts[cat_key]["invalid"] += 1

        results.append(result)

    elapsed = time.time() - start_time

    # 통계 요약
    avg_mb = size_stats["total_mb"] / total if total > 0 else 0
    if size_stats["min_mb"] == float('inf'):
        size_stats["min_mb"] = 0
    if dim_stats["min_w"] == float('inf'):
        dim_stats["min_w"] = 0
    if dim_stats["min_h"] == float('inf'):
        dim_stats["min_h"] = 0

    summary = {
        "source_key": source_key,
        "description": source_cfg["description"],
        "path": str(source_dir),
        "exists": True,
        "total_found": total,
        "expected": source_cfg["expected"],
        "elapsed_seconds": round(elapsed, 1),
        "status_counts": dict(stats),
        "valid_count": stats.get("valid", 0),
        "usable_rate": round(stats.get("valid", 0) / total * 100, 1) if total > 0 else 0,
        "size_stats": {
            "min_mb": size_stats["min_mb"],
            "max_mb": size_stats["max_mb"],
            "avg_mb": round(avg_mb, 2),
            "total_mb": round(size_stats["total_mb"], 1),
        },
        "dimension_stats": {
            "min_width": dim_stats["min_w"],
            "max_width": dim_stats["max_w"],
            "min_height": dim_stats["min_h"],
            "max_height": dim_stats["max_h"],
        },
        "format_counts": dict(format_counts),
        "category_counts": {k: dict(v) for k, v in category_counts.items()},
    }

    # 유효하지 않은 이미지 목록
    invalid_files = [r for r in results if r["status"] != "valid"]
    summary["invalid_files_sample"] = invalid_files[:20]  # 최대 20개 샘플

    # 결과 출력
    print(f"\n  --- {source_cfg['description']} 결과 ---")
    print(f"  총 이미지: {total}장")
    print(f"  유효(valid): {stats.get('valid', 0)}장 ({summary['usable_rate']}%)")
    for status, count in stats.items():
        if status != "valid":
            print(f"  {status}: {count}장")
    print(f"  파일 크기: {size_stats['min_mb']:.2f}MB ~ {size_stats['max_mb']:.2f}MB (평균 {avg_mb:.2f}MB)")
    print(f"  해상도: {dim_stats['min_w']}x{dim_stats['min_h']} ~ {dim_stats['max_w']}x{dim_stats['max_h']}")
    print(f"  포맷: {dict(format_counts)}")
    if category_counts:
        print(f"  카테고리: {len(category_counts)}개")
        for cat, cnt in sorted(category_counts.items(), key=lambda x: x[1]['total'], reverse=True)[:10]:
            print(f"    {cat}: {cnt['total']}장 (유효 {cnt['valid']}장)")
    print(f"  소요 시간: {elapsed:.1f}초")

    return summary, results


def generate_usable_list(all_results: dict) -> dict:
    """사용 가능한 이미지 목록 생성"""
    usable = {}
    for source_key, (summary, results) in all_results.items():
        valid_paths = [r["path"] for r in results if r["status"] == "valid"]
        usable[source_key] = {
            "description": summary["description"],
            "count": len(valid_paths),
            "paths": valid_paths,
        }
    return usable


def main():
    print("=" * 60)
    print("  Drawing Datasets 품질 검수 시작")
    print(f"  기준 디렉토리: {BASE_DIR}")
    print(f"  파일 크기 제한: {MAX_FILE_SIZE_MB}MB")
    print(f"  해상도 제한: {MAX_DIMENSION_PX}px")
    print("=" * 60)

    # 출력 디렉토리 생성
    OUTPUT_DIR.mkdir(exist_ok=True)

    all_results = {}
    grand_total = 0
    grand_valid = 0
    grand_invalid = 0

    for source_key, source_cfg in DATASET_SOURCES.items():
        summary, results = inspect_source(source_key, source_cfg)
        all_results[source_key] = (summary, results)

        if summary.get("exists"):
            grand_total += summary["total_found"]
            grand_valid += summary.get("valid_count", 0)
            grand_invalid += summary["total_found"] - summary.get("valid_count", 0)

    # === 전체 요약 ===
    print("\n" + "=" * 60)
    print("  전체 검수 결과 요약")
    print("=" * 60)
    print(f"  총 이미지: {grand_total}장")
    print(f"  사용 가능(valid): {grand_valid}장 ({grand_valid/grand_total*100:.1f}%)" if grand_total > 0 else "")
    print(f"  사용 불가: {grand_invalid}장 ({grand_invalid/grand_total*100:.1f}%)" if grand_total > 0 else "")

    print("\n  소스별 요약:")
    for source_key, (summary, _) in all_results.items():
        if summary.get("exists"):
            status = f"✓ {summary['valid_count']}/{summary['total_found']}"
        else:
            status = "✗ 디렉토리 없음"
        print(f"    {source_key:25s}: {status} ({summary.get('usable_rate', 0)}%)")

    # === 결과 저장 ===

    # 1. 소스별 요약 JSON
    summaries = {}
    for source_key, (summary, _) in all_results.items():
        summaries[source_key] = summary

    summary_path = OUTPUT_DIR / "inspection_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  요약 저장: {summary_path}")

    # 2. 사용 가능 이미지 목록 (경로만)
    usable = generate_usable_list(all_results)

    # 경로 목록은 크기가 크므로, 경로 리스트를 소스별 별도 파일로 저장
    usable_summary = {}
    for source_key, data in usable.items():
        usable_summary[source_key] = {
            "description": data["description"],
            "count": data["count"],
        }
        # 소스별 유효 이미지 경로 목록 저장
        list_path = OUTPUT_DIR / f"valid_{source_key}.txt"
        with open(list_path, 'w', encoding='utf-8') as f:
            for p in data["paths"]:
                f.write(p + "\n")

    usable_path = OUTPUT_DIR / "usable_summary.json"
    with open(usable_path, 'w', encoding='utf-8') as f:
        json.dump(usable_summary, f, ensure_ascii=False, indent=2)
    print(f"  사용 가능 목록 저장: {usable_path}")

    # 3. 유효하지 않은 이미지 목록
    invalid_all = []
    for source_key, (_, results) in all_results.items():
        for r in results:
            if r["status"] != "valid":
                invalid_all.append({
                    "source": source_key,
                    "path": r["path"],
                    "status": r["status"],
                    "error": r["error"],
                    "file_size_mb": r["file_size_mb"],
                    "width": r["width"],
                    "height": r["height"],
                })

    invalid_path = OUTPUT_DIR / "invalid_images.json"
    with open(invalid_path, 'w', encoding='utf-8') as f:
        json.dump(invalid_all, f, ensure_ascii=False, indent=2, default=str)
    print(f"  유효하지 않은 이미지 목록 저장: {invalid_path}")
    print(f"  유효하지 않은 이미지 수: {len(invalid_all)}개")

    # 4. 전체 통계 JSON (간결한 보고서)
    report = {
        "inspection_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base_dir": str(BASE_DIR),
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "max_dimension_px": MAX_DIMENSION_PX,
        "grand_total": grand_total,
        "grand_valid": grand_valid,
        "grand_invalid": grand_invalid,
        "usable_rate_percent": round(grand_valid / grand_total * 100, 1) if grand_total > 0 else 0,
        "per_source": usable_summary,
    }

    report_path = OUTPUT_DIR / "quality_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  최종 리포트 저장: {report_path}")

    print("\n  검수 완료!")
    return report


if __name__ == "__main__":
    report = main()
