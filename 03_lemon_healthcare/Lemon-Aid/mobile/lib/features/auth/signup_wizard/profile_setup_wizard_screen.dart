import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app_providers.dart';
import '../../../utils/design_tokens_v2.dart' as ds2;
import '../../profile/profile_models.dart';
import '../../profile/profile_repository.dart';

const int _minBirthYear = 1900;
const double _minHeightCm = 30;
const double _maxHeightCm = 260;
const double _minWeightKg = 1;
const double _maxWeightKg = 500;
const int _stepCount = 3;

/// 프로필 보완 위저드 — 가이드 01 2단계(가입 위저드의 백엔드-가능 단계).
///
/// 성별·출생연도(Profile) → 키·몸무게(Body) → 검토(Review)를 거쳐
/// `POST /health/profile-snapshots`로 한 번에 저장한다. 진입 시 최신 스냅샷으로
/// 프리필하고, 403 consent_required는 [ProfileRepository]가 동의 1회 후 재시도한다.
/// auth 도입 전에는 설정의 "프로필 보완" 진입점으로 사용한다.
class ProfileSetupWizardScreen extends ConsumerStatefulWidget {
  /// 위저드 화면을 만든다.
  const ProfileSetupWizardScreen({super.key});

  @override
  ConsumerState<ProfileSetupWizardScreen> createState() =>
      _ProfileSetupWizardScreenState();
}

