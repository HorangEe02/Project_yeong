// screens/calendar_screen.dart — 캘린더 (월 그리드 + 일자 상세)
//
// 가이드 07 ② (figma 763:24 + 364:24):
//   AppBar(← + '캘린더')
//   ├─ 월 네비: ◀ 2026년 6월 ▶
//   ├─ 요일 행: 일(danger)·토(info)·평일(inkSecondary) — 색+텍스트 병행
//   ├─ 월 그리드 7×N: 오늘 = brand 원, 선택일 = brandSoft 원,
//   │                 기록 점 = 식단(brand)·영양제(info)
//   ├─ 일자 상세 카드: '6월 12일 기록 N건' + 끼니[메뉴·kcal]/영양제[이름] + ›
//   └─ 면책 푸터
//
// 데이터: RecordsRepository.fetchMonth(월 단위 1회 로드 + 캐시). 월 이동 시 재로드.
// 행 탭 → 기존 기록 모드 재사용(DashboardScreen(recordDate:)) — 신규 상세 화면 X
// (가이드 02 ④(b) 10번). 미구현 동선은 비활성 + TODO 주석.
//
// 연산은 모두 백엔드. 모바일은 표시·날짜 버킷팅만. 사용자 문구는 해요체 +
// 금칙어(진단/처방/치료/효능) 미사용.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../app_controller.dart';
import '../core/storage/local_prefs.dart';
import '../features/dashboard/home_models.dart';
import '../features/records/records_models.dart';
import '../features/records/records_repository.dart';
import '../shared/widgets/status_state_view.dart';
import '../utils/design_tokens_v2.dart';
import '../widgets/common/pressable.dart';

/// 월 그리드 + 일자 상세 캘린더 화면.
class CalendarScreen extends StatefulWidget {
  /// 월 단위 기록을 로드하는 리포지토리.
  const CalendarScreen({
    required this.repository,
    required this.controller,
    this.localPrefs,
    super.key,
  });

  /// 캘린더 월 단위 로더(캐시 포함).
  final RecordsRepository repository;

  /// '지난 기록' 모드 진입 시 재사용할 홈 컨트롤러.
  final AppController controller;

  /// 날짜별 체크 상태를 영속하는 로컬 저장 래퍼 (지난 기록 모드로 전달).
  final LocalPrefs? localPrefs;

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  // 현재 보고 있는 달 (1일 고정).
  late DateTime _focusedMonth;
  // 상세 카드가 보여주는 선택일.
  late DateTime _selectedDate;
  // 현재 달 기록 (로딩 전 null).
  MonthRecords? _records;
  bool _loading = false;
  bool _failed = false;

  // Figma 05 "캘린더 (홈 서브)" canonical — 일요일 시작 (일 월 화 수 목 금 토)
  static const List<String> _weekdayLabels = <String>[
    '일',
    '월',
    '화',
    '수',
    '목',
    '금',
    '토',
  ];

  @override
  void initState() {
    super.initState();
    final DateTime now = DateTime.now();
    _focusedMonth = DateTime(now.year, now.month);
    _selectedDate = DateTime(now.year, now.month, now.day);
    _loadMonth();
  }

  bool _isFuture(DateTime day) {
    final DateTime now = DateTime.now();
    final DateTime today = DateTime(now.year, now.month, now.day);
    return day.isAfter(today);
  }

  bool get _canGoNextMonth {
    final DateTime now = DateTime.now();
    final DateTime thisMonth = DateTime(now.year, now.month);
    return _focusedMonth.isBefore(thisMonth);
  }

  Future<void> _loadMonth() async {
    setState(() {
      _loading = true;
      _failed = false;
    });
    try {
      final MonthRecords records = await widget.repository.fetchMonth(
        _focusedMonth,
      );
      if (!mounted) return;
      setState(() {
        _records = records;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _failed = true;
        _loading = false;
      });
    }
  }

  void _shiftMonth(int delta) {
    final DateTime next = DateTime(
      _focusedMonth.year,
      _focusedMonth.month + delta,
    );
    // 미래 달로는 이동하지 않는다.
    final DateTime now = DateTime.now();
    if (next.isAfter(DateTime(now.year, now.month))) return;
    setState(() {
      _focusedMonth = next;
      // 새 달의 선택일은 그 달 1일 (오늘이 그 달이면 오늘).
      _selectedDate = (next.year == now.year && next.month == now.month)
          ? DateTime(now.year, now.month, now.day)
          : DateTime(next.year, next.month);
      _records = null;
    });
    _loadMonth();
  }

