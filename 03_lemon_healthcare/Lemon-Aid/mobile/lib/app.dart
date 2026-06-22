import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'app_controller.dart';
import 'app_providers.dart';
import 'core/config/app_config.dart';
import 'core/storage/local_prefs.dart';
import 'features/auth/login_screen.dart';
import 'features/auth/signup_wizard/profile_setup_wizard_screen.dart';
import 'features/auth/token_session.dart';
import 'features/consent/consent_gate_sheet.dart';
import 'features/onboarding/onboarding_screen.dart';
import 'features/profile/profile_interests_screen.dart';
import 'features/records/records_providers.dart';
import 'features/supplements/supplement_models.dart';
import 'features/supplements/supplement_repository.dart';
import 'screens/analysis_result_screen.dart' as source_analysis;
import 'screens/calendar_screen.dart' as source_calendar;
import 'screens/camera_screen.dart' as source_camera;
import 'screens/daily_records_screen.dart' as source_records;
import 'screens/chat_screen.dart' as source_chat;
import 'screens/dashboard_screen.dart' as source_dashboard;
import 'screens/meal_management_screen.dart' as source_meal_management;
import 'screens/score_screen.dart' as source_score;
import 'screens/settings_screen.dart' as source_settings;
import 'screens/settings/health_profile_screen.dart';
import 'screens/settings/medication_reminder_screen.dart';
import 'screens/settings/notification_settings_screen.dart';
import 'screens/settings/policies_screen.dart';
import 'screens/settings/profile_edit_screen.dart';
import 'screens/settings/withdraw_screen.dart';
import 'screens/splash_screen.dart' as source_splash;
import 'screens/supplement_management_screen.dart'
    as source_supplement_management;
import 'shared/theme/brand_theme_controller.dart';
import 'shared/theme/lemon_design_tokens.dart';
import 'utils/brand_palette.dart';
import 'shared/widgets/error_panel.dart';
import 'widgets/common/main_shell.dart';

/// Lemon Aid mobile application with the 17 Pro-style shell.
class LemonAidApp extends StatelessWidget {
  /// Creates the app.
  ///
  /// Args:
  ///   repository: Optional repository override for widget tests.
  ///   config: Optional runtime config override for tests.
  ///   tokenStore: Optional external JWT store override for tests.
  const LemonAidApp({this.repository, this.config, this.tokenStore, super.key});

  /// Optional repository override.
  final LemonAidRepository? repository;

  /// Optional config override.
  final AppConfig? config;

  /// Optional bearer-token store override.
  final BearerTokenStore? tokenStore;

  @override
  Widget build(BuildContext context) {
    final List<Override> overrides = <Override>[
      if (config != null) appConfigProvider.overrideWithValue(config!),
      if (repository != null)
        lemonAidRepositoryProvider.overrideWithValue(repository!),
      if (tokenStore != null)
        bearerTokenStoreProvider.overrideWithValue(tokenStore!)
      else if (repository != null)
        bearerTokenStoreProvider.overrideWithValue(MemoryBearerTokenStore()),
    ];

    return ProviderScope(
      overrides: overrides,
      child: const _LemonAidRouterApp(),
    );
  }
}

