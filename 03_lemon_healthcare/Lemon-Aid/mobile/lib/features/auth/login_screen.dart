import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../utils/design_tokens_v2.dart' as ds2;

/// 로그인 화면 — 시안 151:2(소셜 로그인) 적용.
///
/// 백엔드 `/auth/*` 라우트는 아직 없으므로(가이드 01 ① 핵심 제약), 모든
/// 소셜/이메일 버튼은 '아직 준비 중이에요' 안내로 안전하게 종료한다. 디버그
/// 빌드에서는 '로그인' 버튼이 dev JWT 화면(`/login/dev`)으로 연결돼 개발 진입을
/// 유지한다. redirect 로직과 dev 화면 자체는 변경하지 않는다.
class LoginScreen extends StatelessWidget {
  /// 로그인 화면을 만든다.
  const LoginScreen({super.key});

  void _showComingSoon(BuildContext context) {
    final ScaffoldMessengerState messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(const SnackBar(content: Text('아직 준비 중이에요')));
  }

  void _onLoginPressed(BuildContext context) {
    if (!kReleaseMode) {
      context.go('/login/dev');
      return;
    }
    _showComingSoon(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ds2.AppColor.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: ds2.AppSpace.page),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                const SizedBox(height: ds2.AppSpace.xxxl),
                const Center(child: _Wordmark()),
                const SizedBox(height: ds2.AppSpace.md),
                Text(
                  '음식과 영양제를 한 번에 관리해요.',
                  textAlign: TextAlign.center,
                  style: ds2.AppText.body.copyWith(
                    color: ds2.AppColor.inkSecondary,
                  ),
                ),
                const SizedBox(height: ds2.AppSpace.xxl),
                Center(
                  child: Image.asset(
                    'assets/mascot/poses/cool.png',
                    height: 190,
                    fit: BoxFit.contain,
                  ),
                ),
                const SizedBox(height: ds2.AppSpace.xxl),
                ds2.AppPrimaryButton(
                  label: '카카오로 계속하기',
                  accent: true,
                  color: ds2.AppColor.kakao,
                  textColor: ds2.AppColor.ink,
                  leading: const Icon(
                    Icons.chat_bubble_rounded,
                    size: 20,
                    color: ds2.AppColor.ink,
                  ),
                  onPressed: () => _showComingSoon(context),
                ),
                const SizedBox(height: ds2.AppSpace.md),
                ds2.AppSecondaryButton(
                  label: '구글로 계속하기',
                  leading: const Icon(
                    Icons.g_mobiledata_rounded,
                    size: 26,
                    color: ds2.AppColor.ink,
                  ),
                  onPressed: () => _showComingSoon(context),
                ),
                const SizedBox(height: ds2.AppSpace.md),
                ds2.AppPrimaryButton(
                  label: 'Apple로 계속하기',
                  accent: true,
                  color: ds2.AppColor.appleBlack,
                  textColor: Colors.white,
                  leading: const Icon(
                    Icons.apple,
                    size: 22,
                    color: Colors.white,
                  ),
                  onPressed: () => _showComingSoon(context),
                ),
                const SizedBox(height: ds2.AppSpace.xl),
                Row(
                  children: <Widget>[
                    const Expanded(child: Divider(color: ds2.AppColor.border)),
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: ds2.AppSpace.md,
                      ),
                      child: Text(
                        '이메일로 시작하기',
                        style: ds2.AppText.caption.copyWith(
                          color: ds2.AppColor.inkTertiary,
                        ),
                      ),
                    ),
                    const Expanded(child: Divider(color: ds2.AppColor.border)),
                  ],
                ),
                const SizedBox(height: ds2.AppSpace.xl),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: ds2.AppSecondaryButton(
                        label: '회원가입',
                        onPressed: () => _showComingSoon(context),
                      ),
                    ),
                    const SizedBox(width: ds2.AppSpace.md),
                    Expanded(
                      child: ds2.AppPrimaryButton(
                        label: '로그인',
                        accent: true,
                        onPressed: () => _onLoginPressed(context),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: ds2.AppSpace.xxl),
                Center(
                  child: Text(
                    '© Lemon Aid · 이용약관 · 개인정보',
                    style: ds2.AppText.micro.copyWith(
                      color: ds2.AppColor.inkTertiary,
                    ),
                  ),
                ),
                const SizedBox(height: ds2.AppSpace.pageBottom),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// 한국어 워드마크 — "레몬·에이드" (가운데 점이 브랜드 색).
///
/// 흰 배경 위라 점은 [ds2.AppColor.brand] 색으로 노출한다(시안 151:2 워드마크).
class _Wordmark extends StatelessWidget {
  const _Wordmark();

  @override
  Widget build(BuildContext context) {
    final TextStyle base = ds2.AppText.display.copyWith(
      fontWeight: FontWeight.w800,
      color: ds2.AppColor.ink,
    );
    return RichText(
      textAlign: TextAlign.center,
      text: TextSpan(
        style: base,
        children: <TextSpan>[
          const TextSpan(text: '레몬'),
          TextSpan(
            text: '·',
            style: base.copyWith(color: ds2.AppColor.brand),
          ),
          const TextSpan(text: '에이드'),
        ],
      ),
    );
  }
}
