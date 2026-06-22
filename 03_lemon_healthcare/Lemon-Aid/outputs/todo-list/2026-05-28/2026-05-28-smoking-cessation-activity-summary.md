# 2026-05-28 금연 활동 안내 분리 요약

## 기준 정보

- 작업 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 기준 문서: `docs/Nutrition-docs/core-algorithm/09-smoking-alcohol-rationale.md`
- 학술 근거:
  - Aubin HJ, Farley A, Lycett D, Lahmek P, Aveyard P. Weight gain in smokers after quitting cigarettes: meta-analysis. BMJ 2012. https://www.bmj.com/content/345/bmj.e4439
  - PubMed record: https://pubmed.ncbi.nlm.nih.gov/22782848/
- 구현 원칙:
  - 현재 흡연자와 금연 1년 이내 사용자의 메시지를 분리
  - 금연 1년 이내 사용자는 금연 유지와 활동 루틴 중심으로 안내
  - 활동 점수는 질환 개선이나 체중 변화 예측으로 단정하지 않음
  - `.env`, ngrok URL/token, raw OCR/provider payload, 이미지 경로, object URI는 기록하지 않음

## 브랜치/커밋 범위

- 적용 커밋: `a688fe6 fix(algorithm): 금연 활동 안내 분리`
- 직전 관련 커밋:
  - `6aae49b feat(algorithm): 음주 BMI 허리둘레 안내 추가`
  - `53ccc23 docs(todo): 음주 BMI 허리둘레 안내 요약 추가`

## 수행한 작업

- `backend/Nutrition-backend/src/algorithms/activity.py`
  - 현재 흡연 상태(`current_light`, `current_heavy`)와 금연 1년 이내(`former_lt_1y`)를 메시지 분기에서 분리
  - 현재 흡연자는 기존 금연 상담/흡연 위해 상쇄 금지 메시지를 유지
  - 금연 1년 이내 사용자는 체중 변화 가능성과 금연 유지/활동 루틴 확인 메시지를 받도록 조정
  - 기존 v4 활동 동기 가중치의 `max()` 규칙과 multiplier 값은 유지
- `backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py`
  - 금연 1년 이내 사용자가 흡연 중 문구를 받지 않는 회귀 테스트 추가
  - `former_lt_1y` multiplier `1.05` 유지 확인

## 검증 결과

- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py -q --no-cov`
  - 결과: `26 passed`
- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/algorithms -q --no-cov`
  - 결과: `67 passed`
- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit -q --no-cov`
  - 결과: `1219 passed`
- 통과: `black --check backend/Nutrition-backend/src/algorithms/activity.py backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py`
- 통과: `ruff check backend/Nutrition-backend/src/algorithms/activity.py backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py`
- 통과: `git diff --check`
- 통과: `detect-secrets scan backend/Nutrition-backend/src/algorithms/activity.py backend/Nutrition-backend/tests/unit/algorithms/test_activity_algorithms.py`
  - 결과: `"results": {}`
- push 완료: `origin/feat/db-internal-learning-pipeline`

## 남은 TODO

- 금연 후 체중 변화 안내를 체중 예측 UX에 별도 연결할지 검토
- 금연 유지 리소스 또는 상담 안내 문구를 서비스 정책 문서와 맞춰 확정 필요
- 자체 사용자 데이터가 쌓이면 금연 상태별 가중치 보정 여부를 재검토

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
