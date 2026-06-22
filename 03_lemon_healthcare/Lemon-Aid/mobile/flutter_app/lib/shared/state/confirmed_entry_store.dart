import '../../features/activity/domain/activity_models.dart';
import '../../features/food/domain/confirmed_food_entry.dart';
import '../../features/supplement/domain/supplement_analysis_preview.dart';

class ConfirmedEntryStore {
  ConfirmedEntryStore._();

  static final ConfirmedEntryStore instance = ConfirmedEntryStore._();

  final List<ConfirmedFoodEntry> _foods = <ConfirmedFoodEntry>[];
  final List<SupplementConfirmedInput> _supplements =
      <SupplementConfirmedInput>[];
  final List<ConfirmedActivityEntry> _activities = <ConfirmedActivityEntry>[];

  List<ConfirmedFoodEntry> get foods =>
      List<ConfirmedFoodEntry>.unmodifiable(_foods);

  List<SupplementConfirmedInput> get supplements =>
      List<SupplementConfirmedInput>.unmodifiable(_supplements);

  List<ConfirmedActivityEntry> get activities =>
      List<ConfirmedActivityEntry>.unmodifiable(_activities);

  void addFood(ConfirmedFoodEntry food) {
    _foods.add(food);
  }

  void addSupplement(SupplementConfirmedInput supplement) {
    _supplements.add(supplement);
  }

  void addActivity(ConfirmedActivityEntry activity) {
    _activities.add(activity);
  }

  void clear() {
    _foods.clear();
    _supplements.clear();
    _activities.clear();
  }
}
