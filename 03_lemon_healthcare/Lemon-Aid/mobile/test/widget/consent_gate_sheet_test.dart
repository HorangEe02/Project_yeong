import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/features/consent/consent_gate_sheet.dart';
import 'package:lemon_aid_mobile/features/consent/consent_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';

/// Minimal fake: the consent gate only needs fetch/grant; the rest throws.
class _ConsentFakeRepository implements LemonAidRepository {
  final List<String> granted = <String>[];

  @override
  Future<ConsentState> fetchConsents() async =>
      const ConsentState(consents: <ConsentStatus>[]);

  @override
  Future<ConsentAction> grantConsent(String consentType) async {
    granted.add(consentType);
    return ConsentAction(
      consentType: consentType,
      policyVersion: 'v1',
      granted: true,
      occurredAt: DateTime(2026),
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) =>
      throw UnimplementedError('Unexpected call: ${invocation.memberName}');
}

Future<AppController> _bootstrappedController(
  _ConsentFakeRepository repository,
) async {
  final AppController controller = AppController(repository: repository);
  await controller.bootstrap();
  return controller;
}

Widget _wrap(AppController controller) => MaterialApp(
  home: Scaffold(body: ConsentGateSheet(controller: controller)),
);

void main() {
  testWidgets('renders Korean copy without the legacy English demo strings', (
    WidgetTester tester,
  ) async {
    final _ConsentFakeRepository repository = _ConsentFakeRepository();
    final AppController controller = await _bootstrappedController(repository);

    await tester.pumpWidget(_wrap(controller));
    await tester.pumpAndSettle();

    expect(find.text('동의하고 시작하기'), findsOneWidget);
    expect(find.text('전체 동의'), findsOneWidget);
    expect(find.text('건강 정보 분석'), findsOneWidget);
    expect(find.textContaining('Required demo consents'), findsNothing);
    expect(find.textContaining('Grant required consents'), findsNothing);
  });

  testWidgets('CTA is gated until all required consents are checked', (
    WidgetTester tester,
  ) async {
    final _ConsentFakeRepository repository = _ConsentFakeRepository();
    final AppController controller = await _bootstrappedController(repository);

    await tester.pumpWidget(_wrap(controller));
    await tester.pumpAndSettle();

    // Disabled before any required consent is checked: tapping grants nothing.
    await tester.tap(find.text('동의하고 시작하기'));
    await tester.pumpAndSettle();
    expect(repository.granted, isEmpty);

    // The master row checks every required and optional consent.
    await tester.tap(find.text('전체 동의'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('동의하고 시작하기'));
    await tester.pumpAndSettle();

    expect(
      repository.granted,
      containsAll(<String>[
        'sensitive_health_analysis',
        'ocr_image_processing',
        'food_image_processing',
        'external_ocr_processing',
        'data_retention',
        'image_learning_dataset',
      ]),
    );
  });
}
