import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../app_providers.dart';
import '../core/storage/local_prefs.dart';
import '../utils/design_tokens_v2.dart' as ds2;

/// 17 Pro UIUX branch style splash screen wired to the current token session.
class SplashScreen extends ConsumerStatefulWidget {
  /// Creates the Lemon Aid splash screen.
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  static const String _tagline = '상큼하게 찍고, 톡 쏘게 채우는 스마트 헬스케어';
  static const Duration _typeStep = Duration(milliseconds: 80);
  static const Duration _minimumHold = Duration(milliseconds: 3200);

  int _typedCount = 0;
  Timer? _typeTimer;

  @override
  void initState() {
    super.initState();
    SystemChrome.setSystemUIOverlayStyle(
      const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
      ),
    );
    _typeTimer = Timer.periodic(_typeStep, (Timer timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_typedCount >= _tagline.length) {
        timer.cancel();
        return;
      }
      setState(() => _typedCount++);
    });
    _routeAfterSessionBootstrap();
  }

  @override
  void dispose() {
    _typeTimer?.cancel();
    super.dispose();
  }

  Future<void> _routeAfterSessionBootstrap() async {
    final Future<String> routeFuture = _nextRoute();
    final List<dynamic> result = await Future.wait<dynamic>(<Future<dynamic>>[
      routeFuture,
      Future<void>.delayed(_minimumHold),
    ]);
    if (!mounted) return;
    context.go(result.first as String);
  }

  Future<String> _nextRoute() async {
    for (int attempt = 0; attempt < 100; attempt++) {
      if (!mounted) {
        return '/login';
      }
      final session = ref.read(tokenSessionProvider);
      if (session.bootstrapped) {
        if (!await _onboardingSeen()) {
          return '/onboarding';
        }
        return session.canEnterShell ? '/shell/home' : '/login';
      }
      await Future<void>.delayed(const Duration(milliseconds: 50));
    }
    return '/login';
  }

  Future<bool> _onboardingSeen() async {
    try {
      final LocalPrefs prefs = await ref.read(localPrefsProvider.future);
      return prefs.onboardingSeen();
    } on Object {
      // 로컬 저장소 로드 실패(테스트/엣지) 시 온보딩을 건너뛰어 흐름을 막지 않는다.
      return true;
    }
  }

  @override
  Widget build(BuildContext context) {
    final String typed = _tagline.substring(
      0,
      _typedCount.clamp(0, _tagline.length),
    );
    return Scaffold(
      backgroundColor: ds2.AppColor.bg,
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Image.asset(
                'assets/mascot/gold-poster.png',
                width: 240,
                height: 240,
                fit: BoxFit.contain,
              ),
              const SizedBox(height: 6),
              _TypingTagline(text: typed),
            ],
          ),
        ),
      ),
    );
  }
}

class _TypingTagline extends StatelessWidget {
  const _TypingTagline({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: ds2.AppText.bodyLg.copyWith(color: ds2.AppColor.inkSecondary),
      ),
    );
  }
}
