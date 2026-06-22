// screens/dashboard_screen.dart — 홈 (메인 화면)
//
// 디자인: Pillyze 시안 기반 LADS 톤 변환 (비주얼 보존, 데이터는 실연동).
//   - 상단: brand 노랑 헤더 (로고 + 우측 아이콘 3개 + 캘린더 weekday strip)
//   - 본문: 흰 배경 카드들 — 모두 실데이터 (P0 배치 A)
//
// 데이터:
//   - 건강 점수: dashboard summary 의 health_score (ready/not_ready)
//   - kcal/매크로: 당일 meals nutrition_summary 합산
//   - 주간 스트립: 최근 7일 meals 기록 여부로 점 표시
//   - 상호작용: 영양제 영향도 preview 3상태
//   - 오늘의 분석: health_score.message
//   - 식단 관리: 당일 끼니별 / 영양제 관리: 등록 영양제 체크리스트
//
// 연산은 모두 백엔드. 모바일은 표시·합산만.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../app_controller.dart';
import '../core/storage/local_prefs.dart';
import '../features/dashboard/home_models.dart';
import '../features/nutrition/kdri_models.dart';
import '../features/profile/profile_models.dart';
import '../features/profile/profile_repository.dart';
import '../features/supplements/supplement_models.dart';
import '../features/supplements/supplement_repository.dart';
import '../shared/widgets/status_state_view.dart';
import '../utils/design_tokens_v2.dart';
import '../utils/mascot_poses.dart';
import '../widgets/common/app_modals.dart';
import '../widgets/common/pressable.dart';
import '../widgets/common/staggered_entrance.dart';
import '../widgets/dashboard/health_hero_card.dart';
import '../widgets/dashboard/medication_add_sheet.dart';

class DashboardScreen extends StatefulWidget {
  // recordDate 가 null 이면 메인(오늘 고정).
  // 값이 있으면 '과거 기록 조회' 모드 — 풀스크린 별도 페이지.
  final DateTime? recordDate;

  /// 홈 데이터(점수·식단·영양제·상호작용)를 제공하는 앱 컨트롤러.
  final AppController controller;

  /// 날짜별 체크 상태를 영속하는 로컬 저장 래퍼.
  ///
  /// null 이면(예: prefs 로딩 전·실패) 세션 메모리로만 동작한다 — 기능 영향 없음.
  final LocalPrefs? localPrefs;

  /// 목표 kcal 주입용 프로필 스냅샷 저장소 (가이드 02 ④-13).
  ///
  /// null 이면 목표 조회를 생략하고 히어로 카드는 '기록 합계' 모드로 동작한다.
  final ProfileRepository? profileRepository;

  const DashboardScreen({
    required this.controller,
    super.key,
    this.recordDate,
    this.localPrefs,
    this.profileRepository,
  });

  bool get isRecordMode => recordDate != null;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen>
    with WidgetsBindingObserver {
  // 선택된 날짜 — 메인이면 항상 오늘, 기록 모드면 recordDate 부터.
  late DateTime _selectedDate;
  // _selectedDate 가 '오늘'을 따라가는 중인지 (사용자가 과거 날짜를 고르면 false).
  // 앱이 자정을 넘겨 다시 활성화되면 오늘로 롤오버해 영양제/복약 체크를 초기화한다.
  bool _followingToday = true;
  // 헤더 strip 이 보여주는 주 (그 주의 시작일 = 일요일, 캘린더와 통일)
  late DateTime _focusedMonday;
  // 영양제 체크 토글 — 선택 날짜 기준 LocalPrefs 영속 (자정 넘어가면 새 날짜 키).
  Set<String> _checkedSupplementIds = <String>{};
  // 복약 복용 체크 토글 — 선택 날짜 기준 LocalPrefs 영속.
  Set<String> _checkedMedicationIds = <String>{};
  // 목표 kcal — 백엔드(KDRIs 에너지 기준) 값 확보 시에만 채워진다.
  int? _targetKcal;

  bool get _isRecordMode => widget.isRecordMode;

  AppController get _controller => widget.controller;

  LocalPrefs? get _prefs => widget.localPrefs;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final now = DateTime.now();
    final base = widget.recordDate ?? now;
    _selectedDate = DateTime(base.year, base.month, base.day);
    _focusedMonday = _mondayOf(_selectedDate);
    // 메인(오늘) 진입은 날짜 자동 롤오버 대상, 기록 모드(특정 날짜)는 고정.
    _followingToday = widget.recordDate == null;
    _loadChecksForSelectedDate();
    _loadTargetKcal();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    // 앱이 다시 활성화될 때, 오늘을 따라가는 중이고 자정을 넘겨 날짜가 지났으면
    // 오늘로 롤오버한다 → 새 날짜의 (빈) 체크 상태를 읽어 복용 체크가 초기화된다.
    if (state != AppLifecycleState.resumed || !_followingToday) return;
    final DateTime today = DateTime.now();
    if (_sameDay(_selectedDate, today)) return;
    setState(() {
      _selectedDate = DateTime(today.year, today.month, today.day);
      _focusedMonday = _mondayOf(_selectedDate);
      _loadChecksForSelectedDate();
    });
  }

  /// 목표 kcal 을 백엔드 값으로 주입한다 (가이드 02 ④-13 — 클라이언트 계산 금지).
  ///
  /// 프로필 스냅샷(sex/birth_year)이 있을 때만 KDRIs 에너지 기준(EER,
  /// `energy_kcal`)을 조회해 그대로 전달한다. 미확보·실패 시 null 유지 —
  /// 히어로 카드는 '기록 합계' 모드로 동작한다 (목표 추정치 날조 금지).
  Future<void> _loadTargetKcal() async {
    final ProfileRepository? profiles = widget.profileRepository;
    if (profiles == null) return;
    try {
      final BodyProfileSnapshot? snapshot = await profiles.fetchLatest();
      final ProfileSex? sex = snapshot?.sex;
      final int? birthYear = snapshot?.birthYear;
      if (sex == null || birthYear == null) return;
      // 나이는 KDRIs 조회 파라미터 준비일 뿐 영양 연산이 아니다.
      final int age = DateTime.now().year - birthYear;
      if (age <= 0 || age > 120) return;
      final KdriLookupResult result = await _controller.repository.lookupKdris(
        age: age,
        sex: sex.code,
      );
      final double? amount = result
          .referenceFor('energy_kcal')
          ?.referenceAmount;
      if (!mounted || amount == null || amount <= 0) return;
      setState(() => _targetKcal = amount.round());
    } on Exception {
      // 목표 미확보 — 기록 합계 모드 유지.
    }
  }

  @override
  void didUpdateWidget(covariant DashboardScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    // prefs 가 늦게 로드되면(앱 기동 직후 FutureProvider) 그 시점에 한 번 더 읽는다.
    if (oldWidget.localPrefs == null && widget.localPrefs != null) {
      _loadChecksForSelectedDate();
    }
  }

  // 선택 날짜의 영양제/복약 체크 상태를 LocalPrefs 에서 읽어온다.
  void _loadChecksForSelectedDate() {
    final LocalPrefs? prefs = _prefs;
    if (prefs == null) return;
    _checkedSupplementIds = prefs.supplementCheckedIds(_selectedDate);
    _checkedMedicationIds = prefs.medicationCheckedIds(_selectedDate);
  }

