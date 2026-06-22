// screens/settings/medication_reminder_screen.dart — 복약 알림 (figma 916:76)
//
// 가이드 08 (d) step 24. 시간 행(토글) 목록 + [시간 추가] → 시간 휠 + 요일 칩 7개.
// 저장 시 로컬 스케줄 재등록 + 서버(/notifications/reminders) 동기화.
// 로컬이 1차 소스 — 서버 실패 시 로컬은 유지하고 재시도 안내만 띄운다.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_providers.dart';
import '../../features/reminders/medication_reminder_models.dart';
import '../../features/reminders/medication_reminder_store.dart';
import '../../features/reminders/medication_reminder_sync.dart';
import '../../shared/services/local_notification_service.dart';
import '../../utils/design_tokens_v2.dart';
import '../../widgets/common/time_wheel_sheet.dart';

/// 요일 칩 라벨 (1=월 … 7=일).
const List<String> _kWeekdayLabels = <String>[
  '월',
  '화',
  '수',
  '목',
  '금',
  '토',
  '일',
];

/// 복약 알림 설정 화면.
class MedicationReminderScreen extends ConsumerStatefulWidget {
  /// 화면을 생성한다.
  const MedicationReminderScreen({super.key});

  @override
  ConsumerState<MedicationReminderScreen> createState() =>
      _MedicationReminderScreenState();
}

