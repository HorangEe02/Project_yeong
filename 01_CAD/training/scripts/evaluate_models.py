#!/usr/bin/env python3
"""
Step 5-C: 모델 평가 스크립트
- YOLOv8-cls: test set top-1/top-5 accuracy
- CLIP: 검색 메트릭 (Recall@1/5/10, i2t + t2i)
- Fine-tuned vs Pre-trained CLIP 비교

사용법:
  python training/evaluate_models.py                              # 전체 평가
  python training/evaluate_models.py --yolo-only                  # YOLO만
  python training/evaluate_models.py --clip-only                  # CLIP만
  python training/evaluate_models.py --clip training/clip_runs/clip_best.pt
"""

import sys
import json
import time
import argparse
from pathlib import Path

import torch
import numpy as np
from PIL import Image

BASE_DIR = Path("<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD")
DATASET_DIR = BASE_DIR / "drawing-datasets" / "preprocessed_dataset"
CLIP_RUNS_DIR = BASE_DIR / "drawing-datasets" / "training" / "clip_runs"
CLIP_V2_RUNS_DIR = BASE_DIR / "drawing-datasets" / "training" / "clip_v2_runs"


def evaluate_yolo_cls(model_path: str, data_dir: str):
    """YOLOv8-cls test set 평가"""
    from ultralytics import YOLO

    print("\n" + "=" * 60)
    print("  YOLOv8-cls Test Set Evaluation")
    print("=" * 60)
    print(f"  Model: {model_path}")
    print(f"  Data:  {data_dir}")

    model = YOLO(model_path, task="classify")

    # Val set 평가
    print("\n  [Val Set]")
    val_results = model.val(data=data_dir, split="val", verbose=False)
    print(f"    Top-1 Accuracy: {val_results.top1:.4f}")
    print(f"    Top-5 Accuracy: {val_results.top5:.4f}")

    # Test set 평가
    print("\n  [Test Set]")
    test_results = model.val(data=data_dir, split="test", verbose=False)
    print(f"    Top-1 Accuracy: {test_results.top1:.4f}")
    print(f"    Top-5 Accuracy: {test_results.top5:.4f}")

    return {
        'model_path': str(model_path),
        'val': {
            'top1': round(val_results.top1, 5),
            'top5': round(val_results.top5, 5),
        },
        'test': {
            'top1': round(test_results.top1, 5),
            'top5': round(test_results.top5, 5),
        },
    }


