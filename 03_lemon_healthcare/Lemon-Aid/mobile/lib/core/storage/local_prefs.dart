// core/storage/local_prefs.dart — 로컬 영속 래퍼 (shared_preferences)
//
// 화면·컨트롤러가 SharedPreferences 를 직접 만지지 않도록 얇게 감싼다.
// 테스트는 SharedPreferences.setMockInitialValues({...}) 로 초기값을 주입한 뒤
// LocalPrefs.create() 로 동일 인스턴스를 얻어 라운드트립을 검증한다.
//
// 영속 대상(가이드 02 (e) · SoT §9.5):
//   - 날짜별 영양제/복약 체크 상태 (자정 지나면 새 날짜 키로 자동 초기화).
//   - 사용자 선택 브랜드 테마.
//
// 키 설계 (날짜는 로컬 타임존 기준 yyyy-MM-dd):
//   home.supplement.checked.<yyyy-MM-dd>  → 체크된 supplement id 리스트
//   home.medication.checked.<yyyy-MM-dd>  → 체크된 medication id 리스트
//   brand.theme                           → 선택 브랜드 테마 코드

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// 일별 체크 상태와 테마 선택을 영속하는 얇은 래퍼.
///
/// 모든 메서드는 동기 캐시(`SharedPreferences`)를 사용하므로 빠르게 동작한다.
class LocalPrefs {
  /// 미리 로드된 [SharedPreferences] 인스턴스로 래퍼를 만든다.
  const LocalPrefs(this._prefs);

  final SharedPreferences _prefs;

  static const String _supplementCheckedPrefix = 'home.supplement.checked.';
  static const String _medicationCheckedPrefix = 'home.medication.checked.';
  static const String _captureGuideDismissedPrefix = 'capture.guide.dismissed.';
  static const String _brandThemeKey = 'brand.theme';
  static const String _profileDisplayNameKey = 'profile_display_name';
  static const String _medicationRemindersKey = 'medication_reminders';
  static const String _notificationSettingsKey = 'notification_settings';
  static const String _firstLaunchKey = 'app.first_launch';
  static const String _profileCareModeKey = 'profile.care_mode';
  static const String _profilePurposesKey = 'profile.purposes';
  static const String _profileConcernsKey = 'profile.concerns';
  static const String _onboardingSeenKey = 'app.onboarding_seen';

