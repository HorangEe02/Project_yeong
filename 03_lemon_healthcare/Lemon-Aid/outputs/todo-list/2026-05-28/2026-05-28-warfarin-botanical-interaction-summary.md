# 2026-05-28 와파린 생약 상호작용 경고 적용 요약

## 기준 정보

- 작성일: 2026-05-28
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `68baa52 fix(nutrition): 와파린 생약 경고 추가`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/06-goal-matrix.md`
  - `docs/Nutrition-docs/core-algorithm/05-nutrition-diagnosis.md`
- 확인 근거:
  - NIH NCCIH Ginkgo safety: https://www.nccih.nih.gov/health/ginkgo
  - NIH NCCIH Garlic safety: https://www.nccih.nih.gov/health/garlic
  - NIH ODS Vitamin K fact sheet: https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/
  - FDA/DailyMed warfarin labeling: https://dailymed.nlm.nih.gov/dailymed/

## 브랜치/커밋 범위

- 직전 기준 head: `3af518b docs(todo): 운동 심박 TDEE 요약 추가`
- 이번 phase head: `68baa52 fix(nutrition): 와파린 생약 경고 추가`
- push 대상: `origin/feat/db-internal-learning-pipeline`
- push 상태: `68baa52` 팀 remote push 완료

## 수행한 작업

- `backend/Nutrition-backend/src/nutrition/comprehensive.py`의 와파린 상호작용 분기에 은행잎·마늘 보충제 경고를 추가했다.
  - 코드 기반 식별: `ginkgo_mg`, `ginkgo_biloba_mg`, `garlic_mg`
  - 표시명 기반 식별: `ginkgo`, `ginkgo biloba`, `은행잎`, `은행`, `garlic`, `마늘`
- 새 경고 reason은 `warfarin_botanical_bleeding_risk`로 고정했다.
- severity는 기존 와파린 고위험 경고와 동일하게 `high`로 지정했다.
- 사용자 문구는 의료 단정 없이 “출혈 위험 검토가 필요합니다” 수준으로 제한했다.
- `backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`에 은행잎·마늘 각각을 검증하는 회귀 테스트를 추가했다.

## 검증 결과

- comprehensive focused test: 19 passed
- nutrition unit: 61 passed
- full backend unit: 1213 passed
- `black --check` on changed files: passed
- `ruff check` on changed files: passed
- `git diff --check`: passed
- `detect-secrets scan` on changed files: no findings
- `68baa52` push 완료

## 남은 TODO

1. `core-algorithm/06-goal-matrix.md`
   - G6PD 결핍은 현재 `ChronicCondition` enum에 없으므로 별도 profile 확장 설계가 필요하다.
   - 면역억제제·항생제 간격 등 P2 목적별 세부 약물 분기는 별도 scope로 남긴다.

2. `core-algorithm/05-nutrition-diagnosis.md`
   - 영양 진단 분류명(EAR/RDA/AI/UL 기반 신규 status)과 현재 API 응답 용어의 최종 정렬은 아직 completion audit 대상이다.
   - 만성질환 일반 KDRIs 보류 경로는 기존 guidance/deficiency path와 함께 추가 대조가 필요하다.

3. mobile/API 표시
   - `warfarin_botanical_bleeding_risk` reason을 5-card UI에서 기존 high caution과 동일한 우선순위로 노출하는지 확인이 필요하다.

## 주의할 파일/커밋 제외 항목

- 커밋 금지:
  - `.env`
  - Supabase service role key
  - ngrok token/public URL
  - raw OCR text
  - provider raw payload
  - image bytes
  - object URI/path
  - signed URL/public URL
  - 개인 로컬 절대 경로가 포함된 metadata
- 현재 유지 중인 untracked 제외 항목:
  - `.omc/`
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
- 음식 YOLO `best.pt`는 로컬 ignored artifact로 유지한다.
  - `runs/food_yolo/exp01_yolov8n_baseline_pc1_b48_w8_cache_disk_det_true/weights/best.pt`