  void _selectDate(DateTime day) {
    if (_isFuture(day)) return;
    setState(() {
      _selectedDate = day;
    });
  }

  // 일자 상세 행 탭 → 오늘의 기록(일일 타임라인) 화면으로 이동 (가이드 ⑧).
  // 선택일을 ?date=YYYY-MM-DD 로 넘긴다. GoRouter 가 없는 환경(일부 테스트)에서는
  // no-op 으로 안전하게 무시한다.
  void _openRecordMode() {
    final String key = MonthRecords.keyForDay(_selectedDate);
    GoRouter.maybeOf(context)?.go('/shell/home/records?date=$key');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColor.bg,
      appBar: AppBar(
        backgroundColor: AppColor.bg,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: AppColor.ink),
          onPressed: () => Navigator.of(context).maybePop(),
        ),
        title: Text(
          '캘린더',
          style: AppText.subtitle.copyWith(fontWeight: FontWeight.w800),
        ),
        centerTitle: false,
      ),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.page,
            AppSpace.md,
            AppSpace.page,
            AppSpace.xl,
          ),
          children: <Widget>[
            // Figma 364:24 — 월 헤더 + 요일 + 그리드를 하나의 흰 카드로 묶음.
            Container(
              width: double.infinity,
              decoration: _calendarCardDeco(),
              padding: const EdgeInsets.all(AppSpace.cardInside),
              child: Column(
                children: <Widget>[
                  _MonthNav(
                    month: _focusedMonth,
                    canGoNext: _canGoNextMonth,
                    onPrev: () => _shiftMonth(-1),
                    onNext: _canGoNextMonth ? () => _shiftMonth(1) : null,
                  ),
                  const SizedBox(height: AppSpace.lg),
                  _WeekdayRow(labels: _weekdayLabels),
                  const SizedBox(height: AppSpace.sm),
                  _MonthGrid(
                    month: _focusedMonth,
                    records: _records,
                    selectedDate: _selectedDate,
                    loading: _loading,
                    onSelectDate: _selectDate,
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpace.xl),
            _DayDetail(
              date: _selectedDate,
              records: _records,
              loading: _loading,
              failed: _failed,
              onRetry: _loadMonth,
              onOpenRecord: _openRecordMode,
            ),
            const SizedBox(height: AppSpace.xl),
            const _CalendarDisclaimer(),
          ],
        ),
      ),
    );
  }
}

// 캘린더 공용 카드 데코 — 월 그리드 카드 + 일자 상세 카드 공유 (단일 출처).
BoxDecoration _calendarCardDeco() => BoxDecoration(
  color: AppColor.surface,
  borderRadius: BorderRadius.circular(AppRadius.lg),
  boxShadow: AppShadow.softCard,
);

// ═══════════════════════════════════════════
// 월 네비 — ‹ 2026년 6월 ›  (중앙정렬) — Figma 05 "캘린더 (홈 서브)"
// ═══════════════════════════════════════════
class _MonthNav extends StatelessWidget {
  final DateTime month;
  final bool canGoNext;
  final VoidCallback onPrev;
  final VoidCallback? onNext;
  const _MonthNav({
    required this.month,
    required this.canGoNext,
    required this.onPrev,
    required this.onNext,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        _NavArrow(icon: Icons.chevron_left_rounded, onTap: onPrev),
        const SizedBox(width: AppSpace.lg),
        Text(
          '${month.year}년 ${month.month}월',
          style: AppText.subtitle.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(width: AppSpace.lg),
        _NavArrow(icon: Icons.chevron_right_rounded, onTap: onNext),
      ],
    );
  }
}

