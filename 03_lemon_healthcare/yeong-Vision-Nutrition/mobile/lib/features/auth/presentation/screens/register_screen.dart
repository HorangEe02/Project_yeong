/// 회원가입 화면 — 3-step Stepper (계정 / 프로필 / 동의 매트릭스).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../domain/auth_errors.dart';
import '../../domain/auth_models.dart';
import '../../domain/auth_state.dart';
import '../providers/auth_notifier.dart';
import '../widgets/consent_matrix.dart';
import '../widgets/email_password_form.dart';
import '../widgets/profile_form.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  int _currentStep = 0;
  final GlobalKey<FormState> _emailFormKey = GlobalKey<FormState>();
  final TextEditingController _emailCtrl = TextEditingController();
  final TextEditingController _passwordCtrl = TextEditingController();
  ProfileInput? _profile;
  List<ConsentAccept>? _consents;

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  bool get _canProceed {
    switch (_currentStep) {
      case 0:
        return true; // 검증은 _onStepContinue 에서.
      case 1:
        return _profile != null;
      case 2:
        return _consents != null;
      default:
        return false;
    }
  }

  Future<void> _onStepContinue() async {
    if (_currentStep == 0) {
      if (!(_emailFormKey.currentState?.validate() ?? false)) return;
      setState(() => _currentStep = 1);
      return;
    }
    if (_currentStep == 1) {
      if (_profile == null) return;
      setState(() => _currentStep = 2);
      return;
    }
    if (_currentStep == 2 && _consents != null) {
      await _submit();
    }
  }

  Future<void> _submit() async {
    final RegisterRequest request = RegisterRequest(
      email: _emailCtrl.text.trim(),
      password: _passwordCtrl.text,
      profile: _profile!,
      consents: _consents!,
    );
    try {
      await ref.read(authNotifierProvider.notifier).register(request);
    } on ConsentRequiredException {
      if (!mounted) return;
      setState(() => _currentStep = 2);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('필요한 동의를 다시 확인해주세요.'),
        ),
      );
      return;
    }
    if (!mounted) return;
    final AsyncValue<AuthState> state = ref.read(authNotifierProvider);
    final AuthState? value = state.valueOrNull;
    if (value is AuthFailed) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(value.message)),
      );
    }
    // 성공 → redirect 가 /home 으로 이동.
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<AuthState> auth = ref.watch(authNotifierProvider);
    final bool isLoading = auth.isLoading || auth.valueOrNull is Authenticating;

    return Scaffold(
      appBar: AppBar(title: const Text('회원가입')),
      body: Stepper(
        currentStep: _currentStep,
        type: StepperType.vertical,
        onStepContinue: isLoading ? null : _onStepContinue,
        onStepCancel: isLoading || _currentStep == 0
            ? null
            : () => setState(() => _currentStep -= 1),
        controlsBuilder: (BuildContext context, ControlsDetails details) {
          final bool isLast = details.currentStep == 2;
          return Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Row(
              children: <Widget>[
                FilledButton(
                  onPressed:
                      (_canProceed && !isLoading) ? details.onStepContinue : null,
                  child: Text(isLast ? '가입 완료' : '다음'),
                ),
                const SizedBox(width: 8),
                if (details.currentStep > 0)
                  TextButton(
                    onPressed: details.onStepCancel,
                    child: const Text('이전'),
                  ),
              ],
            ),
          );
        },
        steps: <Step>[
          Step(
            title: const Text('계정 정보'),
            isActive: _currentStep >= 0,
            content: EmailPasswordForm(
              formKey: _emailFormKey,
              emailController: _emailCtrl,
              passwordController: _passwordCtrl,
            ),
          ),
          Step(
            title: const Text('프로필'),
            isActive: _currentStep >= 1,
            content: ProfileForm(
              onChanged: (ProfileInput? v) => setState(() => _profile = v),
            ),
          ),
          Step(
            title: const Text('동의'),
            isActive: _currentStep >= 2,
            content: ConsentMatrix(
              profile: _profile,
              onChanged: (List<ConsentAccept>? v) =>
                  setState(() => _consents = v),
            ),
          ),
        ],
      ),
    );
  }
}
