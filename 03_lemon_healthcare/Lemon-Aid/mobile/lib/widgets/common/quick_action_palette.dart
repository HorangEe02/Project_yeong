// widgets/common/quick_action_palette.dart — 중앙 FAB 빠른 액션 팔레트
//
// 중앙 카메라 FAB 를 누르면 반원형(부채꼴)으로 5개 액션이 펼쳐진다.
//   1 영양제 촬영  2 식단 촬영  3 복약 기록  4 물 섭취  5 직접 입력
//
// 디자인 (LADS Flat 2.0 + Soft UI):
//   - 배경 반투명 검정 (탭하면 닫힘)
//   - FAB 중심에서 부채꼴로 5개가 stagger 로 튀어나옴 (easeOutBack)
//   - 각 버튼 = 원형 컬러 면 + 아이콘. 라벨은 버튼 '바깥쪽'에 배치 → 겹침 0
//
// 사용: showQuickActionPalette(context, onAction: (id) {...})

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../utils/design_tokens_v2.dart';

/// 빠른 액션 종류
enum QuickAction {
  supplementShot, // 영양제 촬영
  mealShot, // 식단 촬영
  medication, // 복약 기록
  water, // 물 섭취
  manualInput, // 직접 입력
}

class _ActionSpec {
  final QuickAction action;
  final IconData icon;
  final String label;
  final Color color;
  const _ActionSpec(this.action, this.icon, this.label, this.color);
}

// 왼쪽 → 오른쪽 순서로 부채꼴에 배치.
// Figma 팔레트 — 아이콘은 전부 단일 딥 골드(모노). 멀티컬러 아님.
// 흰 원 위 대비 확보 위해 brand(#FFC700) 대신 brandDeep(#C99100) 사용.
// 라벨은 Figma 표기대로 짧게 (영양제 / 식단 / 복약). 색은 토큰만.
final List<_ActionSpec> _kActions = [
  _ActionSpec(
    QuickAction.manualInput,
    Icons.edit_rounded,
    '직접 입력',
    AppColor.brandDeep,
  ),
  _ActionSpec(
    QuickAction.water,
    Icons.water_drop_rounded,
    '물 섭취',
    AppColor.brandDeep,
  ),
  _ActionSpec(
    QuickAction.supplementShot,
    Icons.medication_rounded,
    '영양제',
    AppColor.brandDeep,
  ),
  _ActionSpec(
    QuickAction.mealShot,
    Icons.restaurant_rounded,
    '식단',
    AppColor.brandDeep,
  ),
  _ActionSpec(
    QuickAction.medication,
    Icons.check_circle_rounded,
    '복약',
    AppColor.brandDeep,
  ),
];

const Duration _kPaletteTransitionDuration = Duration(milliseconds: 420);

/// 팔레트를 오버레이로 띄운다. 액션 선택 시 [onAction] 호출 후 닫힘.
Future<void> showQuickActionPalette(
  BuildContext context, {
  required ValueChanged<QuickAction> onAction,
}) async {
  final QuickAction? selected = await showGeneralDialog<QuickAction>(
    context: context,
    barrierDismissible: true,
    barrierLabel: '닫기',
    // Figma — 거의 불투명 다크 (뒤 카드/헤더가 비치지 않게).
    barrierColor: Colors.black.withValues(alpha: 0.86),
    transitionDuration: _kPaletteTransitionDuration,
    pageBuilder: (_, _, _) => const SizedBox.shrink(),
    transitionBuilder: (_, anim, _, _) {
      return _QuickActionPalette(progress: anim);
    },
  );
  if (!context.mounted || selected == null) {
    return;
  }
  await Future<void>.delayed(_kPaletteTransitionDuration);
  if (!context.mounted) {
    return;
  }
  onAction(selected);
}

class _QuickActionPalette extends StatelessWidget {
  final Animation<double> progress;
  const _QuickActionPalette({required this.progress});

  static const double _fabSize = 64;
  // 부채꼴 반지름 — Figma 측정값(≈160pt). 5개 버튼이 FAB 중심 기준 반원에 위치.
  static const double _radius = 160;
  static const double _btnSize = 56;

