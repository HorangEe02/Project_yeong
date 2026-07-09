#!/bin/bash
# ============================================================
#  Step 5: 모델 학습/Fine-tuning 오케스트레이터
# ============================================================
#
#  사용법:
#    bash training/run_step5.sh                 # 전체 실행 (YOLO → CLIP → 평가)
#    bash training/run_step5.sh --yolo-only     # YOLOv8-cls만
#    bash training/run_step5.sh --clip-only     # CLIP만
#    bash training/run_step5.sh --eval-only     # 평가만
#
#  참고: YOLO와 CLIP은 모두 MPS를 사용하므로 순차 실행 권장
# ============================================================

set -euo pipefail

BASE_DIR="<EXTERNAL_DRIVE>/00_work_out/01_complete/me/01_CAD"
DATASET_DIR="$BASE_DIR/drawing-datasets/preprocessed_dataset"
DRAWING_LLM="$BASE_DIR/drawing-llm"
TRAINING_DIR="$BASE_DIR/drawing-datasets/training"

YOLO_LOG="/tmp/yolo_cls_v2_train.log"
CLIP_LOG="/tmp/clip_finetune.log"

# 인자 파싱
YOLO_ONLY=false
CLIP_ONLY=false
EVAL_ONLY=false

for arg in "$@"; do
    case $arg in
        --yolo-only) YOLO_ONLY=true ;;
        --clip-only) CLIP_ONLY=true ;;
        --eval-only) EVAL_ONLY=true ;;
    esac
done

echo "============================================================"
echo "  Step 5: 모델 학습/Fine-tuning"
echo "============================================================"
echo "  Dataset:  $DATASET_DIR"
echo "  시작시간: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

# === 5-A: YOLOv8-cls ===
if [ "$CLIP_ONLY" = false ] && [ "$EVAL_ONLY" = false ]; then
    echo ""
    echo "=== 5-A: YOLOv8-cls 82카테고리 학습 ==="
    echo "  로그: $YOLO_LOG"

    cd "$DRAWING_LLM"
    python scripts/train_yolo_cls.py \
        --data "$DATASET_DIR" \
        --model yolov8s-cls.pt \
        --epochs 100 --imgsz 224 --batch 64 --patience 20 \
        --device mps --lr0 0.01 --workers 8 --seed 42 \
        --project runs/classify --name train_v2_82cls \
        2>&1 | tee "$YOLO_LOG"

    echo "  [DONE] YOLOv8-cls 학습 완료: $(date '+%H:%M:%S')"

    if [ "$YOLO_ONLY" = true ]; then
        echo "  (--yolo-only 모드: CLIP 학습 건너뜀)"
        exit 0
    fi
fi

# === 5-B: CLIP Fine-tuning ===
if [ "$YOLO_ONLY" = false ] && [ "$EVAL_ONLY" = false ]; then
    echo ""
    echo "=== 5-B: CLIP ViT-B/32 Fine-tuning ==="
    echo "  로그: $CLIP_LOG"

    cd "$BASE_DIR/drawing-datasets"
    python training/train_clip.py \
        --csv-dir "$DATASET_DIR" \
        --epochs 30 --batch 64 --lr 1e-5 \
        --lock-image-epochs 5 \
        --output-dir training/clip_runs \
        2>&1 | tee "$CLIP_LOG"

    echo "  [DONE] CLIP Fine-tuning 완료: $(date '+%H:%M:%S')"

    if [ "$CLIP_ONLY" = true ]; then
        echo "  (--clip-only 모드: 평가 건너뜀)"
        exit 0
    fi
fi

# === 5-C: 평가 ===
echo ""
echo "=== 5-C: 모델 평가 ==="

cd "$BASE_DIR/drawing-datasets"
python training/evaluate_models.py \
    --data "$DATASET_DIR" \
    --max-samples 2000

echo ""
echo "============================================================"
echo "  Step 5 완료: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

# === 모델 배포 안내 ===
echo ""
echo "  다음 단계 (수동):"
echo "  1. YOLO best.pt → drawing-llm/models/yolo_cls_best.pt 복사"
echo "  2. CLIP clip_best.pt → drawing-llm/models/clip_finetuned.pt 복사"
echo "  3. drawing-llm/config/settings.py 에서 image_weight 수정"
echo "  4. drawing-llm/core/embeddings.py 에서 finetuned CLIP 로딩 추가"
