# 2026-05-28 흡연자 비타민 C 종합 카드 보정 요약

## 기준 정보

- 작업 repo: `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- 작업 브랜치: `feat/db-internal-learning-pipeline`
- 기준 문서: `docs/Nutrition-docs/core-algorithm/09-smoking-alcohol-rationale.md`
- 공식 근거: NIH Office of Dietary Supplements Vitamin C Health Professional Fact Sheet
  - https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/
- 구현 원칙:
  - 현재 흡연자만 비타민 C 기준 섭취량에 +35mg 보정 적용
  - 금연 1년 이내 상태는 베타카로틴/비타민 A 안전 경고에는 포함하되, 비타민 C +35mg 기준 보정에는 포함하지 않음
  - OCR 원문, provider payload, 이미지 경로, `.env`, ngrok URL/token, object URI는 기록하지 않음

## 브랜치/커밋 범위

- 적용 커밋: `da17171 fix(nutrition): 흡연자 비타민C 카드 보정`
- 직전 관련 커밋:
  - `beec93f feat(algorithm): 허리둘레 복부비만 flag 추가`
  - `b44fe07 docs(todo): BMI 허리둘레 보정 요약 추가`

## 수행한 작업

- `backend/Nutrition-backend/src/nutrition/comprehensive.py`
  - 종합 5-card 부족 영양소 산출 함수가 `UserProfileInput`을 함께 받도록 변경
  - `vitamin_c_mg` 기준을 현재 흡연자(`current_light`, `current_heavy`)에 한해 `100mg -> 135mg`로 보정
  - 보정이 적용된 경우 `warnings`에 `smoker_vitamin_c_reference_iom_plus_35mg` 토큰을 남겨 기준 출처 라벨링이 가능하도록 함
- `backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`
  - 현재 흡연자에서 비타민 C 120mg 입력 시 135mg 기준 부족으로 판정되는 회귀 테스트 추가
  - 금연 1년 이내(`former_lt_1y`)는 비타민 C 기준을 올리지 않는 회귀 테스트 추가
  - 다른 KDRIs 부족 항목이 상위 5개 카드 산출을 가리지 않도록 테스트 입력 헬퍼를 추가

## 검증 결과

- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py -q --no-cov`
  - 결과: `21 passed`
- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit/nutrition -q --no-cov`
  - 결과: `63 passed`
- 통과: `PYTHONPATH=backend/Nutrition-backend:backend /opt/anaconda3/bin/python -m pytest backend/Nutrition-backend/tests/unit -q --no-cov`
  - 결과: `1216 passed`
- 통과: `black --check backend/Nutrition-backend/src/nutrition/comprehensive.py backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`
- 통과: `ruff check backend/Nutrition-backend/src/nutrition/comprehensive.py backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`
- 통과: `git diff --check`
- 통과: `detect-secrets scan backend/Nutrition-backend/src/nutrition/comprehensive.py backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`
  - 결과: `"results": {}`
- push 완료: `origin/feat/db-internal-learning-pipeline`

## 남은 TODO

- `09-smoking-alcohol-rationale.md`의 phase 2 항목 중 남은 gap 재점검
  - BMI 음주자 WHtR 보조 입력
  - HRrest 음주 다음날 outlier 처리
  - 흡연자 금연 권고 메시지의 사용자 노출 위치 정리
- 종합 카드의 inline `_KDRIS_TABLE`을 정식 KDRIs 룩업 모듈과 통합할지 별도 설계 필요
- 비타민 C +35mg 기준을 UI에 사용자 친화 문구로 노출할 때는 "참고 기준"임을 명시하고 의료 단정 표현을 피해야 함

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
