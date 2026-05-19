/// 영양소 상태 5단계 → 색상 + 한글 라벨 칩.
library;

import 'package:flutter/material.dart';

import '../../domain/supplement_models.dart';

class StatusChip extends StatelessWidget {
  const StatusChip({super.key, required this.status});

  final NutrientStatus status;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final _ChipStyle style = _styleFor(status, theme);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: style.background,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        style.label,
        style: theme.textTheme.labelMedium?.copyWith(
          color: style.foreground,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  _ChipStyle _styleFor(NutrientStatus status, ThemeData theme) {
    switch (status) {
      case NutrientStatus.deficient:
        return _ChipStyle(
          background: Colors.red.shade100,
          foreground: Colors.red.shade900,
          label: '부족',
        );
      case NutrientStatus.low:
        return _ChipStyle(
          background: Colors.orange.shade100,
          foreground: Colors.orange.shade900,
          label: '낮음',
        );
      case NutrientStatus.adequate:
        return _ChipStyle(
          background: Colors.green.shade100,
          foreground: Colors.green.shade900,
          label: '적정',
        );
      case NutrientStatus.excessive:
        return _ChipStyle(
          background: Colors.amber.shade100,
          foreground: Colors.amber.shade900,
          label: '과다',
        );
      case NutrientStatus.risky:
        return _ChipStyle(
          background: theme.colorScheme.errorContainer,
          foreground: theme.colorScheme.onErrorContainer,
          label: '주의',
        );
    }
  }
}

class _ChipStyle {
  const _ChipStyle({
    required this.background,
    required this.foreground,
    required this.label,
  });

  final Color background;
  final Color foreground;
  final String label;
}
