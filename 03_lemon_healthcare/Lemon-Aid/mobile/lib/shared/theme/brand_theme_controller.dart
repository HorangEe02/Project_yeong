// shared/theme/brand_theme_controller.dart — 브랜드 테마 Riverpod 컨트롤러
//
// SoT v1.1 §9.5: 사용자 선택 브랜드 테마를 상태로 관리한다.
// 선택값은 LocalPrefs(shared_preferences) 로 영속 — 앱 기동 시 복원.

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_providers.dart';
import '../../core/storage/local_prefs.dart';
import '../../utils/brand_palette.dart';
import '../../utils/design_tokens_v2.dart';

/// 현재 선택된 [BrandTheme] 을 관리하는 StateNotifier.
///
/// 생성 시 [prefs] 에 저장된 테마 코드가 있으면 그 값으로 복원하고,
/// [select] 호출 시 새 선택을 저장한다. [prefs] 가 null 이면(예: prefs 로드
/// 실패) 인메모리로만 동작한다 — 기능에는 영향 없음.
///
/// 사용법:
/// ```dart
/// final theme = ref.watch(brandThemeProvider);
/// ref.read(brandThemeProvider.notifier).select(BrandTheme.purple);
/// ```
class BrandThemeNotifier extends StateNotifier<BrandTheme> {
  /// 저장된 테마가 있으면 복원하고, 없으면 yellow 로 시작한다.
  BrandThemeNotifier({LocalPrefs? prefs})
    : _prefs = prefs,
      super(_restore(prefs)) {
    // 복원된 테마를 전역 디자인 토큰(AppColor brand 계열)에 즉시 반영.
    _applyToTokens(state);
  }

  final LocalPrefs? _prefs;

  /// 선택된 브랜드 테마 색을 전역 AppColor 토큰에 반영한다.
  /// app.dart 루트가 ValueKey(brandTheme) 로 트리를 재빌드해 화면에 적용된다.
  static void _applyToTokens(BrandTheme theme) {
    AppColor.brand = theme.color;
    AppColor.brandPressed = theme.pressedColor;
    AppColor.brandDeep = theme.deepColor;
    AppColor.brandSoft = theme.softColor;
    AppColor.brandTint = theme.tintColor;
    AppColor.yellow = theme.color;
    AppColor.yellowSoft = theme.softColor;
  }

  static BrandTheme _restore(LocalPrefs? prefs) {
    final String? code = prefs?.brandThemeCode();
    if (code == null) return BrandTheme.yellow;
    for (final BrandTheme theme in BrandTheme.values) {
      if (theme.name == code) return theme;
    }
    return BrandTheme.yellow;
  }

  /// 브랜드 테마를 변경하고 선택을 영속한다.
  void select(BrandTheme theme) {
    if (state == theme) return;
    _applyToTokens(theme); // 전역 토큰 먼저 갱신 후 상태 변경 → 루트 재빌드 시 적용
    state = theme;
    // 저장 실패는 무시 (다음 기동에서 기본값으로 복원되며 기능 영향 없음).
    _prefs?.setBrandThemeCode(theme.name);
  }
}

/// 앱 전역 브랜드 테마 Provider.
///
/// [localPrefsProvider] 가 로드되면 그 값으로 영속을 연결하고, 아직 로딩 중이면
/// 인메모리 기본값으로 동작한다 (로드 완료 시 provider 가 재생성되며 복원).
final StateNotifierProvider<BrandThemeNotifier, BrandTheme> brandThemeProvider =
    StateNotifierProvider<BrandThemeNotifier, BrandTheme>((Ref ref) {
      final LocalPrefs? prefs = ref.watch(localPrefsProvider).value;
      return BrandThemeNotifier(prefs: prefs);
    });
