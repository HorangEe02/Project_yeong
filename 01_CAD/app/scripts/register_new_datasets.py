#!/usr/bin/env python3
"""
Step 5-D: 신규 데이터셋 ChromaDB 등록 확장 (최적화 버전)

최적화 적용:
  1. OCR fast_mode: mobile_det + 전처리 비활성화 (25x 빠름)
  2. 멀티프로세스 병렬화: 4 워커 (M4 Pro 12코어)
  3. 이미지별 진행 추적 (카테고리 중간 중단 시 재개 가능)

예상: ~2-3시간 (기존 36시간 → 12-18x 단축)
"""

import os
import sys
import json
import time
import multiprocessing as mp
from pathlib import Path
from collections import defaultdict

# PaddleOCR 모델 소스 체크 비활성화 (속도 향상)
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

# === 설정 ===
STAGED_DIR = Path("<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/data/staged")
PROGRESS_FILE = STAGED_DIR / "registration_progress.json"
NUM_WORKERS = 1     # 단일 프로세스 (records.json/ChromaDB 파일 경합 방지)
IMAGE_EXTS = {".png", ".jpg", ".jpeg"}

# DrawingPipeline 설정 (OCR fast_mode 활성화)
PIPELINE_CONFIG = {
    "upload_dir": str(PROJECT_ROOT / "data" / "sample_drawings"),
    "vector_store_dir": str(PROJECT_ROOT / "data" / "vector_store"),
    "ollama_url": "http://localhost:11434",
    "ollama_model": "qwen3-vl:8b",
    "clip_model": "ViT-B/32",
    "ocr_lang": "korean",
    "ocr_fast_mode": True,       # 전략 1+2: mobile_det + 전처리 비활성화
    "yolo_cls_model": "",        # 카테고리 수동 지정이므로 비활성
    "yolo_det_model": "",        # 탐지 비활성 (속도 우선)
}


# ─────────────────────────────────────────────
# 진행 관리 (파일 기반, 이미지 단위)
# ─────────────────────────────────────────────

