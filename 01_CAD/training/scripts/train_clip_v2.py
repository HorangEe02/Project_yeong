#!/usr/bin/env python3
"""
Step 6: CLIP v2 Fine-tuning — Improved Training

v1 대비 주요 개선:
1. Image tower 영구 동결 (v1: 5에폭 후 해동 → 오버피팅)
2. SupCon multi-positive loss (v1: InfoNCE diagonal-only → false negative 문제)
3. Category-balanced batch sampling (v1: random shuffle → 불균형)
4. 풍부화된 캡션 (v1: 1,652 → v2: 15,206 고유 캡션)
5. Category-aware R@5 기반 early stopping (v1: val_loss 기준)
6. 배치 크기 128 (v1: 64)

사용법:
  python training/train_clip_v2.py                           # 기본 설정
  python training/train_clip_v2.py --epochs 2 --log-every 5  # 테스트
  python training/train_clip_v2.py --resume clip_v2_runs/clip_v2_best_recall.pt

입력: preprocessed_dataset/{train,val,test}_v2.csv
출력: training/clip_v2_runs/clip_v2_best_recall.pt
"""

import os
import sys
import csv
import math
import json
import time
import random
import argparse
from pathlib import Path
from collections import defaultdict

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, Sampler
from PIL import Image

# macOS MPS 호환을 위한 spawn 방식
try:
    torch.multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass

BASE_DIR = Path("<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD")


# ============================================================
#  Dataset
# ============================================================

class CLIPDrawingDatasetV2(Dataset):
    """
    CLIP v2 데이터셋: (image_tensor, text_token, category_index) 반환.

    v1 대비 개선:
    - category_index 반환 (SupCon loss 용)
    - 캡션 사전 토큰화 (v1은 매 __getitem__마다 clip.tokenize 호출)
    """

    def __init__(self, csv_path, preprocess_fn):
        self.preprocess = preprocess_fn
        self.data = []
        self.categories = []
        self.cat_to_idx = {}
        self.cat_indices = []

        # CSV 로드
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.data.append(row)

        # 카테고리 매핑 구축
        cats = sorted(set(row['category'] for row in self.data))
        self.categories = cats
        self.cat_to_idx = {c: i for i, c in enumerate(cats)}
        self.cat_indices = [self.cat_to_idx[row['category']] for row in self.data]

        # 캡션 사전 토큰화 (배치 단위로 메모리 효율적)
        import clip
        all_captions = [row['caption'] for row in self.data]
        token_batches = []
        batch_size = 10000
        for i in range(0, len(all_captions), batch_size):
            batch = all_captions[i:i + batch_size]
            tokens = clip.tokenize(batch, truncate=True)
            token_batches.append(tokens)
        self.text_tokens = torch.cat(token_batches, dim=0)

        print(f"  Dataset: {len(self.data)} pairs, {len(cats)} categories")
        print(f"  Unique captions: {len(set(all_captions))}")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        row = self.data[idx]
        try:
            image = Image.open(row['filepath']).convert('RGB')
            image_tensor = self.preprocess(image)
        except Exception:
            image_tensor = self.preprocess(
                Image.new('RGB', (224, 224), (255, 255, 255))
            )

        text_token = self.text_tokens[idx]
        cat_idx = self.cat_indices[idx]

        return image_tensor, text_token, cat_idx


# ============================================================
#  Category-Balanced Batch Sampler
# ============================================================

