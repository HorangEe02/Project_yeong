import 'package:flutter/material.dart';

import '../../app_controller.dart';
import '../../utils/design_tokens_v2.dart' as ds2;
import 'consent_models.dart';

/// 동의 항목 정의 — 백엔드 `consent_type` ↔ 한국어 문구.
class _ConsentItem {
  const _ConsentItem({
    required this.consentType,
    required this.title,
    required this.description,
    required this.required,
  });

  /// 백엔드 동의 버킷 식별자.
  final String consentType;

  /// 화면에 표시하는 동의 제목.
  final String title;

  /// 동의 항목 설명(해요체).
  final String description;

  /// 서비스 이용에 필요한 필수 항목인지 여부.
  final bool required;
}

/// 필수 동의 항목 — 모두 체크해야 시작할 수 있다.
const List<_ConsentItem> _requiredItems = <_ConsentItem>[
  _ConsentItem(
    consentType: 'sensitive_health_analysis',
    title: '건강 정보 분석',
    description: '입력하신 프로필과 건강 기록을 바탕으로 맞춤 정보를 보여드려요.',
    required: true,
  ),
  _ConsentItem(
    consentType: 'ocr_image_processing',
    title: '영양제 라벨 인식',
    description: '촬영한 영양제 라벨에서 성분 정보를 읽어와요.',
    required: true,
  ),
  _ConsentItem(
    consentType: 'food_image_processing',
    title: '음식 사진 분석',
    description: '촬영한 음식 사진에서 식단 정보를 인식해요.',
    required: true,
  ),
];

/// 선택 동의 항목 — 체크하지 않아도 시작할 수 있다.
const List<_ConsentItem> _optionalItems = <_ConsentItem>[
  _ConsentItem(
    consentType: 'external_ocr_processing',
    title: '외부 인식 서비스 사용',
    description: '더 정확한 인식을 위해 외부 OCR 서비스로 이미지를 보낼 수 있어요.',
    required: false,
  ),
  _ConsentItem(
    consentType: 'data_retention',
    title: '기록 보관',
    description: '분석 기록을 저장해 변화 추이를 보여드려요.',
    required: false,
  ),
  _ConsentItem(
    consentType: 'image_learning_dataset',
    title: '비식별 학습 활용',
    description: '개인을 알 수 없게 처리한 이미지를 서비스 개선에 활용해요.',
    required: false,
  ),
];

List<_ConsentItem> get _allItems => <_ConsentItem>[
  ..._requiredItems,
  ..._optionalItems,
];

/// 동의 게이트 시트 — 시안 206:17.
///
/// 전체 동의 마스터 체크 + 필수/선택 동의 행 + 하단 고정 CTA로 구성된다. 카메라
/// 진입 시 최소 동의가 미충족이면 표시되며, 필수 항목을 모두 체크해야
/// "동의하고 시작하기" CTA가 활성화된다. 동의 부여는 항목별
/// `POST /me/privacy/consents/{consent_type}`로 처리한다.
class ConsentGateSheet extends StatefulWidget {
  /// 동의 게이트 시트를 만든다.
  const ConsentGateSheet({required this.controller, super.key});

  /// 앱 플로우 컨트롤러.
  final AppController controller;

  @override
  State<ConsentGateSheet> createState() => _ConsentGateSheetState();
}

class _ConsentGateSheetState extends State<ConsentGateSheet> {
  final Set<String> _checked = <String>{};

  @override
  void initState() {
    super.initState();
    final ConsentState? state = widget.controller.consentState;
    for (final _ConsentItem item in _allItems) {
      if (state?.isGranted(item.consentType) ?? false) {
        _checked.add(item.consentType);
      }
    }
  }

  bool get _allRequiredChecked => _requiredItems.every(
    (_ConsentItem item) => _checked.contains(item.consentType),
  );

  bool get _allChecked =>
      _allItems.every((_ConsentItem item) => _checked.contains(item.consentType));

  void _toggle(String consentType, {required bool value}) {
    setState(() {
      if (value) {
        _checked.add(consentType);
      } else {
        _checked.remove(consentType);
      }
    });
  }

  void _toggleAll({required bool value}) {
    setState(() {
      _checked.clear();
      if (value) {
        for (final _ConsentItem item in _allItems) {
          _checked.add(item.consentType);
        }
      }
    });
  }

  Future<void> _submit() async {
    await widget.controller.grantConsents(_checked.toList(growable: false));
  }

