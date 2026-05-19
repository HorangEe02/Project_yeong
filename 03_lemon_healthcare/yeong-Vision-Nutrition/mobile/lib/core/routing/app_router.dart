/// go_router Provider — AuthNotifier 상태 변경 시 refresh + redirect 가드.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../features/auth/domain/auth_state.dart';
import '../../features/auth/presentation/providers/auth_notifier.dart';
import '../../features/auth/presentation/screens/login_screen.dart';
import '../../features/auth/presentation/screens/register_screen.dart';
import '../../features/home/presentation/screens/home_screen.dart';

part 'app_router.g.dart';

@riverpod
GoRouter appRouter(AppRouterRef ref) {
  final _RouterRefreshNotifier refresh = _RouterRefreshNotifier();
  // AuthNotifier 상태 변경 시 redirect 재평가.
  ref.listen<AsyncValue<AuthState>>(
    authNotifierProvider,
    (AsyncValue<AuthState>? _, AsyncValue<AuthState> __) => refresh.notify(),
  );
  ref.onDispose(refresh.dispose);

  return GoRouter(
    initialLocation: '/',
    debugLogDiagnostics: true,
    refreshListenable: refresh,
    redirect: (BuildContext context, GoRouterState state) {
      final AsyncValue<AuthState> auth = ref.read(authNotifierProvider);
      // 초기 build (loading) 중에는 redirect 보류.
      if (auth.isLoading || !auth.hasValue) return null;
      final AuthState value = auth.requireValue;
      final bool loggedIn = value is Authenticated;
      final String location = state.matchedLocation;
      final bool atAuthRoute =
          location == '/login' || location == '/register';

      if (!loggedIn && !atAuthRoute) return '/login';
      if (loggedIn && atAuthRoute) return '/';
      return null;
    },
    routes: <RouteBase>[
      GoRoute(
        path: '/',
        name: 'home',
        builder: (BuildContext context, GoRouterState state) =>
            const HomeScreen(),
      ),
      GoRoute(
        path: '/login',
        name: 'login',
        builder: (BuildContext context, GoRouterState state) =>
            const LoginScreen(),
      ),
      GoRoute(
        path: '/register',
        name: 'register',
        builder: (BuildContext context, GoRouterState state) =>
            const RegisterScreen(),
      ),
      // /supplement/* 는 M-3 에서 채움.
    ],
  );
}

/// AuthNotifier 상태 변경 → GoRouter redirect 재평가 트리거.
class _RouterRefreshNotifier extends ChangeNotifier {
  void notify() => notifyListeners();
}
