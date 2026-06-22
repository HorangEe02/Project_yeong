// screens/settings/profile_edit_screen.dart — 프로필 편집 (figma 957:24)
//
// 가이드 08 (a) step 9. 이름(로컬), 생년, 성별 세그먼트, 키/몸무게 숫자 입력.
// 저장 시 POST /health/profile-snapshots. 이름은 백엔드 공백이라 로컬 저장만.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_providers.dart';
import '../../core/api/api_error.dart';
import '../../core/storage/local_prefs.dart';
import '../../features/profile/profile_models.dart';
import '../../features/profile/profile_repository.dart';
import '../../utils/design_tokens_v2.dart';

/// 신체 정보 편집 화면.
class ProfileEditScreen extends ConsumerStatefulWidget {
  /// 화면을 생성한다.
  const ProfileEditScreen({super.key});

  @override
  ConsumerState<ProfileEditScreen> createState() => _ProfileEditScreenState();
}

class _ProfileEditScreenState extends ConsumerState<ProfileEditScreen> {
  final TextEditingController _nameController = TextEditingController();
  // 이메일은 백엔드 필드가 없어 읽기 전용 안내용 — 저장 경로에 포함하지 않는다.
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _birthYearController = TextEditingController();
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _weightController = TextEditingController();

  ProfileSex? _sex;
  bool _loading = true;
  bool _saving = false;
  bool _notReady = false;
  String? _formError;

  /// 이미지 업로드 백엔드가 없어 아바타 카메라 배지는 장식용 — 탭 시
  /// "준비 중" 안내만(가짜 업로드 배선 금지).
  void _showAvatarComingSoon() {
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(const SnackBar(content: Text('아직 준비 중이에요')));
  }

  /// 출생 연도 휠 시트 — 기존 검증 범위(1900~2100)를 채운다.
  Future<void> _pickBirthYear() async {
    FocusScope.of(context).unfocus();
    final int nowYear = DateTime.now().year;
    final int initial = int.tryParse(_birthYearController.text.trim()) ?? 1990;
    // 1900~2100 범위(검증과 동일). 현재 연도까지만 노출해도 검증은 유지된다.
    final List<int> years = <int>[for (int y = 1900; y <= nowYear; y += 1) y];
    final int startIndex = years.indexOf(initial).clamp(0, years.length - 1);
    final int? picked = await _showWheelSheet<int>(
      title: '출생 연도',
      items: years,
      labelOf: (int y) => '$y년',
      initialIndex: startIndex,
    );
    if (picked != null) {
      setState(() => _birthYearController.text = picked.toString());
    }
  }

  /// 성별 선택 시트.
  Future<void> _pickSex() async {
    FocusScope.of(context).unfocus();
    final List<ProfileSex> options = ProfileSex.values;
    final int startIndex = _sex == null ? 0 : options.indexOf(_sex!);
    final ProfileSex? picked = await _showWheelSheet<ProfileSex>(
      title: '성별',
      items: options,
      labelOf: (ProfileSex s) => s.label,
      initialIndex: startIndex.clamp(0, options.length - 1),
    );
    if (picked != null) {
      setState(() => _sex = picked);
    }
  }

