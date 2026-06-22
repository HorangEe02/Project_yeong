import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../app_controller.dart';
import '../features/dashboard/home_models.dart';
import '../features/supplements/supplement_models.dart';
import '../utils/design_tokens_v2.dart';
import '../widgets/common/app_modals.dart';

/// Saved supplement management screen.
///
/// Users can review saved supplements, delete records, add a supplement from a
/// known category, or continue into the OCR camera flow. Unknown free-text
/// categories are intentionally rejected until the backend category catalog is
/// updated through a reviewed path.
class SupplementManagementScreen extends StatefulWidget {
  /// Creates the supplement management screen.
  ///
  /// Args:
  ///   controller: App-level controller that owns supplement repository calls.
  const SupplementManagementScreen({required this.controller, super.key});

  /// Backend-connected app controller.
  final AppController controller;

  @override
  State<SupplementManagementScreen> createState() =>
      _SupplementManagementScreenState();
}

class _SupplementManagementScreenState
    extends State<SupplementManagementScreen> {
  final TextEditingController _nameController = TextEditingController();
  List<SupplementCategory> _categories = const <SupplementCategory>[];
  SupplementCategory? _selectedCategory;
  String _selectedTimeOfDay = 'morning';
  bool _loadingCategories = true;
  String? _categoryError;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadCategories();
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _loadCategories() async {
    try {
      final List<SupplementCategory> categories = await widget
          .controller
          .repository
          .fetchSupplementCategories();
      if (!mounted) return;
      setState(() {
        _categories = categories;
        _loadingCategories = false;
        _categoryError = null;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingCategories = false;
        _categoryError = '카테고리 목록을 불러오지 못했어요.';
      });
    }
  }

  void _selectCategory(SupplementCategory category) {
    setState(() {
      _selectedCategory = category;
      if (_nameController.text.trim().isEmpty) {
        _nameController.text = category.displayName;
      }
    });
  }

  Future<void> _saveManualSupplement() async {
    final String displayName = _nameController.text.trim();
    final SupplementCategory? category =
        _selectedCategory ?? _matchedCategory(displayName);
    if (displayName.isEmpty) {
      _showMessage('영양제명을 입력해주세요.');
      return;
    }
    if (category == null) {
      _showMessage('등록된 카테고리와 매칭되지 않아 저장하지 않았어요. 카메라 분석 또는 DB 업데이트가 필요해요.');
      return;
    }
    setState(() => _saving = true);
    await widget.controller.registerSupplement(
      UserSupplementCreate(
        analysisId: null,
        displayName: displayName,
        manufacturer: null,
        ingredients: <UserSupplementIngredientInput>[
          UserSupplementIngredientInput(
            displayName: category.displayName,
            nutrientCode: null,
            amount: null,
            unit: null,
            confidence: 1,
            source: 'user_confirmed',
          ),
        ],
        serving: const SupplementServing(
          amount: null,
          unit: null,
          dailyServings: 1,
        ),
        intakeSchedule: SupplementIntakeSchedule(
          frequency: 'daily',
          timeOfDay: <String>[_selectedTimeOfDay],
          timesPerDay: 1,
        ),
        categoryKey: category.categoryKey,
      ),
    );
    if (!mounted) return;
    setState(() => _saving = false);
    final String? error = widget.controller.apiError?.message;
    if (error != null && error.trim().isNotEmpty) {
      _showMessage(error);
      return;
    }
    _nameController.clear();
    setState(() => _selectedCategory = null);
    _showMessage('영양제를 추가했어요.');
  }

  Future<void> _confirmDelete(HomeSupplement supplement) async {
    final bool? confirmed = await showAppDialog(
      context,
      title: '영양제를 삭제할까요?',
      body: '${supplement.displayName} 기록을 목록에서 제거합니다.',
      primaryLabel: '삭제',
      secondaryLabel: '취소',
    );
    if (confirmed != true || !mounted) return;
    final HomeSupplement? removed = widget.controller
        .removeSupplementOptimistically(supplement.id);
    if (removed == null) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('${removed.displayName}을 삭제했어요.'),
        action: SnackBarAction(
          label: '되돌리기',
          onPressed: () => widget.controller.undoSupplementRemoval(removed),
        ),
      ),
    );
  }

  SupplementCategory? _matchedCategory(String raw) {
    final String needle = _normalizeCategoryText(raw);
    if (needle.isEmpty) return null;
    for (final SupplementCategory category in _categories) {
      if (_normalizeCategoryText(category.displayName) == needle ||
          _normalizeCategoryText(category.categoryKey) == needle) {
        return category;
      }
    }
    return null;
  }

  static String _normalizeCategoryText(String value) {
    return value.trim().toLowerCase().replaceAll(RegExp(r'[\s_\-]+'), '');
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (BuildContext context, Widget? child) {
        final List<HomeSupplement> supplements =
            widget.controller.homeSupplements.results;
        return Scaffold(
          backgroundColor: AppColor.section,
          body: SafeArea(
            bottom: false,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(
                AppSpace.page,
                AppSpace.lg,
                AppSpace.page,
                AppSpace.xl + 96,
              ),
              children: <Widget>[
                _Header(
                  onBack: () => context.go('/shell/home'),
                  onCamera: () => context.go('/shell/camera?mode=supplement'),
                ),
                const SizedBox(height: AppSpace.lg),
                _SavedSupplementSection(
                  supplements: supplements,
                  onDelete: _confirmDelete,
                ),
                const SizedBox(height: AppSpace.lg),
                _ManualAddSection(
                  nameController: _nameController,
                  categories: _categories,
                  selectedCategory: _selectedCategory,
                  selectedTimeOfDay: _selectedTimeOfDay,
                  loadingCategories: _loadingCategories,
                  categoryError: _categoryError,
                  saving: _saving,
                  onCategorySelected: _selectCategory,
                  onTimeOfDayChanged: (String value) {
                    setState(() => _selectedTimeOfDay = value);
                  },
                  onSave: _saveManualSupplement,
                  onCamera: () => context.go('/shell/camera?mode=supplement'),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.onBack, required this.onCamera});

  final VoidCallback onBack;
  final VoidCallback onCamera;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        _IconButton(icon: Icons.arrow_back_rounded, onTap: onBack),
        const SizedBox(width: AppSpace.sm),
        Expanded(child: Text('영양제 관리', style: AppText.title)),
        _IconButton(icon: Icons.photo_camera_rounded, onTap: onCamera),
      ],
    );
  }
}

