import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/core/api/api_error.dart';

void main() {
  test('parses backend consent-required detail', () {
    final ApiError error = ApiError.fromBody(
      statusCode: 403,
      body: jsonEncode(<String, Object?>{
        'detail': <String, Object?>{
          'code': 'consent_required',
          'message': 'Consent is required.',
          'required_consents': <String>[
            'ocr_image_processing',
            'sensitive_health_analysis',
          ],
        },
      }),
    );

    expect(error.statusCode, 403);
    expect(error.code, 'consent_required');
    expect(error.message, 'Consent is required.');
    expect(error.requiredConsents, <String>[
      'ocr_image_processing',
      'sensitive_health_analysis',
    ]);
  });
}