class _MedicationReminderScreenState
    extends ConsumerState<MedicationReminderScreen> {
  List<MedicationReminder> _reminders = <MedicationReminder>[];
  // 삭제됐지만 아직 서버에서 비활성화하지 못한 알림의 serverId (저장 시 disable).
  final List<String> _removedServerIds = <String>[];
  bool _permissionDenied = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _reminders = ref.read(medicationReminderStoreProvider).load();
  }

  Future<void> _addReminder() async {
    final TimeOfDayResult? time = await showTimeWheelSheet(context);
    if (time == null || !mounted) return;
    setState(() {
      _reminders = <MedicationReminder>[
        ..._reminders,
        MedicationReminder(
          id: 'rem-${DateTime.now().microsecondsSinceEpoch}',
          hour: time.hour,
          minute: time.minute,
          weekdays: <int>{1, 2, 3, 4, 5, 6, 7},
        ),
      ];
    });
  }

  void _toggleEnabled(int index, bool value) {
    setState(() {
      _reminders = List<MedicationReminder>.of(_reminders)
        ..[index] = _reminders[index].copyWith(enabled: value);
    });
  }

  void _toggleWeekday(int index, int weekday) {
    setState(() {
      final MedicationReminder reminder = _reminders[index];
      final Set<int> next = Set<int>.of(reminder.weekdays);
      if (next.contains(weekday)) {
        next.remove(weekday);
      } else {
        next.add(weekday);
      }
      _reminders = List<MedicationReminder>.of(_reminders)
        ..[index] = reminder.copyWith(weekdays: next);
    });
  }

  void _removeReminder(int index) {
    setState(() {
      final MedicationReminder removed = _reminders[index];
      final String? serverId = removed.serverId;
      if (serverId != null) {
        _removedServerIds.add(serverId);
      }
      _reminders = List<MedicationReminder>.of(_reminders)..removeAt(index);
    });
  }

  Future<void> _save() async {
    setState(() => _saving = true);

    final MedicationReminderStore store = ref.read(
      medicationReminderStoreProvider,
    );
    final ReminderScheduler scheduler = ref.read(reminderSchedulerProvider);
    final MedicationReminderSync sync = ref.read(
      medicationReminderSyncProvider,
    );

    // 저장 중 추가/삭제와의 경합을 피하려 작업 스냅샷을 뜬다.
    final List<MedicationReminder> working = List<MedicationReminder>.of(
      _reminders,
    );
    final List<String> removedServerIds = List<String>.of(_removedServerIds);

    // 1) 로컬 영속(내구성). serverId 갱신은 서버 동기화 후 다시 저장한다.
    await store.save(working);

    // 2) 로컬 알림 권한 + 재스케줄 (1차 소스).
    final bool granted = await scheduler.ensurePermissions();
    if (!granted && mounted) {
      setState(() => _permissionDenied = true);
    }
    await scheduler.reschedule(working);

    // 3) 서버 동기화 (동기화 사본 — 실패해도 로컬은 유지).
    bool anyServerFailure = false;

    // 3a) 삭제된 알림: 서버에서 비활성화. 실패분은 다음 저장에 재시도하도록 남긴다.
    // (삭제분은 _removeReminder 에서 _reminders/working 에서 이미 빠지므로 3b 와
    // 중복 disable 되지 않는다.)
    final List<String> stillPendingRemoval = <String>[];
    for (final String serverId in removedServerIds) {
      if (await sync.disable(serverId)) continue;
      anyServerFailure = true;
      stillPendingRemoval.add(serverId);
    }

    // 3b) 현재 알림: 활성·미동기화면 생성(serverId 회수), 비활성·동기화됐으면 비활성화.
    final List<MedicationReminder> synced = <MedicationReminder>[];
    for (final MedicationReminder reminder in working) {
      final String? serverId = reminder.serverId;
      if (reminder.enabled && serverId == null) {
        final ReminderSyncResult result = await sync.push(reminder);
        if (result.synced) {
          synced.add(reminder.copyWith(serverId: result.serverId));
        } else {
          anyServerFailure = true;
          synced.add(reminder);
        }
      } else if (!reminder.enabled && serverId != null) {
        if (await sync.disable(serverId)) {
          synced.add(reminder.copyWith(clearServerId: true));
        } else {
          anyServerFailure = true;
          synced.add(reminder);
        }
      } else {
        synced.add(reminder);
      }
    }

    // 4) serverId 갱신을 "현재 목록"에 병합해 로컬 저장(다음 저장 시 중복 생성 방지).
    //    synced 는 working 스냅샷 기반이라 그대로 저장하면 저장 중 추가/삭제가
    //    누락·부활하므로, 영속본과 메모리 모두 _reminders 기준으로 병합한다.
    final Map<String, MedicationReminder> syncedById =
        <String, MedicationReminder>{
          for (final MedicationReminder r in synced) r.id: r,
        };
    await store.save(<MedicationReminder>[
      for (final MedicationReminder r in _reminders) syncedById[r.id] ?? r,
    ]);

    if (!mounted) return;
    setState(() {
      _reminders = <MedicationReminder>[
        for (final MedicationReminder r in _reminders) syncedById[r.id] ?? r,
      ];
      _removedServerIds
        ..clear()
        ..addAll(stillPendingRemoval);
      _saving = false;
    });
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(
        SnackBar(
          content: Text(
            anyServerFailure
                ? '알림을 설정했어요. 서버 동기화는 잠시 후 다시 시도해주세요'
                : '알림을 설정했어요',
          ),
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColor.section,
      appBar: AppBar(
        backgroundColor: AppColor.section,
        elevation: 0,
        title: const Text(
          '복약 알림',
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontWeight: FontWeight.w800,
            color: AppColor.ink,
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            if (_permissionDenied) const _PermissionBanner(),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.all(AppSpace.page),
                children: <Widget>[
                  for (int i = 0; i < _reminders.length; i += 1)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpace.md),
                      child: _ReminderCard(
                        reminder: _reminders[i],
                        onToggle: (bool v) => _toggleEnabled(i, v),
                        onWeekday: (int w) => _toggleWeekday(i, w),
                        onDelete: () => _removeReminder(i),
                      ),
                    ),
                  _AddTimeButton(onTap: _addReminder),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(AppSpace.page),
              child: SizedBox(
                height: 52,
                child: AppPrimaryButton(
                  label: '저장하기',
                  loading: _saving,
                  onPressed: _saving ? null : _save,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PermissionBanner extends StatelessWidget {
  const _PermissionBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColor.warningSoft,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.page,
        vertical: AppSpace.md,
      ),
      child: Text(
        '알림 권한을 허용해야 시간에 맞춰 알려드릴 수 있어요',
        style: AppText.caption.copyWith(
          color: AppColor.warning,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _ReminderCard extends StatelessWidget {
  const _ReminderCard({
    required this.reminder,
    required this.onToggle,
    required this.onWeekday,
    required this.onDelete,
  });

  final MedicationReminder reminder;
  final ValueChanged<bool> onToggle;
  final ValueChanged<int> onWeekday;
  final VoidCallback onDelete;

  String get _timeLabel {
    final int hour12 = reminder.hour % 12 == 0 ? 12 : reminder.hour % 12;
    final String ampm = reminder.hour < 12 ? '오전' : '오후';
    return '$ampm $hour12:${reminder.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.lg),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        boxShadow: AppShadow.elev1,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Text(
                _timeLabel,
                style: AppText.subtitle.copyWith(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const Spacer(),
              IconButton(
                onPressed: onDelete,
                icon: const Icon(
                  Icons.delete_outline_rounded,
                  color: AppColor.inkTertiary,
                ),
              ),
              Switch(
                value: reminder.enabled,
                activeTrackColor: AppColor.brand,
                onChanged: onToggle,
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: <Widget>[
              for (int w = 1; w <= 7; w += 1)
                _WeekdayChip(
                  label: _kWeekdayLabels[w - 1],
                  selected: reminder.weekdays.contains(w),
                  onTap: () => onWeekday(w),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _WeekdayChip extends StatelessWidget {
  const _WeekdayChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 36,
        height: 36,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? AppColor.brand : AppColor.surface,
          shape: BoxShape.circle,
          border: Border.all(
            color: selected ? AppColor.brand : AppColor.border,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: selected ? Colors.white : AppColor.inkSecondary,
          ),
        ),
      ),
    );
  }
}

class _AddTimeButton extends StatelessWidget {
  const _AddTimeButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 56,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColor.surface,
          borderRadius: BorderRadius.circular(AppRadius.xl),
          border: Border.all(color: AppColor.border),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            Icon(Icons.add_rounded, color: AppColor.brandDeep),
            const SizedBox(width: AppSpace.sm),
            Text(
              '시간 추가',
              style: AppText.body.copyWith(
                fontWeight: FontWeight.w700,
                color: AppColor.brandDeep,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
