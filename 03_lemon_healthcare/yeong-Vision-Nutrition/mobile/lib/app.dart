/// 루트 위젯 — ``MaterialApp.router`` + Material 3 + 한국어 로케일.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/routing/app_router.dart';
import 'core/theme/app_theme.dart';

class LemonHealthcareApp extends ConsumerWidget {
  const LemonHealthcareApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);

    return MaterialApp.router(
      title: '레몬헬스케어',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      routerConfig: router,
      locale: const Locale('ko', 'KR'),
      supportedLocales: const <Locale>[Locale('ko', 'KR')],
    );
  }
}