class _ProfileSetupWizardScreenState
    extends ConsumerState<ProfileSetupWizardScreen> {
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _weightController = TextEditingController();

  int _step = 0;
  ProfileSex? _sex;
  int? _birthYear;
  bool _loading = true;
  bool _saving = false;
  bool _saved = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _heightController.addListener(_onFieldChange);
    _weightController.addListener(_onFieldChange);
    WidgetsBinding.instance.addPostFrameCallback((_) => _prefill());
  }

  @override
  void dispose() {
    _heightController
      ..removeListener(_onFieldChange)
      ..dispose();
    _weightController
      ..removeListener(_onFieldChange)
      ..dispose();
    super.dispose();
  }

  void _onFieldChange() {
    if (mounted) setState(() {});
  }

  Future<void> _prefill() async {
    final ProfileRepository repository = ref.read(profileRepositoryProvider);
    try {
      final BodyProfileSnapshot? latest = await repository.fetchLatest();
      if (!mounted) return;
      setState(() {
        _sex = latest?.sex;
        _birthYear = latest?.birthYear;
        if (latest?.heightCm != null) {
          _heightController.text = _trim(latest!.heightCm!);
        }
        if (latest?.weightKg != null) {
          _weightController.text = _trim(latest!.weightKg!);
        }
        _loading = false;
      });
    } on Object {
      // 프리필 실패는 조용히 빈 폼으로 시작(에러 아님).
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  double? get _height => double.tryParse(_heightController.text.trim());
  double? get _weight => double.tryParse(_weightController.text.trim());

  bool get _hasAnyValue =>
      _sex != null || _birthYear != null || _height != null || _weight != null;

  String? get _heightError {
    final String raw = _heightController.text.trim();
    if (raw.isEmpty) return null;
    final double? value = _height;
    if (value == null || value < _minHeightCm || value > _maxHeightCm) {
      return '키는 30~260cm 사이로 입력해 주세요.';
    }
    return null;
  }

  String? get _weightError {
    final String raw = _weightController.text.trim();
    if (raw.isEmpty) return null;
    final double? value = _weight;
    if (value == null || value < _minWeightKg || value > _maxWeightKg) {
      return '몸무게는 1~500kg 사이로 입력해 주세요.';
    }
    return null;
  }

  bool get _bodyValid => _heightError == null && _weightError == null;

  void _next() {
    if (_step < _stepCount - 1) {
      setState(() => _step += 1);
    }
  }

  void _back() {
    if (_step > 0) {
      setState(() => _step -= 1);
    }
  }

  Future<void> _openBirthYearPicker() async {
    final int nowYear = DateTime.now().year;
    int selected = _birthYear ?? (nowYear - 30);
    final int? picked = await showModalBottomSheet<int>(
      context: context,
      backgroundColor: ds2.AppColor.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(ds2.AppRadius.xl)),
      ),
      builder: (BuildContext sheetContext) {
        return SafeArea(
          child: SizedBox(
            height: 320,
            child: Column(
              children: <Widget>[
                Padding(
                  padding: const EdgeInsets.all(ds2.AppSpace.lg),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: <Widget>[
                      Text('출생 연도', style: ds2.AppText.subtitle),
                      TextButton(
                        onPressed: () => Navigator.of(sheetContext).pop(selected),
                        child: Text(
                          '완료',
                          style: ds2.AppText.body.copyWith(
                            color: ds2.AppColor.brandDeep,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: CupertinoPicker(
                    scrollController: FixedExtentScrollController(
                      initialItem: selected - _minBirthYear,
                    ),
                    itemExtent: 44,
                    onSelectedItemChanged: (int index) =>
                        selected = _minBirthYear + index,
                    children: <Widget>[
                      for (int year = _minBirthYear; year <= nowYear; year++)
                        Center(child: Text('$year년', style: ds2.AppText.bodyLg)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
    if (picked != null && mounted) {
      setState(() => _birthYear = picked);
    }
  }

  Future<void> _save() async {
    if (!_hasAnyValue) {
      setState(() => _error = '한 가지 이상 입력해 주세요.');
      return;
    }
    if (!_bodyValid) {
      setState(() => _step = 1);
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final ProfileRepository repository = ref.read(profileRepositoryProvider);
    try {
      await repository.save(
        BodyProfileSnapshot(
          sex: _sex,
          birthYear: _birthYear,
          heightCm: _height,
          weightKg: _weight,
        ),
      );
      if (!mounted) return;
      setState(() {
        _saving = false;
        _saved = true;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = '저장에 실패했어요. 잠시 후 다시 시도해 주세요.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ds2.AppColor.bg,
      appBar: AppBar(
        backgroundColor: ds2.AppColor.bg,
        elevation: 0,
        title: Text('프로필 설정', style: ds2.AppText.subtitle),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _saved
          ? _SavedView(onClose: () => Navigator.of(context).maybePop())
          : SafeArea(
              child: Column(
                children: <Widget>[
                  _ProgressBar(step: _step, total: _stepCount),
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(
                        ds2.AppSpace.page,
                        ds2.AppSpace.lg,
                        ds2.AppSpace.page,
                        ds2.AppSpace.lg,
                      ),
                      children: <Widget>[_stepBody()],
                    ),
                  ),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: ds2.AppSpace.page,
                      ),
                      child: Text(
                        _error!,
                        style: ds2.AppText.caption.copyWith(
                          color: ds2.AppColor.danger,
                        ),
                      ),
                    ),
                  _Footer(
                    step: _step,
                    total: _stepCount,
                    saving: _saving,
                    onBack: _back,
                    onNext: _next,
                    onSave: _save,
                  ),
                ],
              ),
            ),
    );
  }

  Widget _stepBody() {
    switch (_step) {
      case 0:
        return _ProfileStep(
          sex: _sex,
          birthYear: _birthYear,
          onSex: (ProfileSex value) => setState(() => _sex = value),
          onPickYear: _openBirthYearPicker,
        );
      case 1:
        return _BodyStep(
          heightController: _heightController,
          weightController: _weightController,
          heightError: _heightError,
          weightError: _weightError,
        );
      default:
        return _ReviewStep(
          sex: _sex,
          birthYear: _birthYear,
          height: _height,
          weight: _weight,
        );
    }
  }

  static String _trim(double value) {
    if (value == value.roundToDouble()) return value.toStringAsFixed(0);
    return value.toStringAsFixed(1);
  }
}

class _ProgressBar extends StatelessWidget {
  const _ProgressBar({required this.step, required this.total});

  final int step;
  final int total;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        ds2.AppSpace.page,
        ds2.AppSpace.md,
        ds2.AppSpace.page,
        0,
      ),
      child: Row(
        children: <Widget>[
          for (int i = 0; i < total; i++)
            Expanded(
              child: Container(
                height: 4,
                margin: EdgeInsets.only(right: i == total - 1 ? 0 : ds2.AppSpace.xs),
                decoration: BoxDecoration(
                  color: i <= step ? ds2.AppColor.brand : ds2.AppColor.border,
                  borderRadius: BorderRadius.circular(ds2.AppRadius.full),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _ProfileStep extends StatelessWidget {
  const _ProfileStep({
    required this.sex,
    required this.birthYear,
    required this.onSex,
    required this.onPickYear,
  });

  final ProfileSex? sex;
  final int? birthYear;
  final ValueChanged<ProfileSex> onSex;
  final VoidCallback onPickYear;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text('기본 정보를 알려 주세요', style: ds2.AppText.title),
        const SizedBox(height: ds2.AppSpace.sm),
        Text(
          '맞춤 분석에 사용해요. 입력한 정보는 언제든 바꿀 수 있어요.',
          style: ds2.AppText.body.copyWith(color: ds2.AppColor.inkSecondary),
        ),
        const SizedBox(height: ds2.AppSpace.xl),
        Text('성별', style: ds2.AppText.caption.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: ds2.AppSpace.sm),
        Row(
          children: <Widget>[
            for (final ProfileSex value in ProfileSex.values) ...<Widget>[
              Expanded(
                child: _ChoiceChip(
                  label: value.label,
                  selected: sex == value,
                  onTap: () => onSex(value),
                ),
              ),
              if (value != ProfileSex.values.last)
                const SizedBox(width: ds2.AppSpace.md),
            ],
          ],
        ),
        const SizedBox(height: ds2.AppSpace.xl),
        Text(
          '출생 연도',
          style: ds2.AppText.caption.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: ds2.AppSpace.sm),
        Material(
          color: ds2.AppColor.sunken,
          borderRadius: BorderRadius.circular(ds2.AppRadius.sm),
          child: InkWell(
            borderRadius: BorderRadius.circular(ds2.AppRadius.sm),
            onTap: onPickYear,
            child: Container(
              height: 56,
              padding: const EdgeInsets.symmetric(horizontal: ds2.AppSpace.lg),
              alignment: Alignment.centerLeft,
              child: Row(
                children: <Widget>[
                  Expanded(
                    child: Text(
                      birthYear != null ? '$birthYear년' : '선택해 주세요',
                      style: ds2.AppText.bodyLg.copyWith(
                        color: birthYear != null
                            ? ds2.AppColor.ink
                            : ds2.AppColor.inkTertiary,
                      ),
                    ),
                  ),
                  const Icon(
                    Icons.expand_more_rounded,
                    color: ds2.AppColor.inkTertiary,
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _BodyStep extends StatelessWidget {
  const _BodyStep({
    required this.heightController,
    required this.weightController,
    required this.heightError,
    required this.weightError,
  });

  final TextEditingController heightController;
  final TextEditingController weightController;
  final String? heightError;
  final String? weightError;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text('키와 몸무게를 알려 주세요', style: ds2.AppText.title),
        const SizedBox(height: ds2.AppSpace.sm),
        Text(
          '비워 두어도 괜찮아요. 입력하면 더 정확한 분석을 받을 수 있어요.',
          style: ds2.AppText.body.copyWith(color: ds2.AppColor.inkSecondary),
        ),
        const SizedBox(height: ds2.AppSpace.xl),
        ds2.AppTextField(
          controller: heightController,
          label: '키 (cm)',
          hint: '예: 168',
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          error: heightError,
        ),
        const SizedBox(height: ds2.AppSpace.lg),
        ds2.AppTextField(
          controller: weightController,
          label: '몸무게 (kg)',
          hint: '예: 62',
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          error: weightError,
        ),
      ],
    );
  }
}

class _ReviewStep extends StatelessWidget {
  const _ReviewStep({
    required this.sex,
    required this.birthYear,
    required this.height,
    required this.weight,
  });

  final ProfileSex? sex;
  final int? birthYear;
  final double? height;
  final double? weight;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text('입력한 내용을 확인해 주세요', style: ds2.AppText.title),
        const SizedBox(height: ds2.AppSpace.lg),
        _ReviewRow(label: '성별', value: sex?.label ?? '미입력'),
        _ReviewRow(label: '출생 연도', value: birthYear != null ? '$birthYear년' : '미입력'),
        _ReviewRow(label: '키', value: height != null ? '${_n(height!)}cm' : '미입력'),
        _ReviewRow(label: '몸무게', value: weight != null ? '${_n(weight!)}kg' : '미입력'),
      ],
    );
  }

  static String _n(double value) {
    if (value == value.roundToDouble()) return value.toStringAsFixed(0);
    return value.toStringAsFixed(1);
  }
}

class _ReviewRow extends StatelessWidget {
  const _ReviewRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: ds2.AppSpace.md),
      child: Row(
        children: <Widget>[
          SizedBox(
            width: 96,
            child: Text(
              label,
              style: ds2.AppText.body.copyWith(color: ds2.AppColor.inkSecondary),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: ds2.AppText.bodyLg.copyWith(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChoiceChip extends StatelessWidget {
  const _ChoiceChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? ds2.AppColor.brandSoft : ds2.AppColor.sunken,
      borderRadius: BorderRadius.circular(ds2.AppRadius.sm),
      child: InkWell(
        borderRadius: BorderRadius.circular(ds2.AppRadius.sm),
        onTap: onTap,
        child: Container(
          height: 54,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(ds2.AppRadius.sm),
            border: Border.all(
              color: selected ? ds2.AppColor.brand : ds2.AppColor.border,
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Text(
            label,
            style: ds2.AppText.bodyLg.copyWith(
              color: selected ? ds2.AppColor.brandDeep : ds2.AppColor.ink,
              fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
            ),
          ),
        ),
      ),
    );
  }
}

class _Footer extends StatelessWidget {
  const _Footer({
    required this.step,
    required this.total,
    required this.saving,
    required this.onBack,
    required this.onNext,
    required this.onSave,
  });

  final int step;
  final int total;
  final bool saving;
  final VoidCallback onBack;
  final VoidCallback onNext;
  final Future<void> Function() onSave;

  @override
  Widget build(BuildContext context) {
    final bool isLast = step == total - 1;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        ds2.AppSpace.page,
        ds2.AppSpace.md,
        ds2.AppSpace.page,
        ds2.AppSpace.pageBottom,
      ),
      child: Row(
        children: <Widget>[
          if (step > 0) ...<Widget>[
            Expanded(child: ds2.AppSecondaryButton(label: '이전', onPressed: onBack)),
            const SizedBox(width: ds2.AppSpace.md),
          ],
          Expanded(
            flex: 2,
            child: ds2.AppPrimaryButton(
              label: isLast ? '저장하기' : '다음',
              accent: true,
              loading: saving,
              onPressed: isLast ? onSave : onNext,
            ),
          ),
        ],
      ),
    );
  }
}

class _SavedView extends StatelessWidget {
  const _SavedView({required this.onClose});

  final VoidCallback onClose;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(ds2.AppSpace.page),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            const Icon(
              Icons.check_circle_rounded,
              color: ds2.AppColor.success,
              size: 64,
            ),
            const SizedBox(height: ds2.AppSpace.lg),
            Text('프로필을 저장했어요', style: ds2.AppText.title),
            const SizedBox(height: ds2.AppSpace.sm),
            Text(
              '입력한 정보로 더 정확한 분석을 보여드릴게요.',
              textAlign: TextAlign.center,
              style: ds2.AppText.body.copyWith(color: ds2.AppColor.inkSecondary),
            ),
            const SizedBox(height: ds2.AppSpace.xxl),
            SizedBox(
              width: double.infinity,
              child: ds2.AppPrimaryButton(
                label: '완료',
                accent: true,
                onPressed: () async => onClose(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