class CategoryBalancedBatchSampler(Sampler):
    """
    각 배치에 K개 카테고리 × N개 샘플을 보장하는 배치 샘플러.

    SupCon loss에서 각 앵커에 최소 (N-1)개의 same-category positive를 보장.
    희소 카테고리는 with-replacement 샘플링.

    Args:
        cat_indices: list[int], 샘플별 카테고리 인덱스
        num_categories_per_batch (K): 배치당 카테고리 수 (기본: 32)
        num_samples_per_category (N): 카테고리당 샘플 수 (기본: 4)
    """

    def __init__(self, cat_indices, num_categories_per_batch=32,
                 num_samples_per_category=4):
        self.cat_indices = cat_indices
        self.K = num_categories_per_batch
        self.N = num_samples_per_category
        self.batch_size = self.K * self.N

        # 카테고리별 샘플 인덱스 구축
        self.cat_to_samples = defaultdict(list)
        for idx, cat in enumerate(cat_indices):
            self.cat_to_samples[cat].append(idx)

        self.all_cats = list(self.cat_to_samples.keys())
        self.num_samples = len(cat_indices)
        self.num_batches = self.num_samples // self.batch_size

        print(f"  Sampler: K={self.K} cats × N={self.N} samples = "
              f"batch {self.batch_size}, {self.num_batches} batches/epoch")

    def __iter__(self):
        # 에폭마다 각 카테고리의 샘플 풀 셔플
        pools = {}
        for cat in self.all_cats:
            pool = list(self.cat_to_samples[cat])
            random.shuffle(pool)
            pools[cat] = pool
        pool_ptrs = {cat: 0 for cat in self.all_cats}

        for _ in range(self.num_batches):
            # K개 카테고리 랜덤 선택
            if len(self.all_cats) >= self.K:
                batch_cats = random.sample(self.all_cats, self.K)
            else:
                batch_cats = random.choices(self.all_cats, k=self.K)

            batch_indices = []
            for cat in batch_cats:
                pool = pools[cat]
                ptr = pool_ptrs[cat]

                if len(pool) >= self.N:
                    # 풀에서 N개 순차 추출
                    if ptr + self.N > len(pool):
                        random.shuffle(pool)
                        ptr = 0
                    samples = pool[ptr:ptr + self.N]
                    pool_ptrs[cat] = ptr + self.N
                else:
                    # 희소 카테고리: with-replacement
                    samples = random.choices(pool, k=self.N)

                batch_indices.extend(samples)

            yield batch_indices

    def __len__(self):
        return self.num_batches


# ============================================================
#  SupCon CLIP Loss
# ============================================================

class SupConCLIPLoss(nn.Module):
    """
    Supervised Contrastive Loss for CLIP (multi-positive).

    같은 카테고리 쌍 = positive, 다른 카테고리 = negative.
    Same-category peer가 없는 orphan → standard InfoNCE fallback.

    양방향 대칭: image→text + text→image.
    """

    def forward(self, image_features, text_features, labels, logit_scale):
        """
        Args:
            image_features: [B, D] L2-normalized
            text_features:  [B, D] L2-normalized
            labels:         [B] integer category indices
            logit_scale:    scalar (exp of model.logit_scale)
        Returns:
            scalar loss
        """
        B = image_features.shape[0]
        device = image_features.device

        # Similarity matrices: [B, B]
        sim_i2t = logit_scale * image_features @ text_features.t()
        sim_t2i = sim_i2t.t()

        # Positive mask: 같은 카테고리
        pos_mask = (labels.unsqueeze(0) == labels.unsqueeze(1)).float()
        pos_mask.fill_diagonal_(0)  # 자기 자신 제외

        # Same-category peer 존재 여부
        has_positive = pos_mask.sum(dim=1) > 0  # [B]

        # 양방향 loss
        loss_i2t = self._direction_loss(sim_i2t, pos_mask, has_positive, B, device)
        loss_t2i = self._direction_loss(sim_t2i, pos_mask, has_positive, B, device)

        return (loss_i2t + loss_t2i) / 2.0

    def _direction_loss(self, sim_matrix, pos_mask, has_positive, B, device):
        """
        단일 방향 SupCon loss.

        SupCon (has_positive):
          L_i = -1/|P(i)| * sum_{p in P(i)} [s_ip - log(sum_j exp(s_ij))]

        InfoNCE fallback (orphan):
          L_i = -s_ii + log(sum_j exp(s_ij))
        """
        # 수치 안정성: max subtraction
        max_sim, _ = sim_matrix.max(dim=1, keepdim=True)
        sim_stable = sim_matrix - max_sim.detach()

        # log-sum-exp 분모
        log_sum_exp = torch.logsumexp(sim_stable, dim=1)  # [B]

        # log-probability: log(exp(s_ij) / sum_k exp(s_ik))
        log_prob = sim_stable - log_sum_exp.unsqueeze(1)  # [B, B]

        # SupCon: positive 위치의 log_prob 평균
        pos_counts = pos_mask.sum(dim=1).clamp(min=1)
        supcon_loss = -(pos_mask * log_prob).sum(dim=1) / pos_counts

        # InfoNCE fallback: diagonal
        diag = torch.diag(sim_stable)
        infonce_loss = -diag + log_sum_exp

        # 조합: peer가 있으면 SupCon, 없으면 InfoNCE
        loss = torch.where(has_positive, supcon_loss, infonce_loss)

        return loss.mean()


# ============================================================
#  Image Tower Control
# ============================================================