  /// `SharedPreferences.getInstance()` 를 기다린 뒤 래퍼를 만든다.
  ///
  /// 최초 실행일(`app.first_launch`)이 없으면 [now]로 1회 기록한다 — 설정
  /// 헤더의 '함께한 지 N일' 산정 기준이다. auth 가 없어 서버 가입일이
  /// 없으므로 로컬 최초 실행일로 임시 산정한다(서버 값 생기면 교체).
  ///
  /// 테스트에서는 호출 전에 `SharedPreferences.setMockInitialValues({...})`
  /// 로 초기값을 주입할 수 있고, [now]로 기준 시각을 고정할 수 있다.
  static Future<LocalPrefs> create({DateTime? now}) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    final LocalPrefs wrapper = LocalPrefs(prefs);
    if (wrapper.firstLaunchDate() == null) {
      await wrapper._setFirstLaunchDate(now ?? DateTime.now());
    }
    return wrapper;
  }

  /// 로컬 [day] 를 `yyyy-MM-dd` 문자열로 만든다 (체크 키의 날짜 부분).
  static String dateKey(DateTime day) {
    final String month = day.month.toString().padLeft(2, '0');
    final String dayOfMonth = day.day.toString().padLeft(2, '0');
    return '${day.year}-$month-$dayOfMonth';
  }

  // ── 영양제 체크 ────────────────────────────────

  /// [day] 에 체크된 영양제 id 집합을 읽는다 (없으면 빈 집합).
  Set<String> supplementCheckedIds(DateTime day) {
    return _readIdSet('$_supplementCheckedPrefix${dateKey(day)}');
  }

  /// [day] 의 체크된 영양제 id 집합을 저장한다.
  Future<void> setSupplementCheckedIds(DateTime day, Set<String> ids) {
    return _writeIdSet('$_supplementCheckedPrefix${dateKey(day)}', ids);
  }

  // ── 복약 체크 ─────────────────────────────────

  /// [day] 에 체크된 복약 id 집합을 읽는다 (없으면 빈 집합).
  Set<String> medicationCheckedIds(DateTime day) {
    return _readIdSet('$_medicationCheckedPrefix${dateKey(day)}');
  }

  /// [day] 의 체크된 복약 id 집합을 저장한다.
  Future<void> setMedicationCheckedIds(DateTime day, Set<String> ids) {
    return _writeIdSet('$_medicationCheckedPrefix${dateKey(day)}', ids);
  }

  // ── 촬영 가이드 모달 '다시 보지 않기' (모드별) ──
  // 가이드 03 ④-3: 모드별 첫 진입 1회 + '다시 보지 않기' 즉시 영속.

  /// [mode]('supplement'/'meal')의 촬영 가이드가 '다시 보지 않기' 상태인지.
  bool captureGuideDismissed(String mode) {
    return _prefs.getBool('$_captureGuideDismissedPrefix${mode.trim()}') ??
        false;
  }

  /// [mode]의 촬영 가이드 '다시 보지 않기' 상태를 저장한다.
  Future<void> setCaptureGuideDismissed(String mode, bool dismissed) {
    final String key = '$_captureGuideDismissedPrefix${mode.trim()}';
    if (!dismissed) {
      return _prefs.remove(key);
    }
    return _prefs.setBool(key, true);
  }

  // ── 최초 실행일 (가입 경과일 임시 산정) ──────────
  // 백엔드 공백: auth 미도입이라 서버 가입일이 없어 로컬 최초 실행일로 대체.

  /// 저장된 최초 실행일(로컬 날짜). 없으면 null.
  DateTime? firstLaunchDate() {
    final String? raw = _prefs.getString(_firstLaunchKey);
    if (raw == null || raw.trim().isEmpty) return null;
    final DateTime? parsed = DateTime.tryParse(raw.trim());
    if (parsed == null) return null;
    return DateTime(parsed.year, parsed.month, parsed.day);
  }

  /// 최초 실행일부터 [today]까지 함께한 일수(첫날 포함, 최소 1).
  ///
  /// 최초 실행일이 없으면 null. [today]가 기록일보다 이전이면(시계 후퇴) 1.
  ///
  /// 두 날짜를 UTC 자정으로 정규화해 빼므로 모든 달력일이 정확히 24시간이다
  /// — 로컬 자정끼리 빼면 봄철 DST(23시간) 구간에서 `Duration.inDays`가
  /// 한 칸 적게 잘려 경과일이 영구히 1 모자라는 버그를 막는다(한국은 DST가
  /// 없으나 코드는 지역 무관).
  int? daysWithApp(DateTime today) {
    final DateTime? first = firstLaunchDate();
    if (first == null) return null;
    final DateTime firstUtc = DateTime.utc(first.year, first.month, first.day);
    final DateTime todayUtc = DateTime.utc(today.year, today.month, today.day);
    final int diff = todayUtc.difference(firstUtc).inDays;
    return diff < 0 ? 1 : diff + 1;
  }

  Future<void> _setFirstLaunchDate(DateTime date) {
    final DateTime dateOnly = DateTime(date.year, date.month, date.day);
    return _prefs.setString(_firstLaunchKey, dateOnly.toIso8601String());
  }

  // ── 온보딩 3장 첫 실행 노출 플래그 ───────────────

  /// 온보딩 3장을 본 적이 있으면 true (첫 실행 1회만 노출하기 위한 게이트).
  bool onboardingSeen() => _prefs.getBool(_onboardingSeenKey) ?? false;

  /// 온보딩을 봤다고 표시한다 (이후 스플래시가 바로 로그인/홈으로 보낸다).
  Future<void> setOnboardingSeen() => _prefs.setBool(_onboardingSeenKey, true);

  // ── 브랜드 테마 ────────────────────────────────

  /// 저장된 브랜드 테마 코드 (없으면 null).
  String? brandThemeCode() {
    final String? value = _prefs.getString(_brandThemeKey);
    if (value == null || value.trim().isEmpty) return null;
    return value;
  }

  /// 브랜드 테마 코드를 저장한다.
  Future<void> setBrandThemeCode(String code) {
    return _prefs.setString(_brandThemeKey, code);
  }

  // ── 프로필 이름(닉네임) ─────────────────────────
  // 백엔드 공백: BodyProfileSnapshotCreate 에 이름 필드가 없어 로컬에만 저장한다.

  /// 저장된 프로필 표시 이름 (없으면 null).
  String? profileDisplayName() {
    final String? value = _prefs.getString(_profileDisplayNameKey);
    if (value == null || value.trim().isEmpty) return null;
    return value.trim();
  }

  /// 프로필 표시 이름을 저장한다. 빈 값이면 키를 제거한다.
  Future<void> setProfileDisplayName(String? name) {
    final String trimmed = name?.trim() ?? '';
    if (trimmed.isEmpty) {
      return _prefs.remove(_profileDisplayNameKey);
    }
    return _prefs.setString(_profileDisplayNameKey, trimmed);
  }

  // ── 가입 목적 / 건강 관심사 (로컬 전용) ─────────────
  // 백엔드 공백: profile-snapshots 에 목적/관심사 필드가 없어 로컬에만 저장한다
  // (가이드 01 2단계, 날조 금지). 선택값은 안정적인 옵션 id 목록으로 보관한다.

  /// 저장된 관리 모드 id(`wellness`/`chronic`)를 읽는다.
  ///
  /// 과거 버전에는 이 키가 없었으므로 null 이면 화면에서 목적/관심사 선택값으로
  /// 보수적으로 추론한다.
  String? profileCareMode() {
    final String? value = _prefs.getString(_profileCareModeKey);
    if (value == null || value.trim().isEmpty) return null;
    return value.trim();
  }

  /// 관리 모드 id를 저장한다. 빈 값이면 키를 제거한다.
  Future<void> setProfileCareMode(String? mode) {
    final String trimmed = mode?.trim() ?? '';
    if (trimmed.isEmpty) {
      return _prefs.remove(_profileCareModeKey);
    }
    return _prefs.setString(_profileCareModeKey, trimmed);
  }

  /// 저장된 가입 목적 id 목록 (없으면 빈 목록).
  List<String> profilePurposes() => _readOrderedList(_profilePurposesKey);

  /// 가입 목적 id 목록을 저장한다 (빈 목록이면 키 제거).
  Future<void> setProfilePurposes(List<String> ids) =>
      _writeOrderedList(_profilePurposesKey, ids);

  /// 저장된 건강 관심사 id 목록 (없으면 빈 목록).
  List<String> profileConcerns() => _readOrderedList(_profileConcernsKey);

  /// 건강 관심사 id 목록을 저장한다 (빈 목록이면 키 제거).
  Future<void> setProfileConcerns(List<String> ids) =>
      _writeOrderedList(_profileConcernsKey, ids);

  List<String> _readOrderedList(String key) {
    final List<String>? raw = _prefs.getStringList(key);
    if (raw == null) return <String>[];
    return raw
        .where((String id) => id.trim().isNotEmpty)
        .toList(growable: false);
  }

  Future<void> _writeOrderedList(String key, List<String> ids) {
    final List<String> clean = ids
        .where((String id) => id.trim().isNotEmpty)
        .toList(growable: false);
    if (clean.isEmpty) {
      return _prefs.remove(key);
    }
    return _prefs.setStringList(key, clean);
  }

  // ── 복약 알림 (로컬 스케줄 1차 소스) ─────────────

  /// 저장된 복약 알림 JSON 객체 목록 (없으면 빈 목록).
  List<Map<String, dynamic>> medicationReminders() {
    final String? raw = _prefs.getString(_medicationRemindersKey);
    if (raw == null || raw.trim().isEmpty) return <Map<String, dynamic>>[];
    final Object? decoded = jsonDecode(raw);
    if (decoded is! List<Object?>) return <Map<String, dynamic>>[];
    return decoded.whereType<Map<String, dynamic>>().toList(growable: false);
  }

  /// 복약 알림 JSON 객체 목록을 저장한다.
  Future<void> setMedicationReminders(List<Map<String, dynamic>> reminders) {
    if (reminders.isEmpty) {
      return _prefs.remove(_medicationRemindersKey);
    }
    return _prefs.setString(_medicationRemindersKey, jsonEncode(reminders));
  }

  // ── 알림 설정 토글 ───────────────────────────────

  /// 저장된 알림 설정 토글 맵 (없으면 빈 맵).
  Map<String, bool> notificationSettings() {
    final String? raw = _prefs.getString(_notificationSettingsKey);
    if (raw == null || raw.trim().isEmpty) return <String, bool>{};
    final Object? decoded = jsonDecode(raw);
    if (decoded is! Map<String, dynamic>) return <String, bool>{};
    final Map<String, bool> result = <String, bool>{};
    decoded.forEach((String key, Object? value) {
      if (value is bool) result[key] = value;
    });
    return result;
  }

  /// 알림 설정 토글 맵을 저장한다.
  Future<void> setNotificationSettings(Map<String, bool> settings) {
    return _prefs.setString(_notificationSettingsKey, jsonEncode(settings));
  }

  // ── 내부 헬퍼 ─────────────────────────────────

  Set<String> _readIdSet(String key) {
    final List<String>? raw = _prefs.getStringList(key);
    if (raw == null) return <String>{};
    return raw.where((String id) => id.trim().isNotEmpty).toSet();
  }

  Future<void> _writeIdSet(String key, Set<String> ids) {
    if (ids.isEmpty) {
      return _prefs.remove(key);
    }
    return _prefs.setStringList(key, ids.toList(growable: false));
  }
}
