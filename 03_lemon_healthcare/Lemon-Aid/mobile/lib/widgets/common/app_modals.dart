// widgets/common/app_modals.dart — Lemon Aid 모달 디자인 시스템 v1
//
// 출처: Claude Design handoff (2026-05-12 / Lemon Aid Modals.html)
// 시안 채택: 02 Soft Hybrid + 04 BottomSheet + 06 Celebrate
// 톤 원칙: "명확하고 직관적인 Flat 2.0 구조 + 뉴모피즘 부드러운 감성"
//
// 사용:
//   - showAppDialog(...) — Confirm / Alert
//   - showAppBottomSheet(...) — 옵션 리스트 / 폴백
//   - showAppCelebrateDialog(...) — 성취·축하

import 'dart:ui';
import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';

// ════════════════════════════════════════════════════════════════
// 1) AppDialog — Soft Hybrid Confirm
//    카드: bg #EEF1F6, radius 28, 부드러운 그림자 + 내부 흰 라인 inset
//    버튼: 좌측 inset(취소), 우측 brand 솔리드 + glow (Primary)
// ════════════════════════════════════════════════════════════════

Future<bool?> showAppDialog(
  BuildContext context, {
  required String title,
  String? body,
  String primaryLabel = '확인',
  String? secondaryLabel,
  bool dangerSecondary = false,
  bool barrierDismissible = true,
}) {
  return showGeneralDialog<bool>(
    context: context,
    barrierDismissible: barrierDismissible,
    barrierLabel: 'modal',
    barrierColor: const Color(0x59141A2C), // rgba(20,26,44,0.35)
    transitionDuration: const Duration(milliseconds: 220),
    transitionBuilder: (_, anim, _, child) {
      final curved = CurvedAnimation(parent: anim, curve: Curves.easeOutCubic);
      return Opacity(
        opacity: curved.value,
        child: Transform.scale(scale: 0.96 + 0.04 * curved.value, child: child),
      );
    },
    pageBuilder: (_, _, _) => _AppDialog(
      title: title,
      body: body,
      primaryLabel: primaryLabel,
      secondaryLabel: secondaryLabel,
      dangerSecondary: dangerSecondary,
    ),
  );
}

class _AppDialog extends StatelessWidget {
  final String title;
  final String? body;
  final String primaryLabel;
  final String? secondaryLabel;
  final bool dangerSecondary;

  const _AppDialog({
    required this.title,
    this.body,
    required this.primaryLabel,
    this.secondaryLabel,
    this.dangerSecondary = false,
  });