def set_image_tower_trainable(model, trainable: bool):
    """Visual encoder 동결/해동"""
    for param in model.visual.parameters():
        param.requires_grad = trainable

    n_params = sum(p.numel() for p in model.visual.parameters())
    status = "UNFROZEN" if trainable else "FROZEN"
    print(f"  Image tower {status}: {n_params / 1e6:.1f}M parameters")


# ============================================================
#  Training Loop
# ============================================================

def train_one_epoch(model, dataloader, optimizer, scaler, scheduler,
                    device, epoch, loss_fn, log_every=50):
    """1 에폭 학습 (v2: labels 포함)"""
    model.train()
    total_loss = 0.0
    num_batches = 0
    start_time = time.time()

    for batch_idx, (images, texts, labels) in enumerate(dataloader):
        images = images.to(device)
        texts = texts.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()

        with torch.autocast(device_type=device.type, dtype=torch.float16):
            image_features = model.encode_image(images)
            text_features = model.encode_text(texts)

            image_features = F.normalize(image_features, dim=-1)
            text_features = F.normalize(text_features, dim=-1)

            logit_scale = model.logit_scale.exp()
            loss = loss_fn(image_features, text_features, labels, logit_scale)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()

        # Logit scale 클램핑
        with torch.no_grad():
            model.logit_scale.clamp_(0, math.log(100))

        scheduler.step()
        total_loss += loss.item()
        num_batches += 1

        if (batch_idx + 1) % log_every == 0:
            elapsed = time.time() - start_time
            avg_loss = total_loss / num_batches
            lr_current = optimizer.param_groups[0]['lr']
            print(f"    [Epoch {epoch}] Batch {batch_idx + 1}/{len(dataloader)} | "
                  f"loss={avg_loss:.4f} | lr={lr_current:.2e} | "
                  f"logit_scale={model.logit_scale.item():.3f} | "
                  f"{elapsed:.0f}s")

    return total_loss / max(num_batches, 1)


# ============================================================
#  Validation
# ============================================================

@torch.no_grad()
def validate(model, dataloader, device, loss_fn, max_samples=2000):
    """
    Validation with:
    1. SupCon loss
    2. Standard R@K (diagonal match)
    3. Category-aware R@K (same category = correct)
    """
    model.eval()
    total_loss = 0.0
    num_batches = 0

    all_img_feats = []
    all_txt_feats = []
    all_labels = []

    for images, texts, labels in dataloader:
        images = images.to(device)
        texts = texts.to(device)
        labels_dev = labels.to(device)

        with torch.autocast(device_type=device.type, dtype=torch.float16):
            img_feat = model.encode_image(images)
            txt_feat = model.encode_text(texts)
            img_feat = F.normalize(img_feat, dim=-1)
            txt_feat = F.normalize(txt_feat, dim=-1)
            logit_scale = model.logit_scale.exp()
            loss = loss_fn(img_feat, txt_feat, labels_dev, logit_scale)

        total_loss += loss.item()
        num_batches += 1

        # Feature 수집 (max_samples까지)
        collected = sum(len(f) for f in all_img_feats)
        if collected < max_samples:
            all_img_feats.append(img_feat.cpu().float())
            all_txt_feats.append(txt_feat.cpu().float())
            all_labels.append(labels)

    avg_loss = total_loss / max(num_batches, 1)

    # 수집된 features 결합
    img_feats = torch.cat(all_img_feats)[:max_samples]
    txt_feats = torch.cat(all_txt_feats)[:max_samples]
    labels_all = torch.cat(all_labels)[:max_samples]
    n = len(img_feats)

    # Similarity matrix
    sim = img_feats @ txt_feats.t()

    metrics = {}
    for k in [1, 5, 10]:
        # --- Standard R@K (diagonal match) ---
        i2t_topk = sim.topk(k, dim=1).indices
        i2t_correct = sum(1 for i in range(n) if i in i2t_topk[i])
        metrics[f'i2t_R@{k}'] = round(i2t_correct / n, 4)

        t2i_topk = sim.t().topk(k, dim=1).indices
        t2i_correct = sum(1 for i in range(n) if i in t2i_topk[i])
        metrics[f't2i_R@{k}'] = round(t2i_correct / n, 4)

        # --- Category-aware R@K ---
        i2t_cat_correct = 0
        for i in range(n):
            if any(labels_all[j] == labels_all[i] for j in i2t_topk[i]):
                i2t_cat_correct += 1
        metrics[f'i2t_catR@{k}'] = round(i2t_cat_correct / n, 4)

        t2i_cat_correct = 0
        for i in range(n):
            if any(labels_all[j] == labels_all[i] for j in t2i_topk[i]):
                t2i_cat_correct += 1
        metrics[f't2i_catR@{k}'] = round(t2i_cat_correct / n, 4)

    return avg_loss, metrics