def load_progress() -> dict:
    """진행 상태 로드 (재개 지원)"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        "completed_files": {},      # {category: [filename, ...]}
        "failed_files": [],
        "total_registered": 0,
    }


def save_progress(progress: dict):
    """진행 상태 저장"""
    tmp = PROGRESS_FILE.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    tmp.rename(PROGRESS_FILE)


def get_all_tasks(progress: dict) -> list[tuple[str, Path]]:
    """등록할 (category, image_path) 목록 반환 (이미 완료된 것 제외)"""
    tasks = []
    completed = progress.get("completed_files", {})

    for d in sorted(STAGED_DIR.iterdir()):
        if not d.is_dir():
            continue
        cat = d.name
        done_set = set(completed.get(cat, []))
        for f in sorted(d.iterdir()):
            if f.suffix.lower() in IMAGE_EXTS and f.name not in done_set:
                tasks.append((cat, f))
    return tasks


# ─────────────────────────────────────────────
# 워커 프로세스
# ─────────────────────────────────────────────

def worker_init():
    """각 워커 프로세스에서 파이프라인 초기화"""
    global _pipeline
    from core.pipeline import DrawingPipeline
    _pipeline = DrawingPipeline(**PIPELINE_CONFIG)


def worker_process(task: tuple[str, str]) -> dict:
    """단일 이미지 등록 (워커 프로세스 내에서 실행)"""
    category, img_path_str = task
    img_path = Path(img_path_str)
    result = {
        "category": category,
        "filename": img_path.name,
        "success": False,
        "error": "",
    }

    try:
        global _pipeline
        _pipeline.register_drawing(
            image_path=img_path_str,
            category=category,
            use_llm=False,
            copy_to_store=False,
        )
        result["success"] = True
    except Exception as e:
        result["error"] = str(e)[:200]

    return result


# ─────────────────────────────────────────────
# 단일 프로세스 폴백 (ChromaDB Lock 이슈 시)
# ─────────────────────────────────────────────

def run_single_process(tasks: list[tuple[str, Path]], progress: dict):
    """단일 프로세스 모드 (ChromaDB 동시 접근 문제 시 폴백)"""
    from core.pipeline import DrawingPipeline

    logger.info(f"  단일 프로세스 모드 (OCR fast_mode 활성)")
    pipeline = DrawingPipeline(**PIPELINE_CONFIG)

    total = len(tasks)
    registered = 0
    start = time.time()

    for i, (cat, img_path) in enumerate(tasks):
        try:
            pipeline.register_drawing(
                image_path=str(img_path),
                category=cat,
                use_llm=False,
                copy_to_store=False,
            )
            registered += 1

            # 진행 기록
            if cat not in progress["completed_files"]:
                progress["completed_files"][cat] = []
            progress["completed_files"][cat].append(img_path.name)
            progress["total_registered"] += 1

        except Exception as e:
            logger.error(f"  실패: {img_path.name} - {e}")
            progress["failed_files"].append({
                "category": cat,
                "file": str(img_path),
                "error": str(e)[:200],
            })

        # 50개마다 진행 저장 + 리포트
        if (i + 1) % 50 == 0:
            save_progress(progress)
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate
            logger.info(
                f"  [{i+1}/{total}] {rate:.2f} img/s | "
                f"성공: {registered} | 남은 시간: {eta/60:.1f}min"
            )

    save_progress(progress)
    return registered


# ─────────────────────────────────────────────
# 멀티프로세스 실행
# ─────────────────────────────────────────────

def run_multiprocess(tasks: list[tuple[str, Path]], progress: dict, num_workers: int):
    """멀티프로세스 병렬 등록"""
    logger.info(f"  멀티프로세스 모드: {num_workers} 워커 (OCR fast_mode 활성)")

    # (category, Path) → (category, str) 변환 (pickle 호환)
    task_args = [(cat, str(img_path)) for cat, img_path in tasks]

    total = len(task_args)
    registered = 0
    failed = 0
    start = time.time()

    try:
        with mp.Pool(processes=num_workers, initializer=worker_init) as pool:
            for i, result in enumerate(pool.imap_unordered(worker_process, task_args, chunksize=4)):
                cat = result["category"]
                fname = result["filename"]

                if result["success"]:
                    registered += 1
                    if cat not in progress["completed_files"]:
                        progress["completed_files"][cat] = []
                    progress["completed_files"][cat].append(fname)
                    progress["total_registered"] += 1
                else:
                    failed += 1
                    progress["failed_files"].append({
                        "category": cat,
                        "file": fname,
                        "error": result["error"],
                    })

                # 100개마다 진행 저장 + 리포트
                if (i + 1) % 100 == 0:
                    save_progress(progress)
                    elapsed = time.time() - start
                    rate = (i + 1) / elapsed
                    eta = (total - i - 1) / rate
                    logger.info(
                        f"  [{i+1}/{total}] {rate:.2f} img/s | "
                        f"성공: {registered} | 실패: {failed} | "
                        f"남은 시간: {eta/60:.1f}min"
                    )

    except Exception as e:
        logger.error(f"  멀티프로세스 오류: {e}")
        logger.info("  → 단일 프로세스 모드로 폴백합니다...")
        # 남은 작업 재계산
        remaining_tasks = get_all_tasks(progress)
        if remaining_tasks:
            additional = run_single_process(remaining_tasks, progress)
            registered += additional

    save_progress(progress)
    return registered


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("  Step 5-D: ChromaDB 등록 확장 (최적화)")
    logger.info(f"  스테이징: {STAGED_DIR}")
    logger.info(f"  워커: {NUM_WORKERS}개 | OCR: fast_mode")
    logger.info("=" * 60)

    # 진행 상태 로드
    progress = load_progress()
    if progress["total_registered"] > 0:
        logger.info(f"\n  이전 진행: {progress['total_registered']}장 등록 완료")

    # 미등록 작업 수집
    tasks = get_all_tasks(progress)
    total_remaining = len(tasks)

    if total_remaining == 0:
        logger.info("\n  모든 이미지 등록 완료!")
        return

    # 카테고리별 통계
    cat_counts = defaultdict(int)
    for cat, _ in tasks:
        cat_counts[cat] += 1
    logger.info(f"\n  남은 작업: {total_remaining}장 ({len(cat_counts)} 카테고리)")
    for cat, cnt in sorted(cat_counts.items()):
        logger.info(f"    {cat:30s}: {cnt:>5d}장")

    # 실행 모드 결정
    grand_start = time.time()

    if NUM_WORKERS > 1:
        # ChromaDB는 프로세스 간 공유 불가 → 각 워커가 독립 인스턴스
        # 주의: 대량 동시 쓰기 시 파일 잠금 이슈 가능
        try:
            grand_registered = run_multiprocess(tasks, progress, NUM_WORKERS)
        except Exception as e:
            logger.error(f"멀티프로세스 실패: {e}, 단일 프로세스로 전환")
            remaining = get_all_tasks(progress)
            grand_registered = run_single_process(remaining, progress)
    else:
        grand_registered = run_single_process(tasks, progress)

    grand_elapsed = time.time() - grand_start

    # === 최종 요약 ===
    logger.info("\n" + "=" * 60)
    logger.info("  등록 완료 요약")
    logger.info("=" * 60)
    logger.info(f"  이번 세션 등록: {grand_registered}장")
    logger.info(f"  누적 등록: {progress['total_registered']}장")
    logger.info(f"  실패: {len(progress['failed_files'])}건")
    logger.info(f"  소요 시간: {grand_elapsed:.1f}s ({grand_elapsed/60:.1f}min)")

    if grand_registered > 0 and grand_elapsed > 0:
        logger.info(f"  평균 속도: {grand_registered/grand_elapsed:.2f} img/s")

    progress["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
    progress["total_elapsed_seconds"] = grand_elapsed
    save_progress(progress)

    logger.info(f"\n  진행 저장: {PROGRESS_FILE}")


if __name__ == "__main__":
    main()
