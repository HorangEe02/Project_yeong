// 4주 추이 모델 파싱 테스트 — null-safe 스킵·중복 날짜·정렬 (가이드 06 §4.1).

import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/analysis_trend/analysis_trend_models.dart';

void main() {
  test('parses valid rows ascending and skips malformed entries', () {
    final Map<String, dynamic> json = <String, dynamic>{
      'results': <dynamic>[
        <String, dynamic>{
          'score': 80,
          'measured_date': '2026-06-12',
          'label': 'good',
        },
        // score 비정수 → 스킵 (날조 금지 — 점수를 지어내지 않는다).
        <String, dynamic>{'score': '75', 'measured_date': '2026-06-11'},
        // measured_date 없음 → 스킵.
        <String, dynamic>{'score': 70, 'measured_date': null},
        // label 비문자열 → 점은 유지하되 label null.
        <String, dynamic>{'score': 65, 'measured_date': '2026-06-10', 'label': 3},
        'not-a-map',
        // 같은 날짜 중복 → 응답 순서상 먼저 온 행(최신 생성분)만 유지.
        <String, dynamic>{
          'score': 90,
          'measured_date': '2026-06-12',
          'label': 'excellent',
        },
      ],
      'limit': 28,
      'offset': 0,
    };

    final List<ScoreTrendPoint> points = ScoreTrendPoint.listFromJson(json);

    expect(points.length, 2);
    expect(points.first.date, '2026-06-10');
    expect(points.first.score, 65);
    expect(points.first.label, isNull);
    expect(points.last.date, '2026-06-12');
    expect(points.last.score, 80);
    expect(points.last.label, 'good');
  });

  test('returns an empty list when results is missing or not a list', () {
    expect(ScoreTrendPoint.listFromJson(<String, dynamic>{}), isEmpty);
    expect(
      ScoreTrendPoint.listFromJson(<String, dynamic>{'results': 'oops'}),
      isEmpty,
    );
  });
}