# ============================================================
#  Checkpoint Management
# ============================================================

def save_checkpoint(model, optimizer, scheduler, scaler, epoch,
                    val_loss, metrics, save_dir, suffix=""):
    """체크포인트 저장 (v1 호환 포맷)"""
    state = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'scheduler_state_dict': scheduler.state_dict(),
        'scaler_state_dict': scaler.state_dict(),
        'val_loss': val_loss,
        'model_name': 'ViT-B/32',
        'embedding_dim': 512,
        'metrics': metrics,
        'training_version': 'v2',
        'loss_type': 'supcon_clip',
    }

    save_path = save_dir / f"clip_v2_{suffix}.pt"
    torch.save(state, save_path)
    return save_path


def load_checkpoint(checkpoint_path, model, optimizer, scheduler, scaler, device):
    """체크포인트에서 재개"""
    print(f"  Loading checkpoint: {checkpoint_path}")
    state = torch.load(checkpoint_path, map_location='cpu')

    model.load_state_dict(state['model_state_dict'])
    model = model.to(device)
    optimizer.load_state_dict(state['optimizer_state_dict'])
    scheduler.load_state_dict(state['scheduler_state_dict'])
    scaler.load_state_dict(state['scaler_state_dict'])

    start_epoch = state['epoch'] + 1
    print(f"  Resumed from epoch {state['epoch']}, "
          f"val_loss={state['val_loss']:.4f}")
    return start_epoch


