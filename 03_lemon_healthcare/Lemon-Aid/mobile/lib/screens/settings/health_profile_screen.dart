// screens/settings/health_profile_screen.dart — 건강 프로필 (figma 767:24)
//
// 가이드 08 (b) step 13~14. 만성질환 칩 멀티선택 + 직접 입력 칩 + 저장하기.
// 진입 시 list() 로 기존 condition 복원, 저장 시 신규→addCondition / 해제→archive.
// 복약 탭은 user_medications 연계(문서 09) 전까지 안내 패널.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_providers.dart';
import '../../core/api/api_error.dart';
import '../../features/medical/medical_models.dart';
import '../../features/medical/medical_records_repository.dart';
import '../../utils/design_tokens_v2.dart';

/// 프리셋 만성질환 칩 (사용자 노출 텍스트는 의료법 금칙어 없는 일반 명칭).
const List<String> _kPresetConditions = <String>[
  '당뇨',
  '고혈압',
  '고지혈증',
  '신장 질환',
  '간 질환',
  '위장 질환',
  '갑상선 질환',
  '관절염',
];

/// 건강 프로필 화면 (만성질환 + 복약 탭).
class HealthProfileScreen extends ConsumerStatefulWidget {
  /// 화면을 생성한다.
  const HealthProfileScreen({super.key});

  @override
  ConsumerState<HealthProfileScreen> createState() =>
      _HealthProfileScreenState();
}

class _HealthProfileScreenState extends ConsumerState<HealthProfileScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  final TextEditingController _customController = TextEditingController();

  bool _loading = true;
  bool _saving = false;
  bool _showCustomField = false;
  String? _error;

  /// 선택된 질환 텍스트 → 기존 레코드 id (신규 선택은 null).
  final Map<String, String?> _selected = <String, String?>{};

  /// 진입 시점의 기존 활성 condition (저장 시 해제 비교용).
  final Map<String, String> _existing = <String, String>{};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _tabController.dispose();
    _customController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final MedicalRecordsRepository repo = ref.read(
      medicalRecordsRepositoryProvider,
    );
    try {
      final List<MedicalRecord> records = await repo.list();
      if (!mounted) return;
      setState(() {
        for (final MedicalRecord record in records) {
          if (!record.isActiveCondition) continue;
          final String? text = record.primaryConditionText;
          if (text == null) continue;
          _existing[text] = record.id;
          _selected[text] = record.id;
        }
        _loading = false;
      });
    } on ApiError catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _loading = false;
      });
    }
  }

  void _toggle(String text) {
    setState(() {
      if (_selected.containsKey(text)) {
        _selected.remove(text);
      } else {
        _selected[text] = _existing[text];
      }
    });
  }

  void _addCustom() {
    final String text = _customController.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _selected[text] = _existing[text];
      _customController.clear();
      _showCustomField = false;
    });
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    final MedicalRecordsRepository repo = ref.read(
      medicalRecordsRepositoryProvider,
    );
    try {
      // 신규 선택(기존 레코드 없음) → addCondition.
      for (final MapEntry<String, String?> entry in _selected.entries) {
        if (entry.value == null && !_existing.containsKey(entry.key)) {
          await repo.addCondition(entry.key);
        }
      }
      // 진입 시 있었으나 지금 해제된 항목 → archive.
      for (final MapEntry<String, String> entry in _existing.entries) {
        if (!_selected.containsKey(entry.key)) {
          await repo.archive(entry.value);
        }
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(const SnackBar(content: Text('저장했어요')));
      Navigator.of(context).maybePop();
    } on ApiError catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = '정보를 다시 불러올게요. (${error.message})';
      });
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColor.section,
      appBar: AppBar(
        backgroundColor: AppColor.section,
        elevation: 0,
        title: const Text(
          '건강 프로필',
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontWeight: FontWeight.w800,
            color: AppColor.ink,
          ),
        ),
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppColor.ink,
          unselectedLabelColor: AppColor.inkTertiary,
          indicatorColor: AppColor.brand,
          tabs: const <Widget>[
            Tab(text: '만성질환'),
            Tab(text: '복약'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: <Widget>[
          _buildConditionTab(),
          _buildMedicationTab(),
        ],
      ),
    );
  }

  Widget _buildConditionTab() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    final Set<String> allChips = <String>{
      ..._kPresetConditions,
      ..._selected.keys,
    };
    return SafeArea(
      child: Column(
        children: <Widget>[
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(AppSpace.page),
              children: <Widget>[
                Wrap(
                  spacing: AppSpace.sm,
                  runSpacing: AppSpace.sm,
                  children: <Widget>[
                    for (final String text in allChips)
                      _ConditionChip(
                        label: text,
                        selected: _selected.containsKey(text),
                        onTap: () => _toggle(text),
                      ),
                    _ConditionChip(
                      label: '직접 입력',
                      selected: false,
                      icon: Icons.add_rounded,
                      onTap: () =>
                          setState(() => _showCustomField = !_showCustomField),
                    ),
                  ],
                ),
                if (_showCustomField) ...<Widget>[
                  const SizedBox(height: AppSpace.lg),
                  AppTextField(
                    controller: _customController,
                    hint: '질환명을 입력해주세요 (최대 180자)',
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _addCustom(),
                  ),
                  const SizedBox(height: AppSpace.sm),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: _addCustom,
                      child: const Text('추가'),
                    ),
                  ),
                ],
                if (_error != null) ...<Widget>[
                  const SizedBox(height: AppSpace.md),
                  Text(
                    _error!,
                    style: AppText.caption.copyWith(color: AppColor.danger),
                  ),
                ],
              ],
            ),
          ),
          const _DisclaimerFooter(),
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
    );
  }

  Widget _buildMedicationTab() {
    return SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.page),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(
                Icons.medication_rounded,
                size: 48,
                color: AppColor.inkTertiary,
              ),
              const SizedBox(height: AppSpace.md),
              Text(
                '복약 정보는 곧 연결돼요',
                style: AppText.subtitle.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: AppSpace.sm),
              Text(
                '약 목록과 교차 점검은 다음 업데이트에서 제공할 예정이에요',
                textAlign: TextAlign.center,
                style: AppText.caption.copyWith(color: AppColor.inkSecondary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ConditionChip extends StatelessWidget {
  const _ConditionChip({
    required this.label,
    required this.selected,
    required this.onTap,
    this.icon,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: selected ? AppColor.brand : AppColor.surface,
          borderRadius: BorderRadius.circular(AppRadius.full),
          border: Border.all(
            color: selected ? AppColor.brand : AppColor.border,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            if (selected)
              const Padding(
                padding: EdgeInsets.only(right: 6),
                child: Icon(Icons.check_rounded, size: 16, color: Colors.white),
              )
            else if (icon != null)
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: Icon(icon, size: 16, color: AppColor.inkSecondary),
              ),
            Text(
              label,
              style: TextStyle(
                fontFamily: 'Pretendard',
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: selected ? Colors.white : AppColor.ink,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 건강 참고용 면책 푸터 (진단·처방 아님).
class _DisclaimerFooter extends StatelessWidget {
  const _DisclaimerFooter();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColor.section,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.page,
        vertical: AppSpace.sm,
      ),
      // 의료법 금칙어(진단/처방/치료/효능) 회피 — 신규 화면 금칙어 가드 통과용.
      child: Text(
        '입력하신 정보는 건강 참고용이며 의료 행위를 대신하지 않아요',
        textAlign: TextAlign.center,
        style: AppText.micro.copyWith(color: AppColor.inkTertiary),
      ),
    );
  }
}
