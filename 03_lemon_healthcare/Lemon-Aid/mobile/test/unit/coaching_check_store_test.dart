// 실천 체크/직접 추가 영속 저장소 단위 테스트 (가이드 06 §4.2·⑦).
//
// 검증: 날짜 키 저장/복원, 일자별 격리, 보관 기한(7일) 정리, 제목 기반 키의
// 순서 변경 내성, 소유 외 키 보존.

import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/ai_coaching/coaching_check_store.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const CoachingCheckStore store = CoachingCheckStore();
  final DateTime day = DateTime(2026, 6, 28);

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  test('saves and restores checked keys and custom titles per date', () async {
    await store.saveChecked(day, <String>{'coach:물 마시기', 'custom:산책'});
    await store.saveCustom(day, <String>['산책']);

    final CoachingDayState state = await store.load(day);
    expect(state.checkedKeys, <String>{'coach:물 마시기', 'custom:산책'});
    expect(state.customTitles, <String>['산책']);

    // 다른 날짜는 비어 있다 — 일자별 격리.
    final CoachingDayState other = await store.load(DateTime(2026, 6, 27));
    expect(other.checkedKeys, isEmpty);
    expect(other.customTitles, isEmpty);
  });

  test('title-based keys survive item reordering', () async {
    // 인덱스가 아니라 제목 키라 저장 순서와 무관하게 같은 집합으로 복원된다.
    await store.saveChecked(day, <String>{'coach:B 항목', 'coach:A 항목'});

    final CoachingDayState state = await store.load(day);
    expect(state.checkedKeys.contains('coach:A 항목'), isTrue);
    expect(state.checkedKeys.contains('coach:B 항목'), isTrue);
  });

  test('cleans up keys older than the retention window on load', () async {
    SharedPreferences.setMockInitialValues(<String, Object>{
      // 18일 전 — 보관 기한(7일) 초과로 정리 대상.
      'coaching_checked:2026-06-10': <String>['coach:옛 항목'],
      'coaching_custom:2026-06-10': <String>['옛 메모'],
      // 6일 전 — 보관.
      'coaching_checked:2026-06-22': <String>['coach:최근 항목'],
      // 날짜 파싱 불가 — 정리.
      'coaching_checked:invalid-date': <String>['coach:깨진 키'],
      // 이 저장소 소유가 아닌 키 — 건드리지 않는다.
      'unrelated_key': 'keep',
    });

    await store.load(day);

    final SharedPreferences prefs = await SharedPreferences.getInstance();
    expect(prefs.getStringList('coaching_checked:2026-06-10'), isNull);
    expect(prefs.getStringList('coaching_custom:2026-06-10'), isNull);
    expect(
      prefs.getStringList('coaching_checked:2026-06-22'),
      <String>['coach:최근 항목'],
    );
    expect(prefs.getStringList('coaching_checked:invalid-date'), isNull);
    expect(prefs.getString('unrelated_key'), 'keep');
  });
}
