/// ``ConsentMatrix`` 위젯 테스트 — 필수 토글 + 조건부 표시.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/features/auth/domain/auth_models.dart';
import 'package:lemon_healthcare/features/auth/presentation/widgets/consent_matrix.dart';

ProfileInput _profileWithChronic({List<String>? chronicDiseases}) => ProfileInput(
      age: 30,
      sex: Sex.male,
      heightCm: 175,
      weightKg: 70,
      chronicDiseases: chronicDiseases ?? const <String>[],
    );

Widget _buildApp(
  ProfileInput? profile,
  ValueChanged<List<ConsentAccept>?> onChanged,
) {
  return MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: ConsentMatrix(profile: profile, onChanged: onChanged),
      ),
    ),
  );
}

void main() {
  group('ConsentMatrix', () {
    testWidgets('필수 항목 + 선택 항목만 표시 (조건부 없음)', (WidgetTester tester) async {
      List<ConsentAccept>? captured = const <ConsentAccept>[];
      await tester.pumpWidget(
        _buildApp(_profileWithChronic(), (List<ConsentAccept>? v) {
          captured = v;
        }),
      );
      await tester.pumpAndSettle(); // postFrameCallback emit 완료 대기

      expect(find.textContaining('서비스 이용 약관'), findsOneWidget);
      expect(find.textContaining('일반 프로필'), findsOneWidget);
      expect(find.textContaining('만성질환'), findsNothing);
      expect(find.textContaining('복약'), findsNothing);
      expect(find.textContaining('사진 히스토리'), findsOneWidget);

      // 첫 emit 에서 필수 토글 미수락 → onChanged(null)
      expect(captured, isNull);
    });

    testWidgets('chronic_diseases 가 있으면 만성질환 토글 추가', (WidgetTester tester) async {
      await tester.pumpWidget(
        _buildApp(
          _profileWithChronic(chronicDiseases: <String>['diabetes']),
          (_) {},
        ),
      );
      await tester.pumpAndSettle();

      // title '만성질환 정보 수집' 만 매칭 (subtitle '만성질환 정보를' 과 구분).
      expect(find.textContaining('만성질환 정보 수집'), findsOneWidget);
    });

    testWidgets('필수 토글 모두 on 시 onChanged 가 List 전달', (WidgetTester tester) async {
      List<ConsentAccept>? captured;
      await tester.pumpWidget(
        _buildApp(_profileWithChronic(), (List<ConsentAccept>? v) {
          captured = v;
        }),
      );

      // 2개 필수 토글 on
      final Finder switches = find.byType(SwitchListTile);
      await tester.tap(switches.at(0));
      await tester.pumpAndSettle();
      expect(captured, isNull); // 1개만 on — 필수 1개 미수락

      await tester.tap(switches.at(1));
      await tester.pumpAndSettle();
      expect(captured, isNotNull);
      expect(captured!.length, greaterThanOrEqualTo(2));
      final ConsentAccept serviceTerms = captured!
          .firstWhere((ConsentAccept c) => c.consentType == 'service_terms');
      expect(serviceTerms.accepted, isTrue);
    });
  });
}
