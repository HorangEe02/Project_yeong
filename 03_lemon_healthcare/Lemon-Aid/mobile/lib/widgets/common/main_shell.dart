// widgets/common/main_shell.dart — 메인 5 탭 BottomNav 셸
//
// 디자인 (Pillyze 시안 기반, LADS 톤으로 변환):
//   - 5 탭: 홈 / 챗 / [중앙 카메라 FAB] / 점수 / 설정
//   - 중앙 카메라 = 큰 brand 원형 FAB (탭바 위로 16dp 떠있음)
//   - 활성 탭 = brand 아이콘 + 아래 작은 dot (•)
//   - 비활성 = inkTertiary outline 아이콘
//   - 배경 흰색, 상단 border 없음, 옅은 soft shadow 만
//   - 5 페이지 상태 보존 — StatefulShellRoute.indexedStack 자동 처리

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../utils/design_tokens_v2.dart';
import 'quick_action_palette.dart';

class MainShell extends StatefulWidget {
  final StatefulNavigationShell navigationShell;
  const MainShell({super.key, required this.navigationShell});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  // 카메라(인덱스 1)는 중앙 FAB. 일반 탭 4개 + 중앙 1개.
  // 라우터 branch 순서: home(0) / camera(1) / chat(2) / score(3) / settings(4)
  // 탭바 시각 순서: home, chat, [camera FAB], score, settings
  // Pillyze 톤 — 둥글둥글 + 채워진(filled) 무게감 있는 픽토그램.
  // 활성/비활성 둘 다 filled 사용, 색만 다름 (시각 무게 일관)
  static const List<_TabSpec> _leftTabs = <_TabSpec>[
    _TabSpec(
      branchIndex: 0,
      // Figma 268:24 — 홈은 집 아이콘 (하트 아님)
      iconOutline: Icons.home_rounded,
      iconFilled: Icons.home_rounded,
      label: '홈',
    ),
    _TabSpec(
      branchIndex: 2,
      // Figma 268:24 — 챗은 겹친 말풍선 2개 (단일 버블 아님)
      iconOutline: Icons.forum_rounded,
      iconFilled: Icons.forum_rounded,
      label: '챗',
    ),
  ];
  static const List<_TabSpec> _rightTabs = <_TabSpec>[
    _TabSpec(
      branchIndex: 3,
      iconOutline: Icons.insert_chart_rounded,
      iconFilled: Icons.insert_chart_rounded,
      label: '분석',
    ),
    _TabSpec(
      branchIndex: 4,
      iconOutline: Icons.settings_rounded,
      iconFilled: Icons.settings_rounded,
      label: '설정',
    ),
  ];
  static const int _cameraBranchIndex = 1;

  void _goBranch(int branchIndex) {
    HapticFeedback.selectionClick();
    widget.navigationShell.goBranch(
      branchIndex,
      initialLocation: branchIndex == widget.navigationShell.currentIndex,
    );
  }

  // 중앙 FAB — 빠른 액션 팔레트 5개 펼침.
  void _openActionPalette() {
    HapticFeedback.mediumImpact();
    showQuickActionPalette(
      context,
      onAction: (QuickAction action) {
        switch (action) {
          case QuickAction.supplementShot:
            context.go('/shell/camera?mode=supplement');
            break;
          case QuickAction.mealShot:
            context.go('/shell/camera?mode=meal');
            break;
          case QuickAction.medication:
            context.push('/shell/home/calendar');
            break;
          case QuickAction.water:
          case QuickAction.manualInput:
            // 백엔드/화면 미구현 — 무음 no-op 대신 안전한 '준비 중' 안내.
            _showComingSoon();
            break;
        }
      },
    );
  }

