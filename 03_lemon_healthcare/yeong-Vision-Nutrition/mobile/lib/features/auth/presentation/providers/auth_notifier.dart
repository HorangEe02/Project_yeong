/// 인증 상태 Notifier — TokenStorage 와 동기화 + AuthRepository 호출.
library;

import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/storage/token_storage.dart';
import '../../data/auth_repository.dart';
import '../../domain/auth_errors.dart';
import '../../domain/auth_models.dart';
import '../../domain/auth_state.dart';

part 'auth_notifier.g.dart';

@riverpod
class AuthNotifier extends _$AuthNotifier {
  @override
  Future<AuthState> build() async {
    final TokenStorage storage = ref.watch(tokenStorageProvider);
    final bool hasTokens = await storage.hasTokens();
    if (!hasTokens) {
      return const Unauthenticated();
    }
    // M-2 시점: 사용자 프로필 fetch 엔드포인트 없음 → email/profile 미상.
    // 토큰 보유만으로 Authenticated 처리. 후속 트랙에서 /auth/me 추가.
    return const Authenticated(User(email: ''));
  }

  /// 로그인.
  Future<void> login({required String email, required String password}) async {
    state = const AsyncData<AuthState>(Authenticating());
    state = await AsyncValue.guard<AuthState>(() async {
      try {
        final TokenResponse tokens = await ref
            .read(authRepositoryProvider)
            .login(LoginRequest(email: email, password: password));
        await ref.read(tokenStorageProvider).save(
              accessToken: tokens.accessToken,
              refreshToken: tokens.refreshToken,
            );
        return Authenticated(User(email: email));
      } on InvalidCredentialsException {
        return const AuthFailed('이메일 또는 비밀번호가 올바르지 않습니다.');
      }
    });
  }

  /// 회원가입 + 성공 시 자동 로그인.
  ///
  /// `ConsentRequiredException` 은 호출처가 직접 catch 해 ConsentMatrix 로
  /// 사용자를 되돌리기 위해 rethrow 한다.
  Future<void> register(RegisterRequest request) async {
    state = const AsyncData<AuthState>(Authenticating());
    try {
      final TokenResponse tokens =
          await ref.read(authRepositoryProvider).register(request);
      await ref.read(tokenStorageProvider).save(
            accessToken: tokens.accessToken,
            refreshToken: tokens.refreshToken,
          );
      state = AsyncData<AuthState>(
        Authenticated(User(email: request.email, profile: request.profile)),
      );
    } on EmailAlreadyExistsException {
      state = const AsyncData<AuthState>(
        AuthFailed('이미 가입된 이메일입니다.'),
      );
    } on ConsentRequiredException {
      state = const AsyncData<AuthState>(
        AuthFailed('필요한 동의를 다시 확인해주세요.'),
      );
      rethrow;
    }
  }

  /// 로그아웃 — TokenStorage 비우고 Unauthenticated 로 전환.
  Future<void> logout() async {
    await ref.read(tokenStorageProvider).clear();
    state = const AsyncData<AuthState>(Unauthenticated());
  }
}
