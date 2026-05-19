/// 동의 매트릭스 — docs/10 §5.2 별도 동의 화면 원칙.
///
/// - 필수: ``service_terms`` + ``general_profile`` (default off, 사용자 명시 토글)
/// - 조건부: ``chronic_disease`` (profile.chronicDiseases 비어있지 않을 때만 노출),
///           ``medications`` (profile.medications 비어있지 않을 때만 노출)
/// - 선택: ``image_history`` (default off)
///
/// 백엔드 ALLOWED_CONSENT_TYPES 와 동기: service_terms / general_profile /
/// chronic_disease / medications / biometric / image_history / image_training /
/// image_partner. M-2 는 핵심 5개만 노출, 나머지는 후속 트랙.
library;

import 'package:flutter/material.dart';

import '../../domain/auth_models.dart';

/// 동의 항목 1개의 메타데이터.
class ConsentItem {
  const ConsentItem({
    required this.consentType,
    required this.titleKo,
    required this.descKo,
    required this.required,
  });

  final String consentType;
  final String titleKo;
  final String descKo;
  final bool required;
}

const List<ConsentItem> _baseItems = <ConsentItem>[
  ConsentItem(
    consentType: 'service_terms',
    titleKo: '[필수] 서비스 이용 약관 동의',
    descKo: '레몬헬스케어 서비스 이용을 위한 기본 약관에 동의합니다.',
    required: true,
  ),
  ConsentItem(
    consentType: 'general_profile',
    titleKo: '[필수] 일반 프로필 수집 동의',
    descKo: '나이·성별·체질 등 영양 분석에 사용되는 일반 정보 수집에 동의합니다.',
    required: true,
  ),
  ConsentItem(
    consentType: 'image_history',
    titleKo: '[선택] 사진 히스토리 보관 동의',
    descKo: '영양제 사진을 90일간 보관하여 이력 조회를 지원합니다. 동의하지 않아도 영양제 분석은 이용 가능합니다.',
    required: false,
  ),
];

const ConsentItem _chronicDiseaseItem = ConsentItem(
  consentType: 'chronic_disease',
  titleKo: '[필수] 만성질환 정보 수집 동의',
  descKo: '입력하신 만성질환 정보를 영양·복약 안전성 검토에 사용합니다. 민감 건강정보에 해당합니다.',
  required: true,
);

const ConsentItem _medicationsItem = ConsentItem(
  consentType: 'medications',
  titleKo: '[필수] 복약 정보 수집 동의',
  descKo: '입력하신 복약 정보를 영양제와의 상호작용 검토에 사용합니다. 민감 건강정보에 해당합니다.',
  required: true,
);

class ConsentMatrix extends StatefulWidget {
  const ConsentMatrix({
    super.key,
    required this.profile,
    required this.onChanged,
  });

  /// Step2 ProfileForm 의 현재 값 — chronic_diseases / medications 노출 여부 결정.
  final ProfileInput? profile;

  /// 변경 시 호출. ``null`` 이면 필수 항목 누락 (회원가입 버튼 비활성).
  final void Function(List<ConsentAccept>?) onChanged;

  @override
  State<ConsentMatrix> createState() => _ConsentMatrixState();
}

class _ConsentMatrixState extends State<ConsentMatrix> {
  final Map<String, bool> _values = <String, bool>{};

  List<ConsentItem> get _items {
    final ProfileInput? p = widget.profile;
    return <ConsentItem>[
      _baseItems[0],
      _baseItems[1],
      if (p != null && p.chronicDiseases.isNotEmpty) _chronicDiseaseItem,
      if (p != null && p.medications.isNotEmpty) _medicationsItem,
      _baseItems[2],
    ];
  }

  void _emit() {
    final List<ConsentItem> items = _items;
    final bool allRequiredAccepted = items.where((ConsentItem i) => i.required).every(
          (ConsentItem i) => _values[i.consentType] == true,
        );
    if (!allRequiredAccepted) {
      widget.onChanged(null);
      return;
    }
    widget.onChanged(
      items
          .map(
            (ConsentItem i) => ConsentAccept(
              consentType: i.consentType,
              accepted: _values[i.consentType] == true,
            ),
          )
          .toList(),
    );
  }

  @override
  void initState() {
    super.initState();
    // 부모가 초기 상태(`null` — 필수 미수락) 를 즉시 받도록 첫 프레임 후 emit.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _emit();
    });
  }

  @override
  void didUpdateWidget(covariant ConsentMatrix oldWidget) {
    super.didUpdateWidget(oldWidget);
    // profile 이 바뀌어 조건부 항목이 추가/제거되면 재emit.
    _emit();
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Text(
          '각 항목별로 별도 동의해주세요. 묶음 동의는 사용하지 않습니다 (개인정보보호법 §22).',
          style: theme.textTheme.bodySmall,
        ),
        const SizedBox(height: 16),
        for (final ConsentItem item in _items)
          Card(
            child: SwitchListTile(
              title: Text(item.titleKo),
              subtitle: Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(item.descKo),
              ),
              value: _values[item.consentType] == true,
              onChanged: (bool v) {
                setState(() => _values[item.consentType] = v);
                _emit();
              },
            ),
          ),
      ],
    );
  }
}
