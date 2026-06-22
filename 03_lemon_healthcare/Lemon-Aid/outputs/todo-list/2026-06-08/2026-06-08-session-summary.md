# 2026-06-08 세션 요약 — 영양제 OCR 파이프라인 갭 해소 + CPU 학습/평가

## 한 줄 요약
파이프라인 구현 평가의 우선권고 갭을 순차 해소(#1·#4·#5·#6 + #2B 엔드포인트 구현)하고, 실사진 recognizer **CPU fine-tune 20epoch 완주 + holdout 평가**까지 진행. 95% 미달이나 **무회귀로 방향성 검증** → A100 본학습이 다음 경로.

## 완료 항목
### 1) 파이프라인 갭 해소 (우선권고 순)
- **#1 YOLO26 ROI**: CLOVA-박스 약지도(weak-supervision) 빌더(`build_crawling_yolo_section_dataset.py`) 구현 + 실증평가 → **부적합 판정**(박스 2,050개 중 93% 미분류, intake/allergen=0). 실제 경로=Label Studio 205 주석 + A100. (`docs/ocr_baseline_reports/2026-06-07-yolo26-section-detector-status-and-path.md`)
- **#4 임상 면책 강화** (코드 반영): `SUPPLEMENT_IMPACT_DISCLAIMER` → "의학적 판단을 대신하지 않음 + 의사·약사 등 전문가와 상담". 금칙어('진단/처방') 회피(면책도 `_reject_forbidden_response` 스캔 대상). **17 테스트 통과**.
- **#2B 옵트인 단일 흐름** (코드 구현): `POST /supplements/analyze?with_recommendation=true`(+`recommendation_use_local_llm`) → 스캔 라벨에 대한 안전 권고를 한 응답에 번들. 비파괴 `SupplementAnalysisPreviewWithRecommendation`(recommendation 기본 null), OCR-동의만 사용(추가 동의 회피), 실패 시 graceful degrade. **30 테스트 통과**.
- **#5 활성화 정책 / #6 95% 게이트 CI / #2·#3 스코프 설계**: `docs/ocr_baseline_reports/2026-06-07-gap-closure-activation-policy-and-scoped-designs.md`.

### 2) CPU fine-tune + 평가 (이 머신, Apple Silicon CPU)
- realphoto rec 데이터셋 v1(train 5,101/val 745)로 PaddleX `build_trainer` device=cpu **20/20 epoch 완주**(patience=3 조기중단 모니터 부착, best가 끝까지 갱신되어 미발동).
- holdout(52) 평가: **recall 0.493→0.527(+3.4pt)**, field_match(전체) 0.560→0.568. **catastrophic forgetting 없음**(이전 합성 smoke는 0.52→0.04 붕괴) → 실사진+teacher-box 학습 방식 검증. 95% 게이트는 미달.
- 상세: `docs/ocr_baseline_reports/2026-06-07-cpu-finetune-results.md`.

### 3) A100 본학습 준비
- 에이전트 SSH(155.230.153.222) **차단(publickey)** → 실제 학습은 사용자가 VS Code 원격에서 실행.
- 권장 데이터셋 = 기존 **crawling v1(max-6, 128,315 crop)** — count gate 통과, 신규 CLOVA 비용 없음, 데이터 최다.
- 실행 절차: `docs/ocr_baseline_reports/2026-06-07-a100-proceed-status.md`.

## Git
- 작업 브랜치: **`chore/ocr-a100-v2-clean-guards`** (origin 동기화). feat 브랜치(`feat/supplement-ocr-paddleocr-finetune-scaleup`)는 035153b2.
- 주요 커밋: `035153b2`(엔드포인트/면책/YOLO/평가), `d4897802`(CPU 결과 리포트 + A100 plan + A100 windows 툴링).
- 제외: teacher-text `datasets/`(GB급), `.venv-paddle/`, `.env`, 생성 `outputs/generated/...`, `.mcp.json`.

## 핵심 수치
| 구분 | holdout recall | field_match(전체) | 95% 게이트 |
|---|---:|---:|---|
| baseline(mobile, det-튜닝) | 0.493 | 0.560 | 미달 |
| **CPU fine-tune(realphoto 20ep)** | **0.527** | **0.568** | 미달 |
| A100 목표 | ≥0.95 | — | 통과 목표 |
