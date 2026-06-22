import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/auth/login_screen.dart';

void main() {
  testWidgets('renders wordmark, three social buttons and email entry', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: LoginScreen()));
    await tester.pump();

    // 소셜 로그인 3종 (figma 151:2).
    expect(find.text('카카오로 계속하기'), findsOneWidget);
    expect(find.text('구글로 계속하기'), findsOneWidget);
    expect(find.text('Apple로 계속하기'), findsOneWidget);
    // 이메일 진입 + 회원가입/로그인.
    expect(find.text('이메일로 시작하기'), findsOneWidget);
    expect(find.text('회원가입'), findsOneWidget);
    expect(find.text('로그인'), findsOneWidget);
    // 워드마크 (RichText '레몬·에이드').
    expect(find.byType(RichText), findsWidgets);
  });

  testWidgets('copy avoids forbidden medical terms and confidence percent', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: LoginScreen()));
    await tester.pump();

    const List<String> banned = <String>['진단', '처방', '치료', '효능'];
    final Iterable<Text> texts = tester.widgetList<Text>(find.byType(Text));
    for (final Text widget in texts) {
      final String data = widget.data ?? '';
      expect(data.contains('%'), isFalse, reason: '"$data" 에 %');
      for (final String term in banned) {
        expect(data.contains(term), isFalse, reason: '"$data" 에 "$term"');
      }
    }
  });
}