final Provider<GoRouter> _routerProvider = Provider<GoRouter>((Ref ref) {
  final TokenSessionController session = ref.watch(tokenSessionProvider);
  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: session,
    redirect: (BuildContext context, GoRouterState state) {
      final String path = state.uri.path;
      final bool isLogin = path == '/login';
      final bool isSplash = path == '/splash';
      final bool isOnboarding = path == '/onboarding';
      if (!session.bootstrapped) {
        return isSplash ? null : '/splash';
      }
      // 스플래시·온보딩은 스스로 다음 화면으로 이동하므로 redirect 면제.
      if (isSplash || isOnboarding) {
        return null;
      }
      if (!session.canEnterShell && !isLogin) {
        return '/login';
      }
      if (session.canEnterShell && isLogin) {
        return '/shell/home';
      }
      return null;
    },
    routes: <RouteBase>[
      GoRoute(
        path: '/splash',
        builder: (BuildContext context, GoRouterState state) {
          return const source_splash.SplashScreen();
        },
      ),
      GoRoute(
        path: '/login',
        builder: (BuildContext context, GoRouterState state) {
          return const LoginScreen();
        },
      ),
      // dev 전용 — JWT 붙여넣기 + dev bypass 진입(릴리즈 보안 가드 대상).
      // 로그인 화면의 '로그인' 버튼이 비릴리즈에서 이 경로로 보낸다.
      GoRoute(
        path: '/login/dev',
        builder: (BuildContext context, GoRouterState state) {
          return const _BearerTokenLoginScreen();
        },
      ),
      GoRoute(
        path: '/onboarding',
        builder: (BuildContext context, GoRouterState state) {
          return Consumer(
            builder: (BuildContext context, WidgetRef ref, Widget? child) {
              final LocalPrefs? prefs = ref.watch(localPrefsProvider).value;
              if (prefs == null) {
                return const Scaffold(
                  body: Center(child: CircularProgressIndicator()),
                );
              }
              return OnboardingScreen(
                prefs: prefs,
                onDone: () {
                  final TokenSessionController session = ref.read(
                    tokenSessionProvider,
                  );
                  context.go(session.canEnterShell ? '/shell/home' : '/login');
                },
              );
            },
          );
        },
      ),
      StatefulShellRoute.indexedStack(
        builder:
            (
              BuildContext context,
              GoRouterState state,
              StatefulNavigationShell navigationShell,
            ) {
              return _LemonAidShell(navigationShell: navigationShell);
            },
        branches: <StatefulShellBranch>[
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: '/shell/home',
                builder: (BuildContext context, GoRouterState state) {
                  return Consumer(
                    builder:
                        (BuildContext context, WidgetRef ref, Widget? child) {
                          return source_dashboard.DashboardScreen(
                            controller: ref.watch(appControllerProvider),
                            localPrefs: ref.watch(localPrefsProvider).value,
                            profileRepository: ref.watch(
                              profileRepositoryProvider,
                            ),
                          );
                        },
                  );
                },
                routes: <RouteBase>[
                  GoRoute(
                    path: 'calendar',
                    builder: (BuildContext context, GoRouterState state) {
                      return Consumer(
                        builder:
                            (
                              BuildContext context,
                              WidgetRef ref,
                              Widget? child,
                            ) {
                              return source_calendar.CalendarScreen(
                                repository: ref.watch(
                                  recordsRepositoryProvider,
                                ),
                                controller: ref.watch(appControllerProvider),
                                localPrefs: ref.watch(localPrefsProvider).value,
                              );
                            },
                      );
                    },
                  ),
                  GoRoute(
                    path: 'records',
                    builder: (BuildContext context, GoRouterState state) {
                      final DateTime? date = _parseRecordDate(
                        state.uri.queryParameters['date'],
                      );
                      return Consumer(
                        builder:
                            (
                              BuildContext context,
                              WidgetRef ref,
                              Widget? child,
                            ) {
                              return source_records.DailyRecordsScreen(
                                repository: ref.watch(
                                  recordsRepositoryProvider,
                                ),
                                initialDate: date,
                              );
                            },
                      );
                    },
                  ),
                  GoRoute(
                    path: 'notifications',
                    builder: (BuildContext context, GoRouterState state) {
                      return const _NeutralBranch(
                        icon: Icons.notifications_rounded,
                        title: '알림',
                        message: '복약 알림과 분석 리포트 알림 설정을 연결할 예정입니다.',
                      );
                    },
                  ),
                  GoRoute(
                    path: 'analysis-result',
                    builder: (BuildContext context, GoRouterState state) {
                      final String mode =
                          state.uri.queryParameters['mode'] ?? 'supplement';
                      return Consumer(
                        builder:
                            (
                              BuildContext context,
                              WidgetRef ref,
                              Widget? child,
                            ) {
                              return source_analysis.AnalysisResultScreen(
                                mode: mode,
                                controller: ref.watch(appControllerProvider),
                              );
                            },
                      );
                    },
                  ),
                  GoRoute(
                    path: 'supplements',
                    builder: (BuildContext context, GoRouterState state) {
                      return Consumer(
                        builder:
                            (
                              BuildContext context,
                              WidgetRef ref,
                              Widget? child,
                            ) {
                              return source_supplement_management.SupplementManagementScreen(
                                controller: ref.watch(appControllerProvider),
                              );
                            },
                      );
                    },
                  ),
                  GoRoute(
                    path: 'meals',
                    builder: (BuildContext context, GoRouterState state) {
                      return Consumer(
                        builder:
                            (
                              BuildContext context,
                              WidgetRef ref,
                              Widget? child,
                            ) {
                              return source_meal_management.MealManagementScreen(
                                controller: ref.watch(appControllerProvider),
                              );
                            },
                      );
                    },
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: '/shell/camera',
                builder: (BuildContext context, GoRouterState state) {
                  return _SupplementCameraBranch(
                    initialMode:
                        state.uri.queryParameters['mode'] ?? 'supplement',
                    initialImageRole:
                        state.uri.queryParameters['role'] ?? 'unknown',
                  );
                },
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: '/shell/chat',
                builder: (BuildContext context, GoRouterState state) {
                  return Consumer(
                    builder:
                        (BuildContext context, WidgetRef ref, Widget? child) {
                          return source_chat.ChatScreen(
                            controller: ref.watch(appControllerProvider),
                          );
                        },
                  );
                },
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: '/shell/score',
                builder: (BuildContext context, GoRouterState state) {
                  return Consumer(
                    builder:
                        (BuildContext context, WidgetRef ref, Widget? child) {
                          return source_score.ScoreScreen(
                            controller: ref.watch(appControllerProvider),
                            coachingRepository: ref.watch(
                              aiCoachingRepositoryProvider,
                            ),
                            trendRepository: ref.watch(
                              analysisTrendRepositoryProvider,
                            ),
                          );
                        },
                  );
                },
              ),
            ],
          ),
          StatefulShellBranch(
            routes: <RouteBase>[
              GoRoute(
                path: '/shell/settings',
                builder: (BuildContext context, GoRouterState state) {
                  return const _SettingsBranch();
                },
                routes: <RouteBase>[
                  GoRoute(
                    path: 'profile-edit',
                    builder: (BuildContext context, GoRouterState state) =>
                        const ProfileEditScreen(),
                  ),
                  GoRoute(
                    path: 'profile-setup',
                    builder: (BuildContext context, GoRouterState state) =>
                        const ProfileSetupWizardScreen(),
                  ),
                  GoRoute(
                    path: 'profile-interests',
                    builder: (BuildContext context, GoRouterState state) {
                      return Consumer(
                        builder:
                            (
                              BuildContext context,
                              WidgetRef ref,
                              Widget? child,
                            ) {
                              final LocalPrefs? prefs = ref
                                  .watch(localPrefsProvider)
                                  .value;
                              if (prefs == null) {
                                return const Scaffold(
                                  body: Center(
                                    child: CircularProgressIndicator(),
                                  ),
                                );
                              }
                              return ProfileInterestsScreen(prefs: prefs);
                            },
                      );
                    },
                  ),
                  GoRoute(
                    path: 'health-profile',
                    builder: (BuildContext context, GoRouterState state) =>
                        const HealthProfileScreen(),
                  ),
                  GoRoute(
                    path: 'medication-reminders',
                    builder: (BuildContext context, GoRouterState state) =>
                        const MedicationReminderScreen(),
                  ),
                  GoRoute(
                    path: 'notification-settings',
                    builder: (BuildContext context, GoRouterState state) =>
                        const NotificationSettingsScreen(),
                  ),
                  GoRoute(
                    path: 'policies',
                    builder: (BuildContext context, GoRouterState state) =>
                        const PoliciesScreen(),
                  ),
                  GoRoute(
                    path: 'withdraw',
                    builder: (BuildContext context, GoRouterState state) =>
                        const WithdrawScreen(),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    ],
  );
});

class _LemonAidRouterApp extends ConsumerWidget {
  const _LemonAidRouterApp();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final BrandTheme brandTheme = ref.watch(brandThemeProvider);
    return MaterialApp.router(
      // 테마 변경 시 트리 전체 재빌드 → static AppColor(brand 계열) 읽는 위젯까지
      // 새 색을 다시 읽는다. GoRouter(routerConfig)는 provider 라 내비 상태 보존.
      key: ValueKey<BrandTheme>(brandTheme),
      title: 'Lemon Aid',
      debugShowCheckedModeBanner: false,
      theme: buildLemonAidTheme(brandTheme.color),
      // 한국어 단일 서비스 — 데이트 피커 등 Material 위젯 문구를 ko 로 고정
      // (가이드 06 (c) 날짜 칩 데이트 피커 ko 로케일).
      locale: const Locale('ko'),
      supportedLocales: const <Locale>[Locale('ko'), Locale('en')],
      localizationsDelegates: const <LocalizationsDelegate<dynamic>>[
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      routerConfig: ref.watch(_routerProvider),
    );
  }
}

class _LemonAidShell extends ConsumerWidget {
  const _LemonAidShell({required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  static const int _cameraIndex = 1;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppController controller = ref.watch(appControllerProvider);
    final bool isCamera = navigationShell.currentIndex == _cameraIndex;
    final String? completedAnalysisRoute = controller.completedAnalysisRoute;

    return Stack(
      children: <Widget>[
        MainShell(navigationShell: navigationShell),
        if (!isCamera && controller.busy)
          const Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: SafeArea(bottom: false, child: LinearProgressIndicator()),
          ),
        if (!isCamera && controller.apiError != null)
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: SafeArea(
              bottom: false,
              child: ErrorPanel(
                error: controller.apiError!,
                onDismissed: controller.clearMessages,
              ),
            ),
          ),
        if (!isCamera && controller.notice != null)
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: SafeArea(
              bottom: false,
              child: _NoticePanel(
                message: controller.notice!,
                actionLabel: completedAnalysisRoute == null ? null : '결과 보기',
                onAction: completedAnalysisRoute == null
                    ? null
                    : () {
                        final String route = completedAnalysisRoute;
                        controller.markAnalysisCompletionRead();
                        controller.clearMessages();
                        context.go(route);
                      },
                onDismissed: () {
                  controller.markAnalysisCompletionRead();
                  controller.clearMessages();
                },
              ),
            ),
          ),
      ],
    );
  }
}

class _SupplementCameraBranch extends ConsumerWidget {
  const _SupplementCameraBranch({
    required this.initialMode,
    required this.initialImageRole,
  });

  final String initialMode;
  final String initialImageRole;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppController controller = ref.watch(appControllerProvider);
    if (!controller.hasMinimumConsents) {
      return ConsentGateSheet(controller: controller);
    }
    return source_camera.CameraScreen(
      key: ValueKey<String>('camera-$initialMode-$initialImageRole'),
      initialMode: initialMode,
      initialImageRole: initialImageRole,
      localPrefs: ref.watch(localPrefsProvider).value,
      onClose: () => context.go('/shell/home'),
      onAnalyzeSupplementImage:
          (String imagePath, {required String ocrProvider}) async {
            await controller.startSupplementImageAnalysis(imagePath);
            if (!context.mounted) return;
            context.go('/shell/home/analysis-result?mode=supplement');
          },
      onAnalyzeSupplementImages:
          (
            List<SupplementImageUpload> images, {
            required String ocrProvider,
            required bool sameSupplementBatch,
          }) async {
            await controller.startSupplementImageBatchAnalysis(
              images,
              sameSupplementBatch: sameSupplementBatch,
            );
            if (!context.mounted) return;
            context.go('/shell/home/analysis-result?mode=supplement');
          },
      onAnalyzeMealImage: (String imagePath) async {
        await controller.startMealImageAnalysis(imagePath);
        if (!context.mounted) return;
        context.go('/shell/home/analysis-result?mode=meal');
      },
    );
  }
}

class _SettingsBranch extends ConsumerWidget {
  const _SettingsBranch();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return source_settings.SettingsScreen(
      controller: ref.watch(appControllerProvider),
      session: ref.watch(tokenSessionProvider),
    );
  }
}

class _BearerTokenLoginScreen extends ConsumerStatefulWidget {
  const _BearerTokenLoginScreen();

  @override
  ConsumerState<_BearerTokenLoginScreen> createState() =>
      _BearerTokenLoginScreenState();
}

class _BearerTokenLoginScreenState
    extends ConsumerState<_BearerTokenLoginScreen> {
  final TextEditingController _tokenController = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _tokenController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: LemonColors.canvas,
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: LemonColors.paper,
                  borderRadius: BorderRadius.circular(LemonRadius.lg),
                  border: Border.all(color: LemonColors.border),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      Text(
                        'Lemon Aid',
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(
                              color: LemonColors.ink,
                              fontFamily: 'AtoZ',
                              fontWeight: FontWeight.w900,
                            ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        '외부 OIDC/JWT 발급 토큰으로 staging API를 테스트합니다.',
                        style: TextStyle(
                          color: LemonColors.inkSoft,
                          height: 1.35,
                        ),
                      ),
                      const SizedBox(height: 18),
                      TextField(
                        controller: _tokenController,
                        obscureText: true,
                        decoration: InputDecoration(
                          labelText: 'JWT bearer token',
                          errorText: _error,
                          border: const OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 14),
                      FilledButton.icon(
                        onPressed: _saveAndEnter,
                        icon: const Icon(Icons.login_rounded),
                        label: const Text('토큰으로 시작'),
                      ),
                      if (!kReleaseMode) ...<Widget>[
                        const SizedBox(height: 8),
                        TextButton(
                          onPressed: () => context.go('/shell/home'),
                          child: const Text('로컬 dev bypass로 계속'),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _saveAndEnter() async {
    setState(() {
      _error = null;
    });
    try {
      await ref
          .read(tokenSessionProvider)
          .saveBearerToken(_tokenController.text);
      if (mounted) {
        context.go('/shell/home');
      }
    } on ArgumentError {
      setState(() {
        _error = '토큰을 입력해주세요.';
      });
    }
  }
}

/// Parses a `?date=YYYY-MM-DD` query into a local date, ignoring invalid input.
DateTime? _parseRecordDate(String? raw) {
  if (raw == null || raw.trim().isEmpty) return null;
  final DateTime? parsed = DateTime.tryParse(raw.trim());
  if (parsed == null) return null;
  return DateTime(parsed.year, parsed.month, parsed.day);
}

class _NeutralBranch extends StatelessWidget {
  const _NeutralBranch({
    required this.icon,
    required this.title,
    required this.message,
  });

  final IconData icon;
  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(icon, color: LemonColors.leaf, size: 56),
              const SizedBox(height: 14),
              Text(
                title,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: LemonColors.ink,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: LemonColors.inkSoft,
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NoticePanel extends StatelessWidget {
  const _NoticePanel({
    required this.message,
    required this.onDismissed,
    this.actionLabel,
    this.onAction,
  });

  final String message;
  final VoidCallback onDismissed;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Theme.of(context).colorScheme.secondaryContainer,
      child: ListTile(
        leading: const Icon(Icons.check_circle_outline),
        title: Text(message),
        subtitle: actionLabel == null
            ? null
            : Align(
                alignment: Alignment.centerLeft,
                child: TextButton(
                  onPressed: onAction,
                  child: Text(actionLabel!),
                ),
              ),
        trailing: IconButton(
          tooltip: 'Dismiss',
          onPressed: onDismissed,
          icon: const Icon(Icons.close),
        ),
      ),
    );
  }
}
