# 2026-05-28 음주 BMI 허리둘레 보조 입력 요약

## 기준 정보

- 작업 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 기준 문서:
  - `docs/Nutrition-docs/core-algorithm/01-bmi-classification.md`
  - `docs/Nutrition-docs/core-algorithm/09-smoking-alcohol-rationale.md`
- 공식 근거:
  - WHO obesity and overweight fact sheet: https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight
  - WHO waist circumference and waist-hip ratio report: https://www.who.int/nutrition/publications/obesity/WHO_report_waistcircumference_and_waisthip_ratio/en/
- 구현 원칙:
  - BMI 자체를 진단으로 표현하지 않고 스크리닝/보조 지표 안내로 제한
  - AUDIT-KR 위험 음주 cut-off 이상이고 허리둘레가 없을 때만 허리둘레 입력 안내
  - 허리둘레가 이미 있으면 WHtR 계산 결과를 사용하고 중복 안내를 반복하지 않음
  - `.env`, ngrok URL/token, raw OCR/provider payload, 이미지 경로, object URI는 기록하지 않음

## 브랜치/커밋 범위

- 적용 커밋: `6aae49b feat(algorithm): 음주 BMI 허리둘레 안내 추가`
- 직전 관련 커밋:
  - `beec93f feat(algorithm): 허리둘레 복부비만 flag 추가`
  - `103cbab docs(todo): 흡연자 비타민C 카드 요약 추가`

## 수행한 작업

- `backend/Nutrition-backend/src/algorithms/bmi.py`
  - `evaluate_bmi()`에 `audit_kr_score` 인자를 추가
  - AUDIT-KR 위험 음주 범위(`>= 3`)이고 `waist_cm`이 없으면 BMI notes에 허리둘레 입력 권장 메시지 추가
- `backend/Nutrition-backend/src/algorithms/activity.py`
  - `ActivityScoreRequest.profile.audit_kr_score`를 BMI 평가 경로로 전달
  - 모바일/백엔드 activity 응답의 `bmi.notes`에서도 동일한 보조 입력 안내가 보이도록 정렬
- `backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py`
  - 위험 음주 + 허리둘레 없음이면 허리둘레 입력 안내가 생성되는 테스트 추가
  - 위험 음주 + 허리둘레 있음이면 중복 안내 없이 WHtR 값이 계산되는 테스트 추가

## 검증 결과

- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py -q --no-cov`
  - 결과: `25 passed`
- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/algorithms -q --no-cov`
  - 결과: `66 passed`
- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/services/test_analysis_results.py backend/Nutrition-backend/tests/unit/services/test_dashboard.py -q --no-cov`
  - 결과: `8 passed`
- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit -q --no-cov`
  - 결과: `1218 passed`
- 통과: `black --check backend/Nutrition-backend/src/algorithms/bmi.py backend/Nutrition-backend/src/algorithms/activity.py backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py`
- 통과: `ruff check backend/Nutrition-backend/src/algorithms/bmi.py backend/Nutrition-backend/src/algorithms/activity.py backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py`
- 통과: `git diff --check`
- 통과: `detect-secrets scan backend/Nutrition-backend/src/algorithms/bmi.py backend/Nutrition-backend/src/algorithms/activity.py backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py`
  - 결과: `"results": {}`
- push 완료: `origin/feat/db-internal-learning-pipeline`

## 남은 TODO

- 식단 입력/meal flow의 주류 카테고리와 자동 kcal 산입이 실제 UI/식단 API에 어떻게 연결되는지 별도 점검 필요
- 음주 다음날 HRrest outlier 처리 함수는 있으나, 실제 건강 데이터 sync 흐름에서 `drinking_next_day_flags`를 어떻게 생성할지 후속 설계 필요
- BMI note를 모바일 UI에서 어디에 노출할지 확인 필요

## 주의할 파일/커밋 제외 항목

- 제외 유지:
  - `.env`
  - ngrok token 또는 public URL
  - raw OCR text/provider payload
  - 이미지 파일 경로, object URI, signed/public URL
  - `mobile/assets/mascot/Mascot_AppIcon_Rebuild_Assets/`
  - `.omc/`
  - `runs/food_yolo/**/best.pt`
- 이번 문서 커밋에는 코드 변경을 다시 포함하지 않고, 이 요약 파일만 stage한다.
