// utils/mascot_poses.dart — 레몬 마스코트 15 포즈
//
// 에셋: assets/mascot/poses/<pose>.png  (2x: poses/2x/<pose>.png)
// 원본: character/Lemon-Aid_15poses_assets (2026-05-22 통합)
//
// 사용:
//   Image.asset(MascotPose.thanks.asset, width: 96)
//   또는 화면별 추천: MascotFor.greeting(hour) 등

/// 레몬 마스코트 15 포즈.
/// 각 포즈는 표정/동작이 다름 — 화면 맥락에 맞춰 골라 쓴다.
enum MascotPose {
  find, // 01 돋보기 — 검색·탐색·분석 중
  hello, // 02 인사 — 환영·온보딩
  help, // 03 도움 — 안내·가이드
  happy, // 04 행복 — 좋은 결과·칭찬
  solve, // 05 해결 — 완료·문제 해결
  wow, // 06 놀람 — 발견·강조
  curious, // 07 호기심 — 질문·궁금
  thinking, // 08 생각 — 로딩·분석 중
  fresh, // 09 상큼 — 건강·활력
  thanks, // 10 감사 — 감사·완료 인사
  working, // 11 작업 — 처리 중·진행
  resting, // 12 휴식 — 빈 상태·여유
  celebrate, // 13 축하 — 성취·달성
  fighting, // 14 파이팅 — 응원·동기부여
  cool; // 15 멋짐 — 자신감·프로필

  /// 1x 에셋 경로
  String get asset => 'assets/mascot/poses/$name.png';

  /// 2x 고해상도 에셋 경로
  String get asset2x => 'assets/mascot/poses/2x/$name.png';
}

/// 화면 맥락별 포즈 추천 — 일관된 캐릭터 사용을 위해 한 곳에서 관리.
class MascotFor {
  static const Duration _defaultPoseInterval = Duration(minutes: 5);

  // ─── 홈 인사 — 시간대별 ───
  static MascotPose greeting(int hour) {
    if (hour < 11) return MascotPose.fresh; // 아침 — 상큼
    if (hour < 17) return MascotPose.fighting; // 낮 — 파이팅
    return MascotPose.resting; // 저녁 — 휴식
  }

  /// 홈 히어로에서 쓰는 시간 기반 랜덤 포즈.
  ///
  /// Args:
  ///   time: 현재 시각.
  ///   interval: 같은 포즈를 유지할 시간 버킷.
  ///
  /// Returns:
  ///   시간 버킷마다 결정적으로 바뀌는 마스코트 포즈.
  ///
  /// Raises:
  ///   ArgumentError: [interval]이 0 이하일 때.
  static MascotPose timedRandom(
    DateTime time, {
    Duration interval = _defaultPoseInterval,
  }) {
    if (interval <= Duration.zero) {
      throw ArgumentError.value(interval, 'interval', 'must be positive');
    }
    final int bucket = time.millisecondsSinceEpoch ~/ interval.inMilliseconds;
    final int seed =
        (bucket * 1103515245 + time.weekday * 12345 + time.day) & 0x7fffffff;
    return MascotPose.values[seed % MascotPose.values.length];
  }

  // ─── 화면별 고정 ───
  static const MascotPose onboarding = MascotPose.hello; // 온보딩 환영
  static const MascotPose signupDone = MascotPose.celebrate; // 가입 완료
  static const MascotPose analyzing = MascotPose.thinking; // 분석 로딩
  static const MascotPose analysisGood = MascotPose.happy; // 좋은 분석 결과
  static const MascotPose chat = MascotPose.curious; // 챗봇
  static const MascotPose emptyState = MascotPose.resting; // 빈 상태
  static const MascotPose profile = MascotPose.cool; // 프로필
  static const MascotPose scoreGood = MascotPose.celebrate; // 점수 좋음
  static const MascotPose camera = MascotPose.find; // 촬영·탐색
}
