import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/state/confirmed_entry_store.dart';
import '../../../shared/theme/lemon_theme.dart';
import '../../../shared/widgets/medical_disclaimer.dart';
import '../data/activity_repository.dart';
import '../domain/activity_models.dart';

class ActivitySyncScreen extends StatefulWidget {
  const ActivitySyncScreen({super.key});

  @override
  State<ActivitySyncScreen> createState() => _ActivitySyncScreenState();
}

class _ActivitySyncScreenState extends State<ActivitySyncScreen> {
  final ActivityRepository _repository = ActivityRepository();
  final TextEditingController _stepsController =
      TextEditingController(text: '7200');
  final TextEditingController _activeMinutesController =
      TextEditingController(text: '30');
  final TextEditingController _energyController =
      TextEditingController(text: '220');
  final TextEditingController _workoutController =
      TextEditingController(text: 'walk');

  bool userConfirmed = true;
  bool _saved = false;

  @override
  void dispose() {
    _stepsController.dispose();
    _activeMinutesController.dispose();
    _energyController.dispose();
    _workoutController.dispose();
    super.dispose();
  }

  void _saveManualActivity() {
    final ConfirmedActivityEntry entry = _repository.createManualActivity(
      date: DateTime.now(),
      steps: int.tryParse(_stepsController.text.trim()) ?? 0,
      activeMinutes: int.tryParse(_activeMinutesController.text.trim()) ?? 0,
      activityEnergyKcal: int.tryParse(_energyController.text.trim()) ?? 0,
      workoutType: _workoutController.text.trim().isEmpty
          ? 'manual'
          : _workoutController.text.trim(),
      userConfirmed: userConfirmed,
    );
    if (entry.userConfirmed) {
      ConfirmedEntryStore.instance.addActivity(entry);
    }
    setState(() {
      _saved = entry.userConfirmed;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
          children: <Widget>[
            Row(
              children: <Widget>[
                IconButton(
                  onPressed: () => context.go('/'),
                  icon: const Icon(Icons.arrow_back_rounded),
                ),
                Expanded(
                  child: Text(
                    '활동 기록',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            LemonCard(
              color: LemonColors.leafSoft,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('수동 활동 입력', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _stepsController,
                    decoration: const InputDecoration(labelText: '걸음수'),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _activeMinutesController,
                    decoration: const InputDecoration(labelText: '활동 시간(분)'),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _energyController,
                    decoration: const InputDecoration(labelText: '활동 에너지(kcal)'),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _workoutController,
                    decoration: const InputDecoration(labelText: '운동 종류'),
                  ),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    value: userConfirmed,
                    onChanged: (bool? value) {
                      setState(() {
                        userConfirmed = value ?? false;
                      });
                    },
                    title: const Text('내가 확인한 활동 기록입니다'),
                  ),
                  FilledButton.icon(
                    onPressed: _saveManualActivity,
                    icon: const Icon(Icons.check_rounded),
                    label: const Text('활동 기록 저장'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            LemonCard(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const Icon(Icons.sync_disabled_rounded, color: LemonColors.sky),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          'HealthKit / Health Connect',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '권한 흐름이 준비되기 전까지 자동 연동은 꺼져 있습니다.',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                        const SizedBox(height: 10),
                        OutlinedButton.icon(
                          onPressed: null,
                          icon: const Icon(Icons.lock_outline_rounded),
                          label: const Text('자동 연동 준비 중'),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            if (_saved) ...<Widget>[
              const SizedBox(height: 12),
              const LemonCard(
                color: LemonColors.skySoft,
                child: Text('확정된 활동 기록이 Daily Coaching 근거에 추가되었습니다.'),
              ),
            ],
            const SizedBox(height: 20),
            const MedicalDisclaimer(),
          ],
        ),
      ),
    );
  }
}
