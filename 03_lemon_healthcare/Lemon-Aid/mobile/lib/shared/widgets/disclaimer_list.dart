import 'package:flutter/material.dart';

/// Displays user-facing safety disclaimers returned by the backend.
class DisclaimerList extends StatelessWidget {
  /// Creates a disclaimer list.
  const DisclaimerList({required this.disclaimers, super.key});

  /// Safety disclaimers to render.
  final List<String> disclaimers;

  @override
  Widget build(BuildContext context) {
    if (disclaimers.isEmpty) {
      return const SizedBox.shrink();
    }

    final ColorScheme colors = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Icon(Icons.info_outline, color: colors.onSurfaceVariant),
                const SizedBox(width: 8),
                Text(
                  'Safety notes',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ],
            ),
            const SizedBox(height: 8),
            for (final String disclaimer in disclaimers)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(disclaimer),
              ),
          ],
        ),
      ),
    );
  }
}
