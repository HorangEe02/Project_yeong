# ROI-first oracle 평가 — 결과와 해석 (2026-06-08)

목적: detector 학습 전, CLOVA 박스를 oracle ROI로 써서 "ROI scoping이 precision/F1을 0.90 근처로 올리는가"를 holdout 52장에서 실증.

## 결과 (full-image vs ROI-first oracle, holdout 52)
| metric | full-image | ROI-first | delta |
|---|---:|---:|---:|
| char precision | 0.3031 | 0.3386 | +0.036 |
| char recall | 0.5372 | **0.1978** | **−0.339** |
| char F1 | 0.3338 | **0.1773** | **−0.157** |
| field_match macro | 0.4864 | 0.1510 | −0.335 |
| ingredient_recall | 0.4658 | 0.1849 | −0.281 |

crop 통계: 36 cropped(평균 면적 **3.7%**) / 16 fallback(full) / 52 scored.

## 해석 — 전략 반증이 아니라 oracle 결함
1. **키워드 박스가 영역이 아님**: `_classify_section`은 산발적 amount *토큰*만 태깅 → union crop이 3.7% 슬라이버로 수축 → **성분 내용 대부분이 잘려 recall 붕괴**. (실제 성분표는 페이지의 3.7%보다 훨씬 큼.)
2. **ingredient-only ROI는 타 GT 섹션을 버림**: GT는 ingredient+intake(+others) 다중 섹션인데 crop이 ingredient 영역뿐 → intake/precautions GT 텍스트가 crop 밖 → recall 추가 손실.
3. precision은 미미하게만 올라(+0.036) — 잘라낸 영역이 정답도 같이 버려서 precision 이득도 상쇄.

## 결론 (중요)
- **ROI scoping의 이득은 "모든 GT 섹션을 정확한 경계로 덮는 detector"가 있어야 실현**된다. 키워드/sparse-box로는 영역 정의 불가(앞선 약지도 93% 미분류와 동일 한계 재확인).
- precision scope-cap **이론**(full-image char-LCS 상한 ~0.68–0.71)은 유효하나, **실증적 ROI 이득은 진짜 section bbox(사람 주석 → 학습된 다중섹션 detector) 없이는 측정 불가**.
- 즉 이번 oracle은 "ROI가 나쁘다"가 아니라 **"가짜 oracle(키워드 박스)로는 검증 불가"**를 보여줌.

## 권고 — 다음 행동
1. **Stage 3 사람 bbox 리뷰가 진짜 경로**: 후보 이미지에 대해 운영자가 8섹션(특히 ingredient_amounts 전체 표 + intake_method) bbox를 정확히 그림 → 그 박스로 (a) detector 학습, (b) ROI-first 재평가(진짜 oracle = 사람 박스). 이때 비로소 0.90 도달 여부가 측정됨.
2. (선택) 임시 oracle 개선: crop을 "분류 박스의 tight union"이 아니라 **full-width 세로 밴드(분류 박스 y범위 ± 여유)** + 모든 GT 섹션 밴드 합집합으로 확장하면 recall 손실을 줄일 수 있음(추가 CLOVA 1패스). 단 키워드 한계로 상한은 제한적 → 사람 주석이 정답.
3. recognizer(p10)는 충분(val 0.80). 투자는 **section 주석/검출기**에 집중.

## 코드
- `build_roi_first_oracle_bundle.py`: CLOVA oracle crop → 미러 번들 → 기존 eval 재사용. (GT_TO_SECTION 매핑으로 `ingredients`→`ingredient_amounts` 등 정합.) 향후 detector/사람 박스 입력으로 재사용 가능.
- 환경 주의: 백그라운드(detached, 비대화형) 셸은 프로필 미source → CLOVA env 부재. 실행 시 `set -a; . .env; set +a` 필요(검증됨).

> 산출물(eval/summary/crop bundle)은 gitignored reconciled/·datasets/. 본 문서는 수치/해석만.
