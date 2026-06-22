# 2026-06-01 분석 결과 검토 UI 구현 요약

> 작성 기준: 2026-06-01
> 범위: Flutter 모바일 `AnalysisResultScreen`의 OCR 근거 확인, 성분 선택/수정, 누락 섹션 안내, 다중 영양제 결과 전환

---

## 1. Summary

분석 후 결과 화면에서 사용자가 OCR/YOLO/LLM 후보를 맹목적으로 저장하지 않도록, 저장 전 검토 UI를 강화했다.

핵심 변화는 다음과 같다.

- 저장 후보/검토 후보 요약 박스를 누르면 OCR에서 얻은 텍스트 근거를 표로 확인할 수 있다.
- 상세 성분 및 함량은 표 형태로 보여주고, 각 성분 앞 체크박스로 저장 대상을 선택할 수 있다.
- 체크된 성분이 1개일 때 수정 버튼을 누르면 해당 성분만 바로 수정한다.
- 섭취 방법 또는 섭취 시 주의사항이 이미지에 없으면 `해당 이미지에는 해당하는 내용이 없습니다`를 표시하고 추가 촬영을 안내한다.
- 여러 영양제를 함께 분석한 경우 상단 탭으로 각 영양제 결과를 전환한다.

---

## 2. 변경 파일

### 모바일 구현

- `mobile/lib/screens/analysis_result_screen.dart`
  - OCR 텍스트 전체 표 다이얼로그 추가
  - 성분별 체크박스가 포함된 성분/함량 표 추가
  - 선택 성분 단건 수정 흐름 추가
  - 다중 영양제 분석 결과 탭 UI 추가
  - 누락 섹션 안내 문구 및 강조 텍스트 스타일 조정

### 테스트

- `mobile/test/widget/analysis_result_screen_test.dart`
  - OCR 텍스트 표 열기 검증
  - 성분 체크박스 선택 후 선택 성분 수정 검증
  - 섭취 방법/주의사항 누락 문구 검증
  - 다중 영양제 탭 전환 검증
  - 기존 식단 분석 결과 테스트 유지

---

## 3. 구현 의도

기존 화면은 분석 결과가 실패하거나 일부 섹션이 비어 있어도 사용자가 어떤 OCR 근거를 기반으로 후보가 만들어졌는지 확인하기 어려웠다.

이번 변경으로 저장 전 검토 기준을 화면 안에 노출해 다음 문제를 줄인다.

- OCR이 실제 라벨 텍스트를 읽었는지 확인하기 어려운 문제
- 하나의 성분만 수정하려는데 여러 후보를 함께 수정해야 하는 문제
- 섭취 방법/주의사항이 없는 이미지를 정상 분석 결과로 오해하는 문제
- 여러 영양제를 업로드했을 때 현재 보고 있는 결과가 어떤 영양제인지 혼동하는 문제

---

## 4. UI/기능 세부

### OCR 근거 표

- 요약 카드에 `supplement-candidate-summary` key를 부여했다.
- 클릭 시 `OCR 텍스트 전체` 다이얼로그를 표시한다.
- 표 컬럼은 `구역`, `출처`, `텍스트`, `신뢰도`다.
- raw provider payload, 원본 이미지 경로, 로컬 파일 경로는 표시하지 않는다.

### 성분 표와 체크박스

- 성분/함량 표에 `선택`, `성분명`, `함량` 컬럼을 구성했다.
- 체크박스 key는 `ingredient-row-checkbox-<index>`로 테스트 가능하게 했다.
- 기본 선택은 함량과 단위가 있는 후보를 우선한다.
- 함량이 없는 원료 후보는 사용자가 직접 체크하면 저장 대상으로 들어간다.

### 선택 성분 수정

- 체크된 성분이 1개면 `선택 성분 수정` 다이얼로그를 열어 해당 성분만 수정한다.
- 체크된 성분이 0개 또는 여러 개면 기존 다중 성분 선택/수정 흐름을 유지한다.
- 저장 시 선택된 성분만 `UserSupplementCreate.ingredients`로 전달한다.

### 누락 섹션 안내

- `intake_method` 또는 `precautions`가 missing section에 포함되면 본문에 `해당 이미지에는 해당하는 내용이 없습니다`를 표시한다.
- 카드 하단에는 `사진을 더 찍어서 보강해주세요.`를 추가로 표시한다.
- 이전처럼 기본 `daily`를 무조건 보여줘서 실제 라벨에 없는 섭취 방법처럼 보이는 흐름을 제거했다.

### 다중 영양제 탭

- `controller.multiImageAnalysisPreview.previews`가 2개 이상이면 상단에 `ChoiceChip` 탭을 표시한다.
- 탭 라벨은 제품명 또는 첫 성분명을 사용하고, 없으면 `영양제 N`으로 대체한다.
- 탭 전환 시 해당 preview로 입력 필드와 성분 후보를 다시 seed한다.

---

## 5. 참고한 공식 문서

- Flutter `AlertDialog`: https://api.flutter.dev/flutter/material/AlertDialog-class.html
- Flutter `Checkbox`: https://api.flutter.dev/flutter/material/Checkbox-class.html
- Flutter `ChoiceChip`: https://api.flutter.dev/flutter/material/ChoiceChip-class.html
- Flutter `Table`: https://api.flutter.dev/flutter/widgets/Table-class.html

---

## 6. 보안/개인정보 기준

- OCR 전체 표에는 backend가 이미 제한해서 내려준 `evidenceSpans`와 `labelSections`만 표시한다.
- raw OCR 원문 전체, provider payload, 이미지 파일 경로, 로컬 source path는 UI와 문서에 포함하지 않는다.
- `.env`, `.vercel/.env.*.local`, Supabase key, ngrok token은 stage하지 않는다.
