import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/theme/lemon_theme.dart';
import '../../../shared/widgets/medical_disclaimer.dart';
import '../data/user_medication_repository.dart';
import '../domain/user_medication_models.dart';

class MedicationSettingsScreen extends StatefulWidget {
  const MedicationSettingsScreen({super.key});

  @override
  State<MedicationSettingsScreen> createState() =>
      _MedicationSettingsScreenState();
}

class _MedicationSettingsScreenState extends State<MedicationSettingsScreen> {
  final UserMedicationRepository _repository = UserMedicationRepository();
  final TextEditingController _nameController = TextEditingController();
  String _medicationClass = 'calcium_channel_blocker';
  bool _hypertensionTag = true;
  bool _isLoading = false;
  bool _hasError = false;
  List<UserMedication> _medications = <UserMedication>[];

  @override
  void initState() {
    super.initState();
    _loadMedications();
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _loadMedications() async {
    setState(() {
      _isLoading = true;
      _hasError = false;
    });
    try {
      final List<UserMedication> medications =
          await _repository.listMedications();
      if (!mounted) {
        return;
      }
      setState(() {
        _medications = medications;
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

  Future<void> _saveMedication() async {
    final String name = _nameController.text.trim();
    if (name.isEmpty || _isLoading) {
      return;
    }
    setState(() {
      _isLoading = true;
      _hasError = false;
    });
    try {
      await _repository.grantSensitiveHealthAnalysisConsent();
      await _repository.createMedication(
        UserMedicationDraft(
          displayName: name,
          normalizedName: name.toLowerCase(),
          medicationClass: _medicationClass,
          conditionTags: _hypertensionTag
              ? const <String>['hypertension']
              : const <String>[],
        ),
      );
      _nameController.clear();
      await _loadMedications();
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

  Future<void> _deactivate(UserMedication medication) async {
    setState(() {
      _isLoading = true;
      _hasError = false;
    });
    try {
      await _repository.grantSensitiveHealthAnalysisConsent();
      await _repository.deactivateMedication(medication.id);
      await _loadMedications();
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
                  tooltip: '뒤로',
                ),
                Expanded(
                  child: Text(
                    '복용약 관리',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            LemonCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    '혈압약 이름 저장',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _nameController,
                    decoration: const InputDecoration(
                      labelText: '약 이름',
                      hintText: '예: 암로디핀, 로사르탄',
                      prefixIcon: Icon(Icons.medication_rounded),
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: _medicationClass,
                    decoration: const InputDecoration(
                      labelText: '약물군',
                      prefixIcon: Icon(Icons.category_rounded),
                    ),
                    items: medicationClassLabels.entries
                        .map(
                          (MapEntry<String, String> entry) =>
                              DropdownMenuItem<String>(
                            value: entry.key,
                            child: Text(entry.value),
                          ),
                        )
                        .toList(growable: false),
                    onChanged: _isLoading
                        ? null
                        : (String? value) {
                            if (value == null) {
                              return;
                            }
                            setState(() {
                              _medicationClass = value;
                            });
                          },
                  ),
                  const SizedBox(height: 8),
                  CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _hypertensionTag,
                    onChanged: _isLoading
                        ? null
                        : (bool? value) {
                            setState(() {
                              _hypertensionTag = value ?? false;
                            });
                          },
                    title: const Text('고혈압 맥락으로 사용'),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: _isLoading ? null : _saveMedication,
                      icon: _isLoading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.save_rounded),
                      label: const Text('저장'),
                    ),
                  ),
                ],
              ),
            ),
            if (_hasError) ...<Widget>[
              const SizedBox(height: 12),
              Text(
                '저장된 복용약 정보를 불러오지 못했습니다.',
                style: Theme.of(context)
                    .textTheme
                    .bodyMedium
                    ?.copyWith(color: LemonColors.danger),
              ),
            ],
            const SizedBox(height: 16),
            Text(
              '저장된 복용약',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            ..._medications.map(
              (UserMedication medication) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _MedicationTile(
                  medication: medication,
                  onDeactivate: _isLoading || !medication.isActive
                      ? null
                      : () => _deactivate(medication),
                ),
              ),
            ),
            if (_medications.isEmpty && !_isLoading)
              const Text('아직 저장된 복용약이 없습니다.'),
            const SizedBox(height: 20),
            const MedicalDisclaimer(),
          ],
        ),
      ),
    );
  }
}

class _MedicationTile extends StatelessWidget {
  const _MedicationTile({
    required this.medication,
    required this.onDeactivate,
  });

  final UserMedication medication;
  final VoidCallback? onDeactivate;

  @override
  Widget build(BuildContext context) {
    final String classLabel =
        medicationClassLabels[medication.medicationClass] ?? '분류 미지정';
    return LemonCard(
      child: Row(
        children: <Widget>[
          Icon(
            medication.isActive
                ? Icons.medication_liquid_rounded
                : Icons.medication_outlined,
            color:
                medication.isActive ? LemonColors.leaf : LemonColors.inkMuted,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  medication.displayName,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 2),
                Text(
                  medication.isActive ? classLabel : '$classLabel · 비활성',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: onDeactivate,
            icon: const Icon(Icons.visibility_off_rounded),
            tooltip: '비활성화',
          ),
        ],
      ),
    );
  }
}
