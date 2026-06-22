import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'features/activity/presentation/activity_sync_screen.dart';
import 'features/dashboard/presentation/dashboard_screen.dart';
import 'features/ai_coaching/presentation/daily_coaching_screen.dart';
import 'features/capture_result/presentation/capture_result_screen.dart';
import 'features/chat/presentation/chat_screen.dart';
import 'features/food/presentation/food_capture_screen.dart';
import 'features/medications/presentation/medication_settings_screen.dart';
import 'features/notifications/presentation/notification_settings_screen.dart';
import 'features/supplement/presentation/supplement_capture_screen.dart';
import 'shared/theme/lemon_theme.dart';
import 'shared/widgets/lemon_main_shell.dart';

final GoRouter appRouter = GoRouter(
  routes: <RouteBase>[
    ShellRoute(
      builder: (
        BuildContext context,
        GoRouterState state,
        Widget child,
      ) =>
          LemonMainShell(
        currentPath: state.uri.path,
        child: child,
      ),
      routes: <RouteBase>[
        GoRoute(
          path: '/',
          builder: (BuildContext context, GoRouterState state) =>
              const DashboardScreen(),
        ),
        GoRoute(
          path: '/coaching',
          builder: (BuildContext context, GoRouterState state) =>
              const DailyCoachingScreen(),
        ),
        GoRoute(
          path: '/chat',
          builder: (BuildContext context, GoRouterState state) =>
              const ChatScreen(),
        ),
        GoRoute(
          path: '/notifications',
          builder: (BuildContext context, GoRouterState state) =>
              const NotificationSettingsScreen(),
        ),
        GoRoute(
          path: '/medications',
          builder: (BuildContext context, GoRouterState state) =>
              const MedicationSettingsScreen(),
        ),
        GoRoute(
          path: '/activity',
          builder: (BuildContext context, GoRouterState state) =>
              const ActivitySyncScreen(),
        ),
        GoRoute(
          path: '/supplement-capture',
          builder: (BuildContext context, GoRouterState state) =>
              const SupplementCaptureScreen(),
        ),
        GoRoute(
          path: '/food-capture',
          builder: (BuildContext context, GoRouterState state) =>
              const FoodCaptureScreen(),
        ),
        GoRoute(
          path: '/entry-result',
          builder: (BuildContext context, GoRouterState state) {
            final Map<String, String> params = state.uri.queryParameters;
            return CaptureResultScreen(
              type: params['type'] ?? 'food',
              title: params['title'] ?? '기록이 확정되었습니다.',
              subtitle: params['subtitle'] ?? '코칭 근거로 사용할 준비가 끝났습니다.',
              details: params.entries
                  .where(
                    (MapEntry<String, String> entry) =>
                        entry.key.startsWith('detail'),
                  )
                  .map((MapEntry<String, String> entry) => entry.value)
                  .where((String value) => value.isNotEmpty)
                  .toList(growable: false),
            );
          },
        ),
      ],
    ),
  ],
);

class LemonAidApp extends StatelessWidget {
  const LemonAidApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Lemon Aid',
      debugShowCheckedModeBanner: false,
      theme: LemonTheme.data(),
      routerConfig: appRouter,
      builder: (BuildContext context, Widget? child) {
        return _MobileViewport(
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}

class _MobileViewport extends StatelessWidget {
  const _MobileViewport({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        if (constraints.maxWidth <= 520) {
          return KeyedSubtree(
            key: const Key('lemon-mobile-viewport'),
            child: child,
          );
        }

        return ColoredBox(
          color: LemonColors.canvas,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 430),
              child: DecoratedBox(
                key: const Key('lemon-mobile-viewport'),
                decoration: BoxDecoration(
                  color: LemonColors.canvas,
                  border: Border.all(color: LemonColors.line),
                  boxShadow: const <BoxShadow>[
                    BoxShadow(
                      color: Color(0x22000000),
                      blurRadius: 32,
                      offset: Offset(0, 12),
                    ),
                  ],
                ),
                child: ClipRect(child: child),
              ),
            ),
          ),
        );
      },
    );
  }
}
