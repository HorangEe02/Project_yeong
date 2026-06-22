import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/theme/lemon_theme.dart';

class SupplementCaptureScreen extends StatelessWidget {
  const SupplementCaptureScreen({super.key});

  static const List<_RoutineSlot> _slots = <_RoutineSlot>[
    _RoutineSlot(
      label: '아침 루틴',
      timeLabel: '08:00 기준 · 2/2 완료',
      icon: Icons.wb_sunny_rounded,
      items: <_RoutineItem>[
        _RoutineItem('당뇨약 A', '식후 30분 · 1정', _RoutineKind.medication, true),
        _RoutineItem('오메가-3', '아침 식사 직후', _RoutineKind.supplement, true),
      ],
    ),
    _RoutineSlot(
      label: '점심 루틴',
      timeLabel: '12:30 기준 · 1/2 완료',
      icon: Icons.light_mode_rounded,
      items: <_RoutineItem>[
        _RoutineItem('비타민 D', '점심 식사 후 · 1캡슐', _RoutineKind.supplement, true),
        _RoutineItem('혈압약 B', '정오 알림 · 1정', _RoutineKind.medication, false),
      ],
    ),
    _RoutineSlot(
      label: '저녁 루틴',
      timeLabel: '19:00 기준 · 0/2 완료',
      icon: Icons.nightlight_round,
      items: <_RoutineItem>[
        _RoutineItem('마그네슘', '저녁 식후 · 수면 루틴', _RoutineKind.supplement, false),
        _RoutineItem('업로드한 멀티비타민', '저녁 식사 직후', _RoutineKind.supplement, false),
      ],
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: LemonColors.canvas,
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 20, 0, 32),
          children: <Widget>[
            Text(
              '오늘의 Agent',
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: LemonColors.warning,
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              '복용 루틴과 식단 기준을 함께 봅니다',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 6),
            Text('3/6개 항목 확인됨', style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 14),
            const _MealTabs(),
            const SizedBox(height: 16),
            for (final _RoutineSlot slot in _slots) ...<Widget>[
              _RoutineSection(slot: slot),
              const SizedBox(height: 14),
            ],
            FilledButton.icon(
              onPressed: () => context.go(
                '/entry-result'
                '?type=supplement'
                '&title=${Uri.encodeComponent('식단 + 영양제 통합 분석')}'
                '&subtitle=${Uri.encodeComponent('식단의 당과 탄수화물 조절을 먼저 잡고, 영양제는 식사 직후 복용 흐름으로 연결하면 오늘 루틴이 안정적입니다.')}'
                '&detail1=${Uri.encodeComponent('식단 주의: 탄수화물 양 조절')}'
                '&detail2=${Uri.encodeComponent('복용 연결: 식후 루틴 유지')}',
              ),
              icon: const Icon(Icons.insights_rounded),
              label: const Text('분석 보기'),
            ),
          ],
        ),
      ),
    );
  }
}

class _MealTabs extends StatelessWidget {
  const _MealTabs();

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: LemonColors.paper,
        borderRadius: BorderRadius.circular(24),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x0F000000),
            blurRadius: 14,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: const Padding(
        padding: EdgeInsets.all(4),
        child: Row(
          children: <Widget>[
            Expanded(
              child: _MealTab(
                label: '아침',
                icon: Icons.wb_sunny_rounded,
                active: true,
              ),
            ),
            Expanded(
              child: _MealTab(label: '점심', icon: Icons.light_mode_rounded),
            ),
            Expanded(
              child: _MealTab(label: '저녁', icon: Icons.nightlight_round),
            ),
          ],
        ),
      ),
    );
  }
}

class _MealTab extends StatelessWidget {
  const _MealTab({
    required this.label,
    required this.icon,
    this.active = false,
  });

  final String label;
  final IconData icon;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: active ? Colors.white : Colors.transparent,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Column(
          children: <Widget>[
            Icon(
              icon,
              color: active ? LemonColors.warning : LemonColors.inkMuted,
              size: 20,
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: active ? LemonColors.ink : LemonColors.inkMuted,
                    fontWeight: FontWeight.w900,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RoutineSection extends StatelessWidget {
  const _RoutineSection({required this.slot});

  final _RoutineSlot slot;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: LemonColors.paper,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x10000000),
            blurRadius: 16,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: <Widget>[
            Row(
              children: <Widget>[
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: LemonColors.paper,
                    shape: BoxShape.circle,
                    border: Border.all(color: LemonColors.line),
                  ),
                  child: SizedBox(
                    width: 44,
                    height: 44,
                    child: Icon(slot.icon, color: LemonColors.warning),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        slot.label,
                        style:
                            Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontSize: 20,
                                ),
                      ),
                      Text(
                        slot.timeLabel,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            for (final _RoutineItem item in slot.items) ...<Widget>[
              _RoutineRow(item: item),
              if (item != slot.items.last) const SizedBox(height: 8),
            ],
          ],
        ),
      ),
    );
  }
}

class _RoutineRow extends StatelessWidget {
  const _RoutineRow({required this.item});

  final _RoutineItem item;

  @override
  Widget build(BuildContext context) {
    final bool isMedication = item.kind == _RoutineKind.medication;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: LemonColors.paper,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: LemonColors.line),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        child: Row(
          children: <Widget>[
            DecoratedBox(
              decoration: BoxDecoration(
                color: item.done ? LemonColors.lemon : LemonColors.paper,
                shape: BoxShape.circle,
                border: Border.all(
                  color: item.done ? LemonColors.lemon : LemonColors.line,
                  width: 2,
                ),
              ),
              child: SizedBox(
                width: 32,
                height: 32,
                child: item.done
                    ? const Icon(Icons.check_rounded, size: 19)
                    : const SizedBox.shrink(),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    item.name,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontSize: 17,
                        ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    item.note,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
            LemonPill(
              label: isMedication ? '복용약' : '영양제',
              color: isMedication ? LemonColors.sky : LemonColors.leaf,
              backgroundColor:
                  isMedication ? LemonColors.skySoft : LemonColors.leafSoft,
            ),
          ],
        ),
      ),
    );
  }
}

class _RoutineSlot {
  const _RoutineSlot({
    required this.label,
    required this.timeLabel,
    required this.icon,
    required this.items,
  });

  final String label;
  final String timeLabel;
  final IconData icon;
  final List<_RoutineItem> items;
}

class _RoutineItem {
  const _RoutineItem(this.name, this.note, this.kind, this.done);

  final String name;
  final String note;
  final _RoutineKind kind;
  final bool done;
}

enum _RoutineKind {
  medication,
  supplement,
}
