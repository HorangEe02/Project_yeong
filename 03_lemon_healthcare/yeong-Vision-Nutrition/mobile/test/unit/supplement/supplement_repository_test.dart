/// SupplementRepository 단위 테스트 — Dio mock + 임시 파일 + status 분기.
library;

import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/features/supplement/data/supplement_repository.dart';
import 'package:lemon_healthcare/features/supplement/domain/supplement_models.dart';
import 'package:mocktail/mocktail.dart';

class _MockDio extends Mock implements Dio {}

late File _tempImage;

Map<String, dynamic> _successJson() => <String, dynamic>{
      'supplement_id': '11111111-1111-1111-1111-111111111111',
      'product_name': '종합비타민',
      'manufacturer': '레몬제약',
      'ingredients': <Map<String, dynamic>>[
        <String, dynamic>{
          'code': 'vitamin_c_mg',
          'name_ko': '비타민 C',
          'amount': 1000.0,
          'unit': 'mg',
        },
      ],
      'unmatched_ingredient_names': <String>['루테인'],
      'diagnosis': <String, dynamic>{
        'diagnoses': <Map<String, dynamic>>[
          <String, dynamic>{
            'code': 'vitamin_c_mg',
            'name_ko': '비타민 C',
            'rda': 100.0,
            'ai': null,
            'ear': 75.0,
            'ul': 2000.0,
            'actual': 1000.0,
            'unit': 'mg',
            'ratio': 10.0,
            'status': 'excessive',
            'message_ko': '비타민 C 섭취가 권장량의 1000% 수준입니다.',
          },
        ],
        'deficient_count': 0,
        'risky_count': 0,
        'adequate_count': 0,
        'summary_message_ko': '요약',
      },
      'ocr_engine': 'google_vision_v1',
      'llm_engine': 'ollama:qwen3.5:9b',
      'elapsed_ms': 3420.5,
      'disclaimers': <String>['본 서비스 ...', '영양제는 ...'],
      'emergency_resources': <Map<String, String>>[
        <String, String>{'name': '정신건강위기상담', 'phone': '1577-0199'},
      ],
      'consult_professional_message_ko': '약사 상담 ...',
    };

Response<Map<String, dynamic>> _okResponse() =>
    Response<Map<String, dynamic>>(
      requestOptions:
          RequestOptions(path: '/api/v1/supplements/register'),
      statusCode: 200,
      data: _successJson(),
    );

DioException _statusError(int statusCode, {Map<String, dynamic>? body}) =>
    DioException(
      requestOptions:
          RequestOptions(path: '/api/v1/supplements/register'),
      response: Response<dynamic>(
        requestOptions:
            RequestOptions(path: '/api/v1/supplements/register'),
        statusCode: statusCode,
        data: body ?? <String, dynamic>{'detail': 'error'},
      ),
    );

void main() {
  setUpAll(() {
    registerFallbackValue(RequestOptions(path: '/fallback'));
  });

  setUp(() async {
    _tempImage = File(
      '${Directory.systemTemp.path}/supp_test_${DateTime.now().microsecondsSinceEpoch}.jpg',
    );
    await _tempImage.writeAsBytes(<int>[0xFF, 0xD8, 0xFF, 0xE0]);
  });

  tearDown(() async {
    if (_tempImage.existsSync()) {
      await _tempImage.delete();
    }
  });

  group('SupplementRepository.register', () {
    test('200 → SupplementResponse 전 필드 + nested 매핑', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
          onSendProgress: any<ProgressCallback?>(named: 'onSendProgress'),
        ),
      ).thenAnswer((_) async => _okResponse());

      final SupplementResponse result =
          await SupplementRepository(dio).register(imagePath: _tempImage.path);

      expect(result.supplementId, '11111111-1111-1111-1111-111111111111');
      expect(result.productName, '종합비타민');
      expect(result.manufacturer, '레몬제약');
      expect(result.ingredients, hasLength(1));
      expect(result.ingredients.first.code, 'vitamin_c_mg');
      expect(result.ingredients.first.nameKo, '비타민 C');
      expect(result.ingredients.first.amount, 1000.0);
      expect(result.unmatchedIngredientNames, equals(<String>['루테인']));
      expect(result.diagnosis.diagnoses, hasLength(1));
      expect(
        result.diagnosis.diagnoses.first.status,
        NutrientStatus.excessive,
      );
      expect(result.diagnosis.diagnoses.first.rda, 100.0);
      expect(result.diagnosis.diagnoses.first.ai, isNull);
      expect(result.diagnosis.diagnoses.first.ul, 2000.0);
      expect(result.diagnosis.diagnoses.first.ratio, 10.0);
      expect(result.ocrEngine, 'google_vision_v1');
      expect(result.llmEngine, 'ollama:qwen3.5:9b');
      expect(result.elapsedMs, 3420.5);
      expect(result.disclaimers, hasLength(2));
      expect(result.emergencyResources, hasLength(1));
      expect(result.emergencyResources.first.name, '정신건강위기상담');
      expect(result.emergencyResources.first.phone, '1577-0199');
      expect(result.consultProfessionalMessageKo, '약사 상담 ...');
    });

    test('onSendProgress 콜백 호출 (0.5 → 1.0)', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
          onSendProgress: any<ProgressCallback?>(named: 'onSendProgress'),
        ),
      ).thenAnswer((Invocation invocation) async {
        final ProgressCallback? cb =
            invocation.namedArguments[#onSendProgress] as ProgressCallback?;
        cb?.call(50, 100);
        cb?.call(100, 100);
        return _okResponse();
      });

      final List<double> progresses = <double>[];
      await SupplementRepository(dio).register(
        imagePath: _tempImage.path,
        onProgress: progresses.add,
      );
      expect(progresses, equals(<double>[0.5, 1]));
    });

    test('400 → DioException raw rethrow', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
          onSendProgress: any<ProgressCallback?>(named: 'onSendProgress'),
        ),
      ).thenThrow(_statusError(400));

      await expectLater(
        SupplementRepository(dio).register(imagePath: _tempImage.path),
        throwsA(
          isA<DioException>().having(
            (DioException e) => e.response?.statusCode,
            'statusCode',
            400,
          ),
        ),
      );
    });

    test('422 → DioException raw rethrow', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
          onSendProgress: any<ProgressCallback?>(named: 'onSendProgress'),
        ),
      ).thenThrow(_statusError(422));

      await expectLater(
        SupplementRepository(dio).register(imagePath: _tempImage.path),
        throwsA(
          isA<DioException>().having(
            (DioException e) => e.response?.statusCode,
            'statusCode',
            422,
          ),
        ),
      );
    });

    test('429 → DioException raw rethrow', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
          onSendProgress: any<ProgressCallback?>(named: 'onSendProgress'),
        ),
      ).thenThrow(_statusError(429));

      await expectLater(
        SupplementRepository(dio).register(imagePath: _tempImage.path),
        throwsA(
          isA<DioException>().having(
            (DioException e) => e.response?.statusCode,
            'statusCode',
            429,
          ),
        ),
      );
    });
  });
}