  @override
  Widget build(BuildContext context) {
    return BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 2, sigmaY: 2),
      child: Center(
        child: Material(
          color: Colors.transparent,
          child: Container(
            width: 320,
            padding: const EdgeInsets.fromLTRB(24, 28, 24, 22),
            decoration: BoxDecoration(
              color: AppColor.surface, // #FFFFFF 흰색
              borderRadius: BorderRadius.circular(28),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF141A2C).withValues(alpha: 0.30),
                  blurRadius: 60,
                  spreadRadius: -10,
                  offset: const Offset(0, 30),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontFamily: 'Pretendard',
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: AppColor.ink,
                    letterSpacing: 0,
                    height: 1.3,
                  ),
                ),
                if (body != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    body!,
                    style: const TextStyle(
                      fontFamily: 'Pretendard',
                      fontSize: 14.5,
                      fontWeight: FontWeight.w500,
                      color: AppColor.inkSecondary,
                      height: 1.55,
                    ),
                  ),
                ],
                const SizedBox(height: 24),
                Row(
                  children: [
                    if (secondaryLabel != null) ...[
                      Expanded(
                        flex: 4,
                        child: _NeuInsetButton(
                          label: secondaryLabel!,
                          color: dangerSecondary
                              ? AppColor.danger
                              : AppColor.inkSecondary,
                          onPressed: () => Navigator.of(context).pop(false),
                        ),
                      ),
                      const SizedBox(width: 10),
                    ],
                    Expanded(
                      flex: secondaryLabel != null
                          ? 6
                          : 10, // Primary 약간 더 넓게 (6:4)
                      child: _NeuPrimaryButton(
                        label: primaryLabel,
                        onPressed: () => Navigator.of(context).pop(true),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// 흰 카드 버튼 — Login 의 AppSecondaryButton 과 동일한 톤 (2단 그림자, 보더 X)
class _NeuInsetButton extends StatelessWidget {
  final String label;
  final Color color;
  final VoidCallback onPressed;
  const _NeuInsetButton({
    required this.label,
    required this.color,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        height: 50,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColor.surface,
          borderRadius: BorderRadius.circular(16),
          boxShadow: const [
            // 가까운 그림자 (날카로운 경계)
            BoxShadow(
              color: Color.fromRGBO(140, 155, 175, 0.09),
              blurRadius: 4,
              offset: Offset(0, 2),
            ),
            // 멀리 부드러운 그림자 (떠 있는 입체감)
            BoxShadow(
              color: Color.fromRGBO(140, 155, 175, 0.22),
              blurRadius: 18,
              offset: Offset(0, 8),
            ),
          ],
        ),
        child: Text(
          label,
          maxLines: 1,
          softWrap: false,
          overflow: TextOverflow.visible,
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontSize: 15,
            fontWeight: FontWeight.w700,
            color: color,
          ),
        ),
      ),
    );
  }
}

// Primary brand 버튼 (glow + inset 1px white)
class _NeuPrimaryButton extends StatelessWidget {
  final String label;
  final VoidCallback onPressed;
  const _NeuPrimaryButton({required this.label, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        height: 50,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColor.brand,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: AppColor.brand.withValues(alpha: 0.55),
              blurRadius: 14,
              spreadRadius: -4,
              offset: const Offset(0, 6),
            ),
          ],
          border: Border(
            top: BorderSide(
              color: Colors.white.withValues(alpha: 0.25),
              width: 1,
            ),
          ),
        ),
        child: Text(
          label,
          style: const TextStyle(
            fontFamily: 'Pretendard',
            fontSize: 15,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════
// 2) AppBottomSheet — 옵션 리스트 (드래그 핸들 + 흰 카드 + 행)
// ════════════════════════════════════════════════════════════════

class AppBottomSheetItem {
  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback? onTap;
  const AppBottomSheetItem({
    required this.icon,
    required this.title,
    this.subtitle,
    this.onTap,
  });
}

Future<void> showAppBottomSheet(
  BuildContext context, {
  required String title,
  String? subtitle,
  required List<AppBottomSheetItem> items,
}) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    barrierColor: const Color(0x80141A2C),
    isScrollControlled: true,
    // consent_modal 과 핸들 패턴 통일 — Material 3 기본 핸들 OFF
    showDragHandle: false,
    builder: (_) =>
        _AppBottomSheet(title: title, subtitle: subtitle, items: items),
  );
}

class _AppBottomSheet extends StatelessWidget {
  final String title;
  final String? subtitle;
  final List<AppBottomSheetItem> items;

  const _AppBottomSheet({
    required this.title,
    this.subtitle,
    required this.items,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: AppColor.surface, // #FFFFFF 흰색
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(28),
          topRight: Radius.circular(28),
        ),
        boxShadow: [
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
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 드래그 핸들 — consent_modal 과 통일 (36×4 + border + radius 2)
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
              Text(
                title,
                style: const TextStyle(
                  fontFamily: 'Pretendard',
                  fontSize: 19,
                  fontWeight: FontWeight.w800,
                  color: AppColor.ink,
                  letterSpacing: 0,
                ),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 4),
                Text(
                  subtitle!,
                  style: const TextStyle(
                    fontFamily: 'Pretendard',
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: AppColor.inkSecondary,
                  ),
                ),
              ],
              const SizedBox(height: 18),
              // 흰 카드 + 행 리스트 + 뉴모 작은 그림자
              Container(
                decoration: BoxDecoration(
                  color: AppColor.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppColor.border, width: 1),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x1A8C9BAF),
                      blurRadius: 14,
                      offset: Offset(0, 6),
                    ),
                  ],
                ),
                padding: const EdgeInsets.all(8),
                child: Column(
                  children: List.generate(items.length, (i) {
                    final it = items[i];
                    final last = i == items.length - 1;
                    return _SheetRow(item: it, last: last);
                  }),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SheetRow extends StatelessWidget {
  final AppBottomSheetItem item;
  final bool last;
  const _SheetRow({required this.item, required this.last});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () {
          Navigator.of(context).pop();
          item.onTap?.call();
        },
        borderRadius: BorderRadius.circular(14),
        child: Container(
          padding: const EdgeInsets.fromLTRB(12, 14, 12, 14),
          decoration: BoxDecoration(
            border: last
                ? null
                : const Border(
                    bottom: BorderSide(color: AppColor.border, width: 1),
                  ),
          ),
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: AppColor.brandSoft,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(item.icon, color: AppColor.brand, size: 20),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.title,
                      style: const TextStyle(
                        fontFamily: 'Pretendard',
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: AppColor.ink,
                      ),
                    ),
                    if (item.subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        item.subtitle!,
                        style: const TextStyle(
                          fontFamily: 'Pretendard',
                          fontSize: 12.5,
                          fontWeight: FontWeight.w500,
                          color: AppColor.inkTertiary,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const Icon(
                Icons.chevron_right,
                color: AppColor.inkTertiary,
                size: 20,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════
// 3) AppCelebrateDialog — 성취·축하 (06 Celebrate)
//    노란 원형 아이콘 + 컨페티 점 + 검정 시작하기 버튼
// ════════════════════════════════════════════════════════════════

Future<void> showAppCelebrateDialog(
  BuildContext context, {
  required String title,
  required String body,
  String primaryLabel = '시작하기',
  IconData icon = Icons.check_rounded,
  VoidCallback? onPrimary,
}) {
  return showGeneralDialog<void>(
    context: context,
    barrierDismissible: false,
    barrierLabel: 'celebrate',
    barrierColor: const Color(0x80141A2C),
    transitionDuration: const Duration(milliseconds: 280),
    transitionBuilder: (_, anim, _, child) {
      final curved = CurvedAnimation(parent: anim, curve: Curves.easeOutBack);
      return Opacity(
        opacity: anim.value,
        child: Transform.scale(scale: 0.85 + 0.15 * curved.value, child: child),
      );
    },
    pageBuilder: (_, _, _) => _AppCelebrate(
      title: title,
      body: body,
      primaryLabel: primaryLabel,
      icon: icon,
      onPrimary: onPrimary,
    ),
  );
}

class _AppCelebrate extends StatelessWidget {
  final String title;
  final String body;
  final String primaryLabel;
  final IconData icon;
  final VoidCallback? onPrimary;

  const _AppCelebrate({
    required this.title,
    required this.body,
    required this.primaryLabel,
    required this.icon,
    this.onPrimary,
  });

  @override
  Widget build(BuildContext context) {
    return BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 6, sigmaY: 6),
      child: Center(
        child: Material(
          color: Colors.transparent,
          child: Container(
            width: 320,
            padding: const EdgeInsets.fromLTRB(24, 36, 24, 20),
            decoration: BoxDecoration(
              color: AppColor.surface,
              borderRadius: BorderRadius.circular(28),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x47141A2C),
                  blurRadius: 60,
                  spreadRadius: -12,
                  offset: Offset(0, 24),
                ),
              ],
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(28),
              child: Stack(
                children: [
                  // confetti 점
                  Positioned.fill(
                    child: CustomPaint(painter: _ConfettiPainter()),
                  ),

                  Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // 노란 원형 아이콘
                      Container(
                        width: 88,
                        height: 88,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: RadialGradient(
                            center: const Alignment(-0.4, -0.4),
                            radius: 0.9,
                            colors: [const Color(0xFFFFE066), AppColor.yellow],
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: const Color(
                                0xFFE0AC00,
                              ).withValues(alpha: 0.55),
                              blurRadius: 24,
                              spreadRadius: -8,
                              offset: const Offset(0, 12),
                            ),
                          ],
                          border: Border(
                            top: BorderSide(
                              color: Colors.white.withValues(alpha: 0.6),
                              width: 2,
                            ),
                          ),
                        ),
                        alignment: Alignment.center,
                        child: Icon(icon, color: Colors.white, size: 40),
                      ),
                      const SizedBox(height: 18),
                      Text(
                        title,
                        style: const TextStyle(
                          fontFamily: 'Pretendard',
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          color: AppColor.ink,
                          letterSpacing: 0,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        body,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          fontFamily: 'Pretendard',
                          fontSize: 14.5,
                          fontWeight: FontWeight.w500,
                          color: AppColor.inkSecondary,
                          height: 1.55,
                        ),
                      ),
                      const SizedBox(height: 24),
                      GestureDetector(
                        onTap: () {
                          Navigator.of(context).pop();
                          onPrimary?.call();
                        },
                        child: Container(
                          width: double.infinity,
                          height: 54,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: AppColor.ink,
                            borderRadius: BorderRadius.circular(16),
                            boxShadow: [
                              BoxShadow(
                                color: AppColor.ink.withValues(alpha: 0.40),
                                blurRadius: 18,
                                spreadRadius: -6,
                                offset: const Offset(0, 8),
                              ),
                            ],
                          ),
                          child: Text(
                            primaryLabel,
                            style: const TextStyle(
                              fontFamily: 'Pretendard',
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════
// 4) showInteractionWarningDialog — 소프트 블록 경고 (상호작용 주의)
//    dangerSoft 원 + ⚠ 아이콘, 크림 인포 배너, primary + 회색 텍스트 링크
// ════════════════════════════════════════════════════════════════

Future<void> showInteractionWarningDialog(
  BuildContext context, {
  required String body,
  required VoidCallback onViewDetail,
  required VoidCallback onSaveAnyway,
}) {
  return showGeneralDialog<void>(
    context: context,
    barrierDismissible: false,
    barrierLabel: 'interaction_warning',
    barrierColor: const Color(0x59141A2C),
    transitionDuration: const Duration(milliseconds: 220),
    transitionBuilder: (_, anim, _, child) {
      final curved = CurvedAnimation(parent: anim, curve: Curves.easeOutCubic);
      return Opacity(
        opacity: curved.value,
        child: Transform.scale(scale: 0.96 + 0.04 * curved.value, child: child),
      );
    },
    pageBuilder: (_, _, _) => _InteractionWarningDialog(
      body: body,
      onViewDetail: onViewDetail,
      onSaveAnyway: onSaveAnyway,
    ),
  );
}

class _InteractionWarningDialog extends StatelessWidget {
  final String body;
  final VoidCallback onViewDetail;
  final VoidCallback onSaveAnyway;

  const _InteractionWarningDialog({
    required this.body,
    required this.onViewDetail,
    required this.onSaveAnyway,
  });

  @override
  Widget build(BuildContext context) {
    return BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 2, sigmaY: 2),
      child: Center(
        child: Material(
          color: Colors.transparent,
          child: Container(
            width: 320,
            padding: const EdgeInsets.fromLTRB(24, 28, 24, 22),
            decoration: BoxDecoration(
              color: AppColor.surface,
              borderRadius: BorderRadius.circular(28),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF141A2C).withValues(alpha: 0.30),
                  blurRadius: 60,
                  spreadRadius: -10,
                  offset: const Offset(0, 30),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // dangerSoft 원형 배경 + ⚠ 아이콘
                Container(
                  width: 72,
                  height: 72,
                  decoration: const BoxDecoration(
                    color: AppColor.dangerSoft,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: const Icon(
                    Icons.warning_rounded,
                    color: AppColor.danger,
                    size: 34,
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  '잠깐, 확인해 주세요',
                  style: TextStyle(
                    fontFamily: 'Pretendard',
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: AppColor.ink,
                    letterSpacing: 0,
                    height: 1.3,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  body,
                  style: const TextStyle(
                    fontFamily: 'Pretendard',
                    fontSize: 14.5,
                    fontWeight: FontWeight.w500,
                    color: AppColor.inkSecondary,
                    height: 1.55,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 14),
                // 크림(brandSoft) 인포 배너
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 10,
                  ),
                  decoration: BoxDecoration(
                    color: AppColor.brandSoft,
                    borderRadius: BorderRadius.circular(AppRadius.sm),
                  ),
                  child: Text(
                    '드시기 전 의사·약사와 상담을 권해요',
                    style: TextStyle(
                      fontFamily: 'Pretendard',
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppColor.brandDeep,
                      height: 1.4,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 20),
                // Primary — 안전 정보 자세히 보기
                _NeuPrimaryButton(
                  label: '안전 정보 자세히 보기',
                  onPressed: () {
                    Navigator.of(context).pop();
                    onViewDetail();
                  },
                ),
                const SizedBox(height: 14),
                // 회색 텍스트 링크
                GestureDetector(
                  onTap: () {
                    Navigator.of(context).pop();
                    onSaveAnyway();
                  },
                  child: const Text(
                    '그래도 저장할게요',
                    style: TextStyle(
                      fontFamily: 'Pretendard',
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: AppColor.inkTertiary,
                      height: 1.4,
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

// ════════════════════════════════════════════════════════════════
// 5) showDeleteConfirmDialog — 삭제 확인 (dangerSoft 원 + 휴지통)
// ════════════════════════════════════════════════════════════════

/// 삭제 확인 다이얼로그.
///
/// Returns:
///   true  — 사용자가 '삭제' 선택
///   false — 사용자가 '취소' 선택 또는 다이얼로그 외부 탭
Future<bool> showDeleteConfirmDialog(
  BuildContext context, {
  required String targetLabel,
  String? subLabel,
}) async {
  final result = await showGeneralDialog<bool>(
    context: context,
    barrierDismissible: true,
    barrierLabel: 'delete_confirm',
    barrierColor: const Color(0x59141A2C),
    transitionDuration: const Duration(milliseconds: 220),
    transitionBuilder: (_, anim, _, child) {
      final curved = CurvedAnimation(parent: anim, curve: Curves.easeOutCubic);
      return Opacity(
        opacity: curved.value,
        child: Transform.scale(scale: 0.96 + 0.04 * curved.value, child: child),
      );
    },
    pageBuilder: (_, _, _) =>
        _DeleteConfirmDialog(targetLabel: targetLabel, subLabel: subLabel),
  );
  return result ?? false;
}

class _DeleteConfirmDialog extends StatelessWidget {
  final String targetLabel;
  final String? subLabel;

  const _DeleteConfirmDialog({required this.targetLabel, this.subLabel});

  @override
  Widget build(BuildContext context) {
    return BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 2, sigmaY: 2),
      child: Center(
        child: Material(
          color: Colors.transparent,
          child: Container(
            width: 320,
            padding: const EdgeInsets.fromLTRB(24, 28, 24, 22),
            decoration: BoxDecoration(
              color: AppColor.surface,
              borderRadius: BorderRadius.circular(28),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF141A2C).withValues(alpha: 0.30),
                  blurRadius: 60,
                  spreadRadius: -10,
                  offset: const Offset(0, 30),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // dangerSoft 원형 배경 + 휴지통 아이콘
                Container(
                  width: 72,
                  height: 72,
                  decoration: const BoxDecoration(
                    color: AppColor.dangerSoft,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: const Icon(
                    Icons.delete_outline_rounded,
                    color: AppColor.danger,
                    size: 34,
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  '이 기록을 삭제할까요?',
                  style: TextStyle(
                    fontFamily: 'Pretendard',
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: AppColor.ink,
                    letterSpacing: 0,
                    height: 1.3,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  subLabel != null
                      ? '$targetLabel\n삭제하면 되돌릴 수 없어요.'
                      : '$targetLabel\n삭제하면 되돌릴 수 없어요.',
                  style: const TextStyle(
                    fontFamily: 'Pretendard',
                    fontSize: 14.5,
                    fontWeight: FontWeight.w500,
                    color: AppColor.inkSecondary,
                    height: 1.55,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                Row(
                  children: [
                    // 취소 버튼 (연회색)
                    Expanded(
                      flex: 4,
                      child: _NeuInsetButton(
                        label: '취소',
                        color: AppColor.inkTertiary,
                        onPressed: () => Navigator.of(context).pop(false),
                      ),
                    ),
                    const SizedBox(width: 10),
                    // 삭제 버튼 (danger 채움)
                    Expanded(
                      flex: 6,
                      child: GestureDetector(
                        onTap: () => Navigator.of(context).pop(true),
                        child: Container(
                          height: 50,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: AppColor.danger,
                            borderRadius: BorderRadius.circular(16),
                            boxShadow: [
                              BoxShadow(
                                color: AppColor.danger.withValues(alpha: 0.40),
                                blurRadius: 14,
                                spreadRadius: -4,
                                offset: const Offset(0, 6),
                              ),
                            ],
                          ),
                          child: const Text(
                            '삭제',
                            style: TextStyle(
                              fontFamily: 'Pretendard',
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ════════════════════════════════════════════════════════════════
// 6) showCelebrationDialog — 축하 (brandSoft 원 + 환호 마스코트)
// ════════════════════════════════════════════════════════════════

Future<void> showCelebrationDialog(
  BuildContext context, {
  required String title,
  required String body,
}) {
  return showGeneralDialog<void>(
    context: context,
    barrierDismissible: false,
    barrierLabel: 'celebration',
    barrierColor: const Color(0x80141A2C),
    transitionDuration: const Duration(milliseconds: 280),
    transitionBuilder: (_, anim, _, child) {
      final curved = CurvedAnimation(parent: anim, curve: Curves.easeOutBack);
      return Opacity(
        opacity: anim.value,
        child: Transform.scale(scale: 0.85 + 0.15 * curved.value, child: child),
      );
    },
    pageBuilder: (_, _, _) => _CelebrationDialog(title: title, body: body),
  );
}

class _CelebrationDialog extends StatelessWidget {
  final String title;
  final String body;

  const _CelebrationDialog({required this.title, required this.body});

  @override
  Widget build(BuildContext context) {
    return BackdropFilter(
      filter: ImageFilter.blur(sigmaX: 6, sigmaY: 6),
      child: Center(
        child: Material(
          color: Colors.transparent,
          child: Container(
            width: 320,
            padding: const EdgeInsets.fromLTRB(24, 36, 24, 20),
            decoration: BoxDecoration(
              color: AppColor.surface,
              borderRadius: BorderRadius.circular(28),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x47141A2C),
                  blurRadius: 60,
                  spreadRadius: -12,
                  offset: Offset(0, 24),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // brandSoft 원형 배경 + 환호 마스코트 아이콘
                Container(
                  width: 88,
                  height: 88,
                  decoration: BoxDecoration(
                    color: AppColor.brandSoft,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    Icons.celebration_rounded,
                    color: AppColor.brand,
                    size: 44,
                  ),
                ),
                const SizedBox(height: 18),
                Text(
                  title,
                  style: const TextStyle(
                    fontFamily: 'Pretendard',
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: AppColor.ink,
                    letterSpacing: 0,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  body,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontFamily: 'Pretendard',
                    fontSize: 14.5,
                    fontWeight: FontWeight.w500,
                    color: AppColor.inkSecondary,
                    height: 1.55,
                  ),
                ),
                const SizedBox(height: 24),
                // 풀폭 primary '확인' 버튼
                GestureDetector(
                  onTap: () => Navigator.of(context).pop(),
                  child: Container(
                    width: double.infinity,
                    height: 54,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: AppColor.brand,
                      borderRadius: BorderRadius.circular(16),
                      boxShadow: [
                        BoxShadow(
                          color: AppColor.brand.withValues(alpha: 0.55),
                          blurRadius: 14,
                          spreadRadius: -4,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: const Text(
                      '확인',
                      style: TextStyle(
                        fontFamily: 'Pretendard',
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
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

// ════════════════════════════════════════════════════════════════
// 7) showUndoToast — 실행취소 토스트 (SnackBar 기반)
//    하단 다크(ink) 라운드 스낵바: success ✓ 원 + 메시지 + 노랑 '실행취소' 액션
//    4초 자동 소멸
// ════════════════════════════════════════════════════════════════

void showUndoToast(
  BuildContext context, {
  required String message,
  required VoidCallback onUndo,
}) {
  // SnackBarAction 을 사용해야 테스트 환경(IgnorePointer 레이어)에서도
  // hit-test 가 올바르게 동작한다. content 는 시각 스타일만 담당.
  ScaffoldMessenger.of(context).clearSnackBars();
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      duration: const Duration(seconds: 4),
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColor.ink,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 20),
      // content: 성공 원 + 메시지 (스타일 전용)
      content: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            decoration: const BoxDecoration(
              color: AppColor.success,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.check_rounded,
              color: Colors.white,
              size: 16,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                fontFamily: 'Pretendard',
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: Colors.white,
                height: 1.4,
              ),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
      // SnackBarAction 은 Flutter 가 직접 hit-test 처리 → 테스트에서 안정적
      action: SnackBarAction(
        label: '실행취소',
        textColor: AppColor.brand,
        onPressed: onUndo,
      ),
    ),
  );
}

class _ConfettiPainter extends CustomPainter {
  static final _dots = <List<dynamic>>[
    [0.22, 28.0, AppColor.yellow, 6.0],
    [0.46, 52.0, AppColor.brand, 4.0],
    [0.76, 24.0, AppColor.yellow, 5.0],
    [0.88, 70.0, AppColor.brand, 5.0],
    [0.16, 80.0, AppColor.danger, 4.0],
    [0.60, 18.0, AppColor.yellow, 4.0],
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint();
    for (final d in _dots) {
      final lx = (d[0] as double) * size.width;
      final ty = d[1] as double;
      final c = d[2] as Color;
      final r = (d[3] as double) / 2;
      paint.color = c.withValues(alpha: 0.85);
      canvas.drawCircle(Offset(lx, ty), r, paint);
    }
  }

  @override
  bool shouldRepaint(_ConfettiPainter oldDelegate) => false;
}