  // 주 시작 = 일요일. DateTime.weekday: 월=1..일=7 → 일=0 으로 (weekday % 7).
  static DateTime _mondayOf(DateTime d) =>
      DateTime(d.year, d.month, d.day).subtract(Duration(days: d.weekday % 7));

  static bool _sameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;

  bool get _isToday => _sameDay(_selectedDate, DateTime.now());

  void _selectDate(DateTime d) {
    final picked = DateTime(d.year, d.month, d.day);
    // 미래 날짜는 선택 불가 (아직 기록 없음)
    if (picked.isAfter(DateTime.now())) return;
    // 페이지 이동 없이 그 자리에서 날짜 교체 — 본문이 페이드로 바뀜
    setState(() {
      _selectedDate = picked;
      _focusedMonday = _mondayOf(picked);
      // 과거 날짜를 직접 고르면 오늘 자동 롤오버를 멈춘다(오늘 선택 시 재개).
      _followingToday = _sameDay(picked, DateTime.now());
      // 날짜가 바뀌면 그 날짜의 체크 상태를 다시 읽는다 (자정 롤오버 포함).
      _loadChecksForSelectedDate();
    });
  }

  void _shiftWeek(int delta) {
    setState(() {
      _focusedMonday = _focusedMonday.add(Duration(days: 7 * delta));
    });
  }

  void _goToday() {
    // 기록 모드면 → 메인(오늘)으로 돌아감 (페이지 pop)
    if (_isRecordMode) {
      if (context.canPop()) context.pop();
      return;
    }
    final now = DateTime.now();
    setState(() {
      _selectedDate = DateTime(now.year, now.month, now.day);
      _focusedMonday = _mondayOf(now);
      _followingToday = true;
      _loadChecksForSelectedDate();
    });
  }

  // 본문 좌우 스와이프 — 오→왼(velocity<0) = 다음날 / 왼→오 = 이전날
  void _onBodySwipe(DragEndDetails d) {
    final v = d.primaryVelocity ?? 0;
    if (v.abs() < 200) return; // 약한 스와이프 무시
    if (v < 0) {
      // 다음 날 (미래는 _selectDate 가 막음)
      _selectDate(_selectedDate.add(const Duration(days: 1)));
    } else {
      // 이전 날
      _selectDate(_selectedDate.subtract(const Duration(days: 1)));
    }
  }

  // 카메라 딥링크 — 끼니/영양제 촬영
  void _openCamera(String mode) {
    context.go('/shell/camera?mode=$mode');
  }

  void _openSupplementManager() {
    context.go('/shell/home/supplements');
  }

  void _openMealManager() {
    context.go('/shell/home/meals');
  }

  void _toggleSupplement(String id) {
    setState(() {
      if (_checkedSupplementIds.contains(id)) {
        _checkedSupplementIds.remove(id);
      } else {
        _checkedSupplementIds.add(id);
      }
    });
    // 선택 날짜 키로 영속 (저장 실패는 무시 — 세션 상태는 이미 반영됨).
    _prefs?.setSupplementCheckedIds(_selectedDate, _checkedSupplementIds);
  }

  void _toggleMedication(String id) {
    setState(() {
      if (_checkedMedicationIds.contains(id)) {
        _checkedMedicationIds.remove(id);
      } else {
        _checkedMedicationIds.add(id);
      }
    });
    _prefs?.setMedicationCheckedIds(_selectedDate, _checkedMedicationIds);
  }

  // '+ 약 추가' → 바텀시트 폼 → POST. 성공 시 컨트롤러가 목록을 새로고침.
  Future<void> _openAddMedication() async {
    final MedicationCreateRequest? request = await showMedicationAddSheet(
      context,
    );
    if (request == null || !mounted) return;
    final bool created = await _controller.addMedication(request);
    if (!mounted) return;
    if (!created) {
      _showErrorSnack(
        _controller.apiError?.message ?? '약을 추가하지 못했어요. 잠시 후 다시 시도해주세요.',
      );
    }
  }

  // 길게 누름 → 삭제(비활성화) 확인 → deactivate → 실행취소 토스트(reactivate).
  Future<void> _confirmDeactivateMedication(HomeMedication medication) async {
    final bool confirmed = await showDeleteConfirmDialog(
      context,
      targetLabel: medication.displayName,
      subLabel: '목록에서 빼면 상호작용 확인 대상에서 제외돼요.',
    );
    if (!confirmed || !mounted) return;
    final bool done = await _controller.deactivateMedication(medication.id);
    if (!mounted) return;
    if (!done) {
      _showErrorSnack(
        _controller.apiError?.message ?? '약을 비활성화하지 못했어요. 잠시 후 다시 시도해주세요.',
      );
      return;
    }
    _checkedMedicationIds.remove(medication.id);
    _prefs?.setMedicationCheckedIds(_selectedDate, _checkedMedicationIds);
    showUndoToast(
      context,
      message: '${medication.displayName}을(를) 목록에서 뺐어요.',
      onUndo: () => _controller.reactivateMedication(medication.id),
    );
  }

  // 길게 누름 → 삭제 확인 → 낙관적 제거 → 실행취소 토스트(4초 지연 commit).
  // 미취소 시 컨트롤러 큐가 DELETE /supplements/{id} 를 보낸다(soft-delete).
  Future<void> _confirmDeleteSupplement(HomeSupplement supplement) async {
    final String name = supplement.displayName.isNotEmpty
        ? supplement.displayName
        : '영양제';
    final bool confirmed = await showDeleteConfirmDialog(
      context,
      targetLabel: name,
    );
    if (!confirmed || !mounted) return;
    final HomeSupplement? removed = _controller.removeSupplementOptimistically(
      supplement.id,
    );
    if (removed == null || !mounted) return;
    _checkedSupplementIds.remove(supplement.id);
    _prefs?.setSupplementCheckedIds(_selectedDate, _checkedSupplementIds);
    showUndoToast(
      context,
      message: '영양제를 삭제했어요',
      onUndo: () => _controller.undoSupplementRemoval(removed),
    );
  }

  void _showErrorSnack(String message) {
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(
        SnackBar(
          duration: const Duration(seconds: 4),
          behavior: SnackBarBehavior.floating,
          backgroundColor: AppColor.ink,
          margin: const EdgeInsets.fromLTRB(16, 0, 16, 20),
          content: Text(
            message,
            style: AppText.body.copyWith(color: Colors.white),
          ),
        ),
      );
  }

  // 당일 meals nutrition_summary 합산
  HomeMealNutrition _dayTotals(List<HomeMeal> meals) {
    HomeMealNutrition total = HomeMealNutrition.zero;
    for (final HomeMeal meal in meals) {
      total = total + meal.nutrition;
    }
    return total;
  }

  // 최근 7일(헤더 strip 표시 주) 기록 점
  Set<String> _recordDots() {
    final Set<String> dots = <String>{};
    for (final HomeMeal meal in _controller.recentMeals.results) {
      final DateTime? eatenAt = meal.eatenAt;
      if (eatenAt == null) continue;
      final DateTime local = eatenAt.toLocal();
      dots.add('${local.year}-${local.month}-${local.day}');
    }
    return dots;
  }

