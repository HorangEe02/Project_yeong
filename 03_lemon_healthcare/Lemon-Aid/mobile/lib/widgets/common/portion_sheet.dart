// widgets/common/portion_sheet.dart — 섭취량 조절 바텀시트 (figma 959:80)
//
// 음식 후보를 고른 뒤 섭취량(인분)을 조정한다.
//   - 프리셋 칩: ½ / 1 / 1.5 / 2 인분 (가이드 ④-1 · figma 16-④)
//   - 스테퍼: 0.25 인분 단위 가감 (0.25 ~ 9.75 범위)
//   - 그램 환산 안내: 1인분 ≈ kGramsPerServing(기본 100g) 기준 단순 곱
//
// 결과는 [PortionSelection] (portionAmount/portionUnit) 으로 돌려준다.
// 섭취량 환산·payload 필드명은 가이드 ⑤ 표 기준: portion_amount / portion_unit.
//
// 표시만 담당 — 숫자(%)·금칙어(진단/처방/치료/효능) 없음.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../utils/design_tokens_v2.dart';

/// 1인분을 그램으로 환산할 때 쓰는 기본 기준치 (단순 안내용).
const double kGramsPerServing = 100;

/// 섭취량 프리셋 칩 값 (인분).
const List<double> kPortionPresets = <double>[0.5, 1, 1.5, 2];

/// 스테퍼 한 칸 (인분).
const double kPortionStep = 0.25;

/// 섭취량 하한·상한 (인분).
const double kMinPortion = 0.25;
const double kMaxPortion = 9.75;

/// 섭취량 선택 결과.
class PortionSelection {
  /// 섭취량 선택을 만든다.
  const PortionSelection({required this.portionAmount, required this.portionUnit});

  /// 선택된 섭취량 (인분).
  final double portionAmount;

  /// 섭취 단위 — 항상 'serving'(인분) 고정.
  final String portionUnit;
}

/// 인분 값을 사람이 읽기 좋은 한국어 라벨로 바꾼다.
///
/// 0.5 → '½인분', 1 → '1인분', 1.5 → '1.5인분'.
String formatPortionLabel(double amount) {
  if (amount == 0.5) return '½인분';
  // 정수면 소수점 제거, 아니면 최대 2자리에서 꼬리 0 제거.
  final String number = amount == amount.roundToDouble()
      ? amount.toStringAsFixed(0)
      : amount
            .toStringAsFixed(2)
            .replaceFirst(RegExp(r'0+$'), '')
            .replaceFirst(RegExp(r'\.$'), '');
  return '$number인분';
}

/// 인분 → 그램 단순 환산 라벨 (예: '약 150g').
///
/// 기준치 [gramsPerServing] 가 null 이거나 0 이하이면 null 을 돌려준다(숨김).
String? formatPortionGrams(double amount, {double? gramsPerServing}) {
  final double base = gramsPerServing ?? kGramsPerServing;
  if (base <= 0) return null;
  final double grams = amount * base;
  final String number = grams == grams.roundToDouble()
      ? grams.toStringAsFixed(0)
      : grams
            .toStringAsFixed(1)
            .replaceFirst(RegExp(r'0+$'), '')
            .replaceFirst(RegExp(r'\.$'), '');
  return '약 ${number}g';
}

/// 인분 값을 허용 범위로 자른다.
double clampPortion(double amount) {
  if (amount < kMinPortion) return kMinPortion;
  if (amount > kMaxPortion) return kMaxPortion;
  // 0.25 격자에 맞춘다.
  final double snapped = (amount / kPortionStep).round() * kPortionStep;
  return double.parse(snapped.toStringAsFixed(2));
}

/// 섭취량 조절 바텀시트를 띄우고 선택 결과를 돌려준다.
///
/// 취소하면 null 을 돌려준다.
Future<PortionSelection?> showPortionSheet(
  BuildContext context, {
  required String foodName,
  double initialAmount = 1,
  double? gramsPerServing,
}) {
  return showModalBottomSheet<PortionSelection>(
    context: context,
    backgroundColor: Colors.transparent,
    barrierColor: const Color(0x80141A2C),
    isScrollControlled: true,
    showDragHandle: false,
    builder: (BuildContext sheetContext) => _PortionSheet(
      foodName: foodName,
      initialAmount: clampPortion(initialAmount),
      gramsPerServing: gramsPerServing,
    ),
  );
}

class _PortionSheet extends StatefulWidget {
  const _PortionSheet({
    required this.foodName,
    required this.initialAmount,
    this.gramsPerServing,
  });

  final String foodName;
  final double initialAmount;
  final double? gramsPerServing;

  @override
  State<_PortionSheet> createState() => _PortionSheetState();
}

