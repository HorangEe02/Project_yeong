/// 이메일 + 비밀번호 입력 — 회원가입 Step1 / 로그인 화면 공용.
library;

import 'package:flutter/material.dart';

/// 이메일 정규식 — 백엔드 `models/schemas/auth.py` UserRegisterRequest 의 pattern 과 동일.
final RegExp _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

class EmailPasswordForm extends StatelessWidget {
  const EmailPasswordForm({
    super.key,
    required this.formKey,
    required this.emailController,
    required this.passwordController,
    this.autofocusEmail = true,
  });

  final GlobalKey<FormState> formKey;
  final TextEditingController emailController;
  final TextEditingController passwordController;
  final bool autofocusEmail;

  @override
  Widget build(BuildContext context) {
    return Form(
      key: formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          TextFormField(
            controller: emailController,
            autofocus: autofocusEmail,
            decoration: const InputDecoration(
              labelText: '이메일',
              hintText: 'name@example.com',
              prefixIcon: Icon(Icons.email_outlined),
            ),
            keyboardType: TextInputType.emailAddress,
            textInputAction: TextInputAction.next,
            autocorrect: false,
            validator: (String? value) {
              final String trimmed = (value ?? '').trim();
              if (trimmed.isEmpty) return '이메일을 입력해주세요.';
              if (!_emailPattern.hasMatch(trimmed)) {
                return '이메일 형식이 올바르지 않습니다.';
              }
              return null;
            },
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: passwordController,
            decoration: const InputDecoration(
              labelText: '비밀번호',
              hintText: '최소 8자',
              prefixIcon: Icon(Icons.lock_outline),
            ),
            obscureText: true,
            textInputAction: TextInputAction.done,
            validator: (String? value) {
              if (value == null || value.isEmpty) return '비밀번호를 입력해주세요.';
              if (value.length < 8) return '비밀번호는 최소 8자 이상이어야 합니다.';
              if (value.length > 128) return '비밀번호는 128자 이하로 입력해주세요.';
              return null;
            },
          ),
        ],
      ),
    );
  }
}