  /// 공용 휠 바텀시트 — [items] 중 하나를 고른다(취소 시 null).
  Future<T?> _showWheelSheet<T>({
    required String title,
    required List<T> items,
    required String Function(T) labelOf,
    required int initialIndex,
  }) {
    int selected = initialIndex;
    final FixedExtentScrollController scrollController =
        FixedExtentScrollController(initialItem: initialIndex);
    return showModalBottomSheet<T>(
      context: context,
      backgroundColor: AppColor.surface,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (BuildContext sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpace.page,
              AppSpace.sm,
              AppSpace.page,
              AppSpace.lg,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Text(
                  title,
                  style: AppText.subtitle.copyWith(fontWeight: FontWeight.w800),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AppSpace.md),
                SizedBox(
                  height: 180,
                  child: ListWheelScrollView.useDelegate(
                    controller: scrollController,
                    itemExtent: 44,
                    physics: const FixedExtentScrollPhysics(),
                    onSelectedItemChanged: (int index) => selected = index,
                    childDelegate: ListWheelChildBuilderDelegate(
                      childCount: items.length,
                      builder: (BuildContext context, int index) {
                        return Center(
                          child: Text(
                            labelOf(items[index]),
                            style: AppText.bodyLg.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ),
                const SizedBox(height: AppSpace.md),
                SizedBox(
                  height: 52,
                  child: AppPrimaryButton(
                    label: '확인',
                    onPressed: () =>
                        Navigator.of(sheetContext).pop(items[selected]),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    ).whenComplete(scrollController.dispose);
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _birthYearController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    // localPrefs 가 아직 로딩 중일 수 있으므로 future 를 직접 await 한다.
    final LocalPrefs? prefs = await ref.read(localPrefsProvider.future);
    _nameController.text = prefs?.profileDisplayName() ?? '';
    final ProfileRepository repo = ref.read(profileRepositoryProvider);
    try {
      final BodyProfileSnapshot? snapshot = await repo.fetchLatest();
      if (!mounted) return;
      setState(() {
        _notReady = snapshot == null;
        if (snapshot != null) {
          _sex = snapshot.sex;
          if (snapshot.birthYear != null) {
            _birthYearController.text = snapshot.birthYear.toString();
          }
          if (snapshot.heightCm != null) {
            _heightController.text = _trim(snapshot.heightCm!);
          }
          if (snapshot.weightKg != null) {
            _weightController.text = _trim(snapshot.weightKg!);
          }
        }
        _loading = false;
      });
    } on ApiError catch (error) {
      if (!mounted) return;
      setState(() {
        _formError = error.message;
        _loading = false;
      });
    }
  }

  static String _trim(double value) {
    if (value == value.roundToDouble()) return value.toStringAsFixed(0);
    return value.toStringAsFixed(1);
  }

  String? _validate() {
    final String birthRaw = _birthYearController.text.trim();
    if (birthRaw.isNotEmpty) {
      final int? year = int.tryParse(birthRaw);
      if (year == null || year < 1900 || year > 2100) {
        return '출생 연도는 1900~2100 사이로 입력해주세요.';
      }
    }
    final String heightRaw = _heightController.text.trim();
    if (heightRaw.isNotEmpty) {
      final double? height = double.tryParse(heightRaw);
      if (height == null || height < 30 || height > 260) {
        return '키는 30~260cm 사이로 입력해주세요.';
      }
    }
    final String weightRaw = _weightController.text.trim();
    if (weightRaw.isNotEmpty) {
      final double? weight = double.tryParse(weightRaw);
      if (weight == null || weight < 1 || weight > 500) {
        return '몸무게는 1~500kg 사이로 입력해주세요.';
      }
    }
    return null;
  }

  Future<void> _save() async {
    final String? error = _validate();
    if (error != null) {
      setState(() => _formError = error);
      return;
    }
    setState(() {
      _saving = true;
      _formError = null;
    });

    // 이름은 백엔드 공백 — 로컬에만 저장.
    final LocalPrefs? prefs = await ref.read(localPrefsProvider.future);
    await prefs?.setProfileDisplayName(_nameController.text);

    final BodyProfileSnapshot snapshot = BodyProfileSnapshot(
      sex: _sex,
      birthYear: int.tryParse(_birthYearController.text.trim()),
      heightCm: double.tryParse(_heightController.text.trim()),
      weightKg: double.tryParse(_weightController.text.trim()),
    );

    if (!snapshot.hasAnyValue) {
      // 신체 값이 하나도 없으면 서버 저장은 건너뛰고 이름만 반영.
      if (!mounted) return;
      _finishSaved();
      return;
    }

    try {
      await ref.read(profileRepositoryProvider).save(snapshot);
      if (!mounted) return;
      _finishSaved();
    } on ApiError catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _formError = error.message;
      });
    }
  }

  void _finishSaved() {
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(const SnackBar(content: Text('저장했어요')));
    Navigator.of(context).maybePop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColor.section,
      appBar: AppBar(
        backgroundColor: AppColor.section,
        elevation: 0,
        title: const Text(
          '프로필 편집',
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontWeight: FontWeight.w800,
            color: AppColor.ink,
          ),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: Column(
                children: <Widget>[
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.all(AppSpace.page),
                      children: <Widget>[
                        _AvatarHeader(onEditPhoto: _showAvatarComingSoon),
                        const SizedBox(height: AppSpace.lg),
                        if (_notReady)
                          Padding(
                            padding: const EdgeInsets.only(bottom: AppSpace.lg),
                            child: Text(
                              '신체 정보를 입력하면 분석이 더 정확해져요',
                              style: AppText.caption.copyWith(
                                color: AppColor.inkSecondary,
                              ),
                            ),
                          ),
                        AppTextField(
                          controller: _nameController,
                          label: '이름',
                          hint: '닉네임을 입력해주세요',
                        ),
                        const SizedBox(height: AppSpace.lg),
                        // 이메일 — 백엔드에 이메일 필드가 없어 읽기 전용 안내.
                        // 가짜 저장 호출 없음(이름/스냅샷 저장 로직만 유지).
                        // AppTextField 에 readOnly 옵션이 없어 IgnorePointer 로
                        // 포커스/입력을 막는다(design_tokens_v2 는 수정 금지).
                        IgnorePointer(
                          child: AppTextField(
                            controller: _emailController,
                            label: '이메일',
                            hint: '이메일 정보가 아직 없어요',
                            helper: '이메일 변경은 곧 지원할 예정이에요',
                          ),
                        ),
                        const SizedBox(height: AppSpace.lg),
                        // 출생 연도 · 성별 — 2분할 드롭다운형 탭 타일.
                        Row(
                          children: <Widget>[
                            Expanded(
                              child: _DropdownTile(
                                label: '출생 연도',
                                value: _birthYearController.text.trim().isEmpty
                                    ? null
                                    : _birthYearController.text.trim(),
                                placeholder: '선택',
                                onTap: _pickBirthYear,
                              ),
                            ),
                            const SizedBox(width: AppSpace.md),
                            Expanded(
                              child: _DropdownTile(
                                label: '성별',
                                value: _sex?.label,
                                placeholder: '선택',
                                onTap: _pickSex,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: AppSpace.lg),
                        AppTextField(
                          controller: _heightController,
                          label: '키 (cm)',
                          hint: '예: 172',
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                        ),
                        const SizedBox(height: AppSpace.lg),
                        AppTextField(
                          controller: _weightController,
                          label: '몸무게 (kg)',
                          hint: '예: 68',
                          keyboardType: const TextInputType.numberWithOptions(
                            decimal: true,
                          ),
                        ),
                        if (_formError != null) ...<Widget>[
                          const SizedBox(height: AppSpace.md),
                          Text(
                            _formError!,
                            style: AppText.caption.copyWith(
                              color: AppColor.danger,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
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
            ),
    );
  }
}

/// 상단 중앙 아바타 + 카메라 배지 (figma 957:24).
///
/// 이미지 업로드 백엔드가 없어 배지는 장식용 — 탭 시 "준비 중" 안내만.
class _AvatarHeader extends StatelessWidget {
  const _AvatarHeader({required this.onEditPhoto});

  final VoidCallback onEditPhoto;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: GestureDetector(
        onTap: onEditPhoto,
        child: Stack(
          children: <Widget>[
            CircleAvatar(
              radius: 42,
              backgroundColor: AppColor.brandTint,
              child: const Icon(
                Icons.person_rounded,
                color: AppColor.ink,
                size: 42,
              ),
            ),
            Positioned(
              right: 0,
              bottom: 0,
              child: Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppColor.brand,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.camera_alt_rounded,
                  color: Colors.white,
                  size: 18,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 드롭다운형 탭 타일 (출생 연도·성별). 탭 시 휠 시트를 연다.
class _DropdownTile extends StatelessWidget {
  const _DropdownTile({
    required this.label,
    required this.value,
    required this.placeholder,
    required this.onTap,
  });

  final String label;
  final String? value;
  final String placeholder;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final bool hasValue = value != null && value!.isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(left: 2, bottom: 8),
          child: Text(
            label,
            style: AppText.caption.copyWith(
              fontWeight: FontWeight.w600,
              color: AppColor.inkSecondary,
            ),
          ),
        ),
        GestureDetector(
          onTap: onTap,
          child: Container(
            height: 52,
            padding: const EdgeInsets.symmetric(horizontal: 18),
            decoration: BoxDecoration(
              color: AppColor.surface,
              borderRadius: BorderRadius.circular(AppRadius.sm),
              border: Border.all(color: AppColor.border, width: 1.2),
            ),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    hasValue ? value! : placeholder,
                    style: AppText.bodyLg.copyWith(
                      fontWeight: FontWeight.w600,
                      color: hasValue ? AppColor.ink : AppColor.inkTertiary,
                    ),
                  ),
                ),
                const Icon(
                  Icons.expand_more_rounded,
                  color: AppColor.inkTertiary,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
