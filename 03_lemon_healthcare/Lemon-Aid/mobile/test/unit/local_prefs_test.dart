import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('LocalPrefs date-keyed checks', () {
    test('round-trips supplement checked ids for a date', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();
      final DateTime day = DateTime(2026, 6, 12);

      expect(prefs.supplementCheckedIds(day), isEmpty);

      await prefs.setSupplementCheckedIds(day, <String>{'sup-1', 'sup-2'});

      // Re-create from the same mock store to prove persistence, not memory.
      final LocalPrefs reopened = await LocalPrefs.create();
      expect(reopened.supplementCheckedIds(day), <String>{'sup-1', 'sup-2'});
    });

    test('round-trips medication checked ids for a date', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();
      final DateTime day = DateTime(2026, 6, 12);

      await prefs.setMedicationCheckedIds(day, <String>{'med-1'});
      final LocalPrefs reopened = await LocalPrefs.create();
      expect(reopened.medicationCheckedIds(day), <String>{'med-1'});
    });

    test('checks are isolated per date (midnight rollover)', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();
      final DateTime yesterday = DateTime(2026, 6, 11);
      final DateTime today = DateTime(2026, 6, 12);

      await prefs.setSupplementCheckedIds(yesterday, <String>{'sup-1'});

      // Today starts empty even though yesterday has a check.
      expect(prefs.supplementCheckedIds(today), isEmpty);
      expect(prefs.supplementCheckedIds(yesterday), <String>{'sup-1'});
    });

    test('writing an empty set clears the stored key', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();
      final DateTime day = DateTime(2026, 6, 12);

      await prefs.setMedicationCheckedIds(day, <String>{'med-1'});
      await prefs.setMedicationCheckedIds(day, <String>{});

      final LocalPrefs reopened = await LocalPrefs.create();
      expect(reopened.medicationCheckedIds(day), isEmpty);
    });

    test('dateKey zero-pads month and day', () {
      expect(LocalPrefs.dateKey(DateTime(2026, 6, 1)), '2026-06-01');
      expect(LocalPrefs.dateKey(DateTime(2026, 12, 25)), '2026-12-25');
    });
  });

  group('LocalPrefs capture guide dismissal', () {
    test('defaults to not-dismissed for each mode', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();
      expect(prefs.captureGuideDismissed('supplement'), isFalse);
      expect(prefs.captureGuideDismissed('meal'), isFalse);
    });

    test('persists dismissal per mode independently', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();

      await prefs.setCaptureGuideDismissed('supplement', true);

      final LocalPrefs reopened = await LocalPrefs.create();
      // Persists across re-create (영속), and only for the chosen mode.
      expect(reopened.captureGuideDismissed('supplement'), isTrue);
      expect(reopened.captureGuideDismissed('meal'), isFalse);
    });

    test('clears the dismissal when set back to false', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();

      await prefs.setCaptureGuideDismissed('meal', true);
      await prefs.setCaptureGuideDismissed('meal', false);

      final LocalPrefs reopened = await LocalPrefs.create();
      expect(reopened.captureGuideDismissed('meal'), isFalse);
    });
  });

  group('LocalPrefs brand theme', () {
    test('returns null when no theme is stored', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();
      expect(prefs.brandThemeCode(), isNull);
    });

    test('saves and restores the selected theme code', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();

      await prefs.setBrandThemeCode('purple');

      final LocalPrefs reopened = await LocalPrefs.create();
      expect(reopened.brandThemeCode(), 'purple');
    });

    test('restores a theme injected via setMockInitialValues', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{
        'brand.theme': 'green',
      });
      final LocalPrefs prefs = await LocalPrefs.create();
      expect(prefs.brandThemeCode(), 'green');
    });
  });

  group('LocalPrefs profile care mode', () {
    test('saves and clears profile care mode', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();

      expect(prefs.profileCareMode(), isNull);

      await prefs.setProfileCareMode('chronic');
      final LocalPrefs reopened = await LocalPrefs.create();
      expect(reopened.profileCareMode(), 'chronic');

      await reopened.setProfileCareMode('');
      final LocalPrefs cleared = await LocalPrefs.create();
      expect(cleared.profileCareMode(), isNull);
    });
  });

  group('LocalPrefs first-launch (가입 경과일)', () {
    test('seeds first-launch date once and keeps it stable', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create(
        now: DateTime(2026, 6, 1, 14),
      );
      expect(prefs.firstLaunchDate(), DateTime(2026, 6, 1));

      // 이후 실행이 더 늦어도 최초 실행일은 바뀌지 않는다.
      final LocalPrefs reopened = await LocalPrefs.create(
        now: DateTime(2026, 6, 13),
      );
      expect(reopened.firstLaunchDate(), DateTime(2026, 6, 1));
    });

    test('counts inclusive days with the app from the first launch', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create(
        now: DateTime(2026, 6, 1, 9),
      );
      // 첫날 포함 → 같은 날은 1일째, 12일 뒤는 13일째.
      expect(prefs.daysWithApp(DateTime(2026, 6, 1, 23)), 1);
      expect(prefs.daysWithApp(DateTime(2026, 6, 13)), 13);
    });

    test('clamps to 1 when the clock moves backward', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create(
        now: DateTime(2026, 6, 10),
      );
      expect(prefs.daysWithApp(DateTime(2026, 6, 5)), 1);
    });

    test(
      'inclusive count is timezone-stable across a DST-crossing span',
      () async {
        // 2/1 → 5/1 은 89일 차이(포함 90일)다. 봄철 DST 구간을 지나는 이 구간을
        // 로컬 자정끼리 빼면 inDays 가 한 칸 적게 잘려 89가 나오지만, UTC 정규화
        // 덕에 어느 지역/CI 에서도 90으로 고정된다(회귀 가드).
        SharedPreferences.setMockInitialValues(<String, Object>{});
        final LocalPrefs prefs = await LocalPrefs.create(
          now: DateTime(2026, 2, 1),
        );
        expect(prefs.daysWithApp(DateTime(2026, 5, 1)), 90);
      },
    );

    test('returns null days when no first-launch date is stored', () async {
      // create() 가 시드하므로, 시드 없는 상태를 흉내내려면 직접 래핑한다.
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final SharedPreferences raw = await SharedPreferences.getInstance();
      final LocalPrefs prefs = LocalPrefs(raw);
      expect(prefs.firstLaunchDate(), isNull);
      expect(prefs.daysWithApp(DateTime(2026, 6, 13)), isNull);
    });
  });
}
