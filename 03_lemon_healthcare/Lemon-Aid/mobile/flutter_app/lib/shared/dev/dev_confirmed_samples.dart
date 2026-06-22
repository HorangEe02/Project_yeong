import '../../features/food/domain/confirmed_food_entry.dart';
import '../../features/supplement/domain/supplement_analysis_preview.dart';
import '../state/confirmed_entry_store.dart';

void seedDevConfirmedEntries() {
  ConfirmedEntryStore.instance
    ..clear()
    ..addFood(
      ConfirmedFoodEntry(
        name: '현미밥과 닭가슴살 샐러드',
        mealType: 'lunch',
        servingLabel: '1 plate',
        memo: '개발용 샘플: 음식 인식 결과를 사용자가 확인했다고 가정',
        photoName: 'dev-food-sample.jpg',
      ),
    )
    ..addSupplement(
      SupplementConfirmedInput(
        analysisId: 'dev-supplement-analysis',
        displayName: 'Vitamin D 1000 IU',
        manufacturer: 'Dev Sample',
        ingredients: <SupplementConfirmedIngredientInput>[
          SupplementConfirmedIngredientInput(
            displayName: 'Vitamin D',
            nutrientCode: 'vitamin_d',
            amount: 25,
            unit: 'mcg',
          ),
        ],
        serving: SupplementServingInput(
          amount: 1,
          unit: 'tablet',
          dailyServings: 1,
        ),
        intakeSchedule: SupplementIntakeScheduleInput(
          frequency: 'daily',
          timeOfDay: <String>['morning'],
        ),
      ),
    );
}
