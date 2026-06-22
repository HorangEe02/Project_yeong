import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../app_controller.dart';
import '../features/dashboard/home_models.dart';
import '../features/supplements/supplement_models.dart';
import '../utils/design_tokens_v2.dart';

/// Screen for reviewing and managing saved meal records.
class MealManagementScreen extends StatelessWidget {
  /// Creates a meal management screen.
  ///
  /// Args:
  ///   controller: Application controller that owns meal state and mutations.
  const MealManagementScreen({required this.controller, super.key});

  /// Application state and meal mutation facade.
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (BuildContext context, Widget? child) {
        final DateTime today = DateTime.now();
        final List<HomeMeal> meals = controller.mealsForDay(today);
        final Map<String, List<HomeMeal>> grouped = _groupByMealType(meals);

        return Scaffold(
          backgroundColor: AppColor.bg,
          appBar: AppBar(
            title: const Text('식단 관리'),
            backgroundColor: AppColor.bg,
            elevation: 0,
            actions: <Widget>[
              IconButton(
                tooltip: '카메라로 추가',
                onPressed: () => context.go('/shell/camera?mode=meal'),
                icon: const Icon(Icons.photo_camera_rounded),
              ),
            ],
          ),
          body: ListView(
            padding: const EdgeInsets.fromLTRB(
              AppSpace.page,
              AppSpace.md,
              AppSpace.page,
              AppSpace.xl + 80,
            ),
            children: <Widget>[
              _AddMealBand(
                onCameraAdd: () => context.go('/shell/camera?mode=meal'),
              ),
              const SizedBox(height: AppSpace.lg),
              for (final MapEntry<String, String> slot in _mealSlots) ...[
                _MealGroupSection(
                  label: slot.value,
                  meals: grouped[slot.key] ?? const <HomeMeal>[],
                  onCameraAdd: () => context.go('/shell/camera?mode=meal'),
                  onEdit: (HomeMeal meal) => _openEditSheet(context, meal),
                  onDelete: (HomeMeal meal) => _confirmDelete(context, meal),
                ),
                const SizedBox(height: AppSpace.lg),
              ],
            ],
          ),
        );
      },
    );
  }

  static const List<MapEntry<String, String>> _mealSlots =
      <MapEntry<String, String>>[
        MapEntry<String, String>('breakfast', '아침'),
        MapEntry<String, String>('lunch', '점심'),
        MapEntry<String, String>('dinner', '저녁'),
        MapEntry<String, String>('snack', '간식'),
      ];

  Map<String, List<HomeMeal>> _groupByMealType(List<HomeMeal> meals) {
    final Map<String, List<HomeMeal>> grouped = <String, List<HomeMeal>>{};
    for (final HomeMeal meal in meals) {
      grouped.putIfAbsent(meal.mealType, () => <HomeMeal>[]).add(meal);
    }
    return grouped;
  }

  Future<void> _openEditSheet(BuildContext context, HomeMeal meal) async {
    final MealConfirmationRequest? request =
        await showModalBottomSheet<MealConfirmationRequest>(
          context: context,
          isScrollControlled: true,
          useSafeArea: true,
          builder: (BuildContext context) => _MealEditSheet(meal: meal),
        );
    if (request == null || !context.mounted) return;
    await controller.updateMealRecord(meal.id, request);
  }

  Future<void> _confirmDelete(BuildContext context, HomeMeal meal) async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('식단 기록 삭제'),
          content: Text('${meal.primaryName ?? '이 식단'} 기록을 삭제할까요?'),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('삭제'),
            ),
          ],
        );
      },
    );
    if (confirmed != true || !context.mounted) return;
    await controller.deleteMealRecord(meal.id);
  }
}

class _AddMealBand extends StatelessWidget {
  const _AddMealBand({required this.onCameraAdd});

  final VoidCallback onCameraAdd;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.lg),
      decoration: BoxDecoration(
        color: AppColor.brand,
        borderRadius: BorderRadius.circular(22),
      ),
      child: Row(
        children: <Widget>[
          const Icon(Icons.restaurant_rounded, color: AppColor.ink),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Text(
              '저장한 음식을 확인하고 필요한 식단을 추가해요',
              style: AppText.body.copyWith(fontWeight: FontWeight.w800),
            ),
          ),
          FilledButton.icon(
            onPressed: onCameraAdd,
            icon: const Icon(Icons.photo_camera_rounded),
            label: const Text('촬영'),
          ),
        ],
      ),
    );
  }
}

