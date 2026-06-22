// screens/score_screen.dart — '오늘의 분석' 탭 (figma S-09)
//
// 디자인:
//   - 헤더 '오늘의 분석' + 날짜 칩(탭 → 데이트 피커, 오늘−27일 ~ 오늘)
//       + 과거 보기 상태에서만 '오늘' 복귀 칩 (가이드 06 §4.3)
//   - 카드 1 '오늘의 종합 분석' + 등급 칩: 도넛 링(점수/100, 등급 색) + 종합 코멘트
//       + 연노랑 CTA '🍋 레몬봇에게 물어보기 ›'
//       과거일은 추이 이력 스냅샷(점수·등급 색)으로 표시, 이력 없으면 안내 문구
//   - 카드 2 '실천 리스트'('오늘 챙기면 좋은 N가지'): 체크 원형 + 항목들
//       + safety_warnings 안내 행. 체크·직접 추가는 coaching_check_store 로
//       일자별 영속, 과거일은 읽기 전용 (가이드 06 §4.2~4.3)
//   - 카드 3 '스마트 분석' '지난 4주 추이': 이력 7일치 미만이면 잠금 placeholder
//   - 하단 면책
//
// 데이터:
//   - 종합 점수·등급·코멘트: AppController dashboard summary health_score (배치 A 모델)
//   - 실천 리스트: POST /ai-agent/daily-coaching (AiCoachingRepository)
//   - 선택일 1회 캐시 (날짜 키) — 같은 날짜 재진입 시 재호출하지 않음
//   - 등급 색: shared/score_label_colors (홈 점수 카드와 동일 매핑 — §2.4)
//
// 연산은 모두 백엔드. 모바일은 표시만.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../app_controller.dart';
import '../features/ai_coaching/ai_coaching_models.dart';
import '../features/ai_coaching/ai_coaching_repository.dart';
import '../features/ai_coaching/coaching_check_store.dart';
import '../features/analysis_trend/analysis_trend_models.dart';
import '../features/analysis_trend/analysis_trend_repository.dart';
import '../features/dashboard/home_models.dart';
import '../shared/score_label_colors.dart';
import '../utils/design_tokens_v2.dart';
import '../utils/mascot_poses.dart';
import '../widgets/common/medical_disclaimer.dart';
import '../widgets/common/pressable.dart';

/// 오늘의 분석 화면 (figma S-09).
class ScoreScreen extends StatefulWidget {
  /// 오늘의 분석 화면을 생성한다.
  ///
  /// Args:
  ///   controller: 점수·당일 식사·등록 영양제를 제공하는 앱 컨트롤러.
  ///   coachingRepository: 실천 리스트(daily-coaching) 호출 저장소.
  ///   trendRepository: 4주 추이 조회 저장소 (미주입 시 추이 카드는 잠금 유지).
  ///   checkStore: 실천 체크·직접 추가 일자별 영속 저장소 (미주입 시 기본 생성).
  ///   now: 현재 시각 공급자 — 테스트에서 기준일 고정용. 미주입 시 DateTime.now.
  const ScoreScreen({
    required this.controller,
    required this.coachingRepository,
    this.trendRepository,
    this.checkStore,
    this.now,
    super.key,
  });

  /// 점수·당일 식사·등록 영양제를 제공하는 앱 컨트롤러.
  final AppController controller;

  /// 실천 리스트 호출 저장소.
  final AiCoachingRepository coachingRepository;

  /// 4주 추이 조회 저장소 — 미주입 시 추이 카드는 잠금 placeholder 유지.
  final AnalysisTrendRepository? trendRepository;

  /// 실천 체크·직접 추가 영속 저장소 — 미주입 시 기본 SharedPreferences 저장소.
  final CoachingCheckStore? checkStore;

  /// 현재 시각 공급자 — 테스트에서 기준일을 고정할 때 주입한다.
  final DateTime Function()? now;

  @override
  State<ScoreScreen> createState() => _ScoreScreenState();
}

class _ScoreScreenState extends State<ScoreScreen> {
  // 실천 리스트 로딩 상태.
  bool _loadingCoaching = false;
  // 실천 리스트 호출 실패 여부 (카드 내 가벼운 오류 상태).
  bool _coachingFailed = false;
  // 마지막으로 받은 실천 리스트 결과.
  DailyCoachingResult? _coaching;
  // 선택일별 결과 캐시 (키: YYYY-MM-DD). 같은 날짜 재진입 시 재호출하지 않아
  // 생성형 코칭 재실행으로 제목이 바뀌어 체크 표시가 탈락하는 것을 막는다.
  final Map<String, DailyCoachingResult> _coachingCache =
      <String, DailyCoachingResult>{};
  // 체크된 실천 항목 키 — 제목 기반(coach:/custom:), 일자별 영속 (가이드 06 §4.2).
  Set<String> _checkedKeys = <String>{};
  // 4주 추이 점들 — 7일치 미만이면 잠금 카드 유지 (가이드 06 §4.1).
  List<ScoreTrendPoint> _trendPoints = const <ScoreTrendPoint>[];
  // 사용자가 직접 추가한 실천 항목 — coaching_check_store 로 일자별 영속.
  List<String> _customPractices = <String>[];
  // 조회 중인 날짜 — 기본 오늘, 날짜 칩으로 과거(−27일) 조회 가능 (가이드 06 §4.3).
  late DateTime _selectedDay;

