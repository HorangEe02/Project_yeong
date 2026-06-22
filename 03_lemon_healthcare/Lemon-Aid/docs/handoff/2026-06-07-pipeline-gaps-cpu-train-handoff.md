# Handoff — 파이프라인 갭 해소 + CPU 학습 결과 평가 + 다음 단계

> 다음 섹션 첫 프롬프트로 이 파일 전체를 붙여넣으세요. self-contained. 작성: 2026-06-07.

## 0. 미션
영양제 라벨 AI 파이프라인(YOLO26 ROI → PaddleOCR → Gemma Vision QA → Gemma Text RAG 권고+면책)의
구현 갭을 우선권고 순으로 해소 중. **현재 백그라운드 CPU 학습이 끝나면 그 결과를 평가**하고, 이어서 남은 갭/학습을 진행.

## 1. 환경 / 경로 (먼저 export)
```bash
REPO="/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid"
BACKEND="$REPO/backend"
RD="$REPO/outputs/generated/supplement-learning/2026-06-05/operator-review"
BUNDLE="$RD/ocr-ground-truth-review-bundle"
SPLITS="$RD/reconciled/ocr-benchmark-splits.assignment.json"
PY="$BACKEND/.venv/bin/python"            # py3.13 backend (FastAPI/src)
PYPADDLE="$BACKEND/.venv-paddle/bin/python" # py3.12 paddleocr/paddlex
```
불변식: env-split(paddle=PYPADDLE만, backend=PY만) · paddle 실행 중 Ollama 모델 로드 금지(OOM) · `.env`는 repo 루트, 절대 Read+print 금지 · redaction(outputs에 raw OCR/payload/절대경로 금지; **단 teacher-text 학습 datasets는 운영자 승인하에 `datasets/`에만, gitignore됨**) · 커밋/푸시는 요청 시에만, 트레일러 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` · **개인 깃허브 푸시는 에이전트 하드 차단(크로스-계정)** → 사용자가 직접.

## 2. ⏳ 즉시 이어서 할 일 — 백그라운드 CPU 학습 종료 후 평가
**학습 작업**: realphoto rec fine-tune, device=cpu, 20 epoch. 구동 스크립트 `/tmp/run_rec_finetune_real.py`(cfg, dataset_dir, out).
- 데이터셋: `$RD/datasets/supplement-paddleocr-rec-realphoto/v1` (train 5,101 / val 745, dict 656).
- 출력: `$RD/datasets/supplement-paddleocr-rec-realphoto/v1/_train_cpu/best_accuracy/{best_accuracy.pdparams, inference/}` (+ iter_epoch_*, latest).
- 진행 확인: `pgrep -fl run_rec_finetune_real` (없으면 종료). best 체크포인트는 이미 생성됨.

**종료 후 평가(누수 없는 holdout, det 튜닝 적용):**
```bash
cd "$BACKEND"
FT="$RD/datasets/supplement-paddleocr-rec-realphoto/v1/_train_cpu/best_accuracy/inference"
"$PYPADDLE" scripts/paddleocr_clova_eval.py --bundle-dir "$BUNDLE" \
  --rec-model-dir "$FT" \
  --det-box-thresh 0.15 --det-thresh 0.1 --det-unclip-ratio 2.0 \
  --output "$RD/reconciled/paddleocr-eval-cpu-finetuned.json" \
  --observations-output "$RD/reconciled/paddleocr-obs-cpu-finetuned.jsonl" --apply
# 형식 게이트(holdout):
export PYTHONPATH=Nutrition-backend
"$PY" scripts/merge_paddleocr_text_observations_into_benchmark.py \
  --benchmark-manifest "$RD/reconciled/ocr-benchmark-splits.assignment.json" \
  --observations "$RD/reconciled/paddleocr-obs-cpu-finetuned.jsonl" \
  --output "$RD/reconciled/ocr-benchmark-merged.cpu-ft.jsonl"
"$PY" scripts/build_paddleocr_text_extraction_eval_summary.py \
  --benchmark-manifest "$RD/reconciled/ocr-benchmark-merged.cpu-ft.jsonl" \
  --eval-split holdout --provider paddleocr_local --leakage-check-passed --privacy-review-cleared \
  --output "$RD/reconciled/paddleocr-eval-summary.cpu-ft.json"
"$PY" scripts/gate_paddleocr_text_extraction_target.py \
  --eval-summary "$RD/reconciled/paddleocr-eval-summary.cpu-ft.json" --min-fixtures 30 \
  --output "$RD/reconciled/paddleocr-target-gate.cpu-ft.json"