class _SavedSupplementSection extends StatelessWidget {
  const _SavedSupplementSection({
    required this.supplements,
    required this.onDelete,
  });

  final List<HomeSupplement> supplements;
  final ValueChanged<HomeSupplement> onDelete;

  @override
  Widget build(BuildContext context) {
    if (supplements.isEmpty) {
      return _Panel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('저장된 영양제', style: AppText.subtitle),
            const SizedBox(height: AppSpace.sm),
            Text('아직 저장된 영양제가 없어요.', style: AppText.body),
          ],
        ),
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text('저장된 영양제', style: AppText.subtitle),
        const SizedBox(height: AppSpace.md),
        for (final HomeSupplement supplement in supplements) ...<Widget>[
          _SupplementListTile(
            supplement: supplement,
            onDelete: () => onDelete(supplement),
          ),
          const SizedBox(height: AppSpace.sm),
        ],
      ],
    );
  }
}

class _SupplementListTile extends StatelessWidget {
  const _SupplementListTile({required this.supplement, required this.onDelete});

  final HomeSupplement supplement;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        boxShadow: AppShadow.softCard,
      ),
      child: Row(
        children: <Widget>[
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColor.brandSoft,
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: const Icon(
              Icons.medication_liquid_rounded,
              color: AppColor.ink,
            ),
          ),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  supplement.displayName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.bodyLg.copyWith(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 2),
                Text(
                  [
                    if (supplement.categoryLabel?.isNotEmpty == true)
                      supplement.categoryLabel,
                    supplement.schedule?.summary,
                  ].whereType<String>().join(' · '),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.caption,
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: '삭제',
            onPressed: onDelete,
            icon: const Icon(Icons.delete_outline_rounded),
          ),
        ],
      ),
    );
  }
}