  AppController get _controller => widget.controller;

  late final CoachingCheckStore _checkStore =
      widget.checkStore ?? const CoachingCheckStore();

  DateTime get _today {
    final DateTime now = (widget.now ?? DateTime.now)();
    return DateTime(now.year, now.month, now.day);
  }

  /// 오늘을 보고 있는지 여부 — 과거일은 체크 읽기 전용 + 추가 CTA 숨김.
  bool get _viewingToday => _selectedDay == _today;

  static String _dateKey(DateTime day) {
    final String month = day.month.toString().padLeft(2, '0');
    final String date = day.day.toString().padLeft(2, '0');
    return '${day.year}-$month-$date';
  }

  @override
  void initState() {
    super.initState();
    _selectedDay = _today;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadDayState();
      _loadCoaching();
      _loadTrend();
    });
  }

  /// 선택일의 체크·직접 추가 상태를 영속 저장소에서 복원한다.
  ///
  /// 저장소가 보관 기한(7일)이 지난 키를 로드 시 정리하므로, 날짜가 바뀌면
  /// 체크는 자연히 초기화된다 (가이드 06 §4.2 DoD).
  Future<void> _loadDayState() async {
    final DateTime day = _selectedDay;
    final CoachingDayState state = await _checkStore.load(day);
    if (!mounted || day != _selectedDay) {
      return;
    }
    setState(() {
      _checkedKeys = <String>{...state.checkedKeys};
      _customPractices = <String>[...state.customTitles];
    });
  }

  /// 영속된 일일 점수 이력을 불러온다. 미가용 시 잠금 카드를 유지한다.
  Future<void> _loadTrend() async {
    final AnalysisTrendRepository? repository = widget.trendRepository;
    if (repository == null) {
      return;
    }
    try {
      final List<ScoreTrendPoint> points = await repository
          .fetchDailyScoreTrend();
      if (!mounted) return;
      setState(() => _trendPoints = points);
    } on Exception {
      // 추이 미가용(이력 부족·일시 오류)은 화면 오류로 승격하지 않는다 —
      // 폴백 표(가이드 06 §5): 잠금 카드 "기록이 쌓이면 추이를 보여드려요" 유지.
    }
  }

  /// 선택일의 실천 리스트를 불러온다. 같은 날짜로 이미 받았으면 재호출하지 않는다.
  Future<void> _loadCoaching({bool force = false}) async {
    final DateTime day = _selectedDay;
    final String key = _dateKey(day);
    if (!force) {
      final DailyCoachingResult? cached = _coachingCache[key];
      if (cached != null) {
        if (!identical(_coaching, cached)) {
          setState(() => _coaching = cached);
        }
        return;
      }
    }
    if (_loadingCoaching) return;
    setState(() {
      _loadingCoaching = true;
      _coachingFailed = false;
    });
    try {
      final DailyCoachingResult result = await widget.coachingRepository
          .runDailyCoaching(
            day: day,
            meals: _controller.mealsForDay(day),
            supplements: _controller.homeSupplements.results,
          );
      if (!mounted) return;
      if (day != _selectedDay) {
        // 응답 대기 중 조회 날짜가 바뀜 — 결과를 버리고 현재 선택일로 재요청.
        _loadingCoaching = false;
        unawaited(_loadCoaching());
        return;
      }
      setState(() {
        _coaching = result;
        _coachingCache[key] = result;
        _loadingCoaching = false;
      });
    } catch (_) {
      if (!mounted) return;
      if (day != _selectedDay) {
        _loadingCoaching = false;
        unawaited(_loadCoaching());
        return;
      }
      setState(() {
        _coachingFailed = true;
        _loadingCoaching = false;
      });
    }
  }

  /// 실천 항목 체크를 토글하고 선택일 키로 영속한다.
  ///
  /// 과거 일자 보기는 읽기 전용이라 무시한다 (가이드 06 §4.3).
  void _toggleItem(String itemKey) {
    if (!_viewingToday) {
      return;
    }
    setState(() {
      if (!_checkedKeys.add(itemKey)) {
        _checkedKeys.remove(itemKey);
      }
    });
    unawaited(_checkStore.saveChecked(_selectedDay, _checkedKeys));
  }

  /// 직접 입력으로 오늘 실천 항목을 추가한다 (figma 800:23 CTA).
  ///
  /// 사용자 입력 텍스트는 서버 권고가 아니라 본인 메모이므로 그대로 표시한다.
  Future<void> _addPractice() async {
    final String? entered = await showDialog<String>(
      context: context,
      builder: (BuildContext dialogContext) => const _AddPracticeDialog(),
    );
    final String title = (entered ?? '').trim();
    if (title.isEmpty || !mounted) {
      return;
    }
    // 체크 키가 제목 기반이라 같은 제목 두 행은 함께 토글된다 — 중복 추가 차단.
    if (_customPractices.contains(title)) {
      return;
    }
    setState(() => _customPractices.add(title));
    unawaited(_checkStore.saveCustom(_selectedDay, _customPractices));
  }

  /// 날짜 칩 탭 — 오늘−27일 ~ 오늘 범위의 데이트 피커를 연다 (가이드 06 §4.3).
  Future<void> _pickDay() async {
    final DateTime today = _today;
    final DateTime firstDate = today.subtract(const Duration(days: 27));
    // 화면이 자정을 넘겨 살아 있으면 _selectedDay 가 새 범위 밖일 수 있다 —
    // 범위 밖 initialDate 는 showDatePicker assert 로 죽으므로 클램프.
    DateTime initial = _selectedDay;
    if (initial.isBefore(firstDate)) {
      initial = firstDate;
    } else if (initial.isAfter(today)) {
      initial = today;
    }
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: firstDate,
      lastDate: today,
    );
    if (picked == null || !mounted) {
      return;
    }
    _selectDay(DateTime(picked.year, picked.month, picked.day));
  }

  /// 조회 날짜를 바꾸고 해당 일자의 체크 상태·실천 리스트를 다시 불러온다.
  void _selectDay(DateTime day) {
    if (day == _selectedDay) {
      return;
    }
    setState(() {
      _selectedDay = day;
      // 캐시에 있으면 즉시 표시하고 재호출하지 않는다 (선택일 1회 캐시).
      _coaching = _coachingCache[_dateKey(day)];
      _coachingFailed = false;
      _checkedKeys = <String>{};
      _customPractices = <String>[];
    });
    unawaited(_loadDayState());
    unawaited(_loadCoaching());
  }

  /// 선택일의 점수 이력 스냅샷을 추이 점에서 찾는다. 없으면 null.
  ///
  /// 과거 점수는 GET /dashboard/summary 가 재계산하지 않으므로(당일 전용)
  /// analysis-results 이력(추이 조회 결과)에서만 가져온다 (가이드 06 §4.3).
  ScoreTrendPoint? _historyPointFor(DateTime day) {
    final String key = _dateKey(day);
    for (final ScoreTrendPoint point in _trendPoints) {
      if (point.date == key) {
        return point;
      }
    }
    return null;
  }

  void _openCamera() {
    context.go('/shell/camera?mode=meal');
  }

  void _openLemonBot() {
    context.go('/shell/chat');
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (BuildContext context, Widget? child) {
        final DashboardHealthScore score = _controller.healthScore;
        return Scaffold(
          backgroundColor: AppColor.bg,
          body: SafeArea(
            bottom: false,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                AppSpace.page,
                AppSpace.lg,
                AppSpace.page,
                AppSpace.xl + 80,
              ),
              children: <Widget>[
                _Header(
                  day: _selectedDay,
                  isToday: _viewingToday,
                  onTapDate: _pickDay,
                  onBackToToday: () => _selectDay(_today),
                ),
                const SizedBox(height: AppSpace.lg),
                if (_viewingToday)
                  _SummaryCard(
                    score: score,
                    onLemonBot: _openLemonBot,
                    onRecord: _openCamera,
                  )
                else
                  _PastSummaryCard(point: _historyPointFor(_selectedDay)),
                const SizedBox(height: AppSpace.md),
                _ChecklistCard(
                  loading: _loadingCoaching,
                  failed: _coachingFailed,
                  coaching: _coaching,
                  checkedKeys: _checkedKeys,
                  onToggle: _toggleItem,
                  onRetry: () => _loadCoaching(force: true),
                  customItems: _customPractices,
                  onAddPractice: _addPractice,
                  readOnly: !_viewingToday,
                ),
                const SizedBox(height: AppSpace.md),
                _TrendCard(points: _trendPoints, onLemonBot: _openLemonBot),
                const SizedBox(height: AppSpace.lg),
                const MedicalDisclaimer(variant: DisclaimerVariant.summary),
              ],
            ),
          ),
        );
      },
    );
  }
}

