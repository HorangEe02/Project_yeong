#!/usr/bin/env python3
"""
Step 5-B: CLIP ViT-B/32 Fine-tuning for Engineering Drawings

Contrastive learning으로 CLIP 모델을 CAD 도면 도메인에 적응시킨다.
- InfoNCE loss (symmetric cross-entropy)
- Image tower freezing (처음 N 에폭)
- MPS AMP (Apple Silicon 최적화)
- Differential learning rates (text > image)
- Linear warmup + cosine decay schedule

사용법:
  python training/train_clip.py                          # 기본 설정
  python training/train_clip.py --epochs 30 --batch 64   # 파라미터 지정
  python training/train_clip.py --resume clip_runs/clip_epoch_010.pt  # 재개

입력: preprocessed_dataset/train.csv, val.csv (filepath, caption, category)
출력: training/clip_runs/clip_best.pt
"""

import os
import sys
import csv
import math
import json
import time
import argparse
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from PIL import Image

# macOS MPS 호환을 위한 spawn 방식
try:
    torch.multiprocessing.set_start_method('spawn', force=True)
except RuntimeError:
    pass  # 이미 설정된 경우

BASE_DIR = Path("<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD")


class CLIPDrawingDataset(Dataset):
    """CLIP fine-tuning용 이미지-텍스트 쌍 데이터셋"""

    def __init__(self, csv_path, preprocess_fn):
        """
        Args:
            csv_path: CSV 파일 경로 (filepath, caption, category)
            preprocess_fn: CLIP 이미지 전처리 함수
        """
        self.preprocess = preprocess_fn
        self.data = []

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.data.append({
                    'filepath': row['filepath'],
                    'caption': row['caption'],
                    'category': row['category'],
                })

        print(f"  Dataset loaded: {len(self.data)} pairs from {csv_path}")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        row = self.data[idx]
        try:
            image = Image.open(row['filepath']).convert('RGB')
            image_tensor = self.preprocess(image)
        except Exception:
            # 손상된 이미지 → 빈 이미지로 대체
            image_tensor = self.preprocess(Image.new('RGB', (224, 224), (255, 255, 255)))

        import clip
        text_token = clip.tokenize([row['caption']], truncate=True).squeeze(0)

        return image_tensor, text_token


def clip_loss(logits_per_image, logits_per_text):
    """
    Symmetric InfoNCE contrastive loss.
    Ground truth: diagonal (image_i ↔ text_i)
    """
    batch_size = logits_per_image.shape[0]
    labels = torch.arange(batch_size, device=logits_per_image.device)

    loss_i2t = F.cross_entropy(logits_per_image, labels)
    loss_t2i = F.cross_entropy(logits_per_text, labels)

    return (loss_i2t + loss_t2i) / 2.0


def set_image_tower_trainable(model, trainable: bool):
    """Visual encoder 동결/해동"""
    for param in model.visual.parameters():
        param.requires_grad = trainable

    n_params = sum(p.numel() for p in model.visual.parameters())
    status = "UNFROZEN" if trainable else "FROZEN"
    print(f"  Image tower {status}: {n_params/1e6:.1f}M parameters")


def train_one_epoch(model, dataloader, optimizer, scaler, scheduler,
                    device, epoch, log_every=50):
    """1 에폭 학습"""
    model.train()
    total_loss = 0.0
    num_batches = 0
    start_time = time.time()

    for batch_idx, (images, texts) in enumerate(dataloader):
        images = images.to(device)
        texts = texts.to(device)

        optimizer.zero_grad()

        # Forward with AMP
        with torch.autocast(device_type=device.type, dtype=torch.float16):
            image_features = model.encode_image(images)
            text_features = model.encode_text(texts)

            # Normalize
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Scaled cosine similarity
            logit_scale = model.logit_scale.exp()
            logits_per_image = logit_scale * image_features @ text_features.t()
            logits_per_text = logits_per_image.t()

            loss = clip_loss(logits_per_image, logits_per_text)

        # Backward with GradScaler
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()

        # Logit scale 클램핑 (폭발 방지)
        with torch.no_grad():
            model.logit_scale.clamp_(0, math.log(100))

        # LR schedule step (per-batch)
        scheduler.step()

        total_loss += loss.item()
        num_batches += 1

        if (batch_idx + 1) % log_every == 0:
            elapsed = time.time() - start_time
            avg_loss = total_loss / num_batches
            lr_current = optimizer.param_groups[0]['lr']
            print(f"    [Epoch {epoch}] Batch {batch_idx+1}/{len(dataloader)} | "
                  f"loss={avg_loss:.4f} | lr={lr_current:.2e} | "
                  f"logit_scale={model.logit_scale.item():.3f} | "
                  f"{elapsed:.0f}s")

    return total_loss / num_batches


