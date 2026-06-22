// widgets/common/food_candidate_list.dart — 음식 후보 선택 리스트 (figma 06 · 852:23)
//
// 카메라 음식 분석 후 백엔드 후보(MealFoodCandidate[])를 하나의 카드 안에
// 구분선으로 나눠 보여주고 하나를 단일 선택(라디오)하게 한다 (figma 06 인식 결과).
//   - 후보 행: 썸네일 자리 + 음식명 + 일치 등급(ConfidenceGradeChip, % 비노출)
//              + 예상 영양 요약(kcal·탄단지 — null 필드는 숨김)
//   - 선택 상태: brandSoft 행 배경 + 체크 아이콘
//   - 섭취량: 후보 카드 아래 별도 행 — 탭 → 호출부에서 섭취량 시트 표시
//
// 표시만 담당 — 선택/섭취량 변경 콜백은 호출부 책임.
// 신뢰도 %·금칙어(진단/처방/치료/효능) 노출 없음.

import 'package:flutter/material.dart';

import '../../features/supplements/supplement_models.dart';
import '../../utils/design_tokens_v2.dart';
import 'confidence_grade_chip.dart';
import 'portion_sheet.dart';

/// 음식 후보 단일 선택 리스트.
class FoodCandidateList extends StatelessWidget {
  /// 후보 선택 리스트를 만든다.
  const FoodCandidateList({
    super.key,
    required this.candidates,
    required this.selectedIndex,
    required this.onSelect,
    required this.portionAmount,
    required this.onAdjustPortion,
  });

  /// 백엔드가 돌려준 음식 후보 목록.
  final List<MealFoodCandidate> candidates;

  /// 현재 선택된 후보 인덱스 (없으면 null).
  final int? selectedIndex;

  /// 후보 선택 콜백.
  final ValueChanged<int> onSelect;

  /// 선택된 후보의 현재 섭취량 (인분).
  final double portionAmount;

  /// 섭취량 조절 탭 콜백.
  final VoidCallback onAdjustPortion;

  bool get _hasSelection =>
      selectedIndex != null &&
      selectedIndex! >= 0 &&
      selectedIndex! < candidates.length;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        const Text(
          '어떤 음식이 맞나요?',
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontSize: 18,
            fontWeight: FontWeight.w900,
            color: AppColor.ink,
            letterSpacing: 0,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '가장 비슷한 음식을 하나 골라 주세요.',
          style: AppText.caption.copyWith(color: AppColor.inkTertiary),
        ),
        const SizedBox(height: AppSpace.md),
        // 후보 그룹 카드 — 하나의 카드 안에 구분선으로 행 분리 (figma 06).
        Container(
          decoration: BoxDecoration(
            color: AppColor.surface,
            borderRadius: BorderRadius.circular(AppRadius.lg),
            border: Border.all(color: AppColor.border),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.lg),
            child: Column(
              children: <Widget>[
                for (
                  int index = 0;
                  index < candidates.length;
                  index++
                ) ...<Widget>[
                  _FoodCandidateRow(
                    candidate: candidates[index],
                    selected: selectedIndex == index,
                    onTap: () => onSelect(index),
                  ),
                  if (index != candidates.length - 1)
                    const Divider(
                      height: 1,
                      thickness: 1,
                      color: AppColor.border,
                    ),
                ],
              ],
            ),
          ),
        ),
        // 섭취량 — 선택된 후보가 있을 때만, 카드 아래 별도 행 (figma 06).
        if (_hasSelection) ...<Widget>[
          const SizedBox(height: AppSpace.md),
          _PortionRow(portionAmount: portionAmount, onTap: onAdjustPortion),
        ],
      ],
    );
  }
}

class _FoodCandidateRow extends StatelessWidget {
  const _FoodCandidateRow({
    required this.candidate,
    required this.selected,
    required this.onTap,
  });

  final MealFoodCandidate candidate;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final String? nutritionSummary = _nutritionSummary(candidate);
    return Material(
      color: selected ? AppColor.brandSoft : AppColor.surface,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: <Widget>[
              // 썸네일 자리 (백엔드 후보 이미지 미노출 — placeholder).
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppColor.sunken,
                  borderRadius: BorderRadius.circular(AppRadius.sm),
                ),
                alignment: Alignment.center,
                child: const Icon(
                  Icons.restaurant_rounded,
                  size: 20,
                  color: AppColor.inkTertiary,
                ),
              ),
              const SizedBox(width: AppSpace.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      candidate.displayName,
                      style: const TextStyle(
                        fontFamily: 'Pretendard',
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: AppColor.ink,
                        letterSpacing: 0,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: ConfidenceGradeChip(
                        confidence: candidate.confidence,
                        compact: true,
                      ),
                    ),
                    if (nutritionSummary != null) ...<Widget>[
                      const SizedBox(height: 5),
                      Text(
                        nutritionSummary,
                        style: AppText.caption.copyWith(
                          color: AppColor.inkSecondary,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              // 단일 선택 — 선택 시 체크, 미선택 시 빈 원 (figma 06).
              Icon(
                selected ? Icons.check_circle_rounded : Icons.circle_outlined,
                size: 24,
                color: selected ? AppColor.brand : AppColor.inkDisabled,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PortionRow extends StatelessWidget {
  const _PortionRow({required this.portionAmount, required this.onTap});

  final double portionAmount;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.md),
        child: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpace.md,
            vertical: AppSpace.md,
          ),
          decoration: BoxDecoration(
            color: AppColor.surface,
            borderRadius: BorderRadius.circular(AppRadius.md),
            border: Border.all(color: AppColor.border),
          ),
          child: Row(
            children: <Widget>[
              Icon(
                Icons.rice_bowl_rounded,
                size: 18,
                color: AppColor.brandDeep,
              ),
              const SizedBox(width: AppSpace.sm),
              Text(
                '섭취량',
                style: AppText.caption.copyWith(
                  color: AppColor.inkSecondary,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const Spacer(),
              Text(
                formatPortionLabel(portionAmount),
                key: const ValueKey<String>('candidate-portion-label'),
                style: const TextStyle(
                  fontFamily: 'Pretendard',
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: AppColor.ink,
                  letterSpacing: 0,
                ),
              ),
              const SizedBox(width: 4),
              const Icon(
                Icons.tune_rounded,
                size: 18,
                color: AppColor.inkTertiary,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 후보의 예상 영양을 한 줄 요약으로 만든다 (null 필드는 생략).
///
/// 모두 null 이면 null 을 돌려준다(요약 행 숨김).
String? _nutritionSummary(MealFoodCandidate candidate) {
  final List<String> parts = <String>[
    if (candidate.kcal != null) '${_round(candidate.kcal!)}kcal',
    if (candidate.carbG != null) '탄 ${_round(candidate.carbG!)}g',
    if (candidate.proteinG != null) '단 ${_round(candidate.proteinG!)}g',
    if (candidate.fatG != null) '지 ${_round(candidate.fatG!)}g',
  ];
  if (parts.isEmpty) return null;
  return parts.join(' · ');
}

String _round(double value) => value.round().toString();
