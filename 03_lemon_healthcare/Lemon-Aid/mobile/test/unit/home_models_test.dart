import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/dashboard/dashboard_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';

void main() {
  group('DashboardHealthScore', () {
    test('parses a ready health_score block', () {
      final DashboardHealthScore score = DashboardHealthScore.fromSummaryJson(
        <String, dynamic>{
          'health_score': <String, dynamic>{
            'data_status': 'ready',
            'score': 78,
            'label': 'excellent',
            'label_text': '좋아요',
            'message': '오늘 활동량이 좋아요.',
            'algorithm_version': 'daily-health-score-v1.0.0',
            'measured_date': '2026-06-10',
            'disclaimers': <String>['참고용 정보예요.'],
          },
        },
      );

      expect(score.isReady, isTrue);
      expect(score.status, HealthScoreStatus.ready);
      expect(score.score, 78);
      expect(score.labelText, '좋아요');
      expect(score.message, '오늘 활동량이 좋아요.');
      expect(score.measuredDate, '2026-06-10');
      expect(score.disclaimers, <String>['참고용 정보예요.']);
    });

    test('treats not_ready status as not ready', () {
      final DashboardHealthScore score = DashboardHealthScore.fromSummaryJson(
        <String, dynamic>{
          'health_score': <String, dynamic>{
            'data_status': 'not_ready',
            'score': null,
            'message': '기록을 추가해주세요.',
          },
        },
      );

      expect(score.isReady, isFalse);
      expect(score.status, HealthScoreStatus.notReady);
      expect(score.score, isNull);
      // not_ready 라도 안내 메시지는 살린다.
      expect(score.message, '기록을 추가해주세요.');
    });

    test('treats a missing block as not ready', () {
      final DashboardHealthScore score = DashboardHealthScore.fromSummaryJson(
        <String, dynamic>{'nutrition': <String, dynamic>{}},
      );

      expect(score.isReady, isFalse);
      expect(score.status, HealthScoreStatus.notReady);
      expect(score.score, isNull);
    });

    test('treats a ready status without a score as not ready', () {
      final DashboardHealthScore score = DashboardHealthScore.fromJson(
        <String, dynamic>{'data_status': 'ready'},
      );

      expect(score.isReady, isFalse);
      expect(score.status, HealthScoreStatus.notReady);
    });

    test('tolerates unknown and string-typed fields', () {
      final DashboardHealthScore score = DashboardHealthScore.fromJson(
        <String, dynamic>{
          'data_status': 'ready',
          'score': '64',
          'unknown_future_field': <String, dynamic>{'a': 1},
        },
      );

      expect(score.isReady, isTrue);
      expect(score.score, 64);
    });
  });

  group('DashboardSummary.healthScore', () {
    test('exposes a not_ready score when summary omits the block', () {
      final DashboardSummary summary = DashboardSummary.fromJson(
        <String, dynamic>{
          'as_of': '2026-06-10T00:00:00Z',
          'nutrition': <String, dynamic>{
            'data_status': 'ready',
            'low_count': 0,
            'high_count': 0,
          },
          'activity': <String, dynamic>{'data_status': 'not_ready'},
          'weight': <String, dynamic>{'data_status': 'not_ready'},
          'supplements': <String, dynamic>{
            'registered_count': 0,
            'requires_review_count': 0,
          },
          'disclaimers': <String>[],
          'algorithm_version': 'v1',
        },
      );

      expect(summary.healthScore.isReady, isFalse);
    });

    test('parses a present health_score block', () {
      final DashboardSummary summary = DashboardSummary.fromJson(
        <String, dynamic>{
          'as_of': '2026-06-10T00:00:00Z',
          'nutrition': <String, dynamic>{
            'data_status': 'ready',
            'low_count': 0,
            'high_count': 0,
          },
          'activity': <String, dynamic>{'data_status': 'ready'},
          'weight': <String, dynamic>{'data_status': 'not_ready'},
          'supplements': <String, dynamic>{
            'registered_count': 1,
            'requires_review_count': 0,
          },
          'disclaimers': <String>[],
          'algorithm_version': 'v1',
          'health_score': <String, dynamic>{
            'data_status': 'ready',
            'score': 82,
            'label_text': '좋아요',
          },
        },
      );

      expect(summary.healthScore.isReady, isTrue);
      expect(summary.healthScore.score, 82);
    });
  });

  group('HomeMealsResult', () {
    test('parses meals with nutrition summaries and food items', () {
      final HomeMealsResult result = HomeMealsResult.fromJson(<String, dynamic>{
        'results': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'meal-1',
            'status': 'confirmed',
            'meal_type': 'lunch',
            'eaten_at': '2026-06-10T03:30:00Z',
            'food_items': <Map<String, dynamic>>[
              <String, dynamic>{
                'display_name': '비빔밥',
                'kcal': 520,
                'carb_g': 80,
                'protein_g': 18,
                'fat_g': 12,
              },
            ],
            'nutrition_summary': <String, dynamic>{
              'kcal': 520,
              'carb_g': 80,
              'protein_g': 18,
              'fat_g': 12,
            },
          },
        ],
        'limit': 50,
        'offset': 0,
      });

      expect(result.results, hasLength(1));
      final HomeMeal meal = result.results.first;
      expect(meal.mealType, 'lunch');
      expect(meal.primaryName, '비빔밥');
      expect(meal.nutrition.kcal, 520);
      expect(meal.nutrition.carbG, 80);
      expect(meal.eatenAt, isNotNull);
    });

    test('reads kcal/macros from a totals-nested confirmed summary', () {
      // 백엔드 confirmed meal 요약 실제 구조: 합계가 totals 하위에 중첩된다.
      final HomeMealsResult result = HomeMealsResult.fromJson(<String, dynamic>{
        'results': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'meal-totals',
            'status': 'confirmed',
            'meal_type': 'lunch',
            'food_items': <Map<String, dynamic>>[
              <String, dynamic>{
                'display_name': '초밥',
                'kcal': 549.98,
                'carb_g': 81.55,
                'protein_g': 33.53,
                'fat_g': 7.85,
                'sodium_mg': 1186.73,
              },
            ],
            'nutrition_summary': <String, dynamic>{
              'status': 'user_confirmed',
              'items_count': 1,
              'totals': <String, dynamic>{
                'kcal': 549.98,
                'carb_g': 81.55,
                'protein_g': 33.53,
                'fat_g': 7.85,
                'sodium_mg': 1186.73,
              },
            },
          },
        ],
      });

      final HomeMeal meal = result.results.first;
      expect(meal.primaryName, '초밥');
      expect(meal.nutrition.kcal, 549.98);
      expect(meal.nutrition.carbG, 81.55);
      expect(meal.nutrition.proteinG, 33.53);
      expect(meal.nutrition.fatG, 7.85);
    });

    test('falls back to food items when a confirmed summary has empty totals', () {
      // 요약 객체는 있으나 totals가 비어 kcal을 못 읽어도 0으로 표기되면 안 된다.
      final HomeMealsResult result = HomeMealsResult.fromJson(<String, dynamic>{
        'results': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'meal-empty-totals',
            'status': 'confirmed',
            'meal_type': 'dinner',
            'food_items': <Map<String, dynamic>>[
              <String, dynamic>{
                'display_name': '샐러드',
                'kcal': 150,
                'carb_g': 10,
              },
            ],
            'nutrition_summary': <String, dynamic>{
              'status': 'user_confirmed',
              'items_count': 1,
              'totals': <String, dynamic>{},
            },
          },
        ],
      });

      final HomeMeal meal = result.results.first;
      expect(meal.nutrition.kcal, 150);
      expect(meal.nutrition.carbG, 10);
    });

    test('falls back to summing food items when summary is absent', () {
      final HomeMealsResult result = HomeMealsResult.fromJson(<String, dynamic>{
        'results': <Map<String, dynamic>>[
          <String, dynamic>{
            'id': 'meal-2',
            'meal_type': 'breakfast',
            'food_items': <Map<String, dynamic>>[
              <String, dynamic>{'display_name': '계란', 'kcal': 80, 'protein_g': 6},
              <String, dynamic>{'display_name': '토스트', 'kcal': 120, 'carb_g': 20},
            ],
          },
        ],
      });

      final HomeMeal meal = result.results.first;
      expect(meal.nutrition.kcal, 200);
      expect(meal.nutrition.carbG, 20);
      expect(meal.nutrition.proteinG, 6);
    });

    test('tolerates malformed payloads', () {
      final HomeMealsResult result = HomeMealsResult.fromJson(<String, dynamic>{
        'results': <Object?>['not-a-map', 42],
      });

      expect(result.results, isEmpty);
      expect(result.limit, 0);
    });
  });

  group('HomeSupplementsResult', () {
    test('parses supplements with intake schedule summary', () {
      final HomeSupplementsResult result = HomeSupplementsResult.fromJson(
        <String, dynamic>{
          'results': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'sup-1',
              'display_name': '비타민 D',
              'manufacturer': '레몬랩스',
              'intake_schedule': <String, dynamic>{
                'frequency': 'daily',
                'time_of_day': <String>['morning'],
                'times_per_day': 1,
              },
            },
          ],
          'limit': 50,
          'offset': 0,
        },
      );

      expect(result.results, hasLength(1));
      final HomeSupplement supplement = result.results.first;
      expect(supplement.displayName, '비타민 D');
      expect(supplement.manufacturer, '레몬랩스');
      expect(supplement.schedule?.summary, '매일 · 아침');
    });

    test('keeps a null schedule when intake_schedule is missing', () {
      final HomeSupplementsResult result = HomeSupplementsResult.fromJson(
        <String, dynamic>{
          'results': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'sup-2',
              'display_name': '오메가-3',
              'intake_schedule': null,
            },
          ],
        },
      );

      final HomeSupplement supplement = result.results.first;
      expect(supplement.schedule, isNull);
    });

    test('parses the chosen category label from categories[0]', () {
      final HomeSupplementsResult result = HomeSupplementsResult.fromJson(
        <String, dynamic>{
          'results': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'sup-3',
              'display_name': '비타민B 컴플렉스',
              'category_key': '비타민B',
              'categories': <Map<String, dynamic>>[
                <String, dynamic>{
                  'category_key': '비타민B',
                  'display_name': '비타민B',
                  'sort_order': 1,
                },
              ],
            },
          ],
        },
      );

      expect(result.results.first.categoryLabel, '비타민B');
    });

    test('falls back to category_key when categories has no label', () {
      final HomeSupplementsResult result = HomeSupplementsResult.fromJson(
        <String, dynamic>{
          'results': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'sup-4',
              'display_name': '오메가3',
              'category_key': '오메가3',
              'categories': <Map<String, dynamic>>[],
            },
          ],
        },
      );

      expect(result.results.first.categoryLabel, '오메가3');
    });

    test('keeps a null category label when none is chosen', () {
      final HomeSupplementsResult result = HomeSupplementsResult.fromJson(
        <String, dynamic>{
          'results': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'sup-5',
              'display_name': '분류없음',
              'categories': <Map<String, dynamic>>[],
            },
          ],
        },
      );

      expect(result.results.first.categoryLabel, isNull);
    });
  });

  group('HomeMedicationsResult', () {
    test('parses the items wrapper with class and condition labels', () {
      final HomeMedicationsResult result = HomeMedicationsResult.fromJson(
        <String, dynamic>{
          'items': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'med-1',
              'display_name': '아모디핀',
              'normalized_name': 'amlodipine',
              'medication_class': 'calcium_channel_blocker',
              'condition_tags': <String>['hypertension', 'diabetes'],
              'confirmation_status': 'user_confirmed',
              'is_active': true,
            },
          ],
        },
      );

      expect(result.items, hasLength(1));
      final HomeMedication medication = result.items.first;
      expect(medication.id, 'med-1');
      expect(medication.displayName, '아모디핀');
      expect(medication.medicationClass, 'calcium_channel_blocker');
      expect(medication.medicationClassLabel, '칼슘 채널 차단제');
      expect(medication.conditionTags, <String>['hypertension', 'diabetes']);
      expect(medication.conditionTagLabels, <String>['고혈압', '당뇨']);
      expect(medication.isActive, isTrue);
    });

    test('defaults missing fields safely', () {
      final HomeMedicationsResult result = HomeMedicationsResult.fromJson(
        <String, dynamic>{
          'items': <Map<String, dynamic>>[
            <String, dynamic>{'id': 'med-2', 'display_name': '메트포르민'},
          ],
        },
      );

      final HomeMedication medication = result.items.first;
      expect(medication.medicationClass, isNull);
      expect(medication.medicationClassLabel, isNull);
      expect(medication.conditionTags, isEmpty);
      // is_active 누락 시 활성으로 견고하게 수렴.
      expect(medication.isActive, isTrue);
    });

    test('keeps unknown condition codes as raw labels', () {
      final HomeMedication medication = HomeMedication.fromJson(
        <String, dynamic>{
          'id': 'med-3',
          'display_name': '미지의 약',
          'condition_tags': <String>['future_tag'],
        },
      );

      expect(medication.conditionTagLabels, <String>['future_tag']);
    });

    test('treats a missing items wrapper as empty', () {
      final HomeMedicationsResult result = HomeMedicationsResult.fromJson(
        <String, dynamic>{'unexpected': 1},
      );

      expect(result.items, isEmpty);
      expect(result.activeItems, isEmpty);
    });

    test('activeItems filters out deactivated rows', () {
      final HomeMedicationsResult result = HomeMedicationsResult.fromJson(
        <String, dynamic>{
          'items': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'med-1',
              'display_name': '활성약',
              'is_active': true,
            },
            <String, dynamic>{
              'id': 'med-2',
              'display_name': '비활성약',
              'is_active': false,
            },
          ],
        },
      );

      expect(result.items, hasLength(2));
      expect(result.activeItems, hasLength(1));
      expect(result.activeItems.single.displayName, '활성약');
    });
  });
}
