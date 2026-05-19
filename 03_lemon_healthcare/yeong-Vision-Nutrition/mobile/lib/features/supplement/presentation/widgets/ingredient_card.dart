/// 단일 성분 카드 — 함량 + (있다면) 진단 상태칩 + ratio bar + 메시지.
library;

import 'package:flutter/material.dart';

import '../../domain/supplement_models.dart';
import 'status_chip.dart';

class IngredientCard extends StatelessWidget {
  const IngredientCard({
    super.key,
    required this.ingredient,
    this.diagnosis,
  });

  final Ingredient ingredient;

  /// MFDS 코드로 매칭된 KDRIs 진단. ``null`` 이면 함량만 표시.
  final NutrientDiagnosis? diagnosis;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    ingredient.nameKo,
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                if (diagnosis != null)
                  StatusChip(status: diagnosis!.status),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              '${_formatAmount(ingredient.amount)} ${ingredient.unit}',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            if (diagnosis != null) ...<Widget>[
              const SizedBox(height: 12),
              LinearProgressIndicator(
                value: (diagnosis!.ratio / 2.0).clamp(0.0, 1.0),
                minHeight: 8,
                borderRadius: BorderRadius.circular(4),
              ),
              const SizedBox(height: 4),
              Text(
                '권장량 대비 ${(diagnosis!.ratio * 100).toStringAsFixed(0)}%',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                diagnosis!.messageKo,
                style: theme.textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _formatAmount(double amount) {
    if (amount == amount.roundToDouble()) {
      return amount.toInt().toString();
    }
    return amount.toStringAsFixed(1);
  }
}