  // 본문 — 날짜별로 다시 그려짐 (key 로 AnimatedSwitcher 전환)
  Widget _buildBody({Key? key}) {
    final List<HomeMeal> dayMeals = _controller.mealsForDay(_selectedDate);
    final HomeMealNutrition totals = _dayTotals(dayMeals);
    final DashboardHealthScore score = _controller.healthScore;

    return ListView(
      key: key,
      padding: const EdgeInsets.fromLTRB(
        AppSpace.page,
        AppSpace.xl,
        AppSpace.page,
        AppSpace.xl + 80,
      ),
      children: [
        StaggeredEntrance(
          gap: AppSpace.md,
          children: [
            HealthHeroCard(
              scoreReady: score.isReady,
              healthScore: score.score ?? 0,
              scoreLabelText: score.labelText,
              scoreLabel: score.label,
              consumedKcal: totals.kcal.round(),
              // 백엔드 KDRIs 에너지 기준 확보 시에만 '소비/목표' 모드 전환.
              targetKcal: _targetKcal,
              macrosTotalsOnly: true,
              carbG: totals.carbG.round(),
              proteinG: totals.proteinG.round(),
              fatG: totals.fatG.round(),
              onTapScore: score.isReady
                  ? () => context.go('/shell/score')
                  : () => _openCamera('meal'),
              onTapDetail: () =>
                  context.push('/shell/home/analysis-result?mode=meal'),
            ),
            // Figma 268:24 섹션 순서 — 히어로 → 상호작용 → 오늘의 분석
            //   → 식단 관리 → 복약 관리 → 영양제 관리.
            _InteractionCard(
              preview: _controller.supplementImpactPreview,
              hasSupplements: _controller.homeSupplements.results.isNotEmpty,
              medicationCount: _controller.homeMedications.activeItems.length,
              failed: _controller.homeImpactFailed,
            ),
            _TodayAnalysisCard(
              score: score,
              onTap: () => context.go('/shell/score'),
            ),
            _MealManagementCard(
              meals: dayMeals,
              failed: _controller.homeMealsFailed,
              onManage: _openMealManager,
              onCameraAdd: () => _openCamera('meal'),
            ),
            _MedicationCard(
              medications: _controller.homeMedications.activeItems,
              checkedIds: _checkedMedicationIds,
              failed: _controller.homeMedicationsFailed,
              onToggle: _toggleMedication,
              onAdd: _openAddMedication,
              onDeactivate: _confirmDeactivateMedication,
            ),
            _SupplementChecklistCard(
              supplements: _controller.homeSupplements.results,
              checkedIds: _checkedSupplementIds,
              failed: _controller.homeSupplementsFailed,
              onToggle: _toggleSupplement,
              onAdd: _openSupplementManager,
              onDelete: _confirmDeleteSupplement,
            ),
            const _MedicalDisclaimer(),
          ],
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (BuildContext context, Widget? child) {
        return Scaffold(
          backgroundColor: AppColor.bg,
          body: Column(
            children: [
              // ─── 상단 brand 헤더 (status bar 까지 포함) ───
              _BrandHeader(
                selectedDate: _selectedDate,
                focusedMonday: _focusedMonday,
                isToday: _isToday,
                isRecordMode: _isRecordMode,
                recordDots: _recordDots(),
                onSelectDate: _selectDate,
                onShiftWeek: _shiftWeek,
                onGoToday: _goToday,
                onTapMonth: () => context.push('/shell/home/calendar'),
              ),

              // ─── 본문 ───
              // 헤더(노랑)와 만나는 지점에서 본문(흰)이 위쪽으로 둥글게 올라옴 (Pillyze 톤)
              Expanded(
                child: Transform.translate(
                  offset: const Offset(0, -24),
                  child: Container(
                    // Figma 268:24 — 본문은 옅은 회색 배경, 흰 카드가 떠 보임.
                    decoration: const BoxDecoration(
                      color: AppColor.section,
                      borderRadius: BorderRadius.only(
                        topLeft: Radius.circular(28),
                        topRight: Radius.circular(28),
                      ),
                    ),
                    // 좌우 스와이프로 날짜 이동 (만보기 앱 표준 UX)
                    child: GestureDetector(
                      onHorizontalDragEnd: _onBodySwipe,
                      child: RefreshIndicator(
                        onRefresh: _controller.refreshDashboard,
                        color: AppColor.brand,
                        // 날짜 바뀔 때 본문 페이드 전환 ("딱" 안 바뀜)
                        child: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 280),
                          switchInCurve: Curves.easeOutQuart,
                          transitionBuilder: (child, anim) =>
                              FadeTransition(opacity: anim, child: child),
                          child: _buildBody(
                            key: ValueKey<String>(
                              '${_selectedDate.year}'
                              '-${_selectedDate.month}'
                              '-${_selectedDate.day}',
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ═══════════════════════════════════════════
// 상단 brand 헤더 (Pillyze 톤)
//   - status bar 부터 색 채움
//   - 로고 + 우측 아이콘 3개
//   - weekday strip + 날짜 (오늘 = 흰 원 강조, 기록 점)
// ═══════════════════════════════════════════
class _BrandHeader extends StatelessWidget {
  final DateTime selectedDate;
  final DateTime focusedMonday;
  final bool isToday;
  final bool isRecordMode; // 과거 기록 페이지면 true
  final Set<String> recordDots; // 'y-m-d' 기록 있는 날짜 키
  final ValueChanged<DateTime> onSelectDate;
  final ValueChanged<int> onShiftWeek; // -1 이전 주 / +1 다음 주
  final VoidCallback onGoToday;
  final VoidCallback onTapMonth; // 월 드롭다운 → 캘린더

  const _BrandHeader({
    required this.selectedDate,
    required this.focusedMonday,
    required this.isToday,
    required this.isRecordMode,
    required this.recordDots,
    required this.onSelectDate,
    required this.onShiftWeek,
    required this.onGoToday,
    required this.onTapMonth,
  });

  static bool _isSameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;

  static String _dotKey(DateTime d) => '${d.year}-${d.month}-${d.day}';

  @override
  Widget build(BuildContext context) {
    final today = DateTime.now();
    final days = List.generate(7, (i) => focusedMonday.add(Duration(days: i)));
    // 일요일 시작 (캘린더와 통일).
    const weekdayLabels = ['일', '월', '화', '수', '목', '금', '토'];

    // 요일 라벨 행 — 주말 색(일 red · 토 blue), 평일은 옅은 ink.
    Widget weekdayLabelRow() => Row(
      children: [
        for (int i = 0; i < 7; i++)
          Expanded(
            child: Center(
              child: Text(
                weekdayLabels[i],
                style: AppText.caption.copyWith(
                  color: i == 0
                      ? AppColor.danger
                      : i == 6
                      ? AppColor.info
                      : AppColor.ink.withValues(alpha: 0.75),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ),
      ],
    );

    // 날짜 버블 7칸 (Expanded 배열) — 양 모드 공용.
    List<Widget> dateBubbles() => [
      for (int i = 0; i < 7; i++)
        Expanded(
          child: _DateBubble(
            date: days[i],
            selected: _isSameDay(days[i], selectedDate),
            isToday: _isSameDay(days[i], today),
            isFuture: days[i].isAfter(today),
            hasRecord: recordDots.contains(_dotKey(days[i])),
            onTap: () => onSelectDate(days[i]),
          ),
        ),
    ];

    return Container(
      color: AppColor.brand,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.page,
            AppSpace.lg,
            AppSpace.page,
            // 날짜 strip 이 본문 라운드 겹침과 충돌하지 않도록 여유 확보
            // (기록 모드에서 검증된 값을 메인에도 동일 적용).
            AppSpace.xl + AppSpace.xl,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ─── 상단 행 ───
              // 메인 = 워드마크 + 아이콘 3개 / 기록 모드 = 뒤로 + 제목
              if (isRecordMode)
                Row(
                  children: [
                    _HeaderIconButton(
                      icon: Icons.arrow_back_rounded,
                      onTap: () => context.canPop()
                          ? context.pop()
                          : context.go('/shell/home'),
                    ),
                    const SizedBox(width: AppSpace.xs),
                    const Text(
                      '지난 기록',
                      style: TextStyle(
                        color: AppColor.ink,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0,
                      ),
                    ),
                  ],
                )
              else
                Row(
                  children: [
                    const _Wordmark(),
                    const Spacer(),
                    _HeaderIconButton(
                      icon: Icons.calendar_today_rounded,
                      onTap: () => context.push('/shell/home/calendar'),
                    ),
                    const SizedBox(width: AppSpace.sm),
                    _HeaderIconButton(
                      icon: Icons.notifications_rounded,
                      onTap: () => context.push('/shell/home/notifications'),
                    ),
                    const SizedBox(width: AppSpace.sm),
                    _HeaderIconButton(
                      icon: Icons.person_rounded,
                      onTap: () => context.go('/shell/settings'),
                    ),
                  ],
                ),

              // ─── 기록 모드 = 주 이동 + 날짜 strip ───
              if (isRecordMode) ...[
                const SizedBox(height: AppSpace.lg),
                Row(
                  children: [
                    _WeekArrow(
                      icon: Icons.chevron_left_rounded,
                      onTap: () => onShiftWeek(-1),
                    ),
                    const SizedBox(width: 2),
                    RichText(
                      text: TextSpan(
                        style: const TextStyle(
                          fontFamily: 'Pretendard',
                          color: AppColor.ink,
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0,
                        ),
                        children: [
                          TextSpan(
                            text:
                                '${selectedDate.month}월 '
                                '${selectedDate.day}일',
                          ),
                          TextSpan(
                            text: isToday
                                ? '  ·  오늘'
                                : '  (${weekdayLabels[selectedDate.weekday % 7]})',
                            style: TextStyle(
                              color: isToday
                                  ? AppColor.brandDeep
                                  : AppColor.ink.withValues(alpha: 0.55),
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 2),
                    _WeekArrow(
                      icon: Icons.chevron_right_rounded,
                      onTap: focusedMonday.isBefore(_mondayOfToday(today))
                          ? () => onShiftWeek(1)
                          : null,
                    ),
                    const Spacer(),
                    // 기록 모드에서 오늘이면 '오늘로'(메인 복귀) 버튼
                    if (!isToday) _TodayButton(onTap: onGoToday),
                  ],
                ),
                const SizedBox(height: AppSpace.md),
                // 요일 strip
                weekdayLabelRow(),
                const SizedBox(height: AppSpace.sm),
                // 날짜 strip
                Row(children: dateBubbles()),
              ]
              // ─── 메인 모드 = 월 드롭다운 + 오늘 pill + 주간 strip ───
              else ...[
                const SizedBox(height: AppSpace.lg),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _MonthDropdown(
                      selectedDate: selectedDate,
                      onTap: onTapMonth,
                    ),
                    if (!isToday) _TodayPill(onTap: onGoToday),
                  ],
                ),
                const SizedBox(height: AppSpace.md),
                // 요일 strip
                weekdayLabelRow(),
                const SizedBox(height: AppSpace.sm),
                // 날짜 strip — 양 끝에 주 이동 화살표
                Row(
                  children: [
                    _WeekArrow(
                      icon: Icons.chevron_left_rounded,
                      onTap: () => onShiftWeek(-1),
                    ),
                    Expanded(child: Row(children: dateBubbles())),
                    _WeekArrow(
                      icon: Icons.chevron_right_rounded,
                      onTap: focusedMonday.isBefore(_mondayOfToday(today))
                          ? () => onShiftWeek(1)
                          : null,
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  static DateTime _mondayOfToday(DateTime today) => DateTime(
    today.year,
    today.month,
    today.day,
  ).subtract(Duration(days: today.weekday % 7));
}

// 월 드롭다운 — '{n}월 ▾' 탭 → 캘린더 (figma 268:24 헤더 좌측)
class _MonthDropdown extends StatelessWidget {
  final DateTime selectedDate;
  final VoidCallback onTap;
  const _MonthDropdown({required this.selectedDate, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '${selectedDate.month}월',
            style: const TextStyle(
              fontFamily: 'Pretendard',
              color: AppColor.ink,
              fontSize: 18,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
          const Icon(
            Icons.keyboard_arrow_down_rounded,
            color: AppColor.ink,
            size: 20,
          ),
        ],
      ),
    );
  }
}

// '오늘' pill — 메인 모드에서 과거 날짜 선택 시 오늘로 복귀 (figma 268:24 헤더 우측)
class _TodayPill extends StatelessWidget {
  final VoidCallback onTap;
  const _TodayPill({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.md,
          vertical: 6,
        ),
        decoration: BoxDecoration(
          color: AppColor.surface,
          borderRadius: BorderRadius.circular(AppRadius.full),
          boxShadow: AppShadow.softCard,
        ),
        child: Text(
          '오늘',
          style: AppText.caption.copyWith(
            color: AppColor.ink,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    );
  }
}

// 주 이동 화살표 — null onTap 이면 비활성(흐림)
class _WeekArrow extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;
  const _WeekArrow({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final enabled = onTap != null;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: SizedBox(
        width: 28,
        height: 28,
        child: Icon(
          icon,
          size: 22,
          color: AppColor.ink.withValues(alpha: enabled ? 0.85 : 0.25),
        ),
      ),
    );
  }
}

// '오늘로' 버튼
class _TodayButton extends StatelessWidget {
  final VoidCallback onTap;
  const _TodayButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.md,
          vertical: 6,
        ),
        decoration: BoxDecoration(
          color: AppColor.ink,
          borderRadius: BorderRadius.circular(AppRadius.full),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: const [
            Icon(Icons.today_rounded, color: Colors.white, size: 13),
            SizedBox(width: 4),
            Text(
              '오늘로',
              style: TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 한국어 워드마크 — "레몬·에이드"
/// 로그인 화면 _Brand 동일 패턴 (GmarketSans w800 + 가운데 점) 을 헤더 사이즈로 축소.
/// 노란 헤더 위라 점은 흰색 + 미세 그림자 (가독성).
class _Wordmark extends StatelessWidget {
  const _Wordmark();

  @override
  Widget build(BuildContext context) {
    const baseStyle = TextStyle(
      fontFamily: 'GmarketSans',
      fontSize: 26,
      fontWeight: FontWeight.w800,
      color: AppColor.ink,
      letterSpacing: 0,
      height: 1.0,
    );
    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const Text('레몬', style: baseStyle),
        // 가운데 흰색 점 + 미세 그림자 (노란 헤더 위 가독성)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Container(
            width: 9,
            height: 9,
            decoration: BoxDecoration(
              color: AppColor.surface,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: AppColor.ink.withValues(alpha: 0.10),
                  blurRadius: 6,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
          ),
        ),
        const Text('에이드', style: baseStyle),
      ],
    );
  }
}

class _HeaderIconButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  const _HeaderIconButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: SizedBox(
        width: 32,
        height: 32,
        child: Icon(icon, color: AppColor.ink, size: 22),
      ),
    );
  }
}

// 날짜 칸 — 탭으로 선택. 선택 = 흰 원, 오늘 = 점 표시, 미래 = 흐림, 기록 = 아래 점.
class _DateBubble extends StatelessWidget {
  final DateTime date;
  final bool selected;
  final bool isToday;
  final bool isFuture;
  final bool hasRecord;
  final VoidCallback onTap;
  const _DateBubble({
    required this.date,
    required this.selected,
    required this.isToday,
    required this.isFuture,
    required this.hasRecord,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    // 기록 점: 선택 안 됐고, 오늘 표시 점과 겹치지 않을 때만 (오늘은 brandDeep 점 우선).
    final bool showRecordDot = hasRecord && !selected && !isToday;
    return GestureDetector(
      onTap: isFuture ? null : onTap,
      behavior: HitTestBehavior.opaque,
      child: Center(
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOutCubic,
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: selected ? AppColor.surface : Colors.transparent,
            shape: BoxShape.circle,
            boxShadow: selected
                ? [
                    BoxShadow(
                      color: AppColor.ink.withValues(alpha: 0.10),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ]
                : null,
          ),
          alignment: Alignment.center,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '${date.day}',
                style: AppText.bodyLg.copyWith(
                  color: AppColor.ink.withValues(alpha: isFuture ? 0.3 : 1.0),
                  fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
                  fontSize: 15,
                ),
              ),
              // 오늘 표시 — 선택 안 됐을 때만 작은 점
              if (isToday && !selected)
                Container(
                  width: 4,
                  height: 4,
                  margin: const EdgeInsets.only(top: 1),
                  decoration: BoxDecoration(
                    color: AppColor.brandDeep,
                    shape: BoxShape.circle,
                  ),
                )
              // 기록 점 — 기록 있는 다른 날
              else if (showRecordDot)
                Container(
                  width: 4,
                  height: 4,
                  margin: const EdgeInsets.only(top: 1),
                  decoration: BoxDecoration(
                    color: AppColor.ink.withValues(alpha: 0.45),
                    shape: BoxShape.circle,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 공통 카드 데코 — LADS Flat 2.0 + Soft UI
// 모든 메인 카드는 이 톤 통일 (§17)
// ═══════════════════════════════════════════
BoxDecoration _mainCardDeco() => BoxDecoration(
  color: AppColor.surface,
  borderRadius: BorderRadius.circular(AppRadius.lg),
  boxShadow: const [
    BoxShadow(
      color: Color.fromRGBO(140, 155, 175, 0.20),
      blurRadius: 16,
      offset: Offset(0, 5),
    ),
  ],
);

// ═══════════════════════════════════════════
// Figma 268:24 — 회색 본문 위 섹션 공통 위젯
//   - 섹션 제목 옆 '+' 원형 어포던스 (_AddCircleButton)
//   - 행 앞 컬러 라운드 스퀘어 아이콘 (_RowLeadIcon)
//   - 섹션 하단 회색 '+ 추가' 버튼 (_SectionAddButton)
//   - 개별 흰 카드 (_ItemCard) — 끼니/복약/영양제 행 1개당 1카드
// ═══════════════════════════════════════════

// 섹션 헤더 우측 '+' 원형 버튼 (흰 원 + 옅은 보더).
class _AddCircleButton extends StatelessWidget {
  final VoidCallback onTap;
  const _AddCircleButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: AppColor.surface,
          shape: BoxShape.circle,
          border: Border.all(color: AppColor.border),
        ),
        alignment: Alignment.center,
        child: const Icon(
          Icons.add_rounded,
          size: 20,
          color: AppColor.inkSecondary,
        ),
      ),
    );
  }
}

// 행 앞 컬러 라운드 스퀘어 아이콘 (40x40).
class _RowLeadIcon extends StatelessWidget {
  final IconData icon;
  final Color color;
  const _RowLeadIcon({required this.icon, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      alignment: Alignment.center,
      child: Icon(icon, size: 22, color: color),
    );
  }
}

// 섹션 하단 회색 '+ 추가' 버튼 (sunken, 52px).
class _SectionAddButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _SectionAddButton({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        height: 52,
        decoration: BoxDecoration(
          color: AppColor.sunken,
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.add_rounded,
              size: 20,
              color: AppColor.inkSecondary,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: AppText.body.copyWith(
                color: AppColor.inkSecondary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// 끼니/복약/영양제 행 1개를 감싸는 개별 흰 카드.
class _ItemCard extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  const _ItemCard({required this.child, this.onTap, this.onLongPress});

  @override
  Widget build(BuildContext context) {
    final Widget card = Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.lg,
        vertical: 14,
      ),
      decoration: _mainCardDeco(),
      child: child,
    );
    if (onTap == null && onLongPress == null) return card;
    return GestureDetector(
      onLongPress: onLongPress,
      behavior: HitTestBehavior.opaque,
      child: Pressable(onTap: onTap ?? () {}, child: card),
    );
  }
}

// ═══════════════════════════════════════════
// '오늘의 분석' — AI 요약 카드 (health_score.message 재사용)
// 카드 전체 탭 → 분석 탭(/shell/score) 딥링크 (가이드 02 ④(d)).
// 홈에서 daily-coaching 추가 호출은 하지 않는다 (message 만 재사용).
// ═══════════════════════════════════════════
class _TodayAnalysisCard extends StatelessWidget {
  final DashboardHealthScore score;
  final VoidCallback onTap;
  const _TodayAnalysisCard({required this.score, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final String? message = score.message;
    final bool hasMessage = message != null && message.trim().isNotEmpty;
    // Figma 268:24 — 섹션 제목 + '자세히 >'는 회색 본문 위(카드 밖),
    // 그 아래 흰 카드에 레몬봇 요약. 전체를 한 번에 탭하면 분석 탭으로.
    return Pressable(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('오늘의 분석', style: AppText.subtitle),
              Row(
                children: [
                  Text(
                    '자세히',
                    style: AppText.caption.copyWith(
                      color: AppColor.inkSecondary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Icon(
                    Icons.chevron_right_rounded,
                    size: 18,
                    color: AppColor.inkTertiary,
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: AppSpace.md),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpace.cardInside + 2),
            decoration: _mainCardDeco(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Image.asset(MascotPose.find.asset, width: 32, height: 32),
                    const SizedBox(width: AppSpace.sm),
                    Text(
                      '레몬봇 AI 요약',
                      style: AppText.caption.copyWith(
                        color: AppColor.brandDeep,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpace.md),
                Text(
                  hasMessage
                      ? message.trim()
                      : '오늘 끼니와 영양제를 기록하면 맞춤 코멘트를 보여드려요.',
                  style: AppText.body.copyWith(
                    color: AppColor.inkSecondary,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 상호작용 카드 (3상태)
//   ① 위험 N건 → '주의 N건' + user_message 행들
//   ② 안심 → 영양제 있고 위험 없음
//   ③ 미등록 → 영양제·약 모두 미등록일 때만
// 약이 등록되면 '등록한 약 N개 기준으로 함께 살펴봐요' 각주 추가 (시안 580:29 ②상태).
// ⚠️ 약-음식/약-영양제 상호작용 판정은 백엔드 공백 — 클라이언트 임의 판정 금지,
//    각주 표기까지만. 의사·약사 상담 각주 유지.
// ═══════════════════════════════════════════
class _InteractionCard extends StatelessWidget {
  final SupplementImpactPreviewResponse? preview;
  final bool hasSupplements;
  final int medicationCount;
  final bool failed;
  const _InteractionCard({
    required this.preview,
    required this.hasSupplements,
    required this.medicationCount,
    required this.failed,
  });

  @override
  Widget build(BuildContext context) {
    final List<SupplementNutritionInsight> risks =
        preview?.excessOrDuplicateRisks ?? const <SupplementNutritionInsight>[];
    final bool hasMedications = medicationCount > 0;

    final Widget body;
    if (failed && preview == null) {
      body = _statusLine(
        icon: Icons.cloud_off_rounded,
        color: AppColor.inkTertiary,
        title: '상호작용 정보를 불러오지 못했어요',
        subtitle: '잠시 후 당겨서 새로고침 해주세요.',
      );
    } else if (!hasSupplements && !hasMedications) {
      // ③ 영양제·약 모두 미등록.
      body = _statusLine(
        icon: Icons.medication_outlined,
        color: AppColor.inkTertiary,
        title: '등록된 영양제·약이 없어요',
        subtitle: '영양제나 약을 등록하면 중복·상한 확인을 도와드려요.',
      );
    } else if (!hasSupplements) {
      // 약만 등록 — 영양제 중복·상한 계산 대상은 아직 없음 (약 기준 각주만).
      body = _statusLine(
        icon: Icons.medication_outlined,
        color: AppColor.inkTertiary,
        title: '등록된 영양제가 없어요',
        subtitle: '영양제를 등록하면 중복·상한 확인을 도와드려요.',
      );
    } else if (risks.isNotEmpty) {
      // ① 위험 N건
      body = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _statusLine(
            icon: Icons.warning_amber_rounded,
            color: AppColor.warning,
            title: '확인이 필요해요 · ${risks.length}건',
            subtitle: preview?.safeUserMessage,
          ),
          const SizedBox(height: AppSpace.sm),
          for (final SupplementNutritionInsight risk in risks.take(3))
            Padding(
              padding: const EdgeInsets.only(top: AppSpace.xs),
              child: _RiskRow(risk: risk),
            ),
        ],
      );
    } else {
      // ② 안심
      body = _statusLine(
        icon: Icons.check_circle_outline_rounded,
        color: AppColor.success,
        title: '안심하고 드셔도 돼요',
        subtitle: preview?.safeUserMessage ?? '지금 등록된 영양제에서 중복·상한 신호는 없어요.',
      );
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside + 2),
      decoration: _mainCardDeco(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Figma 268:24 — '상호작용 주의' + 위험 N건 배지(주황).
          Row(
            children: [
              Text('상호작용 주의', style: AppText.subtitle),
              if (risks.isNotEmpty) ...[
                const SizedBox(width: AppSpace.sm),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpace.sm,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: AppColor.warning,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                  ),
                  child: Text(
                    '${risks.length}건',
                    style: AppText.micro.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: AppSpace.md),
          body,
          if (hasMedications) ...[
            const SizedBox(height: AppSpace.sm),
            Text(
              '등록한 약 $medicationCount개 기준으로 함께 살펴봐요 · 방금 확인',
              style: AppText.caption.copyWith(color: AppColor.inkTertiary),
            ),
          ],
          const SizedBox(height: AppSpace.md),
          Text(
            '확인이 필요하면 의사·약사와 상담해주세요.',
            style: AppText.micro.copyWith(color: AppColor.inkTertiary),
          ),
        ],
      ),
    );
  }

  Widget _statusLine({
    required IconData icon,
    required Color color,
    required String title,
    String? subtitle,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(AppRadius.sm - 2),
          ),
          alignment: Alignment.center,
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(width: AppSpace.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: AppText.body.copyWith(
                  color: AppColor.ink,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (subtitle != null && subtitle.trim().isNotEmpty) ...[
                const SizedBox(height: 2),
                Text(
                  subtitle.trim(),
                  style: AppText.caption.copyWith(color: AppColor.inkSecondary),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _RiskRow extends StatelessWidget {
  final SupplementNutritionInsight risk;
  const _RiskRow({required this.risk});

  @override
  Widget build(BuildContext context) {
    final String name = (risk.nutrientName?.trim().isNotEmpty ?? false)
        ? risk.nutrientName!.trim()
        : risk.nutrientCode.trim();
    return Container(
      padding: const EdgeInsets.all(AppSpace.sm + 2),
      decoration: BoxDecoration(
        color: AppColor.sunken,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            margin: const EdgeInsets.only(top: 5),
            width: 6,
            height: 6,
            decoration: const BoxDecoration(
              color: AppColor.warning,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$name · ${risk.actionLabel}',
                  style: AppText.caption.copyWith(
                    color: AppColor.ink,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  risk.userMessage,
                  style: AppText.micro.copyWith(color: AppColor.inkSecondary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 식단 관리 — 당일 끼니별 (아침/점심/저녁/간식)
//   기록되면 메뉴명+kcal, 미기록이면 '아직 기록 전' + [기록하기].
// ═══════════════════════════════════════════
class _MealManagementCard extends StatelessWidget {
  final List<HomeMeal> meals;
  final bool failed;
  final VoidCallback onManage;
  final VoidCallback onCameraAdd;
  const _MealManagementCard({
    required this.meals,
    required this.failed,
    required this.onManage,
    required this.onCameraAdd,
  });

  // Figma 268:24 — 아침/점심/저녁은 개별 카드, 간식은 하단 '+ 간식 추가' 버튼.
  static const List<MapEntry<String, String>> _mainSlots =
      <MapEntry<String, String>>[
        MapEntry('breakfast', '아침'),
        MapEntry('lunch', '점심'),
        MapEntry('dinner', '저녁'),
      ];

  List<HomeMeal> _recordsFor(String mealType) {
    return meals
        .where((HomeMeal meal) => meal.mealType == mealType)
        .toList(growable: false);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // 섹션 제목 + '+' 원형 — 회색 본문 위(카드 밖).
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('식단 관리', style: AppText.subtitle),
            _AddCircleButton(onTap: onManage),
          ],
        ),
        const SizedBox(height: AppSpace.md),
        if (failed)
          StatusStateView(
            variant: StatusStateVariant.syncFailed,
            onPrimary: onCameraAdd,
          )
        else ...[
          for (int i = 0; i < _mainSlots.length; i++) ...[
            _ItemCard(
              onTap: onManage,
              child: _MealSlotRow(
                slotKey: _mainSlots[i].key,
                label: _mainSlots[i].value,
                meals: _recordsFor(_mainSlots[i].key),
              ),
            ),
            const SizedBox(height: AppSpace.sm + 2),
          ],
          _SectionAddButton(label: '간식 추가', onTap: onManage),
        ],
      ],
    );
  }
}

class _MealSlotRow extends StatelessWidget {
  final String slotKey;
  final String label;
  final List<HomeMeal> meals;
  const _MealSlotRow({
    required this.slotKey,
    required this.label,
    required this.meals,
  });

  // 끼니별 리딩 아이콘 + 색 (Figma — 아침/점심 웜, 저녁 쿨/라벤더).
  ({IconData icon, Color color}) get _lead {
    switch (slotKey) {
      case 'breakfast':
        return (icon: Icons.wb_twilight_rounded, color: AppColor.warning);
      case 'lunch':
        return (icon: Icons.wb_sunny_rounded, color: AppColor.warning);
      case 'dinner':
      default:
        return (icon: Icons.bedtime_rounded, color: AppColor.info);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bool hasRecords = meals.isNotEmpty;
    final int itemCount = meals.fold<int>(
      0,
      (int count, HomeMeal meal) =>
          count + (meal.foodItems.isEmpty ? 1 : meal.foodItems.length),
    );
    final double kcal = meals.fold<double>(
      0,
      (double total, HomeMeal meal) => total + meal.nutrition.kcal,
    );
    final List<String> names = <String>[
      for (final HomeMeal meal in meals)
        for (final HomeFoodItem item in meal.foodItems)
          if (item.displayName.trim().isNotEmpty) item.displayName.trim(),
    ];
    final String summary = names.isEmpty
        ? '기록됨'
        : names.length <= 2
        ? names.join(', ')
        : '${names.take(2).join(', ')} 외 ${names.length - 2}개';
    final lead = _lead;
    return Row(
      children: [
        _RowLeadIcon(icon: lead.icon, color: lead.color),
        const SizedBox(width: AppSpace.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: AppText.body.copyWith(
                  color: AppColor.ink,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 2),
              !hasRecords
                  ? Text(
                      '아직 기록 전',
                      style: AppText.caption.copyWith(
                        color: AppColor.inkTertiary,
                      ),
                    )
                  : Text(
                      '$itemCount개 기록 · $summary',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppText.caption.copyWith(
                        color: AppColor.inkSecondary,
                      ),
                    ),
            ],
          ),
        ),
        const SizedBox(width: AppSpace.sm),
        if (!hasRecords)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '기록하기',
                style: AppText.caption.copyWith(
                  color: AppColor.brandDeep,
                  fontWeight: FontWeight.w800,
                ),
              ),
              Icon(Icons.add_rounded, size: 16, color: AppColor.brandDeep),
            ],
          )
        else
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '${kcal.round()} kcal',
                style: AppText.caption.copyWith(
                  color: AppColor.inkSecondary,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const Icon(
                Icons.chevron_right_rounded,
                size: 18,
                color: AppColor.inkTertiary,
              ),
            ],
          ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 영양제 관리 — 등록 영양제 체크리스트
//   이름 + intake_schedule 요약 + 체크 토글 (날짜별 LocalPrefs 영속).
// ═══════════════════════════════════════════
class _SupplementChecklistCard extends StatelessWidget {
  final List<HomeSupplement> supplements;
  final Set<String> checkedIds;
  final bool failed;
  final ValueChanged<String> onToggle;
  final VoidCallback onAdd;
  final ValueChanged<HomeSupplement> onDelete;
  const _SupplementChecklistCard({
    required this.supplements,
    required this.checkedIds,
    required this.failed,
    required this.onToggle,
    required this.onAdd,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final int total = supplements.length;
    final int done = supplements
        .where((HomeSupplement item) => checkedIds.contains(item.id))
        .length;

    // Figma 268:24 — 회색 본문 위 개별 흰 카드. 빈 상태는 StatusStateView 유지.
    final bool isEmpty = supplements.isEmpty;
    Widget body;
    if (failed && isEmpty) {
      body = StatusStateView(
        variant: StatusStateVariant.syncFailed,
        onPrimary: onAdd,
      );
    } else if (isEmpty) {
      body = StatusStateView(
        variant: StatusStateVariant.emptyNew,
        onPrimary: onAdd,
      );
    } else {
      body = Column(
        children: [
          for (int i = 0; i < supplements.length; i++) ...[
            _ItemCard(
              onTap: () => onToggle(supplements[i].id),
              onLongPress: () => onDelete(supplements[i]),
              child: _SupplementRow(
                supplement: supplements[i],
                index: i,
                checked: checkedIds.contains(supplements[i].id),
              ),
            ),
            const SizedBox(height: AppSpace.sm + 2),
          ],
          _SectionAddButton(label: '영양제 추가', onTap: onAdd),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('영양제 관리', style: AppText.subtitle),
            const Spacer(),
            if (total > 0)
              Text(
                '$done/$total 완료',
                style: AppText.caption.copyWith(
                  color: AppColor.brandDeep,
                  fontWeight: FontWeight.w700,
                ),
              ),
            const SizedBox(width: AppSpace.sm),
            _AddCircleButton(onTap: onAdd),
          ],
        ),
        const SizedBox(height: AppSpace.md),
        body,
      ],
    );
  }
}

class _SupplementRow extends StatelessWidget {
  final HomeSupplement supplement;
  final int index;
  final bool checked;
  const _SupplementRow({
    required this.supplement,
    required this.index,
    required this.checked,
  });

  @override
  Widget build(BuildContext context) {
    final String? scheduleText = supplement.schedule?.summary;
    final String? categoryLabel = supplement.categoryLabel;
    final Color iconColor = _rowPalette[index % _rowPalette.length];
    return Row(
      children: [
        _RowLeadIcon(icon: Icons.medication_liquid_rounded, color: iconColor),
        const SizedBox(width: AppSpace.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Flexible(
                    child: Text(
                      supplement.displayName.isNotEmpty
                          ? supplement.displayName
                          : '이름 미상 영양제',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppText.body.copyWith(
                        color: checked ? AppColor.inkTertiary : AppColor.ink,
                        fontWeight: FontWeight.w700,
                        decoration: checked ? TextDecoration.lineThrough : null,
                      ),
                    ),
                  ),
                  // 사용자가 고른 분류 칩 (가이드 10 P2 7 후속).
                  if (categoryLabel != null) ...[
                    const SizedBox(width: AppSpace.sm),
                    _SupplementCategoryChip(label: categoryLabel),
                  ],
                ],
              ),
              if (scheduleText != null) ...[
                const SizedBox(height: 2),
                Text(
                  scheduleText,
                  style: AppText.caption.copyWith(color: AppColor.inkTertiary),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(width: AppSpace.sm),
        // 체크 박스
        Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: checked ? AppColor.brand : const Color(0xFFE5E8EB),
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Icon(Icons.check_rounded, color: Colors.white, size: 16),
        ),
      ],
    );
  }
}

// 행 리딩 아이콘 색 로테이션 — Figma의 다채로운 알약 색을 모사.
final List<Color> _rowPalette = <Color>[
  AppColor.danger,
  AppColor.success,
  AppColor.info,
  AppColor.brandDeep,
];

/// 영양제 행에 붙는 분류 칩 (brandSoft pill — 가이드 10 P2 7 후속).
class _SupplementCategoryChip extends StatelessWidget {
  final String label;
  const _SupplementCategoryChip({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.sm, vertical: 2),
      decoration: BoxDecoration(
        color: AppColor.brandSoft,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: AppText.micro.copyWith(
          color: AppColor.brandDeep,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 복약 관리 — 등록 약 목록 (가이드 02 ④(a))
//   행 = 이름 + medication_class 한국어 라벨 + condition_tags 칩(최대 2 + n)
//        + 복용 체크 토글(날짜별 LocalPrefs 영속) + 길게 누르면 비활성화.
//   빈 상태 = 가벼운 안내 + [약 등록하기].
//   ⚠️ 용량/복용 시점 입력 금지 — 전문가 영역 문구로 대체.
// ═══════════════════════════════════════════
class _MedicationCard extends StatelessWidget {
  final List<HomeMedication> medications;
  final Set<String> checkedIds;
  final bool failed;
  final ValueChanged<String> onToggle;
  final VoidCallback onAdd;
  final ValueChanged<HomeMedication> onDeactivate;
  const _MedicationCard({
    required this.medications,
    required this.checkedIds,
    required this.failed,
    required this.onToggle,
    required this.onAdd,
    required this.onDeactivate,
  });

  @override
  Widget build(BuildContext context) {
    final int total = medications.length;
    final int done = medications
        .where((HomeMedication item) => checkedIds.contains(item.id))
        .length;

    // Figma 268:24 — 회색 본문 위 개별 흰 카드 + 하단 회색 '약 추가'.
    Widget body;
    if (failed && medications.isEmpty) {
      body = StatusStateView(
        variant: StatusStateVariant.syncFailed,
        onPrimary: onAdd,
      );
    } else if (medications.isEmpty) {
      // 빈 상태 — figma 상호작용 카드 ③상태 톤.
      body = _MedicationEmpty(onAdd: onAdd);
    } else {
      body = Column(
        children: [
          for (int i = 0; i < medications.length; i++) ...[
            _ItemCard(
              onTap: () => onToggle(medications[i].id),
              onLongPress: () => onDeactivate(medications[i]),
              child: _MedicationRow(
                medication: medications[i],
                index: i,
                checked: checkedIds.contains(medications[i].id),
              ),
            ),
            const SizedBox(height: AppSpace.sm + 2),
          ],
          _SectionAddButton(label: '약 추가', onTap: onAdd),
        ],
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('복약 관리', style: AppText.subtitle),
            const Spacer(),
            if (total > 0)
              Text(
                '$done/$total 완료',
                style: AppText.caption.copyWith(
                  color: AppColor.brandDeep,
                  fontWeight: FontWeight.w700,
                ),
              ),
            const SizedBox(width: AppSpace.sm),
            _AddCircleButton(onTap: onAdd),
          ],
        ),
        const SizedBox(height: AppSpace.md),
        body,
        const SizedBox(height: AppSpace.md),
        Text(
          '약 변경은 의사·약사와 상담해주세요.',
          style: AppText.micro.copyWith(color: AppColor.inkTertiary),
        ),
      ],
    );
  }
}

// 빈 상태 — 가벼운 안내 + [약 등록하기]
class _MedicationEmpty extends StatelessWidget {
  final VoidCallback onAdd;
  const _MedicationEmpty({required this.onAdd});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '복용 중인 약을 등록하면 음식·영양제 궁합을 확인해드려요.',
          style: AppText.body.copyWith(
            color: AppColor.inkSecondary,
            height: 1.5,
          ),
        ),
        const SizedBox(height: AppSpace.md),
        _SectionAddButton(label: '약 등록하기', onTap: onAdd),
      ],
    );
  }
}

class _MedicationRow extends StatelessWidget {
  final HomeMedication medication;
  final int index;
  final bool checked;
  const _MedicationRow({
    required this.medication,
    required this.index,
    required this.checked,
  });

  @override
  Widget build(BuildContext context) {
    final String? classLabel = medication.medicationClassLabel;
    final List<String> tagLabels = medication.conditionTagLabels;
    final Color iconColor = _rowPalette[index % _rowPalette.length];
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _RowLeadIcon(icon: Icons.medication_rounded, color: iconColor),
        const SizedBox(width: AppSpace.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Flexible(
                    child: Text(
                      medication.displayName.isNotEmpty
                          ? medication.displayName
                          : '이름 미상 약',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppText.body.copyWith(
                        color: checked ? AppColor.inkTertiary : AppColor.ink,
                        fontWeight: FontWeight.w700,
                        decoration: checked ? TextDecoration.lineThrough : null,
                      ),
                    ),
                  ),
                  if (classLabel != null) ...[
                    const SizedBox(width: AppSpace.sm),
                    _ClassLabelChip(label: classLabel),
                  ],
                ],
              ),
              if (tagLabels.isNotEmpty) ...[
                const SizedBox(height: 6),
                _ConditionTagChips(labels: tagLabels),
              ],
            ],
          ),
        ),
        const SizedBox(width: AppSpace.sm),
        // 복용 체크 박스
        Container(
          width: 24,
          height: 24,
          decoration: BoxDecoration(
            color: checked ? AppColor.brand : const Color(0xFFE5E8EB),
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Icon(Icons.check_rounded, color: Colors.white, size: 16),
        ),
      ],
    );
  }
}

// medication_class 한국어 라벨 칩 (옅은 sunken 배경)
class _ClassLabelChip extends StatelessWidget {
  final String label;
  const _ClassLabelChip({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppColor.sunken,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        label,
        style: AppText.micro.copyWith(color: AppColor.inkSecondary),
      ),
    );
  }
}

// condition_tags 칩 — 최대 2개 + 'N개 더'
class _ConditionTagChips extends StatelessWidget {
  final List<String> labels;
  const _ConditionTagChips({required this.labels});

  @override
  Widget build(BuildContext context) {
    final List<String> shown = labels.take(2).toList(growable: false);
    final int extra = labels.length - shown.length;
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: <Widget>[
        for (final String tag in shown) _TagPill(label: tag),
        if (extra > 0) _TagPill(label: '+$extra'),
      ],
    );
  }
}

class _TagPill extends StatelessWidget {
  final String label;
  const _TagPill({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppColor.brandSoft,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        label,
        style: AppText.micro.copyWith(color: AppColor.brandDeep),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 의료 면책 (LADS §14)
// ═══════════════════════════════════════════
class _MedicalDisclaimer extends StatelessWidget {
  const _MedicalDisclaimer();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.brandSoft,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline, color: AppColor.brandDeep, size: 18),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: Text(
              '레몬에이드는 건강 관리를 도와드리는 서비스로\n의사·약사·영양사의 진단을 대신하진 않아요.',
              style: AppText.caption.copyWith(color: AppColor.ink, height: 1.5),
            ),
          ),
        ],
      ),
    );
  }
}
