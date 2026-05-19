/// EmailPasswordForm validator 테스트 — LoginScreen 의 입력 검증 로직.
///
/// LoginScreen 전체 widget test 는 ProviderScope + AuthNotifier mock 셋업이
/// 필요하므로 M-3 의 supplement_capture_screen test 와 함께 통합 mock
/// helper 도입 후 작성. M-2 시점은 순수 form validator 만 검증.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/features/auth/presentation/widgets/email_password_form.dart';

Widget _buildApp({
  required GlobalKey<FormState> formKey,
  required TextEditingController emailController,
  required TextEditingController passwordController,
}) {
  return MaterialApp(
    home: Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: EmailPasswordForm(
          formKey: formKey,
          emailController: emailController,
          passwordController: passwordController,
        ),
      ),
    ),
  );
}

void main() {
  group('EmailPasswordForm validators', () {
    testWidgets('이메일 비어있으면 validator 메시지', (WidgetTester tester) async {
      final GlobalKey<FormState> formKey = GlobalKey<FormState>();
      await tester.pumpWidget(
        _buildApp(
          formKey: formKey,
          emailController: TextEditingController(),
          passwordController: TextEditingController(),
        ),
      );

      expect(formKey.currentState!.validate(), isFalse);
      await tester.pump();
      expect(find.textContaining('이메일을 입력'), findsOneWidget);
    });

    testWidgets('잘못된 이메일 형식', (WidgetTester tester) async {
      final GlobalKey<FormState> formKey = GlobalKey<FormState>();
      final TextEditingController email =
          TextEditingController(text: 'not-email');
      final TextEditingController password =
          TextEditingController(text: 'Password123!');
      await tester.pumpWidget(
        _buildApp(
          formKey: formKey,
          emailController: email,
          passwordController: password,
        ),
      );

      expect(formKey.currentState!.validate(), isFalse);
      await tester.pump();
      expect(find.textContaining('이메일 형식'), findsOneWidget);
    });

    testWidgets('짧은 비밀번호 → validator', (WidgetTester tester) async {
      final GlobalKey<FormState> formKey = GlobalKey<FormState>();
      final TextEditingController email = TextEditingController(text: 'a@b.com');
      final TextEditingController password =
          TextEditingController(text: 'short');
      await tester.pumpWidget(
        _buildApp(
          formKey: formKey,
          emailController: email,
          passwordController: password,
        ),
      );

      expect(formKey.currentState!.validate(), isFalse);
      await tester.pump();
      // '최소 8자' 는 hint 와 validator 양쪽에 등장 — 더 구체적인 substring 사용.
      expect(find.textContaining('8자 이상이어야'), findsOneWidget);
    });

    testWidgets('정상 입력 → validate true', (WidgetTester tester) async {
      final GlobalKey<FormState> formKey = GlobalKey<FormState>();
      final TextEditingController email = TextEditingController(text: 'a@b.com');
      final TextEditingController password =
          TextEditingController(text: 'Password123!');
      await tester.pumpWidget(
        _buildApp(
          formKey: formKey,
          emailController: email,
          passwordController: password,
        ),
      );

      expect(formKey.currentState!.validate(), isTrue);
    });
  });
}
