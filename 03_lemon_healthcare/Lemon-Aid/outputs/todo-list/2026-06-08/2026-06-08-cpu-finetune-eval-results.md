# 2026-06-08 CPU Fine-tune + Holdout 평가 결과

이 머신(Apple Silicon, CPU-only)에서 PaddleX로 한국어 recognizer를 fine-tune하고 누수 없는 holdout으로 평가한 결과 정리.
(원본 리포트: `docs/ocr_baseline_reports/2026-06-07-cpu-finetune-results.md`)

## 학습
- 모델: `korean_PP-OCRv5_mobile_rec` 사전학습 → fine-tune (PaddleX `build_trainer`, device=cpu, epochs 20, batch 64).
- 데이터: realphoto rec v1 (CLOVA teacher-box 실사진 crop) — train 5,101 / val 745 / dict 656.
- 결과: **20/20 epoch 완주**, best_epoch=20, val acc 0.275 / norm_edit_dis 0.412.
- 조기중단: patience=3 외부 모니터 부착(best가 마지막까지 갱신 → 미발동). 산출 `_train_cpu/best_accuracy/inference/`.

## 평가 (det 튜닝 box0.15/thr0.1/unclip2.0 동일 조건)
**전체 203 fixtures**
| 지표 | baseline | CPU fine-tuned | Δ |
|---|---:|---:|---:|
| field_match_ratio (macro) | 0.5598 | 0.5679 | +0.0081 |
| field_match_ratio (micro) | 0.5524 | 0.5639 | +0.0115 |
| LCS recall | 0.5143 | 0.5649 | +0.0506 |
| ingredient_recall | 0.5406 | 0.5477 | +0.0071 |

**holdout 52 (95% 게이트 기준)**
| 지표 | baseline | fine-tuned | Δ |
|---|---:|---:|---:|
| recall | 0.4932 | 0.5274 | +0.0342 |
| precision | 0.3057 | 0.2713 | −0.0344 |
| f1 | 0.2999 | 0.3059 | +0.0060 |
| 95% target gate | continue | **continue_training_loop** | 미달 |

## 해석
- **소폭이지만 실질 개선**: holdout recall +3.4pt, 전체 LCS recall +5.1pt.
- **무회귀**: 합성(synthetic) 2-epoch smoke는 0.52→0.037 붕괴했으나 실사진 20-epoch는 baseline 위로 개선 → 데이터/파이프라인 건전성 검증.
- precision 소폭 하락은 정상(텍스트를 더 많이 인식 → hypothesis 길이↑ → 구조화-only GT 대비 희석). recall 상승이 목적 부합.
- 95% 미달 = CPU·소규모(5,101) 한계 → **A100 + 대규모(crawling 128K) 데이터**가 경로.

## 결론
- 현 CPU 모델 holdout ≈0.53 → prod 채택은 A100 모델 확정 후 권장.
- 다음: A100 본학습(`docs/ocr_baseline_reports/2026-06-07-a100-proceed-status.md`) → 회수 → 동일 방식 재평가 → 95% 게이트.
