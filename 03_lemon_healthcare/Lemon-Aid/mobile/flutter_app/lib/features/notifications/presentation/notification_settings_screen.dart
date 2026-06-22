import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/theme/lemon_theme.dart';
import '../../../shared/widgets/medical_disclaimer.dart';
import '../data/notification_repository.dart';
import '../domain/notification_models.dart';

class NotificationSettingsScreen extends StatefulWidget {
  const NotificationSettingsScreen({super.key});

  @override
  State<NotificationSettingsScreen> createState() =>
      _NotificationSettingsScreenState();
}

class _NotificationSettingsScreenState
    extends State<NotificationSettingsScreen> {
  final NotificationRepository _repository = NotificationRepository();
  final TextEditingController _timeController =
      TextEditingController(text: '09:00');
  final TextEditingController _messageController =
      TextEditingController(text: '오늘 기록 시간을 확인해 주세요.');

  ReminderCategory _category = ReminderCategory.supplementReminder;
  bool _enabled = true;
  bool _isLoading = false;
  bool _hasError = false;
  List<ReminderPreference> _reminders = <ReminderPreference>[];

  @override
  void initState() {
    super.initState();
    _loadReminders();
  }

  @override
  void dispose() {
    _timeController.dispose();
    _messageController.dispose();
    super.dispose();
  }

  Future<void> _loadReminders() async {
    setState(() {
      _isLoading = true;
      _hasError = false;
    });
    try {
      final List<ReminderPreference> reminders =
          await _repository.listReminders();
      if (!mounted) {
        return;
      }
      setState(() {
        _reminders = reminders;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _hasError = true;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _saveReminder() async {
    final String message = _messageController.text.trim();
    final String timeOfDay = _timeController.text.trim();
    if (message.isEmpty || timeOfDay.isEmpty || _isLoading) {
      return;
    }

    setState(() {
      _isLoading = true;
      _hasError = false;
    });
    try {
      await _repository.grantSensitiveHealthAnalysisConsent();
      await _repository.createReminder(
        ReminderPreferenceDraft(
          category: _category,
          timeOfDay: timeOfDay,
          timezone: 'Asia/Seoul',
          enabled: _enabled,
          message: message,
        ),
      );
      await _loadReminders();
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _hasError = true;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _disableReminder(ReminderPreference reminder) async {
    setState(() {
      _isLoading = true;
      _hasError = false;
    });
    try {
      await _repository.grantSensitiveHealthAnalysisConsent();
      await _repository.disableReminder(reminder.id);
      await _loadReminders();
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _hasError = true;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
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
                    '알림 설정',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            LemonCard(
              child: Column(
                children: <Widget>[
                  DropdownButtonFormField<ReminderCategory>(
                    initialValue: _category,
                    decoration: const InputDecoration(labelText: '종류'),
                    items: ReminderCategory.values
                        .map(
                          (ReminderCategory category) => DropdownMenuItem<
                              ReminderCategory>(
                            value: category,
                            child: Text(category.label),
                          ),
                        )
                        .toList(growable: false),
                    onChanged: (ReminderCategory? value) {
                      if (value != null) {
                        setState(() {
                          _category = value;
                        });
                      }
                    },
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _timeController,
                    decoration: const InputDecoration(labelText: '시간 HH:MM'),
                    keyboardType: TextInputType.datetime,
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _messageController,
                    decoration: const InputDecoration(labelText: '문구'),
                    maxLength: 120,
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('켜기'),
                    value: _enabled,
                    onChanged: (bool value) {
                      setState(() {
                        _enabled = value;
                      });
                    },
                  ),
                  const SizedBox(height: 8),
                  FilledButton.icon(
                    onPressed: _isLoading ? null : _saveReminder,
                    icon: const Icon(Icons.save_rounded),
                    label: Text(_isLoading ? '저장 중' : '저장'),
                  ),
                ],
              ),
            ),
            if (_hasError) ...<Widget>[
              const SizedBox(height: 12),
              const _NotificationErrorPanel(),
            ],
            const SizedBox(height: 16),
            Text('저장된 알림', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            if (_reminders.isEmpty)
              Text(
                '저장된 알림이 없습니다.',
                style: Theme.of(context).textTheme.bodyMedium,
              )
            else
              for (final ReminderPreference reminder in _reminders)
                _ReminderTile(
                  reminder: reminder,
                  onDisable: () => _disableReminder(reminder),
                ),
            const SizedBox(height: 20),
            const MedicalDisclaimer(),
          ],
        ),
      ),
    );
  }
}

class _ReminderTile extends StatelessWidget {
  const _ReminderTile({
    required this.reminder,
    required this.onDisable,
  });

  final ReminderPreference reminder;
  final VoidCallback onDisable;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: LemonCard(
        child: Row(
          children: <Widget>[
            Icon(
              reminder.enabled
                  ? Icons.notifications_active_rounded
                  : Icons.notifications_off_rounded,
              color: reminder.enabled ? LemonColors.leaf : LemonColors.inkMuted,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    '${reminder.category.label} ${reminder.timeOfDay}',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    reminder.message,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
            IconButton(
              onPressed: reminder.enabled ? onDisable : null,
              icon: const Icon(Icons.notifications_off_rounded),
            ),
          ],
        ),
      ),
    );
  }
}

class _NotificationErrorPanel extends StatelessWidget {
  const _NotificationErrorPanel();

  @override
  Widget build(BuildContext context) {
    return const LemonCard(
      color: LemonColors.dangerSoft,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.error_outline_rounded, color: LemonColors.danger),
          SizedBox(width: 10),
          Expanded(
            child: Text('알림 설정을 저장하지 못했습니다. 백엔드 연결과 인증 상태를 확인해 주세요.'),
          ),
        ],
      ),
    );
  }
}
