// screens/daily_records_screen.dart — 오늘의 기록 (일일 타임라인)
//
// 가이드 07 ② (figma 947:108):
//   AppBar('오늘의 기록')
//   ├─ 일자 내비: ◀ 6월 12일 (목) ▶ — 미래로는 ▶ 비활성
//   ├─ 합계 카드: 총 kcal | 끼니 N회 | 영양제 N개 (3분할)
//   ├─ 타임라인: 시각 오름차순 병합 (끼니·영양제 행), 영양제 행 ⋯ → 삭제
//   ├─ '저녁 기록 추가' 점선 버튼 → 카메라(/shell/camera)
//   └─ 면책 푸터
//
// 데이터: RecordsRepository.fetchMonth(월 단위 캐시). 일자 이동이 월 경계를 넘으면
// 인접 월을 로드한다. 삭제는 지연 큐(4초)+실행취소 토스트(백엔드 공백 3 대체).
//
// 연산은 모두 백엔드. 모바일은 표시·합산·날짜 버킷팅만. 문구는 해요체 +
// 금칙어(진단/처방/치료/효능) 미사용. 끼니 삭제는 백엔드 공백 2로 비노출.

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../features/dashboard/home_models.dart';
import '../features/records/deferred_delete_queue.dart';
import '../features/records/records_models.dart';
import '../features/records/records_repository.dart';
import '../shared/widgets/status_state_view.dart';
import '../utils/design_tokens_v2.dart';
import '../widgets/common/app_modals.dart';
import '../widgets/common/pressable.dart';

/// 일일 타임라인(오늘의 기록) 화면.
class DailyRecordsScreen extends StatefulWidget {
  /// 일일 기록 화면을 생성한다.
  ///
  /// Args:
  ///   repository: 월 단위 기록 로더(캐시 포함).
  ///   initialDate: 진입 일자(기본 오늘). 미래 일자는 오늘로 보정.
  const DailyRecordsScreen({
    required this.repository,
    this.initialDate,
    super.key,
  });

  /// 월 단위 기록 로더.
  final RecordsRepository repository;

  /// 진입 일자 (null 이면 오늘).
  final DateTime? initialDate;

  @override
  State<DailyRecordsScreen> createState() => _DailyRecordsScreenState();
}

class _DailyRecordsScreenState extends State<DailyRecordsScreen> {
  late DateTime _date;
  MonthRecords? _records;
  bool _loading = false;
  bool _failed = false;

  final DeferredDeleteQueue _deleteQueue = DeferredDeleteQueue();
  // 낙관적으로 화면에서 숨긴 영양제 id (실행취소 시 복원).
  final Set<String> _hiddenSupplementIds = <String>{};

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
  void initState() {
    super.initState();
    final DateTime now = DateTime.now();
    final DateTime today = DateTime(now.year, now.month, now.day);
    final DateTime requested = widget.initialDate == null
        ? today
        : DateTime(
            widget.initialDate!.year,
            widget.initialDate!.month,
            widget.initialDate!.day,
          );
    _date = requested.isAfter(today) ? today : requested;
    _loadMonth();
  }

  @override
  void dispose() {
    // 보류 중인 삭제는 떠나기 전에 즉시 commit 한다(유실 방지).
    _deleteQueue.flush();
    super.dispose();
  }

  bool get _canGoNextDay {
    final DateTime now = DateTime.now();
    final DateTime today = DateTime(now.year, now.month, now.day);
    return _date.isBefore(today);
  }