def evaluate_clip_retrieval(model, preprocess, csv_path, device,
                            max_samples=2000, label=""):
    """CLIP 검색 메트릭 평가 (Recall@K)"""
    import clip
    import csv as csv_module

    print(f"\n  [{label}] Loading test data: {csv_path}")

    # CSV 로드
    data = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv_module.DictReader(f)
        for row in reader:
            data.append(row)

    # 샘플 제한
    if len(data) > max_samples:
        import random
        random.seed(42)
        data = random.sample(data, max_samples)
    print(f"  Evaluating on {len(data)} samples")

    # 임베딩 계산
    model.eval()
    all_img_features = []
    all_txt_features = []
    batch_size = 64

    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]

        # 이미지 배치
        images = []
        for row in batch:
            try:
                img = Image.open(row['filepath']).convert('RGB')
                images.append(preprocess(img))
            except Exception:
                images.append(preprocess(Image.new('RGB', (224, 224), (255, 255, 255))))

        image_tensor = torch.stack(images).to(device)

        # 텍스트 배치
        captions = [row['caption'] for row in batch]
        text_tokens = clip.tokenize(captions, truncate=True).to(device)

        with torch.no_grad():
            with torch.autocast(device_type=device.type, dtype=torch.float16):
                img_feat = model.encode_image(image_tensor)
                txt_feat = model.encode_text(text_tokens)

                img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
                txt_feat = txt_feat / txt_feat.norm(dim=-1, keepdim=True)

        all_img_features.append(img_feat.cpu().float())
        all_txt_features.append(txt_feat.cpu().float())

        if (i // batch_size + 1) % 10 == 0:
            print(f"    Batch {i//batch_size+1}/{(len(data)+batch_size-1)//batch_size}")

    all_img = torch.cat(all_img_features)
    all_txt = torch.cat(all_txt_features)

    # Similarity matrix (N x N)
    sim = all_img @ all_txt.t()
    n = len(sim)

    # Recall@K 계산
    def recall_at_k(similarity_matrix, k, direction='i2t'):
        """direction: 'i2t' (image→text) or 't2i' (text→image)"""
        if direction == 'i2t':
            # 각 이미지에 대해 올바른 텍스트의 순위
            rankings = similarity_matrix.argsort(dim=1, descending=True)
        else:
            # 각 텍스트에 대해 올바른 이미지의 순위
            rankings = similarity_matrix.t().argsort(dim=1, descending=True)

        correct = 0
        for i in range(len(rankings)):
            topk_indices = rankings[i, :k]
            if i in topk_indices:
                correct += 1

        return correct / len(rankings)

    metrics = {}
    for k in [1, 5, 10]:
        metrics[f'i2t_R@{k}'] = round(recall_at_k(sim, k, 'i2t'), 4)
        metrics[f't2i_R@{k}'] = round(recall_at_k(sim, k, 't2i'), 4)

    metrics['num_samples'] = n

    print(f"  [{label}] Results:")
    print(f"    Image→Text: R@1={metrics['i2t_R@1']:.3f}, R@5={metrics['i2t_R@5']:.3f}, R@10={metrics['i2t_R@10']:.3f}")
    print(f"    Text→Image: R@1={metrics['t2i_R@1']:.3f}, R@5={metrics['t2i_R@5']:.3f}, R@10={metrics['t2i_R@10']:.3f}")

    return metrics


def evaluate_clip_category_retrieval(model, preprocess, csv_path, device,
                                      max_samples=2000, label=""):
    """
    Category-aware CLIP 검색 메트릭 평가.

    Standard R@K + Category-aware R@K + Per-category breakdown.
    같은 카테고리에 속하는 결과도 correct로 간주.
    """
    import clip
    import csv as csv_module
    from collections import defaultdict

    print(f"\n  [{label}] Category-aware evaluation: {csv_path}")

    data = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv_module.DictReader(f)
        for row in reader:
            data.append(row)

    if len(data) > max_samples:
        import random
        random.seed(42)
        data = random.sample(data, max_samples)
    print(f"  Evaluating on {len(data)} samples")

    # 임베딩 계산
    model.eval()
    all_img_features = []
    all_txt_features = []
    categories = [row['category'] for row in data]
    batch_size = 64

    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]

        images = []
        for row in batch:
            try:
                img = Image.open(row['filepath']).convert('RGB')
                images.append(preprocess(img))
            except Exception:
                images.append(preprocess(Image.new('RGB', (224, 224), (255, 255, 255))))

        image_tensor = torch.stack(images).to(device)
        captions = [row['caption'] for row in batch]
        text_tokens = clip.tokenize(captions, truncate=True).to(device)

        with torch.no_grad():
            with torch.autocast(device_type=device.type, dtype=torch.float16):
                img_feat = model.encode_image(image_tensor)
                txt_feat = model.encode_text(text_tokens)
                img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
                txt_feat = txt_feat / txt_feat.norm(dim=-1, keepdim=True)

        all_img_features.append(img_feat.cpu().float())
        all_txt_features.append(txt_feat.cpu().float())

        if (i // batch_size + 1) % 10 == 0:
            print(f"    Batch {i // batch_size + 1}/"
                  f"{(len(data) + batch_size - 1) // batch_size}")

    all_img = torch.cat(all_img_features)
    all_txt = torch.cat(all_txt_features)
    sim = all_img @ all_txt.t()
    n = len(sim)

    metrics = {}

    for k in [1, 5, 10]:
        # Standard R@K
        i2t_topk = sim.topk(k, dim=1).indices
        i2t_correct = sum(1 for i in range(n) if i in i2t_topk[i])
        metrics[f'i2t_R@{k}'] = round(i2t_correct / n, 4)

        t2i_topk = sim.t().topk(k, dim=1).indices
        t2i_correct = sum(1 for i in range(n) if i in t2i_topk[i])
        metrics[f't2i_R@{k}'] = round(t2i_correct / n, 4)

        # Category-aware R@K
        i2t_cat_correct = 0
        for i in range(n):
            if any(categories[j] == categories[i] for j in i2t_topk[i].tolist()):
                i2t_cat_correct += 1
        metrics[f'i2t_catR@{k}'] = round(i2t_cat_correct / n, 4)

        t2i_cat_correct = 0
        for i in range(n):
            if any(categories[j] == categories[i] for j in t2i_topk[i].tolist()):
                t2i_cat_correct += 1
        metrics[f't2i_catR@{k}'] = round(t2i_cat_correct / n, 4)

    # Per-category R@5 breakdown
    per_cat = defaultdict(lambda: {'total': 0, 'correct': 0})
    i2t_topk5 = sim.topk(5, dim=1).indices
    for i in range(n):
        cat = categories[i]
        per_cat[cat]['total'] += 1
        if any(categories[j] == cat for j in i2t_topk5[i].tolist()):
            per_cat[cat]['correct'] += 1

    per_cat_r5 = {}
    for cat, vals in per_cat.items():
        per_cat_r5[cat] = round(vals['correct'] / vals['total'], 4) if vals['total'] > 0 else 0

    metrics['per_category_catR@5'] = per_cat_r5
    metrics['num_samples'] = n

    print(f"  [{label}] Results:")
    print(f"    Standard:  i2t_R@5={metrics['i2t_R@5']:.3f}, "
          f"t2i_R@5={metrics['t2i_R@5']:.3f}")
    print(f"    Category:  i2t_catR@5={metrics['i2t_catR@5']:.3f}, "
          f"t2i_catR@5={metrics['t2i_catR@5']:.3f}")

    # 상위/하위 5 카테고리
    sorted_cats = sorted(per_cat_r5.items(), key=lambda x: x[1])
    print(f"\n    Bottom 5 categories (catR@5):")
    for cat, val in sorted_cats[:5]:
        print(f"      {cat}: {val:.3f} ({per_cat[cat]['total']} samples)")
    print(f"    Top 5 categories (catR@5):")
    for cat, val in sorted_cats[-5:]:
        print(f"      {cat}: {val:.3f} ({per_cat[cat]['total']} samples)")

    return metrics


def evaluate_clip(checkpoint_path: str = None, test_csv: str = None,
                  max_samples: int = 2000):
    """CLIP 모델 평가: pre-trained vs fine-tuned 비교"""
    import clip

    print("\n" + "=" * 60)
    print("  CLIP Retrieval Evaluation")
    print("=" * 60)

    # Device
    if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = torch.device('mps')
    elif torch.cuda.is_available():
        device = torch.device('cuda')
    else:
        device = torch.device('cpu')
    print(f"  Device: {device}")

    if not test_csv:
        test_csv = str(DATASET_DIR / "test.csv")

    results = {}

    # === 1. Pre-trained CLIP (baseline) ===
    print("\n  Loading pre-trained CLIP ViT-B/32...")
    model_pretrained, preprocess = clip.load("ViT-B/32", device="cpu")
    model_pretrained = model_pretrained.float().to(device)

    results['pretrained'] = evaluate_clip_retrieval(
        model_pretrained, preprocess, test_csv, device,
        max_samples=max_samples, label="Pre-trained"
    )

    del model_pretrained
    if device.type == 'mps' and hasattr(torch.mps, 'empty_cache'):
        torch.mps.empty_cache()

    # === 2. Fine-tuned CLIP ===
    if checkpoint_path and Path(checkpoint_path).exists():
        print(f"\n  Loading fine-tuned CLIP: {checkpoint_path}")
        model_finetuned, preprocess = clip.load("ViT-B/32", device="cpu")
        model_finetuned = model_finetuned.float()

        state = torch.load(checkpoint_path, map_location='cpu')
        state_dict = state.get('model_state_dict', state)
        model_finetuned.load_state_dict(state_dict)
        model_finetuned = model_finetuned.to(device)

        results['finetuned'] = evaluate_clip_retrieval(
            model_finetuned, preprocess, test_csv, device,
            max_samples=max_samples, label="Fine-tuned"
        )

        del model_finetuned
        if device.type == 'mps' and hasattr(torch.mps, 'empty_cache'):
            torch.mps.empty_cache()

        # === 비교 ===
        print("\n  ---- Comparison ----")
        for metric in ['i2t_R@1', 'i2t_R@5', 'i2t_R@10', 't2i_R@1', 't2i_R@5', 't2i_R@10']:
            pre = results['pretrained'][metric]
            ft = results['finetuned'][metric]
            delta = ft - pre
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="
            print(f"    {metric:12s}: {pre:.3f} → {ft:.3f} ({arrow}{abs(delta):.3f})")

        results['improvement'] = {
            metric: round(results['finetuned'][metric] - results['pretrained'][metric], 4)
            for metric in ['i2t_R@1', 'i2t_R@5', 'i2t_R@10', 't2i_R@1', 't2i_R@5', 't2i_R@10']
        }
    else:
        if checkpoint_path:
            print(f"\n  [WARN] Fine-tuned checkpoint not found: {checkpoint_path}")
        print("  Skipping fine-tuned evaluation (no checkpoint)")

    return results


def main():
    parser = argparse.ArgumentParser(description='Model Evaluation')
    parser.add_argument('--yolo', type=str, default='',
                        help='YOLOv8-cls model path')
    parser.add_argument('--clip', type=str, default='',
                        help='Fine-tuned CLIP checkpoint path')
    parser.add_argument('--data', type=str, default=str(DATASET_DIR),
                        help='Dataset directory')
    parser.add_argument('--yolo-only', action='store_true',
                        help='YOLO 평가만 실행')
    parser.add_argument('--clip-only', action='store_true',
                        help='CLIP 평가만 실행')
    parser.add_argument('--max-samples', type=int, default=2000,
                        help='CLIP 평가 최대 샘플 수')
    parser.add_argument('--category-recall', action='store_true',
                        help='Category-aware R@K 평가 추가')
    args = parser.parse_args()

    print("=" * 65)
    print("  Step 5-C: Model Evaluation")
    print("=" * 65)

    all_results = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'dataset': args.data,
    }

    # === YOLO 평가 ===
    if not args.clip_only:
        yolo_path = args.yolo
        if not yolo_path:
            # 자동 탐색
            candidates = [
                BASE_DIR / "drawing-llm/runs/classify/train_v2_82cls/weights/best.pt",
                BASE_DIR / "drawing-llm/models/yolo_cls_best.pt",
            ]
            for c in candidates:
                if c.exists():
                    yolo_path = str(c)
                    break

        if yolo_path and Path(yolo_path).exists():
            all_results['yolo_cls'] = evaluate_yolo_cls(yolo_path, args.data)
        else:
            print("\n  [SKIP] YOLOv8-cls: model not found")

    # === CLIP 평가 ===
    if not args.yolo_only:
        clip_path = args.clip
        if not clip_path:
            # 자동 탐색 (v2 우선)
            candidates = [
                CLIP_V2_RUNS_DIR / "clip_v2_best_recall.pt",
                CLIP_V2_RUNS_DIR / "clip_v2_production.pt",
                CLIP_RUNS_DIR / "clip_best.pt",
                CLIP_RUNS_DIR / "clip_finetuned_production.pt",
            ]
            for c in candidates:
                if c.exists():
                    clip_path = str(c)
                    break

        test_csv = str(Path(args.data) / "test.csv")
        all_results['clip'] = evaluate_clip(
            checkpoint_path=clip_path,
            test_csv=test_csv,
            max_samples=args.max_samples,
        )

    # === 결과 저장 ===
    report_path = Path(args.data) / "evaluation_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*65}")
    print("  Evaluation Complete")
    print(f"{'='*65}")
    print(f"  Report: {report_path}")

    # 요약
    if 'yolo_cls' in all_results:
        y = all_results['yolo_cls']['test']
        print(f"\n  YOLOv8-cls Test: Top-1={y['top1']:.4f}, Top-5={y['top5']:.4f}")
        passed = y['top1'] >= 0.95 and y['top5'] >= 0.99
        print(f"  Target (≥95%/≥99%): {'✓ PASS' if passed else '✗ FAIL'}")

    if 'clip' in all_results and 'finetuned' in all_results['clip']:
        c = all_results['clip']['finetuned']
        print(f"\n  CLIP Fine-tuned: i2t_R@5={c['i2t_R@5']:.3f}, t2i_R@5={c['t2i_R@5']:.3f}")
        passed = c['i2t_R@5'] >= 0.50
        print(f"  Target (i2t_R@5≥50%): {'✓ PASS' if passed else '✗ FAIL'}")

    # === Category-aware 평가 (--category-recall) ===
    if args.category_recall and not args.yolo_only:
        import clip as clip_module

        print("\n" + "=" * 60)
        print("  Category-Aware Retrieval Evaluation")
        print("=" * 60)

        test_csv = str(Path(args.data) / "test.csv")

        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = torch.device('mps')
        elif torch.cuda.is_available():
            device = torch.device('cuda')
        else:
            device = torch.device('cpu')

        cat_results = {}

        if clip_path and Path(clip_path).exists():
            model_ft, preprocess = clip_module.load("ViT-B/32", device="cpu")
            model_ft = model_ft.float()
            state = torch.load(clip_path, map_location='cpu')
            state_dict = state.get('model_state_dict', state)
            model_ft.load_state_dict(state_dict)
            model_ft = model_ft.to(device)

            version = state.get('training_version', 'v1')
            cat_results['finetuned'] = evaluate_clip_category_retrieval(
                model_ft, preprocess, test_csv, device,
                max_samples=args.max_samples,
                label=f"Fine-tuned ({version})"
            )

            del model_ft
            if device.type == 'mps' and hasattr(torch.mps, 'empty_cache'):
                torch.mps.empty_cache()

        all_results['category_retrieval'] = cat_results

        # 최종 리포트 업데이트
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        if 'finetuned' in cat_results:
            cr = cat_results['finetuned']
            cat_r5 = (cr.get('i2t_catR@5', 0) + cr.get('t2i_catR@5', 0)) / 2
            print(f"\n  Category-aware avg catR@5: {cat_r5:.4f}")
            print(f"  Target (catR@5 ≥ 60%): "
                  f"{'✓ PASS' if cat_r5 >= 0.60 else '✗ FAIL'}")


if __name__ == '__main__':
    main()