class _MealGroupSection extends StatelessWidget {
  const _MealGroupSection({
    required this.label,
    required this.meals,
    required this.onCameraAdd,
    required this.onEdit,
    required this.onDelete,
  });

  final String label;
  final List<HomeMeal> meals;
  final VoidCallback onCameraAdd;
  final ValueChanged<HomeMeal> onEdit;
  final ValueChanged<HomeMeal> onDelete;

  @override
  Widget build(BuildContext context) {
    final double kcal = meals.fold<double>(
      0,
      (double total, HomeMeal meal) => total + meal.nutrition.kcal,
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                '$label ${meals.length}건 · ${kcal.round()} kcal',
                style: AppText.subtitle,
              ),
            ),
            TextButton.icon(
              onPressed: onCameraAdd,
              icon: const Icon(Icons.add_rounded),
              label: const Text('추가'),
            ),
          ],
        ),
        const SizedBox(height: AppSpace.sm),
        if (meals.isEmpty)
          _EmptyMealCard(label: label)
        else
          for (final HomeMeal meal in meals) ...[
            _SavedMealCard(
              meal: meal,
              onEdit: () => onEdit(meal),
              onDelete: () => onDelete(meal),
            ),
            const SizedBox(height: AppSpace.sm),
          ],
      ],
    );
  }
}

class _EmptyMealCard extends StatelessWidget {
  const _EmptyMealCard({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.lg),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
      ),
      child: Text(
        '$label 기록이 아직 없어요.',
        style: AppText.body.copyWith(color: AppColor.inkSecondary),
      ),
    );
  }
}

class _SavedMealCard extends StatelessWidget {
  const _SavedMealCard({
    required this.meal,
    required this.onEdit,
    required this.onDelete,
  });

  final HomeMeal meal;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final String names = meal.foodItems.isEmpty
        ? meal.primaryName ?? '식단'
        : meal.foodItems
              .map((HomeFoodItem item) => item.displayName)
              .where((String value) => value.trim().isNotEmpty)
              .join(', ');
    return Container(
      padding: const EdgeInsets.all(AppSpace.lg),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  names.isEmpty ? '식단' : names,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: AppText.body.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
              IconButton(
                tooltip: '수정',
                onPressed: onEdit,
                icon: const Icon(Icons.edit_rounded),
              ),
              IconButton(
                tooltip: '삭제',
                onPressed: onDelete,
                icon: const Icon(Icons.delete_outline_rounded),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.xs),
          Text(
            '${meal.nutrition.kcal.round()} kcal · 탄 ${meal.nutrition.carbG.round()}g · 단 ${meal.nutrition.proteinG.round()}g · 지 ${meal.nutrition.fatG.round()}g',
            style: AppText.caption.copyWith(color: AppColor.inkSecondary),
          ),
        ],
      ),
    );
  }
}

class _MealEditSheet extends StatefulWidget {
  const _MealEditSheet({required this.meal});

  final HomeMeal meal;

  @override
  State<_MealEditSheet> createState() => _MealEditSheetState();
}

class _MealEditSheetState extends State<_MealEditSheet> {
  late String _mealType;
  late final List<_FoodItemEditState> _items;

  @override
  void initState() {
    super.initState();
    _mealType = widget.meal.mealType;
    _items = widget.meal.foodItems.isEmpty
        ? <_FoodItemEditState>[_FoodItemEditState.empty()]
        : widget.meal.foodItems
              .map(_FoodItemEditState.fromHomeFoodItem)
              .toList(growable: false);
  }

