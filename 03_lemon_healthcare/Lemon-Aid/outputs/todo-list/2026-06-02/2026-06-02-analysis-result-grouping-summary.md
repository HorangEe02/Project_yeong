# 2026-06-02 분석 결과 그룹화 구현 요약

> 작성 기준: 2026-06-02
> 대상: `mobile/lib/screens/analysis_result_screen.dart`, `mobile/test/widget/analysis_result_screen_test.dart`

---

## 1. Summary

여러 장의 영양제 사진을 분석했을 때 결과 화면이 "사진 단위"로만 나뉘면 사용자가 어떤 영양제 결과를 보고 있는지 혼동할 수 있다.

이번 변경은 분석 결과를 "영양제 제품 단위"로 묶어 보여주도록 개선한다.

- 제품명/제조사가 있는 전면 라벨 이미지는 제품 식별 기준으로 사용한다.
- 제품명 없이 성분표만 있는 이미지는 직전 제품 그룹에 붙일 수 있으면 같은 영양제로 병합한다.
- 병합된 그룹은 성분 후보, 라벨 섹션, 섭취 방법, 주의사항, evidence span, pipeline metadata를 합쳐 표시한다.
- 상단 탭은 원본 이미지 수가 아니라 병합된 영양제 개수만큼 표시한다.

---

## 2. 변경 내용

### 모바일 화면

- `_supplementReviewPreviews`를 `_supplementReviewGroups` 흐름으로 바꾸었다.
- `_SupplementReviewGroup`과 `_MutableSupplementReviewGroup`을 추가해 표시용 그룹과 병합용 그룹을 분리했다.
- 제품 identity key는 `manufacturer + productName`을 정규화해서 만든다.
- identity가 없는 성분표 이미지는 이전 그룹에 제품 식별 정보가 있고 아직 성분표 근거가 없을 때만 붙인다.
- 병합 preview는 다음 데이터를 중복 제거해 합친다.
  - 성분 후보
  - 라벨 섹션
  - 주의사항
  - 기능성 문구
  - OCR evidence span
  - missing required sections
  - OCR/YOLO/LLM status metadata

### 테스트

- `groups front and facts photos into supplement-level result tabs` 위젯 테스트를 추가했다.
- 테스트 데이터는 4장 preview를 3개 제품 탭으로 묶는 상황을 검증한다.
- 첫 번째 탭은 전면 이미지와 성분표 이미지를 병합해 `Lemon Multi`와 `Vitamin C 500 mg`를 함께 보여준다.
- 두 번째/세 번째 탭은 각각 `Omega Plus`, `Magnesium Calm`으로 전환된다.

---

## 3. 해결한 문제

- 전면 사진과 성분표 사진을 따로 분석하면 한 영양제가 두 결과로 쪼개져 보이는 문제
- 여러 영양제를 이어서 분석했을 때 이전 결과와 현재 결과를 혼동할 수 있는 문제
- 성분표 이미지만 OCR에 성공한 경우 제품명 카드와 성분 카드가 서로 다른 결과처럼 보이는 문제
- 탭 수가 실제 영양제 수보다 많아져 발표/시연 중 사용자가 헷갈리는 문제

---

## 4. 참고한 공식 문서

- Flutter `ChoiceChip`: https://api.flutter.dev/flutter/material/ChoiceChip-class.html
- Flutter `ValueKey`: https://api.flutter.dev/flutter/foundation/ValueKey-class.html
- Flutter widget testing: https://docs.flutter.dev/cookbook/testing/widget/introduction

---

## 5. 다음 보완 후보

- backend에서 `multi_image_group_id`와 image role을 더 명확히 내려주면 client grouping heuristic을 줄일 수 있다.
- 실제 OCR 결과에서 제품명이 전혀 없는 성분표 이미지가 먼저 들어오는 순서도 별도 테스트할 필요가 있다.
- 동일 제조사의 유사 제품명이 연속 분석될 때 identity 충돌을 UI에 더 명확히 표시하는 보완이 가능하다.
