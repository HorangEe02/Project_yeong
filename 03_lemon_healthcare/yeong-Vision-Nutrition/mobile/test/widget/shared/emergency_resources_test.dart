/// ``EmergencyResources`` 위젯 테스트 — items=null → fallback, items 전달 → 그대로.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/shared/models/emergency_contact.dart';
import 'package:lemon_healthcare/shared/widgets/emergency_resources.dart';

void main() {
  group('EmergencyResources', () {
    testWidgets('items 가 null 이면 디폴트 3개 본문 표시', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: EmergencyResources()),
        ),
      );
      expect(find.text('정신건강위기상담'), findsOneWidget);
      expect(find.text('1577-0199'), findsOneWidget);
      expect(find.text('자살예방상담'), findsOneWidget);
      expect(find.text('109'), findsOneWidget);
      expect(find.text('응급의료정보'), findsOneWidget);
      expect(find.text('1339'), findsOneWidget);
    });

    testWidgets('items 가 빈 리스트면 디폴트 본문', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: EmergencyResources(items: <EmergencyContact>[])),
        ),
      );
      expect(find.text('정신건강위기상담'), findsOneWidget);
    });

    testWidgets('items 전달 시 그대로 표시', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: EmergencyResources(
              items: <EmergencyContact>[
                EmergencyContact(name: '테스트 안내', phone: '0000-0000'),
              ],
            ),
          ),
        ),
      );
      expect(find.text('테스트 안내'), findsOneWidget);
      expect(find.text('0000-0000'), findsOneWidget);
      // 디폴트는 표시되지 않음
      expect(find.text('정신건강위기상담'), findsNothing);
    });
  });
}
