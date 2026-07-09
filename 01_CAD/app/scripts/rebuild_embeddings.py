#!/usr/bin/env python3
"""
ChromaDB 전체 재임베딩 스크립트

Phase 2 (CLIP 512→768-dim) + Phase 3 (GNN) + Phase 4 (DXF) 반영.
기존 records.json의 68,647건을 새 임베딩으로 재생성한다.

작업:
  1. ChromaDB 3개 컬렉션 초기화 (image, text, gnn)
  2. CLIP ViT-L/14 (768-dim) 이미지 임베딩 재생성
  3. E5 텍스트 임베딩 재생성 (카테고리 키워드 보강)
  4. GNN 임베딩 생성 (DXF 보유 도면만, GNN 모델 있을 때)

사용법:
  python scripts/rebuild_embeddings.py
  python scripts/rebuild_embeddings.py --reset             # 컬렉션 초기화 후 재생성
  python scripts/rebuild_embeddings.py --skip-image        # 이미지 임베딩 스킵
  python scripts/rebuild_embeddings.py --gnn-model ./models/gnn_encoder.pt

진행 상태:
  progress.json에 마지막 처리 인덱스를 저장하여 중단 시 이어서 재개 가능.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def build_rich_text(
    ocr_text: str, category: str, category_keywords: dict[str, str]
) -> str:
    """임베딩용 보강 텍스트 (pipeline._build_rich_text 동일 로직)"""
    parts: list[str] = []
    if ocr_text:
        parts.append(ocr_text[:500])
    if category:
        parts.append(category.replace("_", " "))
    kw = category_keywords.get(category, "")
    if kw:
        parts.append(kw)
    return " ".join(parts).strip()


def main():
    parser = argparse.ArgumentParser(
        description="ChromaDB 전체 재임베딩 (CLIP 768-dim + E5 + GNN)",
    )
    parser.add_argument("--data", default="./data/vector_store", help="벡터 스토어 디렉토리")
    parser.add_argument("--keywords", default="./data/category_keywords.json", help="카테고리 키워드 JSON")
    parser.add_argument("--batch-size", type=int, default=32, help="임베딩 배치 크기")
    parser.add_argument("--reset", action="store_true", help="기존 컬렉션 삭제 후 재생성")
    parser.add_argument("--skip-image", action="store_true", help="이미지 임베딩 스킵")
    parser.add_argument("--skip-text", action="store_true", help="텍스트 임베딩 스킵")
    parser.add_argument("--gnn-model", default="", help="GNN 모델 경로 (비어있으면 GNN 스킵)")
    parser.add_argument("--gnn-k-neighbors", type=int, default=8)
    parser.add_argument("--clip-model", default="ViT-L-14", help="OpenCLIP 모델")
    parser.add_argument("--clip-pretrained", default="datacomp_xl_s13b_b90k")
    parser.add_argument("--clip-finetuned", default="", help="Fine-tuned CLIP 체크포인트")
    parser.add_argument(
        "--remap-from", default="<EXTERNAL_DRIVE>/00_work_out/02_ing/CAD/data/",
        help="파일 경로 치환 원본 접두사",
    )
    parser.add_argument(
        "--remap-to", default="<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD/data/",
        help="파일 경로 치환 대상 접두사",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("  ChromaDB 전체 재임베딩")
    print("  CLIP ViT-L/14 (768-dim) + E5 + GNN")
    print("=" * 65)

    # ── 1. records.json 로드 ──
    records_path = Path(args.data) / "records.json"
    if not records_path.exists():
        print(f"[ERROR] records.json 없음: {records_path}")
        sys.exit(1)

    with open(records_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    drawing_ids = list(records.keys())
    total = len(drawing_ids)
    print(f"\n  레코드 수: {total:,}건")

    # ── 2. 카테고리 키워드 로드 ──
    category_keywords: dict[str, str] = {}
    kw_path = Path(args.keywords)
    if kw_path.exists():
        with open(kw_path, "r", encoding="utf-8") as f:
            kw_data = json.load(f)
        category_keywords = kw_data.get("keywords", {})
        print(f"  카테고리 키워드: {len(category_keywords)}개")

    # ── 3. 진행 상태 로드 ──
    progress_path = Path(args.data) / "rebuild_progress.json"
    start_idx = 0
    if progress_path.exists() and not args.reset:
        with open(progress_path, "r") as f:
            progress = json.load(f)
        start_idx = progress.get("last_index", 0) + 1
        if start_idx >= total:
            print(f"\n  이미 완료됨 ({start_idx}/{total}). --reset으로 재시작하세요.")
            return
        print(f"  이전 진행 이어서 시작: {start_idx}/{total}")

    # ── 4. 모델 로딩 ──
    from core.vector_store import VectorStore

    if args.reset:
        print("\n  [RESET] 기존 컬렉션 삭제 중...")
        vs = VectorStore(persist_dir=args.data)
        vs.reset()
        print("  컬렉션 초기화 완료")
        # 재연결
        vs = VectorStore(persist_dir=args.data)
    else:
        vs = VectorStore(persist_dir=args.data)

    stats_before = vs.get_stats()
    print(f"  기존: image={stats_before['image_collection_count']:,}, "
          f"text={stats_before['text_collection_count']:,}, "
          f"gnn={stats_before['gnn_collection_count']:,}")

    # 이미지 임베더
    image_embedder = None
    if not args.skip_image:
        print(f"\n  CLIP 모델 로딩: {args.clip_model}...")
        from core.embeddings import ImageEmbedder
        image_embedder = ImageEmbedder(
            model_name=args.clip_model,
            pretrained=args.clip_pretrained,
            finetuned_path=args.clip_finetuned,
        )
        print("  CLIP 로딩 완료")

    # 텍스트 임베더
    text_embedder = None
    if not args.skip_text:
        print("  E5 모델 로딩...")
        from core.embeddings import TextEmbedder
        text_embedder = TextEmbedder()
        print("  E5 로딩 완료")

    # GNN 임베더
    gnn_embedder = None
    if args.gnn_model and Path(args.gnn_model).exists():
        print(f"  GNN 모델 로딩: {args.gnn_model}...")
        from core.gnn import GNNEmbedder
        gnn_embedder = GNNEmbedder(
            model_path=args.gnn_model,
            k_neighbors=args.gnn_k_neighbors,
        )
        print("  GNN 로딩 완료")

    # ── 5. 재임베딩 루프 ──
    print(f"\n  재임베딩 시작 (batch={args.batch_size}, from={start_idx})...")
    t_start = time.time()
    success = 0
    errors = 0
    gnn_count = 0

    for i in range(start_idx, total):
        did = drawing_ids[i]
        rdata = records[did]
        file_path = rdata.get("file_path", "")
        ocr_text = rdata.get("ocr_text", "")
        category = rdata.get("category", "")
        dxf_path = rdata.get("dxf_path", "")

        # 경로 리매핑
        if args.remap_from and file_path.startswith(args.remap_from):
            file_path = file_path.replace(args.remap_from, args.remap_to, 1)
        if args.remap_from and dxf_path and dxf_path.startswith(args.remap_from):
            dxf_path = dxf_path.replace(args.remap_from, args.remap_to, 1)

        meta = {
            "file_path": file_path,
            "file_name": rdata.get("file_name", ""),
            "category": category,
            "ocr_text": ocr_text[:500],
            "part_numbers": str(rdata.get("part_numbers", [])),
        }

        try:
            # 이미지 임베딩
            img_emb = None
            if image_embedder and file_path and Path(file_path).exists():
                img_emb = image_embedder.embed_image(file_path)

            # 텍스트 임베딩
            txt_emb = None
            if text_embedder:
                rich_text = build_rich_text(ocr_text, category, category_keywords)
                if rich_text:
                    txt_emb = text_embedder.embed_passage(rich_text)

            # GNN 임베딩
            gnn_emb = None
            if gnn_embedder and dxf_path and Path(dxf_path).exists():
                try:
                    gnn_emb = gnn_embedder.embed_dxf(dxf_path)
                    gnn_count += 1
                except Exception:
                    pass

            vs.add_drawing(
                drawing_id=did,
                image_embedding=img_emb,
                text_embedding=txt_emb,
                gnn_embedding=gnn_emb,
                metadata=meta,
            )
            success += 1

        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"    [ERROR] {did} ({rdata.get('file_name', '')}): {e}")

        # 진행 상태 저장 (100건마다)
        if (i + 1) % 100 == 0 or i == total - 1:
            elapsed = time.time() - t_start
            rate = (i - start_idx + 1) / elapsed if elapsed > 0 else 0
            remaining = (total - i - 1) / rate if rate > 0 else 0

            with open(progress_path, "w") as f:
                json.dump({"last_index": i, "total": total, "success": success, "errors": errors}, f)

            print(
                f"    [{i+1:,}/{total:,}] "
                f"성공={success:,} 실패={errors} GNN={gnn_count} | "
                f"{rate:.1f}건/초 | 남은시간: {remaining/3600:.1f}h"
            )

    elapsed = time.time() - t_start

    # ── 6. 결과 ──
    stats_after = vs.get_stats()
    print(f"\n{'=' * 65}")
    print(f"  재임베딩 완료")
    print(f"{'=' * 65}")
    print(f"  성공: {success:,}건 / 실패: {errors}건 / GNN: {gnn_count}건")
    print(f"  소요: {elapsed/3600:.1f}시간 ({success/elapsed:.1f}건/초)")
    print(f"  image: {stats_after['image_collection_count']:,}건")
    print(f"  text:  {stats_after['text_collection_count']:,}건")
    print(f"  gnn:   {stats_after['gnn_collection_count']:,}건")

    # 진행 파일 정리
    if progress_path.exists():
        progress_path.unlink()
    print(f"\n  완료!")


if __name__ == "__main__":
    main()
