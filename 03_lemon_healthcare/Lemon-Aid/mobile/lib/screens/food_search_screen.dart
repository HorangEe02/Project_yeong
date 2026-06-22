// screens/food_search_screen.dart — 직접 입력 (음식 검색)
//
// 가이드 07 ② (figma 916:23 + 951:36):
//   AppBar('직접 입력')
//   ├─ 검색 필드: placeholder "음식 이름을 검색해 보세요" (debounce 300ms)
//   ├─ 분류 칩 가로 스크롤: 전체 | 한식 | ... (GET /meals/cuisines)
//   ├─ 결과 리스트: canonical_name_ko + 분류/코스 라벨 + ⊕ 담기
//   ├─ 0건: StatusStateView(variant: searchEmpty, query: 검색어)
//   └─ 하단: '담은 항목 N개' 바 + '기록에 추가하기' AppPrimaryButton
//
// 진입은 카메라 분석 폴백 한정(후보 0건·저신뢰·requires_manual_entry). 담은 항목은
// 호출자(analysis_result_screen)에게 List<MealFoodItemInput> 로 반환되어 해당
// meal_id 의 confirm payload food_items[] 에 source:'database_match' 로 합류한다.
//
// 연산은 모두 백엔드. 모바일은 표시·선택만. 문구는 해요체 + 금칙어 미사용.

import 'dart:async';

import 'package:flutter/material.dart';

import '../features/records/food_models.dart';
import '../features/records/records_repository.dart';
import '../features/supplements/supplement_models.dart';
import '../shared/widgets/status_state_view.dart';
import '../utils/design_tokens_v2.dart';
import '../widgets/common/lemon_chip.dart';
import '../widgets/common/pressable.dart';

/// 음식 카탈로그 검색 화면 (직접 입력).
///
/// 사용자가 ⊕ 로 담은 항목을 [Navigator.pop] 으로 `List<MealFoodItemInput>`
/// (`source: 'database_match'`) 로 반환한다. 취소 시 null.
class FoodSearchScreen extends StatefulWidget {
  /// 음식 검색 화면을 생성한다.
  ///
  /// Args:
  ///   repository: 검색·분류 로더.
  const FoodSearchScreen({required this.repository, super.key});

  /// 검색·분류 로더.
  final RecordsRepository repository;

  @override
  State<FoodSearchScreen> createState() => _FoodSearchScreenState();
}

class _FoodSearchScreenState extends State<FoodSearchScreen> {
  final TextEditingController _searchController = TextEditingController();
  Timer? _debounce;

  List<FoodCuisine> _cuisines = const <FoodCuisine>[];
  String? _selectedCuisineCode; // null = 전체.
  List<FoodCatalogItem> _results = const <FoodCatalogItem>[];
  final List<MealFoodItemInput> _picked = <MealFoodItemInput>[];
  final Set<String> _pickedIds = <String>{};

  bool _loadingResults = false;
  bool _failed = false;
  String _lastQuery = '';

  static const Duration _debounceDelay = Duration(milliseconds: 300);

