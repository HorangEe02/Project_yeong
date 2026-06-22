// widgets/common/capture_guide_modal.dart — 촬영 가이드 모달 (figma 920:23)
//
// 모드별(영양제/식단) 첫 진입 1회 노출하는 촬영 수칙 안내.
//   - 마스코트 일러스트 + 수칙 3줄(프레임 안에 / 흔들림 없이 / 글자가 보이게)
//   - [다시 보지 않기] 체크 + [촬영 시작] CTA
//
// 결과 [CaptureGuideResult] 로 '다시 보지 않기' 체크 여부를 돌려준다.
// 영속화(모드별 키)는 호출부가 LocalPrefs 로 처리한다 — 이 위젯은 표시·수집만.
//
// 모든 문구 해요체 · 금칙어(진단/처방/치료/효능) 없음.

import 'dart:ui';

import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';
import '../../utils/mascot_poses.dart';

/// 촬영 가이드 모달 결과.
class CaptureGuideResult {
  /// 결과를 만든다.
  const CaptureGuideResult({required this.dismissedForever});

  /// '다시 보지 않기' 체크 여부.
  final bool dismissedForever;
}

/// 촬영 가이드 한 줄 수칙.
class _GuideRule {
  const _GuideRule({
    required this.icon,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String body;
}

const List<_GuideRule> _kGuideRules = <_GuideRule>[
  _GuideRule(
    icon: Icons.crop_free_rounded,
    title: '프레임 안에 담아 주세요',
    body: '가이드 사각형 안에 가득 차게 맞춰 주세요.',
  ),
  _GuideRule(
    icon: Icons.back_hand_rounded,
    title: '흔들림 없이 잠깐 멈춰 주세요',
    body: '손을 고정하면 더 또렷하게 찍혀요.',
  ),
  _GuideRule(
    icon: Icons.text_fields_rounded,
    title: '글자가 잘 보이게 해주세요',
    body: '제품명과 성분 글자가 또렷하면 인식이 잘 돼요.',
  ),
];

/// 촬영 가이드 모달을 띄우고 결과를 돌려준다.
///
/// 배경 탭으로 닫으면 null 을 돌려준다(이 경우 '촬영 시작' 아님).
Future<CaptureGuideResult?> showCaptureGuideModal(
  BuildContext context, {
  required bool isMeal,
}) {
  return showGeneralDialog<CaptureGuideResult>(
    context: context,
    barrierDismissible: true,
    barrierLabel: 'capture-guide',
    barrierColor: const Color(0x59141A2C),
    transitionDuration: const Duration(milliseconds: 220),
    transitionBuilder:
        (
          BuildContext _,
          Animation<double> anim,
          Animation<double> _,
          Widget child,
        ) {
          final CurvedAnimation curved = CurvedAnimation(
            parent: anim,
            curve: Curves.easeOutCubic,
          );
          return Opacity(
            opacity: curved.value,
            child: Transform.scale(
              scale: 0.96 + 0.04 * curved.value,
              child: child,
            ),
          );
        },
    pageBuilder: (BuildContext _, Animation<double> _, Animation<double> _) =>
        _CaptureGuideModal(isMeal: isMeal),
  );
}

class _CaptureGuideModal extends StatefulWidget {
  const _CaptureGuideModal({required this.isMeal});

  final bool isMeal;

  @override
  State<_CaptureGuideModal> createState() => _CaptureGuideModalState();
}

class _CaptureGuideModalState extends State<_CaptureGuideModal> {
  bool _dismissForever = false;

  @override
  Widget build(BuildContext context) {
    final String title = widget.isMeal ? '식단 촬영 팁' : '영양제 촬영 팁';
    return BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 2, sigmaY: 2),
      child: Center(
        child: Material(
          color: Colors.transparent,
          child: Container(
            width: 340,
            padding: const EdgeInsets.fromLTRB(24, 24, 24, 20),
            decoration: BoxDecoration(
              color: AppColor.surface,
              borderRadius: BorderRadius.circular(28),
              boxShadow: AppShadow.elev3,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Center(
                  child: Container(
                    width: 84,
                    height: 84,
                    decoration: BoxDecoration(
                      color: AppColor.brandSoft,
                      shape: BoxShape.circle,
                    ),
                    padding: const EdgeInsets.all(AppSpace.md),
                    child: Image.asset(
                      MascotFor.camera.asset,
                      fit: BoxFit.contain,
                      errorBuilder: (BuildContext _, Object _, StackTrace? _) =>
                          Icon(
                            Icons.photo_camera_rounded,
                            size: 36,
                            color: AppColor.brand,
                          ),
                    ),
                  ),
                ),
                const SizedBox(height: AppSpace.lg),
                Center(
                  child: Text(
                    title,
                    style: const TextStyle(
                      fontFamily: 'Pretendard',
                      fontSize: 20,
                      fontWeight: FontWeight.w900,
                      color: AppColor.ink,
                      letterSpacing: 0,
                    ),
                  ),
                ),
                const SizedBox(height: AppSpace.lg),
                for (
                  int index = 0;
                  index < _kGuideRules.length;
                  index++
                ) ...<Widget>[
                  _GuideRuleRow(rule: _kGuideRules[index]),
                  if (index != _kGuideRules.length - 1)
                    const SizedBox(height: AppSpace.md),
                ],
                const SizedBox(height: AppSpace.lg),
                _DismissForeverToggle(
                  value: _dismissForever,
                  onChanged: (bool value) =>
                      setState(() => _dismissForever = value),
                ),
                const SizedBox(height: AppSpace.md),
                SizedBox(
                  width: double.infinity,
                  child: AppPrimaryButton(
                    label: '촬영 시작',
                    onPressed: () => Navigator.of(context).pop(
                      CaptureGuideResult(dismissedForever: _dismissForever),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _GuideRuleRow extends StatelessWidget {
  const _GuideRuleRow({required this.rule});

  final _GuideRule rule;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: AppColor.sunken,
            borderRadius: BorderRadius.circular(AppRadius.sm),
          ),
          alignment: Alignment.center,
          child: Icon(rule.icon, size: 20, color: AppColor.brandDeep),
        ),
        const SizedBox(width: AppSpace.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                rule.title,
                style: const TextStyle(
                  fontFamily: 'Pretendard',
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                  color: AppColor.ink,
                  letterSpacing: 0,
                  height: 1.3,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                rule.body,
                style: AppText.caption.copyWith(color: AppColor.inkSecondary),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _DismissForeverToggle extends StatelessWidget {
  const _DismissForeverToggle({required this.value, required this.onChanged});

  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => onChanged(!value),
        borderRadius: BorderRadius.circular(AppRadius.sm),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            children: <Widget>[
              Icon(
                value
                    ? Icons.check_box_rounded
                    : Icons.check_box_outline_blank_rounded,
                size: 22,
                color: value ? AppColor.brand : AppColor.inkTertiary,
              ),
              const SizedBox(width: AppSpace.sm),
              Text(
                '다시 보지 않기',
                style: AppText.body.copyWith(
                  color: AppColor.inkSecondary,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