# ============================================================
#  Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='CLIP v2 Fine-tuning')
    parser.add_argument('--csv-dir', type=str,
                        default=str(BASE_DIR / "drawing-datasets/preprocessed_dataset"),
                        help='CSV 디렉토리')
    parser.add_argument('--csv-suffix', type=str, default='_v2',
                        help='CSV 파일 접미사 (기본: _v2)')
    parser.add_argument('--epochs', type=int, default=50,
                        help='에폭 수 (기본: 50)')
    parser.add_argument('--K', type=int, default=32,
                        help='배치당 카테고리 수 (기본: 32)')
    parser.add_argument('--N', type=int, default=4,
                        help='카테고리당 샘플 수 (기본: 4)')
    parser.add_argument('--lr', type=float, default=5e-5,
                        help='Text encoder LR (기본: 5e-5)')
    parser.add_argument('--warmup-steps', type=int, default=300,
                        help='Warmup 스텝 (기본: 300)')
    parser.add_argument('--weight-decay', type=float, default=0.1,
                        help='Weight decay (기본: 0.1)')
    parser.add_argument('--patience', type=int, default=10,
                        help='Early stopping patience (기본: 10)')
    parser.add_argument('--device', type=str, default='',
                        help='디바이스 (기본: auto)')
    parser.add_argument('--workers', type=int, default=0,
                        help='DataLoader 워커 수 (기본: 0, USB drive)')
    parser.add_argument('--save-dir', type=str,
                        default=str(BASE_DIR / "drawing-datasets/training/clip_v2_runs"),
                        help='체크포인트 저장 디렉토리')
    parser.add_argument('--resume', type=str, default='',
                        help='체크포인트에서 재개')
    parser.add_argument('--log-every', type=int, default=50,
                        help='로그 출력 간격 (배치)')
    args = parser.parse_args()

    print("=" * 65)
    print("  CLIP v2 Fine-tuning: SupCon + Frozen Image Tower")
    print("=" * 65)

    # === Device ===
    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device('cuda')
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = torch.device('mps')
    else:
        device = torch.device('cpu')
    print(f"  Device: {device}")

    # === CLIP 모델 ===
    print("\n  Loading CLIP ViT-B/32...")
    import clip
    model, preprocess = clip.load("ViT-B/32", device="cpu")
    model = model.float()
    model = model.to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"  Total parameters: {total_params / 1e6:.1f}M")

    # 이미지 타워 영구 동결
    set_image_tower_trainable(model, False)

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Trainable parameters: {trainable_params / 1e6:.1f}M")

    # === Dataset ===
    csv_dir = Path(args.csv_dir)
    suffix = args.csv_suffix
    train_csv = csv_dir / f"train{suffix}.csv"
    val_csv = csv_dir / f"val{suffix}.csv"

    if not train_csv.exists():
        print(f"  [ERROR] {train_csv} not found")
        print(f"  Run: python training/enrich_captions.py")
        sys.exit(1)

    print(f"\n  Loading datasets (suffix: '{suffix}')...")
    train_dataset = CLIPDrawingDatasetV2(train_csv, preprocess)
    val_dataset = CLIPDrawingDatasetV2(val_csv, preprocess)

    # Category-balanced sampler (training)
    train_sampler = CategoryBalancedBatchSampler(
        train_dataset.cat_indices,
        num_categories_per_batch=args.K,
        num_samples_per_category=args.N,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_sampler=train_sampler,
        num_workers=args.workers,
        pin_memory=False,
    )

    # Validation: 순차 로딩 (balanced sampling 불필요)
    val_batch = args.K * args.N
    val_loader = DataLoader(
        val_dataset,
        batch_size=val_batch,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=False,
        drop_last=False,
    )

    print(f"  Train: {len(train_dataset)} pairs, {len(train_loader)} batches/epoch")
    print(f"  Val:   {len(val_dataset)} pairs")

    # === Optimizer (text encoder + logit_scale only) ===
    text_params = [p for n, p in model.named_parameters()
                   if "visual" not in n and n != "logit_scale" and p.requires_grad]

    param_groups = [
        {"params": text_params, "lr": args.lr, "name": "text_encoder"},
        {"params": [model.logit_scale], "lr": 1e-4, "name": "logit_scale"},
    ]

    optimizer = torch.optim.AdamW(
        param_groups,
        weight_decay=args.weight_decay,
        betas=(0.9, 0.98),
        eps=1e-6,
    )

    # LR Schedule: linear warmup + cosine decay
    total_steps = len(train_loader) * args.epochs

    def lr_lambda(step):
        if step < args.warmup_steps:
            return step / max(1, args.warmup_steps)
        progress = (step - args.warmup_steps) / max(1, total_steps - args.warmup_steps)
        return 0.5 * (1.0 + math.cos(math.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # AMP
    scaler = torch.amp.GradScaler(device.type)

    # Loss
    loss_fn = SupConCLIPLoss()

    # === Resume ===
    start_epoch = 1
    best_cat_r5 = 0.0
    best_val_loss = float('inf')

    if args.resume and Path(args.resume).exists():
        start_epoch = load_checkpoint(
            args.resume, model, optimizer, scheduler, scaler, device
        )
        # 재개 시 image tower 다시 동결 확인
        set_image_tower_trainable(model, False)

    # === Save directory ===
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # 학습 설정 저장
    config = {
        'model': 'ViT-B/32',
        'training_version': 'v2',
        'loss_type': 'supcon_clip',
        'image_tower': 'frozen',
        'epochs': args.epochs,
        'batch_size': args.K * args.N,
        'K': args.K,
        'N': args.N,
        'lr_text': args.lr,
        'lr_logit_scale': 1e-4,
        'warmup_steps': args.warmup_steps,
        'weight_decay': args.weight_decay,
        'patience': args.patience,
        'total_steps': total_steps,
        'train_samples': len(train_dataset),
        'val_samples': len(val_dataset),
        'train_categories': len(train_dataset.categories),
        'csv_suffix': suffix,
        'device': str(device),
    }
    with open(save_dir / 'training_config_v2.json', 'w') as f:
        json.dump(config, f, indent=2)

    # === 학습 루프 ===
    print(f"\n{'=' * 65}")
    print(f"  Training: {args.epochs} epochs, batch {args.K}×{args.N}={args.K * args.N}")
    print(f"  Loss: SupCon multi-positive")
    print(f"  LR: text={args.lr}, logit_scale=1e-4")
    print(f"  Image tower: PERMANENTLY FROZEN")
    print(f"  Early stopping: patience={args.patience} on catR@5")
    print(f"  Total steps: {total_steps}")
    print(f"{'=' * 65}")

    training_log = []
    patience_counter = 0
    overall_start = time.time()

    for epoch in range(start_epoch, args.epochs + 1):
        epoch_start = time.time()

        # Train
        print(f"\n  [Epoch {epoch}/{args.epochs}] Training...")
        train_loss = train_one_epoch(
            model, train_loader, optimizer, scaler, scheduler,
            device, epoch, loss_fn, log_every=args.log_every,
        )

        # Validate
        print(f"  [Epoch {epoch}/{args.epochs}] Validating...")
        val_loss, metrics = validate(model, val_loader, device, loss_fn)

        epoch_time = time.time() - epoch_start

        # Category-aware R@5 (primary metric)
        cat_r5 = (metrics.get('i2t_catR@5', 0) + metrics.get('t2i_catR@5', 0)) / 2

        # Best model by catR@5
        is_best_recall = cat_r5 > best_cat_r5
        if is_best_recall:
            best_cat_r5 = cat_r5
            patience_counter = 0
            save_checkpoint(
                model, optimizer, scheduler, scaler, epoch,
                val_loss, metrics, save_dir, suffix="best_recall"
            )
            print(f"  ★ New best catR@5: {cat_r5:.4f}")
        else:
            patience_counter += 1

        # Best model by val_loss (secondary)
        is_best_loss = val_loss < best_val_loss
        if is_best_loss:
            best_val_loss = val_loss
            save_checkpoint(
                model, optimizer, scheduler, scaler, epoch,
                val_loss, metrics, save_dir, suffix="best_loss"
            )

        # 에폭별 체크포인트 (10에폭 간격)
        if epoch % 10 == 0:
            save_checkpoint(
                model, optimizer, scheduler, scaler, epoch,
                val_loss, metrics, save_dir, suffix=f"epoch_{epoch:03d}"
            )

        # 로그
        log_entry = {
            'epoch': epoch,
            'train_loss': round(train_loss, 5),
            'val_loss': round(val_loss, 5),
            **{k: round(v, 4) for k, v in metrics.items()},
            'cat_r5_avg': round(cat_r5, 4),
            'logit_scale': round(model.logit_scale.item(), 3),
            'lr': optimizer.param_groups[0]['lr'],
            'epoch_time_s': round(epoch_time, 1),
            'patience': patience_counter,
        }
        training_log.append(log_entry)

        with open(save_dir / 'training_log_v2.json', 'w') as f:
            json.dump(training_log, f, indent=2)

        # 콘솔 출력
        print(f"  [Epoch {epoch}/{args.epochs}] "
              f"train={train_loss:.4f} | val={val_loss:.4f} | "
              f"catR@5={cat_r5:.4f} | "
              f"i2t_R@5={metrics.get('i2t_R@5', 0):.3f} | "
              f"t2i_R@5={metrics.get('t2i_R@5', 0):.3f} | "
              f"{'★' if is_best_recall else '○'} | "
              f"p={patience_counter}/{args.patience} | "
              f"{epoch_time:.0f}s")

        # Early stopping
        if patience_counter >= args.patience:
            print(f"\n  Early stopping at epoch {epoch} "
                  f"(patience={args.patience})")
            break

        # MPS 메모리 정리
        if device.type == 'mps' and hasattr(torch.mps, 'empty_cache'):
            torch.mps.empty_cache()

    # === 최종 요약 ===
    overall_time = time.time() - overall_start

    print(f"\n{'=' * 65}")
    print(f"  CLIP v2 Fine-tuning Complete")
    print(f"{'=' * 65}")
    print(f"  Total time: {overall_time:.0f}s ({overall_time / 3600:.1f}h)")
    print(f"  Best catR@5: {best_cat_r5:.4f}")
    print(f"  Best val_loss: {best_val_loss:.4f}")

    # Production 모델 추출
    best_path = save_dir / "clip_v2_best_recall.pt"
    if best_path.exists():
        checkpoint = torch.load(best_path, map_location='cpu')
        production_state = {
            'model_state_dict': checkpoint['model_state_dict'],
            'model_name': checkpoint['model_name'],
            'embedding_dim': checkpoint['embedding_dim'],
            'epoch': checkpoint['epoch'],
            'val_loss': checkpoint['val_loss'],
            'metrics': checkpoint.get('metrics', {}),
            'training_version': 'v2',
        }
        production_path = save_dir / 'clip_v2_production.pt'
        torch.save(production_state, production_path)
        size_mb = production_path.stat().st_size / (1024 * 1024)
        print(f"  Production model: {production_path} ({size_mb:.1f}MB)")

    print(f"\n  Next steps:")
    print(f"    cp {save_dir / 'clip_v2_production.pt'} "
          f"{BASE_DIR / 'drawing-llm/models/clip_finetuned.pt'}")
    print(f"    python training/evaluate_models.py "
          f"--clip {best_path}")


if __name__ == '__main__':
    main()
