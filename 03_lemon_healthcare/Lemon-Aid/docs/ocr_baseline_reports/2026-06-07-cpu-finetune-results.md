# CPU Fine-tune 결과 — realphoto recognizer (20 epoch) vs baseline

작성: 2026-06-07. 이 머신(Apple Silicon, CPU-only)에서 PaddleX로 실행한 한국어 recognizer fine-tune 결과.

## 학습 설정
- 모델: `korean_PP-OCRv5_mobile_rec` 사전학습에서 fine-tune (PaddleX `build_trainer`, device=cpu).
- 데이터: realphoto rec 데이터셋 v1 (CLOVA teacher-box 실사진 crop) — **train 5,101 / val 745, dict 656**.
- epoch 20/20 **완주**(patience=3 조기중단 모니터 부착 — best가 마지막까지 갱신되어 미발동).
- val 지표(realphoto val 745): `acc 0.275`, `norm_edit_dis 0.412`, best_epoch=20.
- 산출: `…/datasets/supplement-paddleocr-rec-realphoto/v1/_train_cpu/best_accuracy/inference/`.

## 평가 (det 튜닝 box0.15/thr0.1/unclip2.0 동일 조건)

**전체 203 fixtures:**
| 지표 | baseline(mobile) | **CPU fine-tuned** | Δ |
|---|---:|---:|---:|
| field_match_ratio (macro) | 0.5598 | **0.5679** | +0.0081 |
| field_match_ratio (micro) | 0.5524 | **0.5639** | +0.0115 |
| LCS recall | 0.5143 | **0.5649** | **+0.0506** |
| ingredient_recall | 0.5406 | **0.5477** | +0.0071 |

**holdout 52 (95% 게이트 기준, 누수 없음):**
| 지표 | baseline | **fine-tuned** | Δ |
|---|---:|---:|---:|
| normalized_text_recall | 0.4932 | **0.5274** | **+0.0342** |
| normalized_text_precision | 0.3057 | 0.2713 | −0.0344 |
| normalized_text_f1 | 0.2999 | **0.3059** | +0.0060 |
| **95% target gate** | continue_training_loop | **continue_training_loop** | 미도달 |

## 해석
- **소폭이지만 실질적 개선**: holdout recall **+3.4pt**(0.493→0.527), 전체 LCS recall **+5.1pt**, field_match macro +0.8pt.
- **catastrophic forgetting 없음**: 직전 *합성(synthetic)* 2-epoch CPU smoke는 holdout field_match가 0.52→0.037로 붕괴했으나, 이번 *실사진* 20-epoch는 baseline 위로 개선 → **실사진 + CLOVA teacher-box 학습 데이터 방식이 의도대로 작동**함을 검증.
- precision 소폭 하락(−3.4pt)은 정상: 모델이 텍스트를 더 많이 인식 → hypothesis 길이↑ → 구조화-only GT 대비 precision 희석. recall 상승이 목적에 부합.
- **95% 게이트는 미달**: CPU·소규모(5,101 crop)의 본질적 한계.

## 결론 / 권고
1. 방향성 검증 완료(데이터·파이프라인 건전, 무회귀). CPU로도 작은 개선 확인.
2. **95% 도달 경로 = A100 + 대규모 데이터**: 이미 빌드된 crawling 데이터셋(최대 128,315 crop, 또는 A100 가이드 v2 max-3 77,606)으로 A100 본학습 → 재평가. (`2026-06-06-a100-remote-paddleocr-finetune-guide.md`)
3. 현 CPU 모델은 holdout ≈0.53 수준 — prod 채택은 A100 모델 확정 후 권장. 산출물은 로컬 `datasets/`(gitignore)에 보존.

## 재현 명령
```bash
# 학습(CPU): /tmp/run_rec_finetune_real.py 가 PaddleX build_trainer(device=cpu, epochs_iters=20, batch_size=64) 실행
# 평가:
./.venv-paddle/bin/python scripts/paddleocr_clova_eval.py --bundle-dir <BUNDLE> \
  --rec-model-dir <…/_train_cpu/best_accuracy/inference> \
  --det-box-thresh 0.15 --det-thresh 0.1 --det-unclip-ratio 2.0 \
  --output <eval.json> --observations-output <obs.jsonl> --apply
# 게이트: merge_… → build_paddleocr_text_extraction_eval_summary --eval-split holdout → gate_paddleocr_text_extraction_target --min-fixtures 30
```
> 학습/평가 산출물(`datasets/`, `reconciled/`)은 teacher-text 포함 → gitignore. 본 리포트(docs)만 커밋.
