/// 프로필 입력 폼 — 회원가입 Step2.
///
/// 트랙 D M-2 범위: 핵심 필드 + 만성질환 chip multi-select. 복약 (medications)
/// 의 dynamic list 는 후속 트랙. M-2 는 빈 list 로 전달.
library;

import 'package:flutter/material.dart';

import '../../domain/auth_models.dart' show ProfileInput, Sex;

/// 만성질환 옵션 — backend `consent_service` 매핑 (예시 셋, 후속 확장).
const List<String> _chronicDiseaseOptions = <String>[
  'diabetes',
  'hypertension',
  'dyslipidemia',
  'cardiovascular',
];

const Map<String, String> _chronicDiseaseLabelsKo = <String, String>{
  'diabetes': '당뇨',
  'hypertension': '고혈압',
  'dyslipidemia': '이상지질혈증',
  'cardiovascular': '심혈관질환',
};

class ProfileForm extends StatefulWidget {
  const ProfileForm({super.key, required this.onChanged});

  /// 폼 값 변경 시마다 호출. 검증 통과 시점에만 ProfileInput 생성.
  final void Function(ProfileInput?) onChanged;

  @override
  State<ProfileForm> createState() => _ProfileFormState();
}

class _ProfileFormState extends State<ProfileForm> {
  final TextEditingController _heightCtrl = TextEditingController();
  final TextEditingController _weightCtrl = TextEditingController();
  int _age = 30;
  Sex _sex = Sex.male;
  bool _isPregnant = false;
  bool _isLactating = false;
  bool _isSmoker = false;
  final Set<String> _chronicDiseases = <String>{};

  @override
  void initState() {
    super.initState();
    _heightCtrl.addListener(_emit);
    _weightCtrl.addListener(_emit);
  }

  @override
  void dispose() {
    _heightCtrl.dispose();
    _weightCtrl.dispose();
    super.dispose();
  }

  void _emit() {
    final double? h = double.tryParse(_heightCtrl.text);
    final double? w = double.tryParse(_weightCtrl.text);
    if (h == null || w == null || h < 50 || h > 250 || w < 10 || w > 300) {
      widget.onChanged(null);
      return;
    }
    widget.onChanged(
      ProfileInput(
        age: _age,
        sex: _sex,
        heightCm: h,
        weightKg: w,
        isPregnant: _isPregnant && _sex == Sex.female,
        isLactating: _isLactating && _sex == Sex.female,
        isSmoker: _isSmoker,
        chronicDiseases: _chronicDiseases.toList(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Text('나이: $_age 세', style: Theme.of(context).textTheme.titleSmall),
        Slider(
          value: _age.toDouble(),
          min: 1,
          max: 120,
          divisions: 119,
          label: '$_age',
          onChanged: (double v) {
            setState(() => _age = v.round());
            _emit();
          },
        ),
        const SizedBox(height: 12),
        SegmentedButton<Sex>(
          segments: const <ButtonSegment<Sex>>[
            ButtonSegment<Sex>(value: Sex.male, label: Text('남성')),
            ButtonSegment<Sex>(value: Sex.female, label: Text('여성')),
          ],
          selected: <Sex>{_sex},
          onSelectionChanged: (Set<Sex> v) {
            setState(() => _sex = v.first);
            _emit();
          },
        ),
        const SizedBox(height: 16),
        TextFormField(
          controller: _heightCtrl,
          decoration: const InputDecoration(labelText: '키 (cm)', hintText: '예: 170'),
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
        ),
        const SizedBox(height: 12),
        TextFormField(
          controller: _weightCtrl,
          decoration: const InputDecoration(labelText: '체중 (kg)', hintText: '예: 65'),
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
        ),
        const SizedBox(height: 16),
        if (_sex == Sex.female) ...<Widget>[
          SwitchListTile(
            title: const Text('임신 중'),
            value: _isPregnant,
            onChanged: (bool v) {
              setState(() => _isPregnant = v);
              _emit();
            },
          ),
          SwitchListTile(
            title: const Text('수유 중'),
            value: _isLactating,
            onChanged: (bool v) {
              setState(() => _isLactating = v);
              _emit();
            },
          ),
        ],
        SwitchListTile(
          title: const Text('흡연'),
          value: _isSmoker,
          onChanged: (bool v) {
            setState(() => _isSmoker = v);
            _emit();
          },
        ),
        const SizedBox(height: 16),
        Text('만성질환 (해당 시 선택)', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          children: <Widget>[
            for (final String d in _chronicDiseaseOptions)
              FilterChip(
                label: Text(_chronicDiseaseLabelsKo[d] ?? d),
                selected: _chronicDiseases.contains(d),
                onSelected: (bool v) {
                  setState(() {
                    if (v) {
                      _chronicDiseases.add(d);
                    } else {
                      _chronicDiseases.remove(d);
                    }
                  });
                  _emit();
                },
              ),
          ],
        ),
      ],
    );
  }
}