  @override
  Widget build(BuildContext context) {
    final media = MediaQuery.of(context);
    final centerX = media.size.width / 2;
    // FAB 중심 Y — MainShell 의 FAB 와 정확히 동일 위치.
    //   ⇒ 화면높이 - bottomPad - 60
    final fabCenterY = media.size.height - media.padding.bottom - 60;
    // 부채꼴 펼침 중심 = FAB(닫기버튼) 중심. Figma 는 X 버튼 중심을 호의 원점으로 함.
    final centerY = fabCenterY;
    final n = _kActions.length;

    // showGeneralDialog 결과는 Material 밖이라 — 감싸야 Text 노란 밑줄 사라짐
    return Material(
      type: MaterialType.transparency,
      child: Stack(
        children: [
          // 배경 탭 → 닫기
          Positioned.fill(
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => Navigator.of(context, rootNavigator: true).pop(),
            ),
          ),

          // 액션 버튼 5개 — FAB 중심에서 부채꼴
          for (int i = 0; i < n; i++)
            _buildActionItem(context, i, n, centerX, centerY),

          // 중앙 닫기 버튼 — FAB 실제 자리(fabCenterY), + 가 X 로 회전
          Positioned(
            left: centerX - _fabSize / 2,
            top: fabCenterY - _fabSize / 2,
            child: ScaleTransition(
              scale: CurvedAnimation(
                parent: progress,
                curve: Curves.easeOutQuart,
              ),
              child: GestureDetector(
                onTap: () => Navigator.of(context, rootNavigator: true).pop(),
                child: Container(
                  width: _fabSize,
                  height: _fabSize,
                  decoration: BoxDecoration(
                    // main_shell _CameraFab 와 동일 — 솔리드 brand + 토큰 그림자
                    color: AppColor.brand,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppColor.brand.withValues(alpha: 0.45),
                        blurRadius: 20,
                        offset: const Offset(0, 8),
                      ),
                      AppShadow.fabDepth,
                    ],
                  ),
                  alignment: Alignment.center,
                  child: AnimatedBuilder(
                    animation: progress,
                    builder: (_, _) => Transform.rotate(
                      angle: progress.value * (math.pi / 4),
                      child: const Icon(
                        Icons.add_rounded,
                        color: AppColor.ink,
                        size: 32,
                        weight: 700,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionItem(
    BuildContext context,
    int i,
    int n,
    double centerX,
    double centerY,
  ) {
    final spec = _kActions[i];
    // 부채꼴 — 위쪽 반원, 적당히 (208° ~ 332°).
    const startAngle = math.pi + math.pi * 0.155; // 208°
    const endAngle = math.pi * 2 - math.pi * 0.155; // 332°
    final t = n == 1 ? 0.5 : i / (n - 1);
    final angle = startAngle + t * (endAngle - startAngle);
    final dx = _radius * math.cos(angle);
    final dy = _radius * math.sin(angle);

    // stagger — 좌측(i=0)부터 우측(i=n-1)까지 순차로 부드럽게 흐름.
    // easeOutQuart = 튐 없이 매끄러운 감속.
    final delay = (i * 0.07).clamp(0.0, 0.45);
    final itemAnim = CurvedAnimation(
      parent: progress,
      curve: Interval(delay, 1.0, curve: Curves.easeOutQuart),
    );
    final fadeAnim = CurvedAnimation(
      parent: progress,
      curve: Interval(
        delay,
        (delay + 0.4).clamp(0.0, 1.0),
        curve: Curves.easeOutCubic,
      ),
    );

    void selectAction() {
      HapticFeedback.lightImpact();
      Navigator.of(context, rootNavigator: true).pop(spec.action);
    }

    // 라벨 위치 — 버튼이 위쪽 부채꼴이라 라벨은 버튼 '위'에 둠 (아래는 겹침).
    return AnimatedBuilder(
      animation: progress,
      builder: (_, _) {
        final p = itemAnim.value.clamp(0.0, 1.0);
        final bx = centerX + dx * p;
        final by = centerY + dy * p;
        return Positioned(
          // 버튼 + 라벨 묶음 — [버튼] 위 / [라벨] 아래 Column.
          // 버튼 중심이 부채꼴 좌표(bx,by)에 오도록.
          left: bx - 48, // 묶음 너비 96, 버튼 중심 정렬
          top: by - _btnSize / 2, // 버튼 중심을 by 에
          child: Opacity(
            opacity: fadeAnim.value.clamp(0.0, 1.0),
            child: Semantics(
              button: true,
              label: spec.label,
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: selectAction,
                child: SizedBox(
                  width: 96,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      // 원형 흰 버튼 — Flat 2.0 흰 면 + 아이콘만 컬러 + Soft 그림자
                      Container(
                        width: _btnSize,
                        height: _btnSize,
                        decoration: BoxDecoration(
                          color: AppColor.surface,
                          shape: BoxShape.circle,
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.16),
                              blurRadius: 14,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        alignment: Alignment.center,
                        child: Icon(spec.icon, color: spec.color, size: 26),
                      ),
                      const SizedBox(height: 8),
                      // 라벨 — 버튼 아래, 흰 글자 (어두운 배경 위라 칩 없이 깔끔).
                      // 타이포는 AppText.micro 토큰 기반 + 어두운 배리어 가독성용 그림자.
                      Text(
                        spec.label,
                        maxLines: 1,
                        textAlign: TextAlign.center,
                        style: AppText.micro.copyWith(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          shadows: const [
                            Shadow(
                              color: Color.fromRGBO(0, 0, 0, 0.5),
                              blurRadius: 4,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
