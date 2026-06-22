// features/analysis_trend/analysis_trend_models.dart — S-09 4주 추이 모델
//
// GET /analysis-results?analysis_type=daily_health_score 목록 응답의
// 요약 필드(score/measured_date/label)를 차트 점으로 파싱한다 (가이드 06 §4.1).
// 점수·라벨은 서버 산출값만 소비하고 누락 행은 조용히 건너뛴다 (날조 금지).

/// 일일 건강 점수 추이의 한 점.
class ScoreTrendPoint {
  /// 추이 점을 생성한다.
  ///
  /// Args:
  ///   date: 점수가 계산된 로컬 날짜 (`YYYY-MM-DD`).
  ///   score: 0~100 일일 건강 점수.
  ///   label: 서버 5단계 등급 라벨 (색 매핑 전용 — 점수→색 재계산 금지, 가이드 06 §2.4).
  const ScoreTrendPoint({required this.date, required this.score, this.label});

  /// 점수가 계산된 로컬 날짜 (`YYYY-MM-DD`).
  final String date;

  /// 0~100 일일 건강 점수.
  final int score;

  /// 서버 등급 라벨 (excellent/good/moderate/warning/needs_attention), 미상이면 null.
  final String? label;

  /// 목록 응답 JSON에서 추이 점들을 날짜 오름차순으로 파싱한다.
  ///
  /// score/measured_date가 없는 행(타 분석 타입·구버전 스냅샷)은 건너뛰고,
  /// 같은 날짜가 중복되면 응답 순서상 먼저 온 행(최신 생성분)만 남긴다.
  ///
  /// Args:
  ///   json: `GET /analysis-results` 목록 응답 객체.
  ///
  /// Returns:
  ///   날짜 오름차순 추이 점 목록.
  static List<ScoreTrendPoint> listFromJson(Map<String, dynamic> json) {
    final Object? rows = json['results'];
    if (rows is! List<dynamic>) {
      return const <ScoreTrendPoint>[];
    }
    final Map<String, ScoreTrendPoint> byDate = <String, ScoreTrendPoint>{};
    for (final Object? row in rows) {
      if (row is! Map<String, dynamic>) {
        continue;
      }
      final Object? score = row['score'];
      final Object? date = row['measured_date'];
      if (score is! int || date is! String || date.isEmpty) {
        continue;
      }
      final Object? label = row['label'];
      byDate.putIfAbsent(
        date,
        () => ScoreTrendPoint(
          date: date,
          score: score,
          label: label is String && label.isNotEmpty ? label : null,
        ),
      );
    }
    final List<ScoreTrendPoint> points = byDate.values.toList(growable: false)
      ..sort((ScoreTrendPoint a, ScoreTrendPoint b) => a.date.compareTo(b.date));
    return points;
  }
}