@torch.no_grad()
def validate(model, dataloader, device):
    """Validation loss + retrieval Recall@1 계산"""
    model.eval()
    total_loss = 0.0
    num_batches = 0

    all_image_features = []
    all_text_features = []

    for images, texts in dataloader:
        images = images.to(device)
        texts = texts.to(device)

        with torch.autocast(device_type=device.type, dtype=torch.float16):
            image_features = model.encode_image(images)
            text_features = model.encode_text(texts)

            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            logit_scale = model.logit_scale.exp()
            logits_per_image = logit_scale * image_features @ text_features.t()
            logits_per_text = logits_per_image.t()

            loss = clip_loss(logits_per_image, logits_per_text)

        total_loss += loss.item()
        num_batches += 1

        # Retrieval 평가용 feature 수집 (최대 1000개)
        if sum(len(f) for f in all_image_features) < 1000:
            all_image_features.append(image_features.cpu().float())
            all_text_features.append(text_features.cpu().float())

    avg_loss = total_loss / num_batches

    # Recall@1 계산 (수집된 샘플에 대해)
    img_feats = torch.cat(all_image_features)[:1000]
    txt_feats = torch.cat(all_text_features)[:1000]

    similarity = img_feats @ txt_feats.t()
    n = len(similarity)

    # Text → Image Recall@1
    t2i_preds = similarity.argmax(dim=0)
    t2i_recall1 = (t2i_preds == torch.arange(n)).float().mean().item()

    # Image → Text Recall@1
    i2t_preds = similarity.argmax(dim=1)
    i2t_recall1 = (i2t_preds == torch.arange(n)).float().mean().item()

    return avg_loss, i2t_recall1, t2i_recall1


def save_checkpoint(model, optimizer, scheduler, scaler, epoch, val_loss,
                    save_dir, is_best=False):
    """체크포인트 저장"""
    state = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'scheduler_state_dict': scheduler.state_dict(),
        'scaler_state_dict': scaler.state_dict(),
        'val_loss': val_loss,
        'model_name': 'ViT-B/32',
        'embedding_dim': 512,
    }

    # 에폭별 체크포인트 (10에폭 간격)
    if epoch % 10 == 0 or is_best:
        save_path = save_dir / f"clip_epoch_{epoch:03d}.pt"
        torch.save(state, save_path)

    if is_best:
        best_path = save_dir / "clip_best.pt"
        torch.save(state, best_path)
        print(f"  ★ New best model saved: val_loss={val_loss:.4f}")


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
    print(f"  Resumed from epoch {state['epoch']}, val_loss={state['val_loss']:.4f}")
    return start_epoch


