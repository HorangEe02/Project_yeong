import 'package:flutter/material.dart';

import '../../core/storage/local_prefs.dart';
import '../../utils/design_tokens_v2.dart' as ds2;

/// 관심 목적 선택 옵션 정의.
class _Option {
  const _Option(this.id, this.label, {this.description});

  /// 로컬 저장에 쓰는 안정적인 옵션 id.
  final String id;

  /// 화면에 표시하는 한국어 라벨.
  final String label;

  /// 선택 의도를 설명하는 짧은 보조 문구.
  final String? description;
}

const String _careModeWellness = 'wellness';
const String _careModeChronic = 'chronic';

// 라벨은 LLM-WIKI/MEDICAL-WIKI의 import scope가 구분한 생활습관·체중관리,
// 만성질환 분류, 복약/영양제 상호작용 클러스터를 UI 선택지 수준으로만
// 축약한다. reviewed claim이 아니므로 질환별 조언 문구로 쓰지 않는다.
const List<_Option> _careModeOptions = <_Option>[
  _Option(
    _careModeWellness,
    '일반 건강 관리',
    description: '체중, 식단, 수면, 영양제 루틴을 중심으로 봐요.',
  ),
  _Option(
    _careModeChronic,
    '만성질환·복약 동반 관리',
    description: '질환·복약 정보를 함께 참고해 더 조심스럽게 봐요.',
  ),
];

const List<_Option> _purposeOptions = <_Option>[
  _Option('diet', '식단·영양 균형'),
  _Option('weight', '체중 관리'),
  _Option('supplement', '영양제 섭취 관리'),
  _Option('activity', '운동·활동량 관리'),
  _Option('sleep_stress', '수면·스트레스 관리'),
  _Option('chronic', '만성질환 관리'),
];

const List<_Option> _generalConcernOptions = <_Option>[
  _Option('fatigue', '피로감'),
  _Option('immune', '면역'),
  _Option('eye', '눈 건강'),
  _Option('liver', '간 건강'),
  _Option('muscle', '운동 능력·근육량'),
  _Option('sleep', '수면·스트레스'),
];

const List<_Option> _chronicConcernOptions = <_Option>[
  _Option('diabetes', '당뇨'),
  _Option('bp', '혈압'),
  _Option('chol', '콜레스테롤'),
  _Option('obesity', '체중·비만'),
  _Option('cardiovascular', '심혈관'),
  _Option('kidney', '신장'),
  _Option('liver_disease', '간 질환'),
  _Option('bone_joint', '뼈·관절'),
  _Option('gi', '위장관'),
  _Option('respiratory', '호흡기'),
  _Option('thyroid', '갑상선'),
];

const Set<String> _chronicConcernIds = <String>{
  'diabetes',
  'bp',
  'chol',
  'obesity',
  'cardiovascular',
  'kidney',
  'liver_disease',
  'bone_joint',
  'gi',
  'respiratory',
  'thyroid',
};

final Map<String, String> _optionLabels = <String, String>{
  for (final _Option option in <_Option>[
    ..._careModeOptions,
    ..._purposeOptions,
    ..._generalConcernOptions,
    ..._chronicConcernOptions,
  ])
    option.id: option.label,
};

/// 설정 탭에 표시할 관심 목적 요약을 만든다.
///
/// Args:
///   prefs: 로컬 프로필 목적/관심사 저장소.
///
/// Returns:
///   저장된 관리 모드와 대표 선택값을 합친 한 줄 요약.
String profileInterestsSummary(LocalPrefs prefs) {
  final List<String> purposes = prefs.profilePurposes();
  final List<String> concerns = prefs.profileConcerns();
  final String mode = _resolveCareMode(
    prefs.profileCareMode(),
    purposes,
    concerns,
  );
  final List<String> labels = _labelsFor(<String>[...concerns, ...purposes]);
  if (labels.isEmpty) {
    return mode == _careModeChronic ? '만성질환·복약 동반 관리' : '관리 목적을 설정해주세요';
  }
  final String prefix = mode == _careModeChronic ? '만성질환 동반' : '일반 관리';
  return '$prefix · ${labels.take(3).join(' · ')}';
}

String _resolveCareMode(
  String? saved,
  List<String> purposes,
  List<String> concerns,
) {
  if (saved == _careModeWellness || saved == _careModeChronic) {
    return saved!;
  }
  if (purposes.contains('chronic') ||
      concerns.any(_chronicConcernIds.contains)) {
    return _careModeChronic;
  }
  return _careModeWellness;
}

List<String> _labelsFor(List<String> ids) {
  final Set<String> seen = <String>{};
  final List<String> labels = <String>[];
  for (final String id in ids) {
    final String? label = _optionLabels[id];
    if (label == null || !seen.add(label)) continue;
    labels.add(label);
  }
  return labels;
}