class _PortionSheetState extends State<_PortionSheet> {
  late double _amount = widget.initialAmount;

  void _setAmount(double next) {
    final double clamped = clampPortion(next);
    if (clamped == _amount) return;
    HapticFeedback.selectionClick();
    setState(() => _amount = clamped);
  }

  @override
  Widget build(BuildContext context) {
    final String? gramsLabel = formatPortionGrams(
      _amount,
      gramsPerServing: widget.gramsPerServing,
    );
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(28),
          topRight: Radius.circular(28),
        ),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: Color(0x40141A2C),
            blurRadius: 40,
            spreadRadius: -10,
            offset: Offset(0, -20),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  margin: const EdgeInsets.only(top: 4, bottom: AppSpace.lg),
                  decoration: BoxDecoration(
                    color: AppColor.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const Text(
                '얼마나 드셨어요?',
                style: TextStyle(
                  fontFamily: 'Pretendard',
                  fontSize: 19,
                  fontWeight: FontWeight.w800,
                  color: AppColor.ink,
                  letterSpacing: 0,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                widget.foodName,
                style: const TextStyle(
                  fontFamily: 'Pretendard',
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppColor.inkSecondary,
                ),
              ),
              const SizedBox(height: AppSpace.lg),
              // 프리셋 칩 행.
              Wrap(
                spacing: AppSpace.sm,
                runSpacing: AppSpace.sm,
                children: <Widget>[
                  for (final double preset in kPortionPresets)
                    _PortionPresetChip(
                      label: formatPortionLabel(preset),
                      selected: _amount == preset,
                      onTap: () => _setAmount(preset),
                    ),
                ],
              ),
              const SizedBox(height: AppSpace.lg),
              // 스테퍼 + 현재 값 + 그램 환산.
              Row(
                children: <Widget>[
                  _StepperButton(
                    key: const ValueKey<String>('portion-step-down'),
                    icon: Icons.remove_rounded,
                    enabled: _amount > kMinPortion,
                    onTap: () => _setAmount(_amount - kPortionStep),
                  ),
                  Expanded(
                    child: Column(
                      children: <Widget>[
                        Text(
                          formatPortionLabel(_amount),
                          key: const ValueKey<String>('portion-amount-label'),
                          style: const TextStyle(
                            fontFamily: 'Pretendard',
                            fontSize: 22,
                            fontWeight: FontWeight.w900,
                            color: AppColor.ink,
                            letterSpacing: 0,
                          ),
                        ),
                        if (gramsLabel != null) ...<Widget>[
                          const SizedBox(height: 2),
                          Text(
                            gramsLabel,
                            style: AppText.caption.copyWith(
                              color: AppColor.inkTertiary,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                  _StepperButton(
                    key: const ValueKey<String>('portion-step-up'),
                    icon: Icons.add_rounded,
                    enabled: _amount < kMaxPortion,
                    onTap: () => _setAmount(_amount + kPortionStep),
                  ),
                ],
              ),
              const SizedBox(height: AppSpace.lg),
              SizedBox(
                width: double.infinity,
                child: AppPrimaryButton(
                  label: '이 양으로 담기',
                  onPressed: () => Navigator.of(context).pop(
                    PortionSelection(
                      portionAmount: _amount,
                      portionUnit: 'serving',
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PortionPresetChip extends StatelessWidget {
  const _PortionPresetChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minWidth: 64, minHeight: 48),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.lg,
          vertical: AppSpace.md,
        ),
        decoration: BoxDecoration(
          color: selected ? AppColor.brandSoft : AppColor.sunken,
          borderRadius: BorderRadius.circular(AppRadius.full),
          border: Border.all(
            color: selected ? AppColor.brand : AppColor.border,
            width: selected ? 1.5 : 1,
          ),
        ),
        alignment: Alignment.center,
        child: Text(
          label,
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontSize: 15,
            fontWeight: FontWeight.w700,
            color: selected ? AppColor.brandDeep : AppColor.inkSecondary,
            letterSpacing: 0,
          ),
        ),
      ),
    );
  }
}

class _StepperButton extends StatelessWidget {
  const _StepperButton({
    super.key,
    required this.icon,
    required this.enabled,
    required this.onTap,
  });

  final IconData icon;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: enabled ? onTap : null,
      child: Container(
        width: 52,
        height: 52,
        decoration: BoxDecoration(
          color: enabled ? AppColor.surface : AppColor.sunken,
          borderRadius: BorderRadius.circular(AppRadius.md),
          border: Border.all(
            color: enabled ? AppColor.borderStrong : AppColor.border,
          ),
        ),
        alignment: Alignment.center,
        child: Icon(
          icon,
          size: 24,
          color: enabled ? AppColor.ink : AppColor.inkDisabled,
        ),
      ),
    );
  }
}