// ═══════════════════════════════════════════
// 헤더 — '오늘의 분석' + 날짜 칩(탭 → 데이트 피커) + '오늘' 복귀 칩
//   과거 보기 상태에서만 '오늘' 칩 노출 (가이드 06 §4.3)
// ═══════════════════════════════════════════
class _Header extends StatelessWidget {
  final DateTime day;
  final bool isToday;
  final VoidCallback onTapDate;
  final VoidCallback onBackToToday;
  const _Header({
    required this.day,
    required this.isToday,
    required this.onTapDate,
    required this.onBackToToday,
  });

  static const List<String> _weekdays = <String>[
    '월',
    '화',
    '수',
    '목',
    '금',
    '토',
    '일',
  ];

  @override
  Widget build(BuildContext context) {
    final String label =
        '${day.month}월 ${day.day}일 (${_weekdays[day.weekday - 1]})';
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: <Widget>[
        Text('오늘의 분석', style: AppText.title),
        Row(
          children: <Widget>[
            if (!isToday) ...<Widget>[
              Pressable(
                onTap: onBackToToday,
                // 칩 시각 크기는 유지하되 히트 영역은 시니어 최소 48 확보
                // (Pressable 은 자식 크기 그대로가 터치 영역).
                child: Container(
                  constraints: const BoxConstraints(
                    minHeight: 48,
                    minWidth: 48,
                  ),
                  alignment: Alignment.center,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpace.md,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: AppColor.brand,
                      borderRadius: BorderRadius.circular(AppRadius.full),
                    ),
                    child: Text(
                      '오늘',
                      style: AppText.caption.copyWith(
                        color: AppColor.ink,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: AppSpace.sm),
            ],
            Pressable(
              onTap: onTapDate,
              // 칩 시각 크기는 유지하되 히트 영역은 시니어 최소 48 확보.
              child: Container(
                constraints: const BoxConstraints(minHeight: 48, minWidth: 48),
                alignment: Alignment.center,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpace.md,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: AppColor.brandSoft,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(
                        label,
                        style: AppText.caption.copyWith(
                          color: AppColor.brandDeep,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(width: 2),
                      Icon(
                        Icons.expand_more_rounded,
                        color: AppColor.brandDeep,
                        size: 16,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 카드 데코 — 대시보드 톤과 통일 (§17)
// ═══════════════════════════════════════════
BoxDecoration _cardDeco() => BoxDecoration(
  color: AppColor.surface,
  borderRadius: BorderRadius.circular(AppRadius.lg),
  boxShadow: AppShadow.softCard,
);

// ═══════════════════════════════════════════
// 카드 1 — 오늘의 종합 분석
//   도넛 링(점수/100) + 등급 칩 + 종합 코멘트 + 레몬봇 CTA
//   not_ready → 기록 추가 안내 + 촬영 CTA
// ═══════════════════════════════════════════
class _SummaryCard extends StatelessWidget {
  final DashboardHealthScore score;
  final VoidCallback onLemonBot;
  final VoidCallback onRecord;
  const _SummaryCard({
    required this.score,
    required this.onLemonBot,
    required this.onRecord,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside + 2),
      decoration: _cardDeco(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: <Widget>[
              Text('오늘의 종합 분석', style: AppText.subtitle),
              if (score.isReady && score.labelText != null)
                _GradeChip(label: score.labelText!, labelCode: score.label),
            ],
          ),
          const SizedBox(height: AppSpace.lg),
          if (score.isReady)
            _ReadyBody(score: score, onLemonBot: onLemonBot)
          else
            _NotReadyBody(onRecord: onRecord),
        ],
      ),
    );
  }
}

class _ReadyBody extends StatelessWidget {
  final DashboardHealthScore score;
  final VoidCallback onLemonBot;
  const _ReadyBody({required this.score, required this.onLemonBot});

  @override
  Widget build(BuildContext context) {
    final String? message = score.message;
    final bool hasMessage = message != null && message.trim().isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Center(
          child: _ScoreRing(
            score: score.score ?? 0,
            color: scoreLabelColor(score.label),
          ),
        ),
        const SizedBox(height: AppSpace.lg),
        Text(
          hasMessage ? message.trim() : '오늘 기록을 바탕으로 한 종합 코멘트예요.',
          style: AppText.body.copyWith(
            color: AppColor.inkSecondary,
            height: 1.55,
          ),
        ),
        const SizedBox(height: AppSpace.lg),
        _LemonBotCta(onTap: onLemonBot),
      ],
    );
  }
}

class _NotReadyBody extends StatelessWidget {
  final VoidCallback onRecord;
  const _NotReadyBody({required this.onRecord});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          '기록을 추가하면 점수를 보여드려요.',
          style: AppText.body.copyWith(
            color: AppColor.inkSecondary,
            height: 1.55,
          ),
        ),
        const SizedBox(height: AppSpace.lg),
        SizedBox(
          width: double.infinity,
          child: AppPrimaryButton(label: '촬영하기', onPressed: onRecord),
        ),
      ],
    );
  }
}

// 과거 일자 점수 카드 — 이력 스냅샷 표시 또는 준비 안내 (가이드 06 §4.3).
class _PastSummaryCard extends StatelessWidget {
  final ScoreTrendPoint? point;
  const _PastSummaryCard({required this.point});

  @override
  Widget build(BuildContext context) {
    final ScoreTrendPoint? history = point;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside + 2),
      decoration: _cardDeco(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text('종합 분석', style: AppText.subtitle),
          const SizedBox(height: AppSpace.lg),
          if (history == null)
            Text(
              '지난 날짜의 점수는 준비 중이에요. 실천 기록만 보여드려요.',
              style: AppText.body.copyWith(
                color: AppColor.inkSecondary,
                height: 1.55,
              ),
            )
          else ...<Widget>[
            Center(
              child: _ScoreRing(
                score: history.score,
                color: scoreLabelColor(history.label),
              ),
            ),
            const SizedBox(height: AppSpace.md),
            // 당일 점수는 재조회 시점 기록 상태로 재계산되므로, 과거에 본
            // 점수와 이력 저장값이 다를 수 있다 — measured_date 기준 캡션.
            Center(
              child: Text(
                '기록 당시 기준이에요',
                style: AppText.caption.copyWith(color: AppColor.inkTertiary),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// 등급 칩 (예: '좋아요') — 색은 서버 label 코드 매핑 (가이드 06 §2.4).
class _GradeChip extends StatelessWidget {
  final String label;
  // 서버 등급 코드 — 색 매핑 전용. null·미지 값은 브랜드 색 폴백.
  final String? labelCode;
  const _GradeChip({required this.label, this.labelCode});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 5),
      decoration: BoxDecoration(
        color: scoreLabelSoftColor(labelCode),
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        label,
        style: AppText.caption.copyWith(
          color: scoreLabelColor(labelCode),
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

/// 도넛 링 점수 (점수/100) — 진행 색은 등급 매핑, 중앙 숫자는 ink 유지.
class _ScoreRing extends StatelessWidget {
  final int score;
  final Color? color;
  const _ScoreRing({required this.score, this.color});

  @override
  Widget build(BuildContext context) {
    final double ratio = (score.clamp(0, 100)) / 100;
    return SizedBox(
      width: 148,
      height: 148,
      child: Stack(
        alignment: Alignment.center,
        children: <Widget>[
          SizedBox(
            width: 148,
            height: 148,
            child: CircularProgressIndicator(
              value: ratio,
              strokeWidth: 12,
              backgroundColor: AppColor.section,
              valueColor: AlwaysStoppedAnimation<Color>(
                color ?? AppColor.brand,
              ),
            ),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(
                '$score',
                style: const TextStyle(
                  fontFamily: 'Pretendard',
                  color: AppColor.ink,
                  fontSize: 44,
                  fontWeight: FontWeight.w800,
                  height: 1,
                  letterSpacing: 0,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                '/ 100',
                style: AppText.caption.copyWith(color: AppColor.inkTertiary),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// 연노랑 '레몬봇에게 물어보기' CTA.
class _LemonBotCta extends StatelessWidget {
  final VoidCallback onTap;
  const _LemonBotCta({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.lg,
          vertical: AppSpace.md + 2,
        ),
        decoration: BoxDecoration(
          color: AppColor.brandSoft,
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        child: Row(
          children: <Widget>[
            // Figma 800:23 — 레몬봇 마스코트 캐릭터(돋보기 포즈). 이모지 아님.
            Image.asset(MascotPose.find.asset, width: 24, height: 24),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: Text(
                '레몬봇에게 물어보기',
                style: AppText.body.copyWith(
                  color: AppColor.brandDeep,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            Icon(
              Icons.chevron_right_rounded,
              color: AppColor.brandDeep,
              size: 22,
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 카드 2 — 실천 리스트 ('오늘 챙기면 좋은 N가지')
//   recommendations + actions → 체크 원형 항목 (세션 메모리)
//   requires_user_approval=true → '기록을 확정하면 맞춤 제안을 드려요' 안내
//   호출 실패 → 가벼운 오류 상태 + 재시도 버튼
// ═══════════════════════════════════════════
// 직접 실천 추가 다이얼로그 — 컨트롤러를 자체 수명주기로 관리한다.
// (pop 직후 외부에서 dispose하면 닫힘 애니메이션 중인 TextField가 깨진다.)
class _AddPracticeDialog extends StatefulWidget {
  const _AddPracticeDialog();

  @override
  State<_AddPracticeDialog> createState() => _AddPracticeDialogState();
}

class _AddPracticeDialogState extends State<_AddPracticeDialog> {
  final TextEditingController _input = TextEditingController();

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: AppColor.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      title: Text('오늘 실천 추가하기', style: AppText.subtitle),
      content: TextField(
        controller: _input,
        autofocus: true,
        style: AppText.body,
        decoration: InputDecoration(
          hintText: '예: 물 한 잔 더 마시기',
          hintStyle: AppText.body.copyWith(color: AppColor.inkTertiary),
        ),
        textInputAction: TextInputAction.done,
        onSubmitted: (String value) => Navigator.of(context).pop(value),
      ),
      actions: <Widget>[
        TextButton(
          style: TextButton.styleFrom(minimumSize: const Size(64, 48)),
          onPressed: () => Navigator.of(context).pop(),
          child: Text(
            '취소',
            style: AppText.body.copyWith(color: AppColor.inkSecondary),
          ),
        ),
        TextButton(
          style: TextButton.styleFrom(minimumSize: const Size(64, 48)),
          onPressed: () => Navigator.of(context).pop(_input.text),
          child: Text(
            '추가',
            style: AppText.body.copyWith(
              color: AppColor.brandDeep,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}

class _ChecklistCard extends StatelessWidget {
  final bool loading;
  final bool failed;
  final DailyCoachingResult? coaching;
  final Set<String> checkedKeys;
  final ValueChanged<String> onToggle;
  final VoidCallback onRetry;
  final List<String> customItems;
  final VoidCallback onAddPractice;
  // 과거 일자 보기 — 체크 토글 잠금 + 추가 CTA 숨김 (가이드 06 §4.3).
  final bool readOnly;
  const _ChecklistCard({
    required this.loading,
    required this.failed,
    required this.coaching,
    required this.checkedKeys,
    required this.onToggle,
    required this.onRetry,
    required this.customItems,
    required this.onAddPractice,
    required this.readOnly,
  });

  /// 코칭 항목의 영속 체크 키 — 제목 기반이라 재호출로 순서가 바뀌어도 유지.
  static String coachKey(String title) => 'coach:$title';

  /// 직접 추가 항목의 영속 체크 키.
  static String customKey(String title) => 'custom:$title';

  @override
  Widget build(BuildContext context) {
    final DailyCoachingResult? result = coaching;
    final int count = (result?.items.length ?? 0) + customItems.length;
    final List<String> warnings = result?.safetyWarnings ?? const <String>[];
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside + 2),
      decoration: _cardDeco(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            count > 0 ? '오늘 챙기면 좋은 $count가지' : '실천 리스트',
            style: AppText.subtitle,
          ),
          const SizedBox(height: AppSpace.md),
          _buildBody(result),
          if (customItems.isNotEmpty) ...<Widget>[
            if (result != null && result.items.isNotEmpty)
              Divider(color: AppColor.border, height: AppSpace.lg),
            for (int i = 0; i < customItems.length; i++) ...<Widget>[
              _ChecklistRow(
                title: customItems[i],
                subtitle: '내가 추가한 실천',
                checked: checkedKeys.contains(customKey(customItems[i])),
                onToggle: readOnly
                    ? null
                    : () => onToggle(customKey(customItems[i])),
              ),
              if (i != customItems.length - 1)
                Divider(color: AppColor.border, height: AppSpace.lg),
            ],
          ],
          if (warnings.isNotEmpty) ...<Widget>[
            const SizedBox(height: AppSpace.lg),
            for (int i = 0; i < warnings.length; i++) ...<Widget>[
              _SafetyWarningRow(text: warnings[i]),
              if (i != warnings.length - 1) const SizedBox(height: AppSpace.sm),
            ],
          ],
          if (!loading && !readOnly) ...<Widget>[
            const SizedBox(height: AppSpace.lg),
            // figma 800:23 — 카드 하단 풀폭 CTA. 시니어 최소 높이 52.
            AppPrimaryButton(
              label: '오늘 실천 추가하기',
              height: 52,
              leading: const Icon(
                Icons.add_rounded,
                color: Colors.white,
                size: 20,
              ),
              onPressed: onAddPractice,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildBody(DailyCoachingResult? result) {
    if (loading && result == null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
        child: Center(
          child: SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(
              strokeWidth: 2.4,
              valueColor: AlwaysStoppedAnimation<Color>(AppColor.brand),
            ),
          ),
        ),
      );
    }
    if (failed && result == null) {
      return _ChecklistError(onRetry: onRetry);
    }
    if (result != null && result.requiresUserApproval && result.items.isEmpty) {
      return _ChecklistHint(text: '기록을 확정하면 맞춤 제안을 드려요.');
    }
    if (result == null || result.items.isEmpty) {
      return _ChecklistHint(text: '오늘 끼니와 영양제를 기록하면 실천 항목을 만들어 드려요.');
    }
    return Column(
      children: <Widget>[
        for (int i = 0; i < result.items.length; i++) ...<Widget>[
          _ChecklistRow(
            title: result.items[i].title,
            subtitle: result.items[i].subtitle,
            checked: checkedKeys.contains(coachKey(result.items[i].title)),
            onToggle: readOnly
                ? null
                : () => onToggle(coachKey(result.items[i].title)),
          ),
          if (i != result.items.length - 1)
            Divider(color: AppColor.border, height: AppSpace.lg),
        ],
      ],
    );
  }
}

/// 안전 경고 안내 행 — 서버 safety_warnings 문구를 그대로 보여준다
/// (프론트 가공 금지, 가이드 06 §4.2-4).
class _SafetyWarningRow extends StatelessWidget {
  final String text;
  const _SafetyWarningRow({required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.md,
        vertical: AppSpace.sm + 2,
      ),
      decoration: BoxDecoration(
        color: AppColor.warningSoft,
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Icon(Icons.info_outline, color: AppColor.warning, size: 18),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: Text(
              text,
              style: AppText.body.copyWith(color: AppColor.ink, height: 1.5),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChecklistRow extends StatelessWidget {
  final String title;
  final String subtitle;
  final bool checked;
  // null 이면 읽기 전용 (과거 일자 보기).
  final VoidCallback? onToggle;
  const _ChecklistRow({
    required this.title,
    required this.subtitle,
    required this.checked,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final bool hasSubtitle = subtitle.trim().isNotEmpty;
    return Pressable(
      onTap: onToggle,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          // 체크 원형
          Container(
            margin: const EdgeInsets.only(top: 1),
            width: 24,
            height: 24,
            decoration: BoxDecoration(
              color: checked ? AppColor.brand : AppColor.borderStrong,
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.check_rounded,
              color: Colors.white,
              size: 16,
            ),
          ),
          const SizedBox(width: AppSpace.sm + 2),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  title.isNotEmpty ? title : '실천 항목',
                  style: AppText.body.copyWith(
                    color: checked ? AppColor.inkTertiary : AppColor.ink,
                    fontWeight: FontWeight.w700,
                    decoration: checked ? TextDecoration.lineThrough : null,
                  ),
                ),
                if (hasSubtitle) ...<Widget>[
                  const SizedBox(height: 2),
                  Text(
                    subtitle.trim(),
                    style: AppText.caption.copyWith(
                      color: AppColor.inkSecondary,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ChecklistHint extends StatelessWidget {
  final String text;
  const _ChecklistHint({required this.text});

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: AppText.body.copyWith(color: AppColor.inkSecondary, height: 1.5),
    );
  }
}

class _ChecklistError extends StatelessWidget {
  final VoidCallback onRetry;
  const _ChecklistError({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: AppColor.inkTertiary.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(AppRadius.sm - 2),
          ),
          alignment: Alignment.center,
          child: const Icon(
            Icons.cloud_off_rounded,
            size: 18,
            color: AppColor.inkTertiary,
          ),
        ),
        const SizedBox(width: AppSpace.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                '실천 리스트를 불러오지 못했어요',
                style: AppText.body.copyWith(
                  color: AppColor.ink,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              Pressable(
                onTap: onRetry,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpace.md,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: AppColor.brandSoft,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                  ),
                  child: Text(
                    '다시 시도',
                    style: AppText.caption.copyWith(
                      color: AppColor.brandDeep,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 카드 3 — 스마트 분석 '지난 4주 추이'
//   영속 이력 7일치 이상이면 28일 라인 차트, 미만이면 잠금 placeholder 유지.
//   차트는 CustomPainter 자체 구현 (점 최대 28개 — 외부 차트 의존성 불필요,
//   가이드 06 §4.1 권고).
// ═══════════════════════════════════════════
class _TrendCard extends StatelessWidget {
  final List<ScoreTrendPoint> points;
  // 카드 하단 레몬봇 CTA (figma 800:23 — 가이드 10 ③-P2 6).
  final VoidCallback onLemonBot;
  const _TrendCard({required this.points, required this.onLemonBot});

  /// 추이 차트를 그리는 최소 데이터 일수 (가이드 06 §4.1).
  static const int _minPoints = 7;

  @override
  Widget build(BuildContext context) {
    if (points.length < _minPoints) {
      return const _TrendLockedCard();
    }
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside + 2),
      decoration: _cardDeco(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Text('스마트 분석', style: AppText.subtitle),
              const SizedBox(width: AppSpace.sm),
              Text(
                '지난 4주 추이',
                style: AppText.caption.copyWith(color: AppColor.inkTertiary),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.lg),
          SizedBox(
            height: 168,
            width: double.infinity,
            child: CustomPaint(painter: _TrendChartPainter(points: points)),
          ),
          const SizedBox(height: AppSpace.sm),
          // 주차 보조 라벨 — 시안 800:23 의 1주~4주 표기 (가이드 10 ③-P2 6).
          // 데이터 구간을 7일 단위로 나눠 최대 4주까지만 표시한다.
          Padding(
            padding: const EdgeInsets.only(left: _TrendChartPainter.padLeft),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: <Widget>[
                for (int week = 1; week <= _weekCount(points); week++)
                  Text('$week주', style: AppText.micro),
              ],
            ),
          ),
          const SizedBox(height: AppSpace.sm),
          Text(
            '점수는 기록 당시 기준이에요',
            style: AppText.caption.copyWith(color: AppColor.inkTertiary),
          ),
          const SizedBox(height: AppSpace.lg),
          // 추세 코멘트는 백엔드 공백(서버 금칙어 처리 문구 필요 — 임의 구현
          // 금지)이라 시안의 코멘트+CTA 중 CTA 만 반영한다.
          _LemonBotCta(onTap: onLemonBot),
        ],
      ),
    );
  }

  /// 표시 구간이 며칠인지로 주 수를 셈한다 (1~4 클램프).
  ///
  /// 날짜 파싱이 안 되는 행은 점 개수로 대신 추정한다 — 라벨은 보조
  /// 표기일 뿐 점수 값에는 영향이 없다. 두 날짜는 UTC 자정으로 정규화해
  /// 빼므로 봄철 DST(23시간) 구간에서도 일수가 한 칸 적게 잘리지 않는다.
  static int _weekCount(List<ScoreTrendPoint> points) {
    final DateTime? first = _utcDate(points.first.date);
    final DateTime? last = _utcDate(points.last.date);
    final int days = (first != null && last != null)
        ? last.difference(first).inDays + 1
        : points.length;
    return ((days + 6) ~/ 7).clamp(1, 4);
  }

  /// `YYYY-MM-DD`를 UTC 자정 DateTime 으로 파싱한다(형식 불가 시 null).
  static DateTime? _utcDate(String date) {
    final DateTime? parsed = DateTime.tryParse(date);
    if (parsed == null) return null;
    return DateTime.utc(parsed.year, parsed.month, parsed.day);
  }
}

class _TrendChartPainter extends CustomPainter {
  _TrendChartPainter({required this.points});

  final List<ScoreTrendPoint> points;

  /// y축 숫자 라벨 폭 확보용 좌측 여백 (축 라벨과 차트 본문 정렬에 공유).
  static const double padLeft = 34;
  static const double _padRight = 8;
  static const double _padTop = 8;
  static const double _padBottom = 8;

  @override
  void paint(Canvas canvas, Size size) {
    final double plotWidth = size.width - padLeft - _padRight;
    final double plotHeight = size.height - _padTop - _padBottom;
    if (plotWidth <= 0 || plotHeight <= 0 || points.length < 2) {
      return;
    }

    double yFor(int score) {
      final double ratio = score.clamp(0, 100).toDouble() / 100;
      return _padTop + (1 - ratio) * plotHeight;
    }

    double xFor(int index) {
      return padLeft + plotWidth * index / (points.length - 1);
    }

    // y축 기준선 0/50/100 + 숫자 라벨 — 점수 숫자는 허용, 신뢰도 %는 금지.
    final Paint gridPaint = Paint()
      ..color = AppColor.border
      ..strokeWidth = 1;
    for (final int gridScore in const <int>[0, 50, 100]) {
      final double y = yFor(gridScore);
      canvas.drawLine(
        Offset(padLeft, y),
        Offset(size.width - _padRight, y),
        gridPaint,
      );
      final TextPainter labelPainter = TextPainter(
        text: TextSpan(text: '$gridScore', style: AppText.micro),
        textDirection: TextDirection.ltr,
      )..layout();
      labelPainter.paint(
        canvas,
        Offset(padLeft - labelPainter.width - 6, y - labelPainter.height / 2),
      );
    }

    // 점수 라인 — 브랜드 색 (가이드 06 §4.1 색 규칙).
    final Paint linePaint = Paint()
      ..color = AppColor.brand
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    final Path linePath = Path();
    for (int i = 0; i < points.length; i++) {
      final Offset point = Offset(xFor(i), yFor(points[i].score));
      if (i == 0) {
        linePath.moveTo(point.dx, point.dy);
      } else {
        linePath.lineTo(point.dx, point.dy);
      }
    }
    canvas.drawPath(linePath, linePaint);

    // 포인트 — 서버 등급 라벨 매핑 색 (shared/score_label_colors, §2.4).
    for (int i = 0; i < points.length; i++) {
      final Offset center = Offset(xFor(i), yFor(points[i].score));
      canvas.drawCircle(
        center,
        3.2,
        Paint()..color = scoreLabelColor(points[i].label),
      );
    }
  }

  @override
  bool shouldRepaint(_TrendChartPainter oldDelegate) {
    return !identical(oldDelegate.points, points);
  }
}

// ═══════════════════════════════════════════
// 카드 3 — 스마트 분석 '지난 4주 추이' (잠금 placeholder)
//   영속 이력이 7일치 미만일 때의 빈 상태 안내.
// ═══════════════════════════════════════════
class _TrendLockedCard extends StatelessWidget {
  const _TrendLockedCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside + 2),
      decoration: _cardDeco(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Text('스마트 분석', style: AppText.subtitle),
              const SizedBox(width: AppSpace.sm),
              Text(
                '지난 4주 추이',
                style: AppText.caption.copyWith(color: AppColor.inkTertiary),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.lg),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpace.lg,
              vertical: AppSpace.xl,
            ),
            decoration: BoxDecoration(
              color: AppColor.sunken,
              borderRadius: BorderRadius.circular(AppRadius.md),
            ),
            child: Column(
              children: <Widget>[
                Icon(
                  Icons.lock_outline_rounded,
                  color: AppColor.inkTertiary,
                  size: 28,
                ),
                const SizedBox(height: AppSpace.sm),
                Text(
                  '기록이 쌓이면 추이를 보여드려요',
                  style: AppText.body.copyWith(
                    color: AppColor.inkSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// 하단 면책 고지는 공용 위젯으로 단일화 — MedicalDisclaimer(summary 변형).
// 문구·스타일 단일 출처: lib/widgets/common/medical_disclaimer.dart