  @override
  void initState() {
    super.initState();
    _searchController.addListener(_onQueryChanged);
    _loadCuisines();
    _runSearch();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.removeListener(_onQueryChanged);
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadCuisines() async {
    try {
      final FoodCuisineList list = await widget.repository.fetchCuisines();
      if (!mounted) return;
      setState(() {
        _cuisines = list.results;
      });
    } catch (_) {
      // 분류 로드 실패는 검색을 막지 않는다 ('전체'만 노출).
    }
  }

  // 검색어 변경 → 300ms 디바운스 후 검색. 마지막 입력만 네트워크로 보낸다.
  void _onQueryChanged() {
    _debounce?.cancel();
    _debounce = Timer(_debounceDelay, _runSearch);
  }

  void _onCuisineSelected(String? cuisineCode) {
    setState(() {
      _selectedCuisineCode = cuisineCode;
    });
    _runSearch();
  }

  Future<void> _runSearch() async {
    final String query = _searchController.text.trim();
    _lastQuery = query;
    setState(() {
      _loadingResults = true;
      _failed = false;
    });
    try {
      final FoodCatalogList list = await widget.repository.searchFoods(
        q: query.isEmpty ? null : query,
        cuisineCode: _selectedCuisineCode,
      );
      if (!mounted) return;
      setState(() {
        _results = list.results;
        _loadingResults = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _failed = true;
        _loadingResults = false;
      });
    }
  }

  void _togglePick(FoodCatalogItem item) {
    setState(() {
      if (_pickedIds.contains(item.id)) {
        _pickedIds.remove(item.id);
        _picked.removeWhere(
          (MealFoodItemInput input) => input.foodCatalogItemId == item.id,
        );
      } else {
        _pickedIds.add(item.id);
        _picked.add(
          MealFoodItemInput(
            displayName: item.canonicalNameKo,
            foodCatalogItemId: item.id,
            source: 'database_match',
          ),
        );
      }
    });
  }

  void _removePicked(MealFoodItemInput input) {
    setState(() {
      _picked.remove(input);
      if (input.foodCatalogItemId != null) {
        _pickedIds.remove(input.foodCatalogItemId);
      }
    });
  }

  void _confirm() {
    Navigator.of(context).pop<List<MealFoodItemInput>>(
      List<MealFoodItemInput>.unmodifiable(_picked),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColor.bg,
      appBar: AppBar(
        backgroundColor: AppColor.bg,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: AppColor.ink),
          onPressed: () => Navigator.of(context).maybePop(),
        ),
        title: Text(
          '직접 입력',
          style: AppText.subtitle.copyWith(fontWeight: FontWeight.w800),
        ),
        centerTitle: false,
      ),
      body: SafeArea(
        top: false,
        child: Column(
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpace.page,
                AppSpace.md,
                AppSpace.page,
                AppSpace.sm,
              ),
              child: AppTextField(
                controller: _searchController,
                hint: '음식 이름을 검색해 보세요',
                onSubmitted: (_) => _runSearch(),
                suffix: const Padding(
                  padding: EdgeInsets.only(right: 12),
                  child: Icon(
                    Icons.search_rounded,
                    color: AppColor.inkTertiary,
                  ),
                ),
              ),
            ),
            _CuisineChipRow(
              cuisines: _cuisines,
              selectedCode: _selectedCuisineCode,
              onSelected: _onCuisineSelected,
            ),
            Expanded(child: _buildResults()),
            if (_picked.isNotEmpty)
              _PickedBar(
                picked: _picked,
                onRemove: _removePicked,
                onConfirm: _confirm,
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildResults() {
    if (_failed) {
      return StatusStateView(
        variant: StatusStateVariant.syncFailed,
        onPrimary: _runSearch,
      );
    }
    if (_loadingResults && _results.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_results.isEmpty) {
      return StatusStateView(
        variant: StatusStateVariant.searchEmpty,
        query: _lastQuery,
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(
        AppSpace.page,
        AppSpace.sm,
        AppSpace.page,
        AppSpace.xl,
      ),
      itemCount: _results.length,
      separatorBuilder: (_, _) =>
          Divider(color: AppColor.border, height: AppSpace.lg),
      itemBuilder: (BuildContext context, int index) {
        final FoodCatalogItem item = _results[index];
        return _FoodResultRow(
          item: item,
          picked: _pickedIds.contains(item.id),
          onToggle: () => _togglePick(item),
        );
      },
    );
  }
}

// ═══════════════════════════════════════════
// 분류 칩 가로 스크롤 — 전체 + cuisines
// ═══════════════════════════════════════════
class _CuisineChipRow extends StatelessWidget {
  final List<FoodCuisine> cuisines;
  final String? selectedCode;
  final ValueChanged<String?> onSelected;
  const _CuisineChipRow({
    required this.cuisines,
    required this.selectedCode,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.page,
          vertical: AppSpace.sm,
        ),
        children: <Widget>[
          LemonChip(
            label: '전체',
            selected: selectedCode == null,
            onTap: () => onSelected(null),
          ),
          for (final FoodCuisine cuisine in cuisines) ...<Widget>[
            const SizedBox(width: AppSpace.sm),
            LemonChip(
              label: cuisine.displayNameKo,
              selected: selectedCode == cuisine.cuisineCode,
              onTap: () => onSelected(cuisine.cuisineCode),
            ),
          ],
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 결과 행 — 이름 + 분류/코스 라벨 + ⊕/✓ 담기
// ═══════════════════════════════════════════
class _FoodResultRow extends StatelessWidget {
  final FoodCatalogItem item;
  final bool picked;
  final VoidCallback onToggle;
  const _FoodResultRow({
    required this.item,
    required this.picked,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final String label = <String>[
      if (item.cuisineCode.isNotEmpty) item.cuisineCode,
      if (item.courseCode.isNotEmpty) item.courseCode,
    ].join(' · ');
    return Pressable(
      onTap: onToggle,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpace.xs),
        child: Row(
          children: <Widget>[
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    item.canonicalNameKo,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: AppText.body.copyWith(fontWeight: FontWeight.w700),
                  ),
                  if (label.isNotEmpty) ...<Widget>[
                    const SizedBox(height: 2),
                    Text(
                      label,
                      style: AppText.caption.copyWith(
                        color: AppColor.inkTertiary,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(width: AppSpace.sm),
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: picked ? AppColor.brand : AppColor.brandSoft,
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Icon(
                picked ? Icons.check_rounded : Icons.add_rounded,
                size: 20,
                color: picked ? Colors.white : AppColor.brandDeep,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 담은 항목 바 — '담은 항목 N개' + 칩 + 기록에 추가하기
// ═══════════════════════════════════════════
class _PickedBar extends StatelessWidget {
  final List<MealFoodItemInput> picked;
  final ValueChanged<MealFoodItemInput> onRemove;
  final VoidCallback onConfirm;
  const _PickedBar({
    required this.picked,
    required this.onRemove,
    required this.onConfirm,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: AppColor.surface,
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: Color.fromRGBO(140, 155, 175, 0.18),
            blurRadius: 18,
            offset: Offset(0, -6),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.page,
            AppSpace.md,
            AppSpace.page,
            AppSpace.md,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                '담은 항목 ${picked.length}개',
                style: AppText.caption.copyWith(
                  color: AppColor.inkSecondary,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              Wrap(
                spacing: AppSpace.sm,
                runSpacing: AppSpace.sm,
                children: <Widget>[
                  for (final MealFoodItemInput input in picked)
                    _PickedChip(
                      label: input.displayName,
                      onRemove: () => onRemove(input),
                    ),
                ],
              ),
              const SizedBox(height: AppSpace.md),
              SizedBox(
                width: double.infinity,
                child: AppPrimaryButton(
                  label: '기록에 추가하기',
                  onPressed: onConfirm,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PickedChip extends StatelessWidget {
  final String label;
  final VoidCallback onRemove;
  const _PickedChip({required this.label, required this.onRemove});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 7, 6, 7),
      decoration: BoxDecoration(
        color: AppColor.brandSoft,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(
            label,
            style: AppText.caption.copyWith(
              color: AppColor.brandDeep,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(width: 4),
          Pressable(
            onTap: onRemove,
            child: Icon(
              Icons.close_rounded,
              size: 16,
              color: AppColor.brandDeep,
            ),
          ),
        ],
      ),
    );
  }
}
