/// "전문가 상담 권장" 카드 — 백엔드 응답 ``consult_professional_message_ko``
/// 가 있으면 그대로 표시, 없으면 ``DisclaimerStrings.consultProfessionalKo``
/// 디폴트.
library;

import 'package:flutter/material.dart';

import 'disclaimer.dart';

class ConsultProfessional extends StatelessWidget {
  const ConsultProfessional({super.key, this.message});

  /// 백엔드 ``consult_professional_message_ko`` 값. ``null`` 또는 빈 문자열
  /// 이면 디폴트 한국어 메시지 사용.
  final String? message;

  @override
  Widget build(BuildContext context) {
    final String text = (message == null || message!.isEmpty)
        ? DisclaimerStrings.consultProfessionalKo
        : message!;
    final ThemeData theme = Theme.of(context);

    return Card(
      color: theme.colorScheme.secondaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Icon(
              Icons.medical_services_outlined,
              color: theme.colorScheme.onSecondaryContainer,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                text,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSecondaryContainer,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
