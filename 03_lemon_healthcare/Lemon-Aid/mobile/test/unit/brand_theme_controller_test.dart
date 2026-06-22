import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:lemon_aid_mobile/shared/theme/brand_theme_controller.dart';
import 'package:lemon_aid_mobile/utils/brand_palette.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('defaults to yellow without persisted prefs', () {
    final BrandThemeNotifier notifier = BrandThemeNotifier();
    expect(notifier.state, BrandTheme.yellow);
  });

  test('restores the persisted theme on construction', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{
      'brand.theme': 'blue',
    });
    final LocalPrefs prefs = await LocalPrefs.create();

    final BrandThemeNotifier notifier = BrandThemeNotifier(prefs: prefs);
    expect(notifier.state, BrandTheme.blue);
  });

  test('select persists the chosen theme', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final LocalPrefs prefs = await LocalPrefs.create();
    final BrandThemeNotifier notifier = BrandThemeNotifier(prefs: prefs);

    notifier.select(BrandTheme.green);
    expect(notifier.state, BrandTheme.green);

    // A fresh notifier reading the same store restores the selection.
    final LocalPrefs reopened = await LocalPrefs.create();
    final BrandThemeNotifier restored = BrandThemeNotifier(prefs: reopened);
    expect(restored.state, BrandTheme.green);
  });

  test('falls back to yellow for an unknown persisted code', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{
      'brand.theme': 'rainbow',
    });
    final LocalPrefs prefs = await LocalPrefs.create();
    final BrandThemeNotifier notifier = BrandThemeNotifier(prefs: prefs);
    expect(notifier.state, BrandTheme.yellow);
  });
}