  @override
  void dispose() {
    for (final _FoodItemEditState item in _items) {
      item.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: AppSpace.page,
        right: AppSpace.page,
        top: AppSpace.lg,
        bottom: MediaQuery.viewInsetsOf(context).bottom + AppSpace.lg,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('식단 수정', style: AppText.subtitle),
            const SizedBox(height: AppSpace.md),
            DropdownButtonFormField<String>(
              initialValue: _mealType,
              decoration: const InputDecoration(labelText: '시간대'),
              items: const <DropdownMenuItem<String>>[
                DropdownMenuItem<String>(value: 'breakfast', child: Text('아침')),
                DropdownMenuItem<String>(value: 'lunch', child: Text('점심')),
                DropdownMenuItem<String>(value: 'dinner', child: Text('저녁')),
                DropdownMenuItem<String>(value: 'snack', child: Text('간식')),
              ],
              onChanged: (String? value) {
                if (value == null) return;
                setState(() => _mealType = value);
              },
            ),
            const SizedBox(height: AppSpace.md),
            for (int index = 0; index < _items.length; index++) ...[
              Text('음식 ${index + 1}', style: AppText.body),
              const SizedBox(height: AppSpace.xs),
              _FoodItemEditor(item: _items[index]),
              const SizedBox(height: AppSpace.md),
            ],
            SizedBox(
              width: double.infinity,
              child: FilledButton(onPressed: _submit, child: const Text('저장')),
            ),
          ],
        ),
      ),
    );
  }

  void _submit() {
    final List<MealFoodItemInput> foodItems = <MealFoodItemInput>[];
    for (final _FoodItemEditState item in _items) {
      final String name = item.name.text.trim();
      if (name.isEmpty) continue;
      foodItems.add(
        MealFoodItemInput(
          displayName: name,
          kcal: _doubleOrNull(item.kcal.text),
          carbG: _doubleOrNull(item.carb.text),
          proteinG: _doubleOrNull(item.protein.text),
          fatG: _doubleOrNull(item.fat.text),
          sodiumMg: _doubleOrNull(item.sodium.text),
          source: 'manual',
        ),
      );
    }
    if (foodItems.isEmpty) return;
    Navigator.of(context).pop(
      MealConfirmationRequest(
        foodItems: foodItems,
        mealType: _mealType,
        eatenAt: widget.meal.eatenAt,
      ),
    );
  }

  double? _doubleOrNull(String value) {
    final String normalized = value.trim();
    if (normalized.isEmpty) return null;
    return double.tryParse(normalized);
  }
}

class _FoodItemEditor extends StatelessWidget {
  const _FoodItemEditor({required this.item});

  final _FoodItemEditState item;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        TextField(
          controller: item.name,
          textInputAction: TextInputAction.next,
          decoration: const InputDecoration(labelText: '음식명'),
        ),
        const SizedBox(height: AppSpace.xs),
        Row(
          children: <Widget>[
            Expanded(
              child: _NumberField(controller: item.kcal, label: 'kcal'),
            ),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: _NumberField(controller: item.sodium, label: '나트륨 mg'),
            ),
          ],
        ),
        const SizedBox(height: AppSpace.xs),
        Row(
          children: <Widget>[
            Expanded(
              child: _NumberField(controller: item.carb, label: '탄수 g'),
            ),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: _NumberField(controller: item.protein, label: '단백질 g'),
            ),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: _NumberField(controller: item.fat, label: '지방 g'),
            ),
          ],
        ),
      ],
    );
  }
}

class _NumberField extends StatelessWidget {
  const _NumberField({required this.controller, required this.label});

  final TextEditingController controller;
  final String label;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      textInputAction: TextInputAction.next,
      decoration: InputDecoration(labelText: label),
    );
  }
}

class _FoodItemEditState {
  _FoodItemEditState({
    required this.name,
    required this.kcal,
    required this.carb,
    required this.protein,
    required this.fat,
    required this.sodium,
  });

  factory _FoodItemEditState.empty() {
    return _FoodItemEditState(
      name: TextEditingController(),
      kcal: TextEditingController(),
      carb: TextEditingController(),
      protein: TextEditingController(),
      fat: TextEditingController(),
      sodium: TextEditingController(),
    );
  }

  factory _FoodItemEditState.fromHomeFoodItem(HomeFoodItem item) {
    return _FoodItemEditState(
      name: TextEditingController(text: item.displayName),
      kcal: TextEditingController(text: _formatNumber(item.kcal)),
      carb: TextEditingController(text: _formatNumber(item.carbG)),
      protein: TextEditingController(text: _formatNumber(item.proteinG)),
      fat: TextEditingController(text: _formatNumber(item.fatG)),
      sodium: TextEditingController(text: _formatNumber(item.sodiumMg)),
    );
  }

  final TextEditingController name;
  final TextEditingController kcal;
  final TextEditingController carb;
  final TextEditingController protein;
  final TextEditingController fat;
  final TextEditingController sodium;

  void dispose() {
    name.dispose();
    kcal.dispose();
    carb.dispose();
    protein.dispose();
    fat.dispose();
    sodium.dispose();
  }

  static String _formatNumber(double value) {
    if (value == 0) return '';
    if (value == value.roundToDouble()) return value.round().toString();
    return value.toStringAsFixed(2);
  }
}