def main():
    parser = argparse.ArgumentParser(description='CLIP ViT-B/32 Fine-tuning')
    parser.add_argument('--csv-dir', type=str,
                        default=str(BASE_DIR / "drawing-datasets/preprocessed_dataset"),
                        help='CSV 파일 디렉토리 (train.csv, val.csv)')
    parser.add_argument('--epochs', type=int, default=30, help='에폭 수 (기본: 30)')
    parser.add_argument('--batch', type=int, default=64, help='배치 크기 (기본: 64)')
    parser.add_argument('--lr', type=float, default=1e-5, help='텍스트 인코더 학습률 (기본: 1e-5)')
    parser.add_argument('--image-lr', type=float, default=1e-6, help='이미지 인코더 학습률 (기본: 1e-6)')
    parser.add_argument('--warmup-steps', type=int, default=500, help='Warmup 스텝 (기본: 500)')
    parser.add_argument('--lock-epochs', type=int, default=5, help='이미지 인코더 동결 에폭 (기본: 5)')
    parser.add_argument('--weight-decay', type=float, default=0.1, help='Weight decay (기본: 0.1)')
    parser.add_argument('--device', type=str, default='', help='디바이스 (기본: auto)')
    parser.add_argument('--workers', type=int, default=4, help='DataLoader 워커 수 (기본: 4)')
    parser.add_argument('--save-dir', type=str,
                        default=str(BASE_DIR / "drawing-datasets/training/clip_runs"),
                        help='체크포인트 저장 디렉토리')
    parser.add_argument('--resume', type=str, default='', help='체크포인트에서 재개')
    parser.add_argument('--log-every', type=int, default=50, help='로그 출력 간격 (배치)')
    args = parser.parse_args()

    print("=" * 65)
    print("  Step 5-B: CLIP ViT-B/32 Fine-tuning")
    print("=" * 65)

    # === Device 설정 ===
    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device('cuda')
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        device = torch.device('mps')
    else:
        device = torch.device('cpu')
    print(f"  Device: {device}")

    # === CLIP 모델 로드 ===
    print("\n  Loading CLIP ViT-B/32...")
    import clip

    model, preprocess = clip.load("ViT-B/32", device="cpu")
    model = model.float()  # float32 base (autocast에서 float16)
    model = model.to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"  Total parameters: {total_params/1e6:.1f}M")
    print(f"  Logit scale: {model.logit_scale.item():.3f} (exp={model.logit_scale.exp().item():.1f})")

    # === Dataset 로드 ===
    csv_dir = Path(args.csv_dir)
    train_csv = csv_dir / "train.csv"
    val_csv = csv_dir / "val.csv"

    if not train_csv.exists():
        print(f"  [ERROR] train.csv 없음: {train_csv}")
        sys.exit(1)

    print(f"\n  Loading datasets...")
    train_dataset = CLIPDrawingDataset(train_csv, preprocess)
    val_dataset = CLIPDrawingDataset(val_csv, preprocess)

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch,
        shuffle=True,
        num_workers=args.workers,
        pin_memory=False,  # MPS는 pin_memory 미지원
        drop_last=True,
        persistent_workers=args.workers > 0,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=False,
        drop_last=False,
        persistent_workers=args.workers > 0,
    )

    print(f"  Train: {len(train_dataset)} pairs, {len(train_loader)} batches/epoch")
    print(f"  Val:   {len(val_dataset)} pairs, {len(val_loader)} batches/epoch")

    # === Optimizer 설정 (differential LR) ===
    # Text encoder + projections: higher LR
    text_params = [p for n, p in model.named_parameters()
                   if "visual" not in n and n != "logit_scale" and p.requires_grad]
    # Image encoder: lower LR
    image_params = [p for n, p in model.named_parameters()
                    if "visual" in n and p.requires_grad]

    param_groups = [
        {"params": text_params, "lr": args.lr, "name": "text_encoder"},
        {"params": image_params, "lr": args.image_lr, "name": "image_encoder"},
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

    # AMP GradScaler
    scaler = torch.amp.GradScaler(device.type)

    # === Resume ===
    start_epoch = 1
    best_val_loss = float('inf')

    if args.resume:
        start_epoch = load_checkpoint(
            args.resume, model, optimizer, scheduler, scaler, device
        )

    # === Save 디렉토리 ===
    save_dir = Path(args.save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # 학습 설정 저장
    config = {
        'model': 'ViT-B/32',
        'epochs': args.epochs,
        'batch_size': args.batch,
        'lr_text': args.lr,
        'lr_image': args.image_lr,
        'warmup_steps': args.warmup_steps,
        'lock_epochs': args.lock_epochs,
        'weight_decay': args.weight_decay,
        'total_steps': total_steps,
        'train_samples': len(train_dataset),
        'val_samples': len(val_dataset),
        'device': str(device),
    }
    with open(save_dir / 'training_config.json', 'w') as f:
        json.dump(config, f, indent=2)

    # === 학습 루프 ===
    print(f"\n{'='*65}")
    print(f"  Training: {args.epochs} epochs, batch {args.batch}")
    print(f"  LR: text={args.lr}, image={args.image_lr}")
    print(f"  Image tower locked for epochs 1-{args.lock_epochs}")
    print(f"  Total steps: {total_steps}")
    print(f"{'='*65}")

    training_log = []
    overall_start = time.time()

    for epoch in range(start_epoch, args.epochs + 1):
        epoch_start = time.time()

        # Image tower freeze/unfreeze
        if epoch <= args.lock_epochs:
            set_image_tower_trainable(model, False)
        elif epoch == args.lock_epochs + 1:
            set_image_tower_trainable(model, True)
            # Image params를 optimizer에 반영 (requires_grad가 바뀌었으므로)
            print("  Image tower unlocked — gradients will flow")

        # Train
        print(f"\n  [Epoch {epoch}/{args.epochs}] Training...")
        train_loss = train_one_epoch(
            model, train_loader, optimizer, scaler, scheduler,
            device, epoch, log_every=args.log_every,
        )

        # Validate
        print(f"  [Epoch {epoch}/{args.epochs}] Validating...")
        val_loss, i2t_recall1, t2i_recall1 = validate(model, val_loader, device)

        epoch_time = time.time() - epoch_start

        # Best model 확인
        is_best = val_loss < best_val_loss
        if is_best:
            best_val_loss = val_loss

        # 체크포인트 저장
        save_checkpoint(
            model, optimizer, scheduler, scaler, epoch, val_loss,
            save_dir, is_best=is_best,
        )

        # 로그
        log_entry = {
            'epoch': epoch,
            'train_loss': round(train_loss, 5),
            'val_loss': round(val_loss, 5),
            'i2t_recall1': round(i2t_recall1, 4),
            't2i_recall1': round(t2i_recall1, 4),
            'logit_scale': round(model.logit_scale.item(), 3),
            'lr': optimizer.param_groups[0]['lr'],
            'epoch_time_s': round(epoch_time, 1),
        }
        training_log.append(log_entry)

        # 로그 파일 업데이트
        with open(save_dir / 'training_log.json', 'w') as f:
            json.dump(training_log, f, indent=2)

        print(f"  [Epoch {epoch}/{args.epochs}] "
              f"train_loss={train_loss:.4f} | val_loss={val_loss:.4f} | "
              f"i2t_R@1={i2t_recall1:.3f} | t2i_R@1={t2i_recall1:.3f} | "
              f"{'★ BEST' if is_best else ''} | "
              f"{epoch_time:.0f}s")

        # MPS 메모리 정리
        if device.type == 'mps' and hasattr(torch.mps, 'empty_cache'):
            torch.mps.empty_cache()

    # === 최종 요약 ===
    overall_time = time.time() - overall_start

    print(f"\n{'='*65}")
    print(f"  CLIP Fine-tuning 완료")
    print(f"{'='*65}")
    print(f"  총 소요시간: {overall_time:.0f}초 ({overall_time/3600:.1f}시간)")
    print(f"  Best val_loss: {best_val_loss:.4f}")
    print(f"  Best checkpoint: {save_dir / 'clip_best.pt'}")
    print(f"  Training log: {save_dir / 'training_log.json'}")

    # Production 모델 추출 (optimizer/scheduler 제외)
    best_checkpoint = torch.load(save_dir / 'clip_best.pt', map_location='cpu')
    production_state = {
        'model_state_dict': best_checkpoint['model_state_dict'],
        'model_name': best_checkpoint['model_name'],
        'embedding_dim': best_checkpoint['embedding_dim'],
        'epoch': best_checkpoint['epoch'],
        'val_loss': best_checkpoint['val_loss'],
    }
    production_path = save_dir / 'clip_finetuned_production.pt'
    torch.save(production_state, production_path)
    size_mb = production_path.stat().st_size / (1024 * 1024)
    print(f"  Production model: {production_path} ({size_mb:.1f}MB)")

    print(f"\n  다음 단계:")
    print(f"    cp {production_path} drawing-llm/models/clip_finetuned.pt")
    print(f"    python training/evaluate_models.py --clip {save_dir / 'clip_best.pt'}")


if __name__ == '__main__':
    main()