class _ManualAddSection extends StatelessWidget {
  const _ManualAddSection({
    required this.nameController,
    required this.categories,
    required this.selectedCategory,
    required this.selectedTimeOfDay,
    required this.loadingCategories,
    required this.categoryError,
    required this.saving,
    required this.onCategorySelected,
    required this.onTimeOfDayChanged,
    required this.onSave,
    required this.onCamera,
  });

  final TextEditingController nameController;
  final List<SupplementCategory> categories;
  final SupplementCategory? selectedCategory;
  final String selectedTimeOfDay;
  final bool loadingCategories;
  final String? categoryError;
  final bool saving;
  final ValueChanged<SupplementCategory> onCategorySelected;
  final ValueChanged<String> onTimeOfDayChanged;
  final VoidCallback onSave;
  final VoidCallback onCamera;

  @override
  Widget build(BuildContext context) {
    return _Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text('직접 추가', style: AppText.subtitle),
          const SizedBox(height: AppSpace.xs),
          Text('등록된 카테고리를 선택하거나 이름을 입력해 저장할 수 있어요.', style: AppText.caption),
          const SizedBox(height: AppSpace.md),
          TextField(
            controller: nameController,
            decoration: const InputDecoration(
              hintText: '예: 오메가3, 루테인, 비타민 D',
              filled: true,
              fillColor: AppColor.sunken,
              border: OutlineInputBorder(
                borderSide: BorderSide(color: AppColor.border),
                borderRadius: BorderRadius.all(Radius.circular(AppRadius.sm)),
              ),
            ),
          ),
          const SizedBox(height: AppSpace.md),
          if (loadingCategories)
            const LinearProgressIndicator(minHeight: 3)
          else if (categoryError != null)
            Text(categoryError!, style: AppText.caption)
          else
            Wrap(
              spacing: AppSpace.xs,
              runSpacing: AppSpace.xs,
              children: <Widget>[
                for (final SupplementCategory category in categories.take(16))
                  ChoiceChip(
                    label: Text(category.displayName),
                    selected:
                        selectedCategory?.categoryKey == category.categoryKey,
                    onSelected: (_) => onCategorySelected(category),
                  ),
              ],
            ),
          const SizedBox(height: AppSpace.md),
          Row(
            children: <Widget>[
              _TimeChip(
                label: '아침',
                value: 'morning',
                selectedValue: selectedTimeOfDay,
                onSelected: onTimeOfDayChanged,
              ),
              const SizedBox(width: AppSpace.xs),
              _TimeChip(
                label: '저녁',
                value: 'evening',
                selectedValue: selectedTimeOfDay,
                onSelected: onTimeOfDayChanged,
              ),
            ],
          ),
          const SizedBox(height: AppSpace.lg),
          Row(
            children: <Widget>[
              Expanded(
                child: _ActionButton(
                  label: saving ? '저장 중' : '저장',
                  icon: Icons.check_rounded,
                  filled: true,
                  onTap: saving ? null : onSave,
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: _ActionButton(
                  label: '카메라 추가',
                  icon: Icons.photo_camera_rounded,
                  onTap: onCamera,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _TimeChip extends StatelessWidget {
  const _TimeChip({
    required this.label,
    required this.value,
    required this.selectedValue,
    required this.onSelected,
  });

  final String label;
  final String value;
  final String selectedValue;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    final bool selected = selectedValue == value;
    return ChoiceChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onSelected(value),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.label,
    required this.icon,
    required this.onTap,
    this.filled = false,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onTap;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    final Color bg = filled ? AppColor.brand : AppColor.surface;
    return Material(
      color: bg,
      borderRadius: BorderRadius.circular(AppRadius.md),
      child: InkWell(
        borderRadius: BorderRadius.circular(AppRadius.md),
        onTap: onTap,
        child: Container(
          height: 52,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppRadius.md),
            border: Border.all(
              color: filled ? AppColor.brand : AppColor.borderStrong,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(icon, size: 18, color: AppColor.ink),
              const SizedBox(width: AppSpace.xs),
              Text(
                label,
                style: AppText.body.copyWith(fontWeight: FontWeight.w800),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _IconButton extends StatelessWidget {
  const _IconButton({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColor.surface,
      shape: const CircleBorder(),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: SizedBox(
          width: 44,
          height: 44,
          child: Icon(icon, color: AppColor.ink),
        ),
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.lg),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.softCard,
      ),
      child: child,
    );
  }
}
