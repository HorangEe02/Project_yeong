import 'package:flutter/material.dart';

import '../../core/api/api_error.dart';

/// Compact API error display for the current screen.
class ErrorPanel extends StatelessWidget {
  /// Creates an error panel.
  const ErrorPanel({required this.error, required this.onDismissed, super.key});

  /// Error to render.
  final ApiError error;

  /// Called when the user dismisses the error.
  final VoidCallback onDismissed;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final String consentText = error.requiredConsents.isEmpty
        ? ''
        : ' Required: ${error.requiredConsents.join(', ')}';

    return Material(
      color: colors.errorContainer,
      child: ListTile(
        leading: Icon(Icons.error_outline, color: colors.onErrorContainer),
        title: Text(
          'Request failed (${error.statusCode})',
          style: TextStyle(color: colors.onErrorContainer),
        ),
        subtitle: Text(
          '${error.message}$consentText',
          style: TextStyle(color: colors.onErrorContainer),
        ),
        trailing: IconButton(
          tooltip: 'Dismiss',
          onPressed: onDismissed,
          icon: Icon(Icons.close, color: colors.onErrorContainer),
        ),
      ),
    );
  }
}