  Future<void> _loadMonth() async {
    setState(() {
      _loading = true;
      _failed = false;
    });
    try {
      final MonthRecords records = await widget.repository.fetchMonth(
        DateTime(_date.year, _date.month),
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

  void _shiftDay(int delta) {
    final DateTime next = DateTime(_date.year, _date.month, _date.day + delta);
    final DateTime now = DateTime.now();
    final DateTime today = DateTime(now.year, now.month, now.day);
    if (next.isAfter(today)) return;
    final bool crossesMonth =
        next.year != _date.year || next.month != _date.month;
    setState(() {
      _date = next;
      if (crossesMonth) _records = null;
    });
    // 월 경계를 넘어가면 인접 월을 로드(캐시 히트 시 즉시).
    if (crossesMonth) _loadMonth();
  }

  DayRecords get _dayRecords {
    final DayRecords day = _records?.forDay(_date) ?? DayRecords.empty;
    if (_hiddenSupplementIds.isEmpty) return day;
    return DayRecords(
      meals: day.meals,
      supplements: day.supplements
          .where((HomeSupplement s) => !_hiddenSupplementIds.contains(s.id))
          .toList(growable: false),
    );
  }

  void _goToCamera() {
    context.go('/shell/camera');
  }

  Future<void> _confirmDeleteSupplement(HomeSupplement supplement) async {
    final bool confirmed = await showDeleteConfirmDialog(
      context,
      targetLabel: supplement.displayName.isNotEmpty
          ? supplement.displayName
          : '영양제',
    );
    if (!confirmed || !mounted) return;
    setState(() {
      _hiddenSupplementIds.add(supplement.id);
    });
    showUndoToast(
      context,
      message: '영양제를 삭제했어요',
      onUndo: () {
        _deleteQueue.undo(supplement.id);
        if (!mounted) return;
        setState(() {
          _hiddenSupplementIds.remove(supplement.id);
        });
      },
    );
    _deleteQueue.schedule(supplement.id, () async {
      await widget.repository.deleteSupplement(supplement.id);
    });
  }

  @override
  Widget build(BuildContext context) {
    final DayRecords day = _dayRecords;
    final List<RecordTimelineEntry> timeline = day.timeline;

    return Scaffold(
      backgroundColor: AppColor.sunken,
      appBar: AppBar(
        backgroundColor: AppColor.sunken,
        elevation: 0,
        scrolledUnderElevation: 0,
        leading: Padding(
          padding: const EdgeInsets.only(left: AppSpace.sm),
          child: Pressable(
            onTap: () => Navigator.of(context).maybePop(),
            child: Container(
              width: 40,
              height: 40,
              decoration: const BoxDecoration(
                color: AppColor.surface,
                shape: BoxShape.circle,
                boxShadow: AppShadow.elev1,
              ),
              alignment: Alignment.center,
              child: const Icon(
                Icons.chevron_left_rounded,
                size: 24,
                color: AppColor.ink,
              ),
            ),
          ),
        ),
        leadingWidth: 40 + AppSpace.sm * 2,
        title: Text(
          '오늘의 기록',
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
            _DayNav(
              label: _dateLabel(_date),
              canGoNext: _canGoNextDay,
              onPrev: () => _shiftDay(-1),
              onNext: _canGoNextDay ? () => _shiftDay(1) : null,
            ),
            const SizedBox(height: AppSpace.lg),
            _SummaryCard(day: day, loading: _loading),
            const SizedBox(height: AppSpace.xl),
            if (_failed)
              _CardFrame(
                child: StatusStateView(
                  variant: StatusStateVariant.syncFailed,
                  onPrimary: _loadMonth,
                ),
              )
            else if (_loading)
              const _CardFrame(child: _TimelineLoading())
            else if (timeline.isEmpty)
              _CardFrame(
                child: StatusStateView(
                  variant: StatusStateVariant.emptyNew,
                  onPrimary: _goToCamera,
                ),
              )
            else
              _TimelineList(
                entries: timeline,
                onDeleteSupplement: _confirmDeleteSupplement,
              ),
            const SizedBox(height: AppSpace.lg),
            _AddRecordButton(onTap: _goToCamera),
            const SizedBox(height: AppSpace.xl),
            const _RecordsDisclaimer(),
          ],
        ),
      ),
    );
  }

  String _dateLabel(DateTime date) {
    final String weekday = _weekdayFull[date.weekday - 1];
    return '${date.month}월 ${date.day}일 $weekday';
  }
}

// ═══════════════════════════════════════════
// 일자 내비 — ◀ 6월 12일 (목) ▶
// ═══════════════════════════════════════════
class _DayNav extends StatelessWidget {
  final String label;
  final bool canGoNext;
  final VoidCallback onPrev;
  final VoidCallback? onNext;
  const _DayNav({
    required this.label,
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
          label,
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
    // 페이지 배경이 sunken 이라 내비 화살표는 흰 원형 + elev1 으로 떠 보이게 한다.
    return Pressable(
      onTap: onTap,
      child: Container(
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          color: AppColor.surface,
          shape: BoxShape.circle,
          boxShadow: enabled ? AppShadow.elev1 : null,
        ),
        alignment: Alignment.center,
        child: Icon(
          icon,
          size: 24,
          color: AppColor.ink.withValues(alpha: enabled ? 0.85 : 0.25),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 합계 카드 — 총 kcal | 끼니 N회 | 영양제 N개
// ═══════════════════════════════════════════
class _SummaryCard extends StatelessWidget {
  final DayRecords day;
  final bool loading;
  const _SummaryCard({required this.day, required this.loading});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: _cardDeco(),
      child: loading
          ? Text(
              '불러오는 중이에요',
              style: AppText.body.copyWith(color: AppColor.inkTertiary),
            )
          : Row(
              children: <Widget>[
                Expanded(
                  child: _SummaryCell(
                    value: '${day.totalKcal}',
                    unit: 'kcal',
                    label: '섭취 열량',
                  ),
                ),
                _divider(),
                Expanded(
                  child: _SummaryCell(
                    value: '${day.meals.length}',
                    unit: '회',
                    label: '끼니',
                  ),
                ),
                _divider(),
                Expanded(
                  child: _SummaryCell(
                    value: '${day.supplements.length}',
                    unit: '개',
                    label: '영양제',
                  ),
                ),
              ],
            ),
    );
  }

  Widget _divider() => Container(
    width: 1,
    height: 40,
    color: AppColor.border,
    margin: const EdgeInsets.symmetric(horizontal: AppSpace.sm),
  );
}

class _SummaryCell extends StatelessWidget {
  final String value;
  final String unit;
  final String label;
  const _SummaryCell({
    required this.value,
    required this.unit,
    required this.label,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        RichText(
          text: TextSpan(
            text: value,
            style: AppText.subtitle.copyWith(
              fontWeight: FontWeight.w800,
              color: AppColor.ink,
            ),
            children: <TextSpan>[
              TextSpan(
                text: ' $unit',
                style: AppText.caption.copyWith(color: AppColor.inkSecondary),
              ),
            ],
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: AppText.caption.copyWith(color: AppColor.inkTertiary),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 타임라인 — 시각 오름차순 병합 행 리스트
// ═══════════════════════════════════════════
class _TimelineList extends StatelessWidget {
  final List<RecordTimelineEntry> entries;
  final ValueChanged<HomeSupplement> onDeleteSupplement;
  const _TimelineList({
    required this.entries,
    required this.onDeleteSupplement,
  });

  @override
  Widget build(BuildContext context) {
    // 항목마다 개별 흰 카드(figma) — 카드 사이 간격, 행간 구분선 없음.
    return Column(
      children: <Widget>[
        for (int i = 0; i < entries.length; i++) ...<Widget>[
          _TimelineCard(
            entry: entries[i],
            onDelete:
                entries[i].kind == RecordTimelineKind.supplement &&
                    entries[i].supplement != null
                ? () => onDeleteSupplement(entries[i].supplement!)
                : null,
          ),
          if (i != entries.length - 1) const SizedBox(height: AppSpace.md),
        ],
      ],
    );
  }
}

/// 타임라인 한 항목 = 독립 흰 카드.
///
/// 레이아웃: [56×56 라운드 썸네일 타일] | [카테고리 칩 + 시각 / 볼드 제목]
/// | [우측 정렬 값(끼니 kcal·영양제는 생략)].
/// 영양제 카드는 길게 누르면 삭제 플로우로 진입한다(인라인 ⋯ 미노출).
class _TimelineCard extends StatelessWidget {
  final RecordTimelineEntry entry;
  final VoidCallback? onDelete;
  const _TimelineCard({required this.entry, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final bool isMeal = entry.kind == RecordTimelineKind.meal;
    final _CategoryChipStyle chip = _categoryChipStyle(entry);

    // figma 카드엔 인라인 ⋯ 가 없다 — 영양제는 길게 눌러 삭제로 진입한다.
    // (삭제 플로우: 확인 모달 → 낙관적 제거 → 실행취소 토스트 → 지연 커밋).
    return GestureDetector(
      onLongPress: onDelete,
      behavior: HitTestBehavior.opaque,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpace.md),
        decoration: BoxDecoration(
          color: AppColor.surface,
          borderRadius: BorderRadius.circular(AppRadius.lg),
          boxShadow: AppShadow.softCard,
        ),
        child: Row(
          children: <Widget>[
            _LeadingTile(isMeal: isMeal),
            const SizedBox(width: AppSpace.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      _CategoryChip(style: chip),
                      const SizedBox(width: AppSpace.sm),
                      Flexible(
                        child: Text(
                          entry.timeLabel,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppText.caption.copyWith(
                            color: AppColor.inkTertiary,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpace.xs),
                  Text(
                    entry.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.body.copyWith(fontWeight: FontWeight.w700),
                  ),
                ],
              ),
            ),
            // 끼니 = kcal 값, 영양제 = 분량 데이터 없어 생략(가짜 '1정' 금지).
            if (isMeal && entry.trailing != null) ...<Widget>[
              const SizedBox(width: AppSpace.sm),
              Text(
                entry.trailing!,
                style: AppText.caption.copyWith(
                  color: AppColor.inkSecondary,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 끼니/영양제 리딩 썸네일 타일 (56×56, 소프트 틴트 + 아이콘).
class _LeadingTile extends StatelessWidget {
  final bool isMeal;
  const _LeadingTile({required this.isMeal});

  @override
  Widget build(BuildContext context) {
    // meal 모델에 사진 url 필드가 없어 소프트 틴트 아이콘 타일로 통일한다.
    final Color tileColor = isMeal ? AppColor.successSoft : AppColor.brandSoft;
    final Color iconColor = isMeal ? AppColor.success : AppColor.brandDeep;
    final IconData icon = isMeal
        ? Icons.restaurant_rounded
        : Icons.medication_rounded;
    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        color: tileColor,
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      alignment: Alignment.center,
      child: Icon(icon, size: 28, color: iconColor),
    );
  }
}

/// 카테고리 칩(색+텍스트 병행) 스타일 묶음.
class _CategoryChipStyle {
  const _CategoryChipStyle({
    required this.label,
    required this.fill,
    required this.textColor,
  });
  final String label;
  final Color fill;
  final Color textColor;
}

/// 타임라인 항목 → 카테고리 칩 스타일을 매핑한다.
///
/// 끼니: 아침→brandSoft/brandDeep, 점심→successSoft/success,
/// 저녁→infoSoft/info, 간식→warningSoft/warning.
/// 영양제: brandDeep 필 + 흰 텍스트.
_CategoryChipStyle _categoryChipStyle(RecordTimelineEntry entry) {
  if (entry.kind == RecordTimelineKind.supplement) {
    return _CategoryChipStyle(
      label: '영양제',
      fill: AppColor.brandDeep,
      textColor: AppColor.surface,
    );
  }
  switch (entry.subtitle) {
    case '아침':
      return _CategoryChipStyle(
        label: '아침',
        fill: AppColor.brandSoft,
        textColor: AppColor.brandDeep,
      );
    case '점심':
      return const _CategoryChipStyle(
        label: '점심',
        fill: AppColor.successSoft,
        textColor: AppColor.success,
      );
    case '저녁':
      return const _CategoryChipStyle(
        label: '저녁',
        fill: AppColor.infoSoft,
        textColor: AppColor.info,
      );
    case '간식':
      return const _CategoryChipStyle(
        label: '간식',
        fill: AppColor.warningSoft,
        textColor: AppColor.warning,
      );
    default:
      return _CategoryChipStyle(
        label: entry.subtitle ?? '끼니',
        fill: AppColor.section,
        textColor: AppColor.inkSecondary,
      );
  }
}

/// 카테고리 알약 칩.
class _CategoryChip extends StatelessWidget {
  final _CategoryChipStyle style;
  const _CategoryChip({required this.style});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.sm,
        vertical: AppSpace.xs,
      ),
      decoration: BoxDecoration(
        color: style.fill,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        style.label,
        style: AppText.micro.copyWith(
          color: style.textColor,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _TimelineLoading extends StatelessWidget {
  const _TimelineLoading();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
      child: Center(
        child: Text(
          '불러오는 중이에요',
          style: AppText.body.copyWith(color: AppColor.inkTertiary),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// '저녁 기록 추가' 점선 버튼 → 카메라
// ═══════════════════════════════════════════
class _AddRecordButton extends StatelessWidget {
  final VoidCallback onTap;
  const _AddRecordButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: DottedBorderBox(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpace.lg),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Icon(Icons.add_a_photo_outlined, size: 20, color: AppColor.brand),
              const SizedBox(width: AppSpace.sm),
              Text(
                '기록 추가하기',
                style: AppText.body.copyWith(
                  color: AppColor.brandDeep,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 점선 보더 박스 (CustomPaint 로 4면 점선).
class DottedBorderBox extends StatelessWidget {
  /// 점선 보더 박스를 만든다.
  const DottedBorderBox({required this.child, super.key});

  /// 박스 내부 위젯.
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _DottedBorderPainter(
        color: AppColor.borderStrong,
        radius: AppRadius.md,
      ),
      child: child,
    );
  }
}

class _DottedBorderPainter extends CustomPainter {
  _DottedBorderPainter({required this.color, required this.radius});

  final Color color;
  final double radius;

  @override
  void paint(Canvas canvas, Size size) {
    final Paint paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;
    final RRect rrect = RRect.fromRectAndRadius(
      Offset.zero & size,
      Radius.circular(radius),
    );
    final Path path = Path()..addRRect(rrect);
    const double dashWidth = 6;
    const double dashGap = 4;
    for (final ui in path.computeMetrics()) {
      double distance = 0;
      while (distance < ui.length) {
        final double next = distance + dashWidth;
        canvas.drawPath(
          ui.extractPath(distance, next.clamp(0, ui.length)),
          paint,
        );
        distance = next + dashGap;
      }
    }
  }

  @override
  bool shouldRepaint(_DottedBorderPainter oldDelegate) =>
      oldDelegate.color != color || oldDelegate.radius != radius;
}

// ═══════════════════════════════════════════
// 카드 프레임 / 면책 푸터
// ═══════════════════════════════════════════
class _CardFrame extends StatelessWidget {
  final Widget child;
  const _CardFrame({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: _cardDeco(),
      child: child,
    );
  }
}

class _RecordsDisclaimer extends StatelessWidget {
  const _RecordsDisclaimer();

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

BoxDecoration _cardDeco() => BoxDecoration(
  color: AppColor.surface,
  borderRadius: BorderRadius.circular(AppRadius.lg),
  boxShadow: AppShadow.softCard,
);
