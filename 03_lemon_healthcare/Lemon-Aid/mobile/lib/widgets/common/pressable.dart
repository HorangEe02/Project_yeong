// widgets/common/pressable.dart — 누를 수 있는 요소 공통 래퍼
//
// CLAUDE.md §7-8 모션 룰:
//   누르는 모든 것에 피드백 — scale down + 햅틱.
//
// 사용:
//   Pressable(
//     onTap: () => ...,
//     child: SomeCard(...),
//   )
//
// 카드·버튼·리스트 항목 등 탭 가능한 어디든 감싸서 쓴다.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class Pressable extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  // 눌렀을 때 줄어드는 정도 (0.96 = 살짝, 0.92 = 뚜렷)
  final double pressedScale;
  // 햅틱 종류
  final bool haptic;

  const Pressable({
    super.key,
    required this.child,
    this.onTap,
    this.pressedScale = 0.97,
    this.haptic = true,
  });

  @override
  State<Pressable> createState() => _PressableState();
}

class _PressableState extends State<Pressable> {
  bool _pressed = false;

  void _set(bool v) {
    if (widget.onTap == null) return;
    if (_pressed != v) setState(() => _pressed = v);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: widget.onTap == null
          ? null
          : () {
              if (widget.haptic) HapticFeedback.lightImpact();
              widget.onTap!();
            },
      onTapDown: (_) => _set(true),
      onTapUp: (_) => _set(false),
      onTapCancel: () => _set(false),
      behavior: HitTestBehavior.opaque,
      child: AnimatedScale(
        scale: _pressed ? widget.pressedScale : 1.0,
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeOutCubic,
        child: widget.child,
      ),
    );
  }
}