  void _showPolicy(_ConsentItem item) {
    showDialog<void>(
      context: context,
      builder: (BuildContext dialogContext) => AlertDialog(
        title: Text(item.title, style: ds2.AppText.subtitle),
        content: Text(item.description, style: ds2.AppText.body),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('닫기'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bool busy = widget.controller.busy;
    return SafeArea(
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
                Center(
                  child: Container(
                    width: 40,
                    height: 4,
                    margin: const EdgeInsets.only(bottom: ds2.AppSpace.lg),
                    decoration: BoxDecoration(
                      color: ds2.AppColor.borderStrong,
                      borderRadius: BorderRadius.circular(ds2.AppRadius.full),
                    ),
                  ),
                ),
                Text('시작하기 전에 동의가 필요해요', style: ds2.AppText.title),
                const SizedBox(height: ds2.AppSpace.sm),
                Text(
                  '안전한 분석을 위해 아래 항목에 동의해 주세요. 필수 항목은 서비스 이용에 필요해요.',
                  style: ds2.AppText.body.copyWith(
                    color: ds2.AppColor.inkSecondary,
                  ),
                ),
                const SizedBox(height: ds2.AppSpace.lg),
                _MasterRow(
                  checked: _allChecked,
                  onChanged: busy ? null : (bool v) => _toggleAll(value: v),
                ),
                const SizedBox(height: ds2.AppSpace.md),
                const _SectionLabel('필수'),
                for (final _ConsentItem item in _requiredItems)
                  _ConsentRow(
                    item: item,
                    checked: _checked.contains(item.consentType),
                    onChanged: busy
                        ? null
                        : (bool v) => _toggle(item.consentType, value: v),
                    onView: () => _showPolicy(item),
                  ),
                const SizedBox(height: ds2.AppSpace.md),
                const _SectionLabel('선택'),
                for (final _ConsentItem item in _optionalItems)
                  _ConsentRow(
                    item: item,
                    checked: _checked.contains(item.consentType),
                    onChanged: busy
                        ? null
                        : (bool v) => _toggle(item.consentType, value: v),
                    onView: () => _showPolicy(item),
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
              label: '동의하고 시작하기',
              accent: true,
              loading: busy,
              enabled: _allRequiredChecked,
              onPressed: _submit,
            ),
          ),
        ],
      ),
    );
  }
}

class _MasterRow extends StatelessWidget {
  const _MasterRow({required this.checked, required this.onChanged});

  final bool checked;
  final ValueChanged<bool>? onChanged;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: checked ? ds2.AppColor.brandSoft : ds2.AppColor.section,
      borderRadius: BorderRadius.circular(ds2.AppRadius.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(ds2.AppRadius.md),
        onTap: onChanged == null ? null : () => onChanged!(!checked),
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: ds2.AppSpace.lg,
            vertical: ds2.AppSpace.md,
          ),
          child: Row(
            children: <Widget>[
              Checkbox(
                value: checked,
                activeColor: ds2.AppColor.brand,
                onChanged: onChanged == null
                    ? null
                    : (bool? v) => onChanged!(v ?? false),
              ),
              const SizedBox(width: ds2.AppSpace.sm),
              Text(
                '전체 동의',
                style: ds2.AppText.bodyLg.copyWith(fontWeight: FontWeight.w700),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.label);

  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(
        left: ds2.AppSpace.xs,
        top: ds2.AppSpace.sm,
        bottom: ds2.AppSpace.sm,
      ),
      child: Text(
        label,
        style: ds2.AppText.caption.copyWith(
          color: ds2.AppColor.inkTertiary,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _ConsentRow extends StatelessWidget {
  const _ConsentRow({
    required this.item,
    required this.checked,
    required this.onChanged,
    required this.onView,
  });

  final _ConsentItem item;
  final bool checked;
  final ValueChanged<bool>? onChanged;
  final VoidCallback onView;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: ds2.AppSpace.sm),
      child: ds2.AppCard(
        elevated: false,
        padding: const EdgeInsets.symmetric(
          horizontal: ds2.AppSpace.md,
          vertical: ds2.AppSpace.xs,
        ),
        onTap: onChanged == null ? null : () => onChanged!(!checked),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: <Widget>[
            Checkbox(
              value: checked,
              activeColor: ds2.AppColor.brand,
              onChanged: onChanged == null
                  ? null
                  : (bool? v) => onChanged!(v ?? false),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(item.title, style: ds2.AppText.body),
                  const SizedBox(height: 2),
                  Text(
                    item.description,
                    style: ds2.AppText.caption.copyWith(
                      color: ds2.AppColor.inkTertiary,
                    ),
                  ),
                ],
              ),
            ),
            TextButton(
              onPressed: onView,
              child: Text(
                '보기',
                style: ds2.AppText.caption.copyWith(
                  color: ds2.AppColor.inkSecondary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