/// 가입 목적 / 건강 관심사 선택 화면 — 가이드 01 2단계(로컬 전용).
///
/// 백엔드에 목적/관심사 필드가 없어 선택값은 [LocalPrefs]에만 저장한다(날조 금지).
/// 설정의 "관심 목적" 진입점으로 사용하며, 진입 시 기존 선택을 프리필한다.
class ProfileInterestsScreen extends StatefulWidget {
  /// 로컬 저장소를 주입받아 화면을 만든다.
  const ProfileInterestsScreen({required this.prefs, super.key});

  /// 목적/관심사를 영속하는 로컬 저장소.
  final LocalPrefs prefs;

  @override
  State<ProfileInterestsScreen> createState() => _ProfileInterestsScreenState();
}

class _ProfileInterestsScreenState extends State<ProfileInterestsScreen> {
  late String _careMode;
  late final Set<String> _purposes;
  late final Set<String> _concerns;
  bool _saving = false;
  bool _saved = false;

  @override
  void initState() {
    super.initState();
    final List<String> purposes = widget.prefs.profilePurposes();
    final List<String> concerns = widget.prefs.profileConcerns();
    _careMode = _resolveCareMode(
      widget.prefs.profileCareMode(),
      purposes,
      concerns,
    );
    _purposes = purposes.toSet();
    _concerns = concerns.toSet();
  }

  void _setCareMode(String id) {
    setState(() {
      _careMode = id;
      if (id == _careModeWellness) {
        _purposes.remove('chronic');
        _concerns.removeWhere(_chronicConcernIds.contains);
      } else {
        _purposes.add('chronic');
      }
      _saved = false;
    });
  }