  // 아직 구현되지 않은 빠른 액션 — 조용히 실패하지 않도록 안내 토스트.
  void _showComingSoon() {
    final ScaffoldMessengerState messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(
      SnackBar(
        content: Text(
          '아직 준비 중이에요.',
          style: AppText.body.copyWith(color: AppColor.bg),
        ),
        backgroundColor: AppColor.ink,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final int currentIndex = widget.navigationShell.currentIndex;
    // 카메라 branch 일 때는 풀스크린 — 탭바 + 배경 검정으로
    final bool isCamera = currentIndex == _cameraBranchIndex;
    return Scaffold(
      backgroundColor: isCamera ? Colors.black : AppColor.bg,
      // extendBody = 카메라 모드일 때 body 가 시스템 영역까지 확장
      extendBody: isCamera,
      body: widget.navigationShell,
      bottomNavigationBar: isCamera
          ? null
          : _BottomBar(
              leftTabs: _leftTabs,
              rightTabs: _rightTabs,
              currentIndex: currentIndex,
              onTabTap: _goBranch,
              onCameraTap: _openActionPalette,
              cameraActive: currentIndex == _cameraBranchIndex,
            ),
    );
  }
}

class _TabSpec {
  final int branchIndex;
  final IconData iconOutline;
  final IconData iconFilled;
  final String label;
  const _TabSpec({
    required this.branchIndex,
    required this.iconOutline,
    required this.iconFilled,
    required this.label,
  });
}

class _BottomBar extends StatelessWidget {
  final List<_TabSpec> leftTabs;
  final List<_TabSpec> rightTabs;
  final int currentIndex;
  final ValueChanged<int> onTabTap;
  final VoidCallback onCameraTap;
  final bool cameraActive;

  const _BottomBar({
    required this.leftTabs,
    required this.rightTabs,
    required this.currentIndex,
    required this.onTabTap,
    required this.onCameraTap,
    required this.cameraActive,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppColor.surface,
        // 상단에 매우 옅은 1px 구분선 + soft shadow (토큰)
        border: Border(top: BorderSide(color: AppColor.border, width: 1)),
        boxShadow: AppShadow.navBar,
      ),
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 92,
          child: Stack(
            clipBehavior: Clip.none,
            alignment: Alignment.topCenter,
            children: [
              // 4 일반 탭 (좌 2 + 우 2) — Row 로 균등 분배
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                height: 72,
                child: Row(
                  children: [
                    for (final t in leftTabs)
                      Expanded(
                        child: _TabItem(
                          spec: t,
                          active: t.branchIndex == currentIndex,
                          onTap: () => onTabTap(t.branchIndex),
                        ),
                      ),
                    // 중앙 공간 (FAB 자리)
                    const Expanded(child: SizedBox.shrink()),
                    for (final t in rightTabs)
                      Expanded(
                        child: _TabItem(
                          spec: t,
                          active: t.branchIndex == currentIndex,
                          onTap: () => onTabTap(t.branchIndex),
                        ),
                      ),
                  ],
                ),
              ),
              // 중앙 카메라 FAB — 시각적으로 떠 있는 영역까지 hit-test 안에 포함.
              Positioned(
                top: 0,
                child: _CameraFab(active: cameraActive, onTap: onCameraTap),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TabItem extends StatelessWidget {
  final _TabSpec spec;
  final bool active;
  final VoidCallback onTap;
  const _TabItem({
    required this.spec,
    required this.active,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    // 포커스: brand 비비드 노랑 / 비활성: 옅은 그레이지 (토큰 inkDisabled #C5C8CE)
    final iconColor = active ? AppColor.brand : AppColor.inkDisabled;
    // 라벨은 활성 시 ink(검정), 비활성은 한 톤 위 (#8A92A5 = inkTertiary)
    final labelColor = active ? AppColor.ink : AppColor.inkTertiary;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpace.sm),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // 아이콘 — Pillyze 처럼 둥글둥글, 활성 시 더 큰 사이즈로 강조
            AnimatedSize(
              duration: const Duration(milliseconds: 180),
              curve: Curves.easeOutCubic,
              child: Icon(
                active ? spec.iconFilled : spec.iconOutline,
                size: active ? 26 : 24,
                color: iconColor,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              spec.label,
              style: AppText.micro.copyWith(
                fontSize: 11,
                fontWeight: active ? FontWeight.w700 : FontWeight.w500,
                color: labelColor,
                letterSpacing: 0,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CameraFab extends StatelessWidget {
  final bool active;
  final VoidCallback onTap;
  const _CameraFab({required this.active, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
        width: 64,
        height: 64,
        decoration: BoxDecoration(
          // Figma 268:24 — 솔리드 레몬 옐로 (그라데이션 없음)
          color: AppColor.brand,
          shape: BoxShape.circle,
          boxShadow: [
            // brand 색 hue 잔향 글로우
            BoxShadow(
              color: AppColor.brand.withValues(alpha: active ? 0.50 : 0.35),
              blurRadius: 20,
              offset: const Offset(0, 8),
            ),
            // 미세 검정 — 깊이감 (토큰)
            AppShadow.fabDepth,
          ],
        ),
        alignment: Alignment.center,
        // 굵은 + 기호 (Pillyze 시안 그대로)
        child: const Icon(
          Icons.add_rounded,
          color: AppColor.ink,
          size: 32,
          weight: 700,
        ),
      ),
    );
  }
}
