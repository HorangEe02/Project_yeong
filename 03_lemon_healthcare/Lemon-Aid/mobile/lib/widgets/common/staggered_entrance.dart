// widgets/common/staggered_entrance.dart — 스태거 등장 애니메이션
//
// CLAUDE.md §7-8 모션 룰:
//   여러 요소 동시 등장 시 80~130ms 간격 순차 등장 (한꺼번에 X).
//
// 사용:
//   StaggeredEntrance(
//     children: [card1, card2, card3, ...],
//   )
//   → 각 자식이 위에서 아래로 순차적으로 fade + slide-up 등장.

import 'package:flutter/material.dart';

class StaggeredEntrance extends StatelessWidget {
  final List<Widget> children;
  // 항목 간 등장 간격
  final Duration stagger;
  // 첫 항목 시작 지연
  final Duration initialDelay;
  // 각 항목 애니메이션 길이
  final Duration itemDuration;
  // 슬라이드 시작 오프셋 (px, 아래에서 위로)
  final double slideOffset;
  // 항목 사이 자동 삽입할 간격 (0 이면 안 넣음 — children 에 직접 SizedBox 넣은 경우)
  final double gap;

  const StaggeredEntrance({
    super.key,
    required this.children,
    this.stagger = const Duration(milliseconds: 90),
    this.initialDelay = const Duration(milliseconds: 80),
    this.itemDuration = const Duration(milliseconds: 420),
    this.slideOffset = 24,
    this.gap = 0,
  });

  @override
  Widget build(BuildContext context) {
    final items = <Widget>[];
    for (int i = 0; i < children.length; i++) {
      items.add(
        _StaggerItem(
          delay: initialDelay + stagger * i,
          duration: itemDuration,
          slideOffset: slideOffset,
          child: children[i],
        ),
      );
      if (gap > 0 && i < children.length - 1) {
        items.add(SizedBox(height: gap));
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: items,
    );
  }
}

class _StaggerItem extends StatefulWidget {
  final Widget child;
  final Duration delay;
  final Duration duration;
  final double slideOffset;
  const _StaggerItem({
    required this.child,
    required this.delay,
    required this.duration,
    required this.slideOffset,
  });

  @override
  State<_StaggerItem> createState() => _StaggerItemState();
}

class _StaggerItemState extends State<_StaggerItem>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;
  late final Animation<double> _opacity;
  late final Animation<double> _slide;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(vsync: this, duration: widget.duration);
    _opacity = CurvedAnimation(parent: _c, curve: Curves.easeOutQuart);
    _slide = Tween<double>(
      begin: widget.slideOffset,
      end: 0.0,
    ).animate(CurvedAnimation(parent: _c, curve: Curves.easeOutQuart));
    // delay 후 등장 시작
    Future.delayed(widget.delay, () {
      if (mounted) _c.forward();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (_, child) => Opacity(
        opacity: _opacity.value.clamp(0.0, 1.0),
        child: Transform.translate(
          offset: Offset(0, _slide.value),
          child: child,
        ),
      ),
      child: widget.child,
    );
  }
}
