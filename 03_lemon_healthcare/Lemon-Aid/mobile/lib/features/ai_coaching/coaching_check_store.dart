// features/ai_coaching/coaching_check_store.dart — 실천 체크·직접 추가 영속
//
// 오늘의 분석(S-09) 실천 리스트의 로컬 상태를 SharedPreferences 에 일자별로
// 저장한다 (가이드 06 §4.2).
//   - `coaching_checked:{YYYY-MM-DD}` : 체크된 항목 키 목록
//   - `coaching_custom:{YYYY-MM-DD}`  : 사용자가 직접 추가한 실천 제목 목록
//
// 항목 키는 인덱스가 아니라 제목 기반(`coach:{title}` / `custom:{title}`)이다
// — 코칭 재호출로 항목 순서가 바뀌어도 체크가 유지된다. Dart `String.hashCode`
// 는 런타임 버전 간 안정성이 보장되지 않으므로 해시 대신 제목 원문을 키로
// 쓴다.
//
// 영속은 보조 기능이다 — 저장소 실패(테스트 환경 플러그인 부재 등) 시 조용히
// 빈 상태로 강하하고 화면은 세션 메모리로 계속 동작한다.

import 'package:shared_preferences/shared_preferences.dart';

/// 하루치 실천 리스트 영속 상태.
class CoachingDayState {
  /// 하루치 상태를 생성한다.
  ///
  /// Args:
  ///   checkedKeys: 체크된 항목 키 집합.
  ///   customTitles: 사용자가 직접 추가한 실천 제목 목록 (입력 순서).
  const CoachingDayState({
    required this.checkedKeys,
    required this.customTitles,
  });

  /// 체크된 항목 키 집합.
  final Set<String> checkedKeys;

  /// 사용자가 직접 추가한 실천 제목 목록.
  final List<String> customTitles;

  /// 빈 상태.
  static const CoachingDayState empty = CoachingDayState(
    checkedKeys: <String>{},
    customTitles: <String>[],
  );
}

/// 실천 체크/직접 추가 항목의 일자별 SharedPreferences 저장소.
class CoachingCheckStore {
  /// 저장소를 생성한다.
  const CoachingCheckStore();

  static const String _checkedPrefix = 'coaching_checked:';
  static const String _customPrefix = 'coaching_custom:';

  /// 보관 일수 — 기준일에서 이 일수보다 오래된 키는 로드 시 정리한다
  /// (가이드 06 §4.2 "7일 보관").
  static const int retentionDays = 7;

  /// 해당 일자의 영속 상태를 복원하고, 보관 기한이 지난 키를 정리한다.
  ///
  /// Args:
  ///   day: 조회할 로컬 날짜 (시각 성분은 무시).
  ///
  /// Returns:
  ///   복원된 상태. 저장소 접근 실패 시 [CoachingDayState.empty].
  Future<CoachingDayState> load(DateTime day) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      await _cleanup(prefs, day);
      final String key = _dateKey(day);
      return CoachingDayState(
        checkedKeys:
            (prefs.getStringList('$_checkedPrefix$key') ?? const <String>[])
                .toSet(),
        customTitles:
            prefs.getStringList('$_customPrefix$key') ?? const <String>[],
      );
    } catch (_) {
      return CoachingDayState.empty;
    }
  }

  /// 해당 일자의 체크된 항목 키 목록을 저장한다. 실패는 무시한다.
  Future<void> saveChecked(DateTime day, Set<String> keys) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(
        '$_checkedPrefix${_dateKey(day)}',
        keys.toList(growable: false),
      );
    } catch (_) {
      // 영속 실패 — 세션 메모리 동작만 유지.
    }
  }

  /// 해당 일자의 직접 추가 실천 제목 목록을 저장한다. 실패는 무시한다.
  Future<void> saveCustom(DateTime day, List<String> titles) async {
    try {
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(
        '$_customPrefix${_dateKey(day)}',
        List<String>.of(titles, growable: false),
      );
    } catch (_) {
      // 영속 실패 — 세션 메모리 동작만 유지.
    }
  }

  /// 기준일에서 [retentionDays]보다 오래됐거나 날짜를 파싱할 수 없는
  /// 이 저장소 소유 키를 제거한다.
  Future<void> _cleanup(SharedPreferences prefs, DateTime reference) async {
    final DateTime cutoff = DateTime(
      reference.year,
      reference.month,
      reference.day,
    ).subtract(const Duration(days: retentionDays));
    for (final String key in prefs.getKeys().toList(growable: false)) {
      final String? datePart = _ownedDatePart(key);
      if (datePart == null) {
        continue;
      }
      final DateTime? parsed = DateTime.tryParse(datePart);
      if (parsed == null || parsed.isBefore(cutoff)) {
        await prefs.remove(key);
      }
    }
  }

  /// 이 저장소가 소유한 키면 날짜 부분을, 아니면 null 을 반환한다.
  static String? _ownedDatePart(String key) {
    if (key.startsWith(_checkedPrefix)) {
      return key.substring(_checkedPrefix.length);
    }
    if (key.startsWith(_customPrefix)) {
      return key.substring(_customPrefix.length);
    }
    return null;
  }

  static String _dateKey(DateTime day) {
    final String month = day.month.toString().padLeft(2, '0');
    final String date = day.day.toString().padLeft(2, '0');
    return '${day.year}-$month-$date';
  }
}
