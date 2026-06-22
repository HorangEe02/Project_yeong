# 2026-05-28 BMI 허리둘레 보완 지표 적용 요약

## 기준 정보

- 작성일: 2026-05-28
- 대상 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 적용 커밋: `beec93f feat(algorithm): 허리둘레 복부비만 flag 추가`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/01-bmi-classification.md`
  - `docs/Nutrition-docs/core-algorithm/00-overview-and-evaluation.md`
- 확인 근거:
  - KSSO 2022 obesity guideline diagnosis update: https://pmc.ncbi.nlm.nih.gov/articles/PMC10327686/
  - KSSO 2022 obesity guideline treatment/comorbidity update: https://pmc.ncbi.nlm.nih.gov/articles/PMC10088549/

## 브랜치/커밋 범위

- 직전 기준 head: `702dcd7 docs(todo): 와파린 생약 경고 요약 추가`
- 이번 phase head: `beec93f feat(algorithm): 허리둘레 복부비만 flag 추가`
- push 대상: `origin/feat/db-internal-learning-pipeline`
- push 상태: `beec93f` 팀 remote push 완료

## 수행한 작업

- `backend/Nutrition-backend/src/models/schemas/algorithm.py`의 `BMIResult`에 `waist_circumference_obesity` 필드를 추가했다.
- `backend/Nutrition-backend/src/algorithms/bmi.py`에 KSSO 성별 허리둘레 기준을 추가했다.
  - 남성: 90 cm 이상
  - 여성: 85 cm 이상
- 기존 `central_obesity`는 WHtR 0.5 기준으로 유지하고, 새 필드는 성별별 허리둘레 기준으로 별도 계산한다.
- `waist_cm`은 있지만 `sex`가 없으면 성별 기준을 계산하지 않고 `None`을 반환한다.
- 성별 허리둘레 기준에 걸릴 경우 `notes`에 BMI와 함께 확인하라는 안전 문구를 추가한다.
- 활동 알고리즘 단위 테스트에 남성/여성 cutoff와 성별 미입력 fallback을 추가했다.

## 검증 결과

- activity focused test: 23 passed
- algorithms unit: 64 passed
- full backend unit: 1214 passed
- `black --check` on changed files: passed
- `ruff check` on changed files: passed
- `git diff --check`: passed
- `detect-secrets scan` on changed files: no findings
- `beec93f` push 완료

## 남은 TODO

1. `core-algorithm/01-bmi-classification.md`
   - 핸드그립 기반 사르코페니아 의심 flag는 아직 profile/schema 입력이 없어 별도 설계가 필요하다.
   - 고령자 BMI 21-27 “양호 구간” 표시를 mobile card UX에서 어떻게 표현할지 확인해야 한다.

2. `core-algorithm/00-overview-and-evaluation.md`
   - BMI, 활동점수, TDEE, 체중예측은 여러 phase가 반영되었으므로 문서별 completion audit 표가 필요하다.

3. mobile/API 표시
   - `waist_circumference_obesity`가 activity/dashboard 응답에서 UI에 노출되는지 widget smoke가 필요하다.

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
