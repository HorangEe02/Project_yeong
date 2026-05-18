"""영양제 사진 한 장을 Google Cloud Vision OCR로 처리하는 데모.

Phase 01 종료 시 점검용 — 실제 Google Cloud Vision 자격증명이 있을 때 한 장의
영양제 라벨 이미지를 OCR로 처리하고 결과를 stdout에 출력한다.

사용:
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
    python scripts/ocr_demo.py path/to/supplement.jpg

전제:
    - ``GOOGLE_APPLICATION_CREDENTIALS`` 환경변수가 service account JSON 경로.
    - 입력 이미지는 JPEG/PNG, 가능한 한 라벨 영역만 크롭된 상태.

Reference:
    /Users/yeong/.claude/plans/lemon-track-b/phase-01-ocr-pipeline.md Step 9
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


async def run(image_path: Path) -> int:
    """이미지 한 장을 OCR로 처리하고 결과를 출력한다."""
    if not image_path.is_file():
        print(f"File not found: {image_path}", file=sys.stderr)
        return 1
    from src.ocr.google_vision import GoogleVisionOCR
    from src.ocr.pipeline import OCRPipeline

    data = image_path.read_bytes()
    pipeline = OCRPipeline(primary=GoogleVisionOCR())
    result = await pipeline.extract(data)
    print(f"engine     : {result.engine}")
    print(f"confidence : {result.confidence:.2f}")
    print(f"elapsed_ms : {result.elapsed_ms:.0f}")
    print(f"word_count : {len(result.words)}")
    print("--- text ---")
    print(result.text)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: python {sys.argv[0]} <image-path>", file=sys.stderr)
        return 2
    return asyncio.run(run(Path(sys.argv[1])))


if __name__ == "__main__":
    sys.exit(main())