class _NavArrow extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;
  const _NavArrow({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final bool enabled = onTap != null;
    return Pressable(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: const BoxDecoration(
          color: AppColor.sunken,
          shape: BoxShape.circle,
        ),
        alignment: Alignment.center,
        child: Icon(
          icon,
          size: 22,
          color: AppColor.ink.withValues(alpha: enabled ? 0.85 : 0.25),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 요일 행 — 일(danger)·토(info)·평일(inkSecondary), 색+텍스트 병행
// ═══════════════════════════════════════════
class _WeekdayRow extends StatelessWidget {
  final List<String> labels;
  const _WeekdayRow({required this.labels});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        for (int i = 0; i < 7; i++)
          Expanded(
            child: Center(
              child: Text(
                labels[i],
                style: AppText.caption.copyWith(
                  color: _weekdayColor(i),
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
      ],
    );
  }

  static Color _weekdayColor(int index) {
    // 일요일 시작: index 0 = 일(danger/빨강), 6 = 토(info/파랑)
    if (index == 0) return AppColor.danger; // 일요일
    if (index == 6) return AppColor.info; // 토요일
    return AppColor.inkSecondary; // 평일
  }
}

// ═══════════════════════════════════════════
// 월 그리드 — 일=0 시작, 셀 48px+, 기록 점/오늘/선택 강조
// ═══════════════════════════════════════════
class _MonthGrid extends StatelessWidget {
  final DateTime month;
  final MonthRecords? records;
  final DateTime selectedDate;
  final bool loading;
  final ValueChanged<DateTime> onSelectDate;
  const _MonthGrid({
    required this.month,
    required this.records,
    required this.selectedDate,
    required this.loading,
    required this.onSelectDate,
  });

  @override
  Widget build(BuildContext context) {
    final DateTime firstOfMonth = DateTime(month.year, month.month);
    // 일요일=0 시작. DateTime.weekday 는 월=1..일=7 → 일=0 으로 변환(%7).
    final int leadingBlanks = firstOfMonth.weekday % 7;
    final int daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    final int totalCells = ((leadingBlanks + daysInMonth) / 7).ceil() * 7;
    final DateTime now = DateTime.now();

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 7,
        childAspectRatio: 0.78,
      ),
      itemCount: totalCells,
      itemBuilder: (BuildContext context, int index) {
        final int dayNumber = index - leadingBlanks + 1;
        if (dayNumber < 1 || dayNumber > daysInMonth) {
          return const SizedBox.shrink();
        }
        final DateTime day = DateTime(month.year, month.month, dayNumber);
        final bool isToday =
            MonthRecords.keyForDay(day) ==
            MonthRecords.keyForDay(DateTime(now.year, now.month, now.day));
        final bool isSelected = _sameDay(day, selectedDate);
        final bool isFuture = day.isAfter(
          DateTime(now.year, now.month, now.day),
        );
        final bool hasMeal = records?.hasMeal(day) ?? false;
        final bool hasSupplement = records?.hasSupplement(day) ?? false;
        return _DayCell(
          dayNumber: dayNumber,
          dateWeekday: day.weekday,
          isToday: isToday,
          isSelected: isSelected,
          isFuture: isFuture,
          hasMeal: hasMeal,
          hasSupplement: hasSupplement,
          // 로딩 중이면 점은 표시하지 않는다 (skeleton 대용 — 회색 비표시).
          showDots: !loading,
          onTap: isFuture ? null : () => onSelectDate(day),
        );
      },
    );
  }

  static bool _sameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;
}

class _DayCell extends StatelessWidget {
  final int dayNumber;
  final int dateWeekday; // DateTime.weekday: 1=월 .. 7=일
  final bool isToday;
  final bool isSelected;
  final bool isFuture;
  final bool hasMeal;
  final bool hasSupplement;
  final bool showDots;
  final VoidCallback? onTap;
  const _DayCell({
    required this.dayNumber,
    required this.dateWeekday,
    required this.isToday,
    required this.isSelected,
    required this.isFuture,
    required this.hasMeal,
    required this.hasSupplement,
    required this.showDots,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    // 숫자 색: 오늘=ink(원 위), 미래=흐림, 일(7)=danger·토(6)=info, 평일 ink.
    Color numberColor;
    if (isFuture) {
      numberColor = AppColor.inkDisabled;
    } else if (dateWeekday == 7) {
      numberColor = AppColor.danger; // 일요일
    } else if (dateWeekday == 6) {
      numberColor = AppColor.info; // 토요일
    } else {
      numberColor = AppColor.ink;
    }

    // 셀 배경: 오늘=brand 원, 선택일=brandSoft 원.
    Color circleColor = Colors.transparent;
    if (isToday) {
      circleColor = AppColor.brand;
      numberColor = AppColor.ink;
    } else if (isSelected) {
      circleColor = AppColor.brandSoft;
    }

    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: <Widget>[
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: circleColor,
              shape: BoxShape.circle,
              border: isSelected && !isToday
                  ? Border.all(color: AppColor.brand, width: 1.4)
                  : null,
            ),
            alignment: Alignment.center,
            child: Text(
              '$dayNumber',
              style: AppText.body.copyWith(
                color: numberColor,
                fontWeight: isToday || isSelected
                    ? FontWeight.w800
                    : FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(height: 3),
          // 기록 점: Figma 364:24 — 기록 있는 날 단일 점.
          // 오늘 셀(brand 원)은 중립 회색 점, 그 외는 brand 노랑 점.
          SizedBox(
            height: 6,
            child: showDots && (hasMeal || hasSupplement)
                ? _dot(isToday ? AppColor.inkTertiary : AppColor.brand)
                : const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }

  Widget _dot(Color color) {
    return Container(
      width: 5,
      height: 5,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

// ═══════════════════════════════════════════
// 일자 상세 카드 — '6월 12일 목요일' + '기록 N건' + 끼니/영양제 행
// ═══════════════════════════════════════════
class _DayDetail extends StatelessWidget {
  final DateTime date;
  final MonthRecords? records;
  final bool loading;
  final bool failed;
  final VoidCallback onRetry;
  final VoidCallback onOpenRecord;
  const _DayDetail({
    required this.date,
    required this.records,
    required this.loading,
    required this.failed,
    required this.onRetry,
    required this.onOpenRecord,
  });

  static const List<String> _weekdayFull = <String>[
    '월요일',
    '화요일',
    '수요일',
    '목요일',
    '금요일',
    '토요일',
    '일요일',
  ];

  @override
  Widget build(BuildContext context) {
    if (failed) {
      return Container(
        decoration: _cardDeco(),
        padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
        child: StatusStateView(
          variant: StatusStateVariant.syncFailed,
          onPrimary: onRetry,
        ),
      );
    }

    final DayRecords day = records?.forDay(date) ?? DayRecords.empty;
    final String dateLabel =
        '${date.month}월 ${date.day}일 ${_weekdayFull[date.weekday - 1]}';

    return Container(
      width: double.infinity,
      decoration: _cardDeco(),
      padding: const EdgeInsets.all(AppSpace.cardInside),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  dateLabel,
                  style: AppText.subtitle.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              if (!loading)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpace.md,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: AppColor.brandSoft,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                  ),
                  child: Text(
                    '기록 ${day.totalCount}건',
                    style: AppText.caption.copyWith(
                      color: AppColor.brandDeep,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: AppSpace.md),
          if (loading)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
              child: Text(
                '불러오는 중이에요',
                style: AppText.body.copyWith(color: AppColor.inkTertiary),
              ),
            )
          else if (day.totalCount == 0)
            StatusStateView(
              variant: StatusStateVariant.emptyNew,
              onPrimary: onOpenRecord,
            )
          else ...<Widget>[
            for (final HomeMeal meal in day.meals)
              _RecordRow(
                icon: Icons.restaurant_rounded,
                iconColor: AppColor.brand,
                title: meal.primaryName ?? '식단 기록',
                trailing: '${meal.nutrition.kcal.round()} kcal',
                onTap: onOpenRecord,
              ),
            for (final HomeSupplement supplement in day.supplements)
              _RecordRow(
                icon: Icons.medication_outlined,
                iconColor: AppColor.info,
                title: supplement.displayName.isNotEmpty
                    ? supplement.displayName
                    : '영양제',
                trailing: null,
                onTap: onOpenRecord,
              ),
          ],
        ],
      ),
    );
  }

  BoxDecoration _cardDeco() => _calendarCardDeco();
}

class _RecordRow extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String? trailing;
  final VoidCallback onTap;
  const _RecordRow({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.trailing,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: AppSpace.sm + 2),
        child: Row(
          children: <Widget>[
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: iconColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(AppRadius.sm - 2),
              ),
              alignment: Alignment.center,
              child: Icon(icon, size: 18, color: iconColor),
            ),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: AppText.body.copyWith(
                  color: AppColor.ink,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            if (trailing != null) ...<Widget>[
              const SizedBox(width: AppSpace.sm),
              Text(
                trailing!,
                style: AppText.caption.copyWith(
                  color: AppColor.inkSecondary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
            const SizedBox(width: 2),
            Icon(
              Icons.chevron_right_rounded,
              color: AppColor.inkTertiary,
              size: 20,
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 면책 푸터
// ═══════════════════════════════════════════
class _CalendarDisclaimer extends StatelessWidget {
  const _CalendarDisclaimer();

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
        children: <Widget>[
          Icon(Icons.info_outline, color: AppColor.brandDeep, size: 18),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: Text(
              '건강 참고용이며 의학적 판단을 대신하지 않아요.',
              style: AppText.caption.copyWith(color: AppColor.ink, height: 1.5),
            ),
          ),
        ],
      ),
    );
  }
}
