import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app_controller.dart';
import 'core/api/api_client.dart';
import 'core/config/app_config.dart';
import 'core/storage/local_prefs.dart';
import 'features/ai_coaching/ai_coaching_repository.dart';
import 'features/analysis_trend/analysis_trend_repository.dart';
import 'features/auth/token_session.dart';
import 'features/chat/chat_repository.dart';
import 'features/medical/medical_records_repository.dart';
import 'features/privacy/privacy_repository.dart';
import 'features/profile/profile_repository.dart';
import 'features/reminders/medication_reminder_store.dart';
import 'features/reminders/medication_reminder_sync.dart';
import 'features/supplements/supplement_repository.dart';
import 'shared/services/local_notification_service.dart';

/// Runtime configuration provider.
final Provider<AppConfig> appConfigProvider = Provider<AppConfig>((Ref ref) {
  return AppConfig.fromEnvironment();
});

/// Local persistence wrapper provider (shared_preferences).
///
/// Loads once on first watch. Consumers read `.value` and degrade gracefully to
/// in-memory behavior while the future is still resolving or if it fails.
final FutureProvider<LocalPrefs> localPrefsProvider =
    FutureProvider<LocalPrefs>((Ref ref) {
      return LocalPrefs.create();
    });

/// External bearer-token persistence provider.
final Provider<BearerTokenStore> bearerTokenStoreProvider =
    Provider<BearerTokenStore>((Ref ref) {
      return SecureBearerTokenStore();
    });

/// Local auth/session provider for dev bypass and externally issued JWTs.
final ChangeNotifierProvider<TokenSessionController> tokenSessionProvider =
    ChangeNotifierProvider<TokenSessionController>((Ref ref) {
      final TokenSessionController controller = TokenSessionController(
        store: ref.watch(bearerTokenStoreProvider),
      );
      controller.bootstrap();
      return controller;
    });

/// API client provider for the current `/api/v1` backend contract.
final Provider<ApiClient> apiClientProvider = Provider<ApiClient>((Ref ref) {
  final AppConfig config = ref.watch(appConfigProvider);
  final TokenSessionController session = ref.watch(tokenSessionProvider);
  final ApiClient client = ApiClient(
    baseUrl: config.apiBaseUrl,
    bearerToken: session.bearerToken ?? config.apiToken,
    devGatewayToken: config.devGatewayToken,
  );
  return client;
});

/// Backend repository provider.
final Provider<LemonAidRepository> lemonAidRepositoryProvider =
    Provider<LemonAidRepository>((Ref ref) {
      return BackendLemonAidRepository(apiClient: ref.watch(apiClientProvider));
    });

/// Chatbot repository provider for the chat tab.
final Provider<ChatRepository> chatRepositoryProvider =
    Provider<ChatRepository>((Ref ref) {
      return ChatRepository(apiClient: ref.watch(apiClientProvider));
    });

/// Daily-coaching repository provider for the analysis tab.
final Provider<AiCoachingRepository> aiCoachingRepositoryProvider =
    Provider<AiCoachingRepository>((Ref ref) {
      return AiCoachingRepository(apiClient: ref.watch(apiClientProvider));
    });

/// 일일 건강 점수 4주 추이 저장소 (가이드 06 (a)).
final Provider<AnalysisTrendRepository> analysisTrendRepositoryProvider =
    Provider<AnalysisTrendRepository>((Ref ref) {
      return AnalysisTrendRepository(apiClient: ref.watch(apiClientProvider));
    });

/// App controller provider that preserves the existing endpoint/data flow.
final ChangeNotifierProvider<AppController> appControllerProvider =
    ChangeNotifierProvider<AppController>((Ref ref) {
      final AppController controller = AppController(
        repository: ref.watch(lemonAidRepositoryProvider),
      );
      controller.bootstrap();
      return controller;
    });

/// 신체 정보 스냅샷 저장소 (가이드 08 (a)).
final Provider<ProfileRepository> profileRepositoryProvider =
    Provider<ProfileRepository>((Ref ref) {
      return ProfileRepository(apiClient: ref.watch(apiClientProvider));
    });

/// 만성질환(의료) 레코드 저장소 (가이드 08 (b)).
final Provider<MedicalRecordsRepository> medicalRecordsRepositoryProvider =
    Provider<MedicalRecordsRepository>((Ref ref) {
      return MedicalRecordsRepository(apiClient: ref.watch(apiClientProvider));
    });

/// 동의 관리·탈퇴 저장소 (가이드 08 (f)).
final Provider<PrivacyRepository> privacyRepositoryProvider =
    Provider<PrivacyRepository>((Ref ref) {
      return PrivacyRepository(apiClient: ref.watch(apiClientProvider));
    });

/// 복약 알림 로컬 스토어 (가이드 08 (d) — 로컬 1차 소스).
final Provider<MedicationReminderStore> medicationReminderStoreProvider =
    Provider<MedicationReminderStore>((Ref ref) {
      return MedicationReminderStore(
        prefs: ref.watch(localPrefsProvider).value,
      );
    });

/// 복약 알림 서버 동기화 저장소 (가이드 08 (d) — 서버는 동기화 사본).
final Provider<MedicationReminderSync> medicationReminderSyncProvider =
    Provider<MedicationReminderSync>((Ref ref) {
      return MedicationReminderSync(apiClient: ref.watch(apiClientProvider));
    });

/// 로컬 알림 스케줄러 (실발송 — 테스트에서 override 로 교체 가능).
final Provider<ReminderScheduler> reminderSchedulerProvider =
    Provider<ReminderScheduler>((Ref ref) {
      return LocalNotificationService();
    });
