// widgets/dashboard/medication_add_sheet.dart — '약 추가' 바텀시트 폼
//
// 가이드 02 ④(a): 이름 입력(필수) + 분류 선택 칩(16종 한국어) + 질환 태그
// 멀티선택(8종). POST 페이로드를 [MedicationCreateRequest] 로 돌려준다.
//
// ⚠️ 의료법·서버 스키마(extra="forbid") 제약:
//   - 용량/복용량/복용 시점 입력 필드 금지 — 전문가 영역.
//   - 사용자 문구는 해요체 + 금칙어(진단/처방/치료/효능) 미사용.
//
// 동선: showMedicationAddSheet(context) → MedicationCreateRequest? (취소면 null).

import 'package:flutter/material.dart';

import '../../features/dashboard/home_models.dart';
import '../../features/supplements/supplement_repository.dart';
import '../../utils/design_tokens_v2.dart';
import '../common/pressable.dart';

/// 약 추가 바텀시트를 띄우고 사용자가 확정한 [MedicationCreateRequest] 를 반환한다.
///
/// 취소하거나 바깥을 탭하면 null 을 반환한다.
Future<MedicationCreateRequest?> showMedicationAddSheet(BuildContext context) {
  return showModalBottomSheet<MedicationCreateRequest>(
    context: context,
    backgroundColor: Colors.transparent,
    barrierColor: const Color(0x80141A2C),
    isScrollControlled: true,
    showDragHandle: false,
    builder: (BuildContext sheetContext) => const _MedicationAddSheet(),
  );
}

class _MedicationAddSheet extends StatefulWidget {
  const _MedicationAddSheet();

  @override
  State<_MedicationAddSheet> createState() => _MedicationAddSheetState();
}

class _MedicationAddSheetState extends State<_MedicationAddSheet> {
  final TextEditingController _nameController = TextEditingController();
  String? _selectedClass;
  final Set<String> _selectedTags = <String>{};

  /// 질환 태그 최대 선택 수 (백엔드 condition_tags max_length=8).
  static const int _maxTags = 8;

  @override
  void initState() {
    super.initState();
    _nameController.addListener(_onChanged);
  }

  @override
  void dispose() {
    _nameController.removeListener(_onChanged);
    _nameController.dispose();
    super.dispose();
  }

  void _onChanged() => setState(() {});

  bool get _canSubmit => _nameController.text.trim().isNotEmpty;

  void _toggleClass(String code) {
    setState(() {
      _selectedClass = _selectedClass == code ? null : code;
    });
  }

  void _toggleTag(String code) {
    setState(() {
      if (_selectedTags.contains(code)) {
        _selectedTags.remove(code);
      } else if (_selectedTags.length < _maxTags) {
        _selectedTags.add(code);
      }
    });
  }

  void _submit() {
    if (!_canSubmit) return;
    Navigator.of(context).pop(
      MedicationCreateRequest(
        displayName: _nameController.text.trim(),
        medicationClass: _selectedClass,
        conditionTags: _selectedTags.toList(growable: false),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final double bottomInset = MediaQuery.of(context).viewInsets.bottom;
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(28),
          topRight: Radius.circular(28),
        ),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: Color(0x40141A2C),
            blurRadius: 40,
            spreadRadius: -10,
            offset: Offset(0, -20),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: EdgeInsets.fromLTRB(20, 12, 20, 20 + bottomInset),
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Center(
                  child: Container(
                    width: 36,
                    height: 4,
                    margin: const EdgeInsets.only(top: 4, bottom: AppSpace.lg),
                    decoration: BoxDecoration(
                      color: AppColor.border,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                Text('약 추가', style: AppText.subtitle),
                const SizedBox(height: 4),
                Text(
                  '복용 중인 약 이름을 적어주세요. 분류와 관련 질환은 선택이에요.',
                  style: AppText.caption.copyWith(color: AppColor.inkSecondary),
                ),
                const SizedBox(height: AppSpace.lg),

                // 이름 입력 (필수)
                AppTextField(
                  controller: _nameController,
                  label: '약 이름',
                  hint: '예: 아모디핀',
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _submit(),
                ),
                const SizedBox(height: AppSpace.lg),

                // 분류 선택 (16종, 단일 선택, 선택 사항)
                Text(
                  '분류 (선택)',
                  style: AppText.caption.copyWith(
                    color: AppColor.inkSecondary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: AppSpace.sm),
                Wrap(
                  spacing: AppSpace.sm,
                  runSpacing: AppSpace.sm,
                  children: <Widget>[
                    for (final MapEntry<String, String> entry
                        in kMedicationClassLabels.entries)
                      _SelectChip(
                        label: entry.value,
                        selected: _selectedClass == entry.key,
                        onTap: () => _toggleClass(entry.key),
                      ),
                  ],
                ),
                const SizedBox(height: AppSpace.lg),

                // 질환 태그 (8종, 멀티 선택)
                Text(
                  '관련 질환 (선택 · 최대 $_maxTags개)',
                  style: AppText.caption.copyWith(
                    color: AppColor.inkSecondary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: AppSpace.sm),
                Wrap(
                  spacing: AppSpace.sm,
                  runSpacing: AppSpace.sm,
                  children: <Widget>[
                    for (final MapEntry<String, String> entry
                        in kConditionTagLabels.entries)
                      _SelectChip(
                        label: entry.value,
                        selected: _selectedTags.contains(entry.key),
                        onTap: () => _toggleTag(entry.key),
                      ),
                  ],
                ),
                const SizedBox(height: AppSpace.lg),

                // 용량·복용 시점 안내 — 입력 대신 전문가 영역 문구.
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 10,
                  ),
                  decoration: BoxDecoration(
                    color: AppColor.brandSoft,
                    borderRadius: BorderRadius.circular(AppRadius.sm),
                  ),
                  child: Text(
                    '복용 시점·용량 안내는 의사·약사와 상담해주세요.',
                    style: AppText.caption.copyWith(color: AppColor.brandDeep),
                  ),
                ),
                const SizedBox(height: AppSpace.lg),

                SizedBox(
                  width: double.infinity,
                  child: AppPrimaryButton(
                    label: '추가하기',
                    enabled: _canSubmit,
                    onPressed: _canSubmit ? _submit : null,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// 선택 칩 — 선택 시 brand 채움, 미선택 시 sunken.
class _SelectChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _SelectChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: selected ? AppColor.brand : AppColor.sunken,
          borderRadius: BorderRadius.circular(AppRadius.full),
          border: Border.all(
            color: selected ? AppColor.brand : AppColor.border,
            width: 1,
          ),
        ),
        child: Text(
          label,
          style: AppText.caption.copyWith(
            color: selected ? Colors.white : AppColor.inkSecondary,
            fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
          ),
        ),
      ),
    );
  }
}