  void _toggle(Set<String> target, String id) {
    setState(() {
      if (target.contains(id)) {
        target.remove(id);
      } else {
        target.add(id);
        if (target == _concerns && _chronicConcernIds.contains(id)) {
          _careMode = _careModeChronic;
          _purposes.add('chronic');
        }
      }
      _saved = false;
    });
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    await widget.prefs.setProfileCareMode(_careMode);
    await widget.prefs.setProfilePurposes(_purposes.toList(growable: false));
    await widget.prefs.setProfileConcerns(_concerns.toList(growable: false));
    if (!mounted) return;
    setState(() {
      _saving = false;
      _saved = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ds2.AppColor.bg,
      appBar: AppBar(
        backgroundColor: ds2.AppColor.bg,
        elevation: 0,
        title: Text('관심 목적', style: ds2.AppText.subtitle),
      ),
      body: SafeArea(
        child: Column(
          children: <Widget>[
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(
                  ds2.AppSpace.page,
                  ds2.AppSpace.lg,
                  ds2.AppSpace.page,
                  ds2.AppSpace.lg,
                ),
                children: <Widget>[
                  Text('어떤 기준으로 관리할까요?', style: ds2.AppText.title),
                  const SizedBox(height: ds2.AppSpace.sm),
                  Text(
                    '일반 건강관리와 만성질환·복약 동반 관리를 분리해 결과 화면의 '
                    '주의 문구와 우선순위를 조정해요.',
                    style: ds2.AppText.body.copyWith(
                      color: ds2.AppColor.inkSecondary,
                      height: 1.45,
                    ),
                  ),
                  const SizedBox(height: ds2.AppSpace.lg),
                  _SafetyNotice(
                    text:
                        '이 설정은 건강관리 참고용 개인화 기준이에요. 질환 진단, 치료, '
                        '처방 또는 복약 변경 판단은 의사·약사와 상담해주세요.',
                  ),
                  const SizedBox(height: ds2.AppSpace.xl),
                  const _SectionTitle('관리 모드'),
                  const SizedBox(height: ds2.AppSpace.md),
                  for (final _Option option in _careModeOptions) ...<Widget>[
                    _ModeCard(
                      option: option,
                      selected: _careMode == option.id,
                      onTap: () => _setCareMode(option.id),
                    ),
                    const SizedBox(height: ds2.AppSpace.sm),
                  ],
                  const SizedBox(height: ds2.AppSpace.lg),
                  const _SectionTitle('가입 목적'),
                  const SizedBox(height: ds2.AppSpace.md),
                  _ChipWrap(
                    options: _purposeOptions,
                    selected: _purposes,
                    onToggle: (String id) {
                      _toggle(_purposes, id);
                      if (id == 'chronic' && _purposes.contains(id)) {
                        _setCareMode(_careModeChronic);
                      }
                    },
                  ),
                  const SizedBox(height: ds2.AppSpace.xl),
                  const _SectionTitle('건강 고민'),
                  const SizedBox(height: ds2.AppSpace.md),
                  _ChipWrap(
                    options: _generalConcernOptions,
                    selected: _concerns,
                    onToggle: (String id) => _toggle(_concerns, id),
                  ),
                  if (_careMode == _careModeChronic) ...<Widget>[
                    const SizedBox(height: ds2.AppSpace.xl),
                    const _SectionTitle('만성질환·복약 관련 관리 항목'),
                    const SizedBox(height: ds2.AppSpace.sm),
                    Text(
                      '해당되는 항목만 선택해 주세요. 앱은 이 값을 복약·영양제 '
                      '주의 신호를 더 보수적으로 보여주는 기준으로만 사용해요.',
                      style: ds2.AppText.caption.copyWith(
                        color: ds2.AppColor.inkSecondary,
                        height: 1.45,
                      ),
                    ),
                    const SizedBox(height: ds2.AppSpace.md),
                    _ChipWrap(
                      options: _chronicConcernOptions,
                      selected: _concerns,
                      onToggle: (String id) => _toggle(_concerns, id),
                    ),
                  ],
                ],
              ),
            ),
            if (_saved)
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: ds2.AppSpace.page,
                ),
                child: Row(
                  children: <Widget>[
                    const Icon(
                      Icons.check_circle_rounded,
                      color: ds2.AppColor.success,
                      size: 18,
                    ),
                    const SizedBox(width: ds2.AppSpace.xs),
                    Text(
                      '관심 목적을 저장했어요',
                      style: ds2.AppText.caption.copyWith(
                        color: ds2.AppColor.success,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                ds2.AppSpace.page,
                ds2.AppSpace.md,
                ds2.AppSpace.page,
                ds2.AppSpace.pageBottom,
              ),
              child: ds2.AppPrimaryButton(
                label: '저장하기',
                accent: true,
                loading: _saving,
                onPressed: _save,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SafetyNotice extends StatelessWidget {
  const _SafetyNotice({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(ds2.AppSpace.cardInside),
      decoration: BoxDecoration(
        color: ds2.AppColor.warningSoft,
        borderRadius: BorderRadius.circular(ds2.AppRadius.md),
        border: Border.all(color: ds2.AppColor.warning.withValues(alpha: 0.28)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Icon(
            Icons.info_outline_rounded,
            color: ds2.AppColor.warning,
            size: 18,
          ),
          const SizedBox(width: ds2.AppSpace.sm),
          Expanded(
            child: Text(
              text,
              style: ds2.AppText.caption.copyWith(
                color: ds2.AppColor.ink,
                height: 1.45,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    return Text(
      label,
      style: ds2.AppText.bodyLg.copyWith(fontWeight: FontWeight.w700),
    );
  }
}

class _ModeCard extends StatelessWidget {
  const _ModeCard({
    required this.option,
    required this.selected,
    required this.onTap,
  });

  final _Option option;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? ds2.AppColor.brandSoft : ds2.AppColor.surface,
      borderRadius: BorderRadius.circular(ds2.AppRadius.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(ds2.AppRadius.md),
        onTap: onTap,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(ds2.AppSpace.cardInside),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(ds2.AppRadius.md),
            border: Border.all(
              color: selected ? ds2.AppColor.brand : ds2.AppColor.border,
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Row(
            children: <Widget>[
              Icon(
                selected
                    ? Icons.radio_button_checked_rounded
                    : Icons.radio_button_off_rounded,
                color: selected ? ds2.AppColor.brand : ds2.AppColor.inkTertiary,
              ),
              const SizedBox(width: ds2.AppSpace.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      option.label,
                      style: ds2.AppText.bodyLg.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    if (option.description != null) ...<Widget>[
                      const SizedBox(height: 4),
                      Text(
                        option.description!,
                        style: ds2.AppText.caption.copyWith(
                          color: ds2.AppColor.inkSecondary,
                          height: 1.35,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChipWrap extends StatelessWidget {
  const _ChipWrap({
    required this.options,
    required this.selected,
    required this.onToggle,
  });

  final List<_Option> options;
  final Set<String> selected;
  final ValueChanged<String> onToggle;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: ds2.AppSpace.sm,
      runSpacing: ds2.AppSpace.sm,
      children: <Widget>[
        for (final _Option option in options)
          _SelectChip(
            label: option.label,
            selected: selected.contains(option.id),
            onTap: () => onToggle(option.id),
          ),
      ],
    );
  }
}

class _SelectChip extends StatelessWidget {
  const _SelectChip({
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
      borderRadius: BorderRadius.circular(ds2.AppRadius.full),
      child: InkWell(
        borderRadius: BorderRadius.circular(ds2.AppRadius.full),
        onTap: onTap,
        child: Container(
          constraints: const BoxConstraints(minHeight: 48),
          padding: const EdgeInsets.symmetric(
            horizontal: ds2.AppSpace.lg,
            vertical: ds2.AppSpace.sm,
          ),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(ds2.AppRadius.full),
            border: Border.all(
              color: selected ? ds2.AppColor.brand : ds2.AppColor.border,
              width: selected ? 1.5 : 1,
            ),
          ),
          child: Text(
            label,
            style: ds2.AppText.body.copyWith(
              color: selected ? ds2.AppColor.brandDeep : ds2.AppColor.ink,
              fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
            ),
          ),
        ),
      ),
    );
  }
}
