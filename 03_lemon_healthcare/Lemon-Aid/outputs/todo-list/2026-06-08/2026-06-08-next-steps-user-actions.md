# 2026-06-08 다음 단계 / 사용자 액션

## 사용자가 직접 해야 하는 것 (에이전트 차단/권한)
1. **A100 본학습 실행** — 에이전트 SSH(155.230.153.222) 차단(publickey). 둘 중 하나:
   - (a) A100에 에이전트 무비밀번호 SSH 키 등록 → 이후 전송/학습/회수까지 에이전트가 원격 구동 가능.
   - (b) VS Code 원격 터미널에서 `docs/ocr_baseline_reports/2026-06-07-a100-proceed-status.md` 절차대로 직접 실행.
   - 권장 데이터셋: crawling **v1(max-6, 128,315 crop)** (count gate 통과, 추가 CLOVA 비용 없음).
2. **개인 GitHub 푸시** — 에이전트 하드 차단(크로스-계정). 필요 시 `git push personal <branch>` 사용자 직접.
3. **(선택) 브랜치 정리** — 현재 작업은 `chore/ocr-a100-v2-clean-guards`(origin 동기화). `feat/supplement-ocr-paddleocr-finetune-scaleup`(035153b2)에 반영하려면 chore→feat 머지/PR.

## 에이전트가 이어서 할 수 있는 것
- A100 학습 모델 회수 후 → holdout 재평가 + 95% 게이트 실행 + baseline/CPU 대비 비교 리포트.
- **#3 Vision-QA 닫힌 루프**: verify→재전사→파서 재투입 reorder + fake 단위테스트 (+ 실 Ollama 통합 스모크). 기본 OFF, prod 사인오프 필요.
- **#1 YOLO26 본학습**: 205 섹션 bbox 주석(Label Studio chain) 완료 후 materialize/validate/gate → A100 `yolo detect train model=yolo26n.pt`.
- **#2 연동**: 모바일/클라이언트가 `with_recommendation=true` 사용하도록 연동(선택).

## 게이트 현황
| 게이트 | 상태 |
|---|---|
| #1 OCR benchmark (teacher-eval ready) | 통과 (ready_for_teacher_ocr_eval) |
| #2 PaddleOCR 95% target | **미달** (continue_training_loop) → A100 본학습 후 재도전 |
| #3 YOLO section dataset | blocked (205 주석 + A100 학습 대기) |

## 우선순위 추천
1. A100 본학습(95% 재도전) — 임팩트 최대.
2. #3 Vision-QA 닫힌 루프(라이브 Ollama 환경 시).
3. #1 YOLO 주석+학습.
