import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';

void main() {
  group('ComprehensiveDietAnalysis.fromJson', () {
    test('parses a full comprehensive diet analysis payload', () {
      final ComprehensiveDietAnalysis analysis =
          ComprehensiveDietAnalysis.fromJson(<String, dynamic>{
            'diet_score': 78,
            'diet_score_label': '균형이 잘 잡혔어요',
            'diet_score_message': '나트륨만 조금 줄이면 좋아요.',
            'diet_score_confidence': 0.9,
            'deficient_nutrients': <Object?>[
              <String, dynamic>{
                'nutrient_code': 'protein_g',
                'nutrient_name': '단백질',
                'current_intake': 18,
                'recommended_intake': 50,
                'deficit_ratio': 0.64,
                'unit': 'g',
                'confidence': 0.7,
                'message': '단백질이 더 필요해요.',
              },
            ],
            'excessive_nutrients': <Object?>[
              <String, dynamic>{
                'nutrient_code': 'sodium_mg',
                'nutrient_name': '나트륨',
                'current_intake': 2200,
                'upper_limit': 2000,
                'excess_ratio': 1.1,
                'unit': 'mg',
                'confidence': 0.5,
                'message': '나트륨을 조금 줄여보세요.',
              },
            ],
            'cautionary_components': <Object?>[
              <String, dynamic>{
                'component': '카페인',
                'reason': '늦은 시간 섭취',
                'severity': 'high',
                'message': '저녁 섭취는 피하는 게 좋아요.',
                'source_citation': 'caffeine.md',
              },
            ],
            'purpose_targets': <Object?>[
              <String, dynamic>{
                'condition': '당뇨',
                'relevance_score': 0.8,
                'evidence_level': 'moderate',
                'message': 'GI 지수를 함께 확인해보세요.',
                'source_citation': 'diabetes-gi.md',
              },
            ],
            'chronic_disease_indications': <String>['type_2_diabetes'],
            'warnings': <String>['estimate_only'],
          });

      expect(analysis.hasScore, isTrue);
      expect(analysis.dietScore, 78);
      expect(analysis.dietScoreLabel, '균형이 잘 잡혔어요');
      expect(analysis.dietScoreConfidence, 0.9);
      expect(analysis.deficientNutrients.single.nutrientName, '단백질');
      expect(analysis.deficientNutrients.single.deficitRatio, 0.64);
      expect(analysis.excessiveNutrients.single.upperLimit, 2000);
      expect(analysis.excessiveNutrients.single.excessRatio, 1.1);
      expect(analysis.cautionaryComponents.single.component, '카페인');
      expect(analysis.cautionaryComponents.single.severity, 'high');
      expect(
        analysis.cautionaryComponents.single.sourceCitation,
        'caffeine.md',
      );
      expect(analysis.purposeTargets.single.condition, '당뇨');
      expect(analysis.purposeTargets.single.message, 'GI 지수를 함께 확인해보세요.');
      expect(analysis.chronicDiseaseIndications, <String>['type_2_diabetes']);
      expect(analysis.warnings, <String>['estimate_only']);
      expect(analysis.hasContent, isTrue);
    });

    test('parses an empty payload without a score and hides content', () {
      final ComprehensiveDietAnalysis analysis =
          ComprehensiveDietAnalysis.fromJson(<String, dynamic>{});

      expect(analysis.hasScore, isFalse);
      expect(analysis.hasContent, isFalse);
      expect(analysis.deficientNutrients, isEmpty);
      expect(analysis.excessiveNutrients, isEmpty);
      expect(analysis.cautionaryComponents, isEmpty);
      expect(analysis.purposeTargets, isEmpty);
      expect(analysis.chronicDiseaseIndications, isEmpty);
    });

    test('serializes a comprehensive ingredient input to backend keys', () {
      const ComprehensiveIngredientInput input = ComprehensiveIngredientInput(
        displayName: '탄수화물',
        nutrientCode: 'carbohydrate_g',
        amount: 78,
        unit: 'g',
      );

      expect(input.toJson(), <String, Object?>{
        'display_name': '탄수화물',
        'nutrient_code': 'carbohydrate_g',
        'amount': 78.0,
        'unit': 'g',
      });
    });
  });
}
