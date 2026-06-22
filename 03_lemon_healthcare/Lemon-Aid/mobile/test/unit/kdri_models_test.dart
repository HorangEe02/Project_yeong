import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';

void main() {
  group('KdriReference.fromJson', () {
    test('parses a full reference row', () {
      final KdriReference reference = KdriReference.fromJson(<String, dynamic>{
        'nutrient_code': 'vitamin_c_mg',
        'nutrient_name_ko': '비타민 C',
        'reference_type': 'RDA',
        'reference_amount': 100,
        'reference_unit': 'mg',
        'ul_amount': 2000,
        'ul_unit': 'mg',
        'review_status': 'reviewed',
      });

      expect(reference.nutrientCode, 'vitamin_c_mg');
      expect(reference.nutrientNameKo, '비타민 C');
      expect(reference.referenceType, 'RDA');
      expect(reference.referenceAmount, 100);
      expect(reference.referenceUnit, 'mg');
      expect(reference.ulAmount, 2000);
      expect(reference.ulUnit, 'mg');
      expect(reference.reviewStatus, 'reviewed');
    });

    test('tolerates null optional fields including ul and reference amount', () {
      final KdriReference reference = KdriReference.fromJson(<String, dynamic>{
        'nutrient_code': 'water_ml',
        'reference_type': 'AI',
        'reference_amount': null,
        'reference_unit': 'mL',
      });

      expect(reference.nutrientNameKo, isNull);
      expect(reference.referenceAmount, isNull);
      expect(reference.ulAmount, isNull);
      expect(reference.ulUnit, isNull);
      expect(reference.reviewStatus, isNull);
    });
  });

  group('KdriLookupResult', () {
    test('parses references and dataset metadata', () {
      final KdriLookupResult result = KdriLookupResult.fromJson(
        <String, dynamic>{
          'references': <Object?>[
            <String, dynamic>{
              'nutrient_code': 'vitamin_c_mg',
              'reference_type': 'RDA',
              'reference_amount': 100,
              'reference_unit': 'mg',
              'ul_amount': 2000,
            },
          ],
          'dataset_status': 'sample',
          'dataset_version': 'kdris-2020-sample',
          'note': '참고 문구',
        },
      );

      expect(result.references, hasLength(1));
      expect(result.datasetStatus, 'sample');
      expect(result.datasetVersion, 'kdris-2020-sample');
      expect(result.note, '참고 문구');
      expect(result.isOfficialDataset, isFalse);
    });

    test('marks official dataset status', () {
      final KdriLookupResult result = KdriLookupResult.fromJson(
        <String, dynamic>{
          'references': <Object?>[],
          'dataset_status': 'official',
          'dataset_version': 'kdris-2020',
        },
      );

      expect(result.isOfficialDataset, isTrue);
      expect(result.note, isNull);
    });

    test('referenceFor matches by nutrient code and returns null otherwise', () {
      final KdriLookupResult result = KdriLookupResult.fromJson(
        <String, dynamic>{
          'references': <Object?>[
            <String, dynamic>{
              'nutrient_code': 'vitamin_c_mg',
              'reference_type': 'RDA',
              'reference_amount': 100,
              'reference_unit': 'mg',
            },
          ],
          'dataset_status': 'sample',
          'dataset_version': 'v1',
        },
      );

      expect(result.referenceFor('vitamin_c_mg')?.referenceAmount, 100);
      expect(result.referenceFor('iron_mg'), isNull);
      expect(result.referenceFor(null), isNull);
      expect(result.referenceFor('  '), isNull);
    });
  });
}