```
**비교 기준**: baseline(mobile, det-튜닝) holdout `field_match_ratio` ≈ **0.52** (LCS recall ≈ 0.55). 
**예상 caveat**: 이전 합성 2-epoch CPU smoke는 0.52→0.037로 **catastrophic forgetting** 발생. realphoto 20-epoch도 소데이터/CPU라 **개선 보장 없음** — 결과를 정직하게 보고하고, best vs latest 비교, 필요시 epoch/LR/freeze 조정. **유의미한 95% 달성은 A100 + 대규모(crawling) 데이터 필요**(§4).

## 3. ✅ 지금까지 완료 (검증됨)
- **Chain A → Gate #1**: `ready_for_teacher_ocr_eval` (203 fixtures, holdout52/test22/train129).
- **PaddleOCR 베이스라인**: field_match 0.560(mobile) → det-튜닝 0.586. **Gate #2(95%) 미달**(continue_training_loop).
- **무학습 개선**: det 파라미터 `box0.15/thr0.1/unclip2.0` 채택(eval에 `--rec-model-dir`/`--det-*` 추가). 해상도↑·server det는 무효.
- **데이터셋(teacher-box, gitignored datasets/)**: realphoto v1(5,846 crop), crawling v1(**128,315 crop**, max-6). 둘 다 `check_dataset` 통과 + 검증된 fine-tune run plan.
- **실제 학습 실행 경험**: PaddleX `build_trainer` CPU 동작 확인(외부 PaddleOCR 플러그인 설치 + 패키징 우회 2건 적용: `repo_manager/repos/`, `repo_apis/PaddleOCR_api/configs/korean_PP-OCRv5_mobile_rec.yaml`).
- **갭 평가 + 해소**(우선권고 순):
  - #1 YOLO26: 약지도 빌더(`build_crawling_yolo_section_dataset.py`) 실증→**부적합**(93% 미분류). 실제 경로=Label Studio 205 주석+A100. (`docs/ocr_baseline_reports/2026-06-07-yolo26-section-detector-status-and-path.md`)
  - **#4 면책**: 강화 완료 — "의학적 판단 대신 안 함 + 의사·약사 상담"(금칙어 '진단/처방' 회피, 17 테스트 통과).
  - **#2B 옵트인 단일 흐름**: `POST /supplements/analyze?with_recommendation=true`(+`recommendation_use_local_llm`) 구현. 비파괴 `SupplementAnalysisPreviewWithRecommendation`(recommendation 기본 null), OCR-동의만, graceful degrade. **30 테스트 통과**.
  - #5 활성화정책 / #6 95%게이트 CI / #2·#3 스코프설계: `docs/ocr_baseline_reports/2026-06-07-gap-closure-activation-policy-and-scoped-designs.md`.
- **Git**: 브랜치 `feat/supplement-ocr-paddleocr-finetune-scaleup`, HEAD **035153b2**, **origin(team)와 동기화 완료**. 개인 remote는 미동기(에이전트 차단).

## 4. 다음 단계 (우선순위)
1. **(즉시)** §2 CPU 학습 결과 평가 + 보고.
2. **A100 본학습 트랙**(Codex가 셋업): `docs/ocr_baseline_reports/2026-06-06-a100-remote-paddleocr-finetune-guide.md` 참조 — A100 Windows 서버(155.230.153.222, VS Code 연결). 절차: v2 dataset(max-3) 재생성 → `validate_paddleocr_rec_dataset_counts.py`(train 70,778/val 6,828/dict 1,066) → `preflight_a100_paddleocr_training_readiness.py`(status=ready_for_a100_transfer) → scp 전송 → `run_a100_paddleocr_windows_training.ps1`(preflight/dataset/smoke/full/export) → 모델 회수 → §2 방식 holdout 재평가 → 95% 게이트.
3. **#3 Vision-QA 닫힌 루프**: verify→재전사→**파서 재투입** reorder + `_FakeHTTPClient` 단위테스트 + 실 Ollama 통합 스모크. (기본 OFF, prod 사인오프 필요.)
4. **#1 YOLO26 본학습**: 205 섹션 bbox 주석(Label Studio chain) → materialize/validate/gate → A100 `yolo detect train ... model=yolo26n.pt`. (헤더-앵커 약지도 개선은 선택.)
5. **#2 추가**: B안 구현됨 → 모바일/클라이언트가 `with_recommendation=true` 사용하도록 연동(선택).
6. **커밋**: 변경 시 team 브랜치에 추가 커밋(요청 시). 개인 remote는 사용자가 직접 `git push personal <branch>`.

## 5. 핵심 caveat 체크리스트
- [ ] CPU 학습 결과는 소데이터/CPU 한계 — 회귀 가능성 정직 보고. 95%는 A100+대규모.
- [ ] 면책 문구에 '진단/치료/처방/복용량 변경' 토큰 금지(`_reject_forbidden_response`가 disclaimer 포함 스캔 → 422). 의미는 우회 표현으로.
- [ ] `with_recommendation` 경로: profile/medical context 미사용(추가 동의 회피), 실패 시 graceful(preview-only).
- [ ] datasets/·.venv-paddle/·.env·생성 outputs/·.mcp.json 커밋 금지(이미 .gitignore/명시 제외).
- [ ] CLOVA 재호출은 유료 — 대규모 전 비용/규모 운영자 확인.
- [ ] paddle 모델 캐시 `~/.paddlex/official_models`(PP-OCRv5 det/rec + korean rec) 의존.
```
```
