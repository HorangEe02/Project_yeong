/// SupplementNotifier 단위 테스트 — 4 상태 전이 + DioException → 한국어 매핑.
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/features/supplement/data/supplement_repository.dart';
import 'package:lemon_healthcare/features/supplement/domain/supplement_models.dart';
import 'package:lemon_healthcare/features/supplement/presentation/providers/supplement_notifier.dart';
import 'package:lemon_healthcare/shared/models/emergency_contact.dart';
import 'package:mocktail/mocktail.dart';

class _MockRepo extends Mock implements SupplementRepository {}

SupplementResponse _fakeResponse() => const SupplementResponse(
      supplementId: 'sup-1',
      productName: '종합비타민',
      manufacturer: null,
      ingredients: <Ingredient>[],
      unmatchedIngredientNames: <String>[],
      diagnosis: DiagnosisResult(
        diagnoses: <NutrientDiagnosis>[],
        deficientCount: 0,
        riskyCount: 0,
        adequateCount: 0,
        summaryMessageKo: '요약',
      ),
      ocrEngine: 'google_vision_v1',
      llmEngine: 'ollama',
      elapsedMs: 100,
      disclaimers: <String>[],
      emergencyResources: <EmergencyContact>[],
      consultProfessionalMessageKo: '상담',
    );

DioException _statusError(int statusCode) => DioException(
      requestOptions: RequestOptions(path: '/api/v1/supplements/register'),
      response: Response<dynamic>(
        requestOptions:
            RequestOptions(path: '/api/v1/supplements/register'),
        statusCode: statusCode,
        data: <String, dynamic>{'detail': 'x'},
      ),
    );

DioException _timeoutError() => DioException(
      requestOptions: RequestOptions(path: '/api/v1/supplements/register'),
      type: DioExceptionType.connectionTimeout,
    );

ProviderContainer _makeContainer(_MockRepo repo) {
  return ProviderContainer(
    overrides: <Override>[
      supplementRepositoryProvider.overrideWithValue(repo),
    ],
  );
}

Future<String> _runAndGetErrorMessage(
  _MockRepo repo,
  Object errorToThrow,
) async {
  when(
    () => repo.register(
      imagePath: any<String>(named: 'imagePath'),
      onProgress: any<void Function(double)?>(named: 'onProgress'),
    ),
  ).thenThrow(errorToThrow);
  final ProviderContainer container = _makeContainer(repo);
  addTearDown(container.dispose);
  await container
      .read(supplementNotifierProvider.notifier)
      .register('/tmp/x.jpg');
  final SupplementState state = container.read(supplementNotifierProvider);
  expect(state, isA<SupplementError>());
  return (state as SupplementError).message;
}

void main() {
  setUpAll(() {
    registerFallbackValue(RequestOptions(path: '/fallback'));
  });

  group('SupplementNotifier', () {
    test('초기 state = SupplementIdle', () {
      final _MockRepo repo = _MockRepo();
      final ProviderContainer container = _makeContainer(repo);
      addTearDown(container.dispose);

      expect(
        container.read(supplementNotifierProvider),
        isA<SupplementIdle>(),
      );
    });

    test('register 성공 → Uploading(progress) 전이 → Success', () async {
      final _MockRepo repo = _MockRepo();
      when(
        () => repo.register(
          imagePath: any<String>(named: 'imagePath'),
          onProgress: any<void Function(double)?>(named: 'onProgress'),
        ),
      ).thenAnswer((Invocation inv) async {
        final void Function(double)? cb =
            inv.namedArguments[#onProgress] as void Function(double)?;
        cb?.call(0.5);
        return _fakeResponse();
      });

      final ProviderContainer container = _makeContainer(repo);
      addTearDown(container.dispose);

      final List<SupplementState> captured = <SupplementState>[];
      container.listen<SupplementState>(
        supplementNotifierProvider,
        (SupplementState? _, SupplementState next) {
          captured.add(next);
        },
      );

      await container
          .read(supplementNotifierProvider.notifier)
          .register('/tmp/img.jpg');

      expect(
        container.read(supplementNotifierProvider),
        isA<SupplementSuccess>(),
      );
      expect(
        captured.any(
          (SupplementState s) =>
              s is SupplementUploading && s.progress == 0.0,
        ),
        isTrue,
        reason: 'Uploading(0) 초기 전이',
      );
      expect(
        captured.any(
          (SupplementState s) =>
              s is SupplementUploading && s.progress == 0.5,
        ),
        isTrue,
        reason: 'onProgress(0.5) 콜백 반영',
      );
    });

    test('reset → SupplementIdle 복귀', () async {
      final _MockRepo repo = _MockRepo();
      when(
        () => repo.register(
          imagePath: any<String>(named: 'imagePath'),
          onProgress: any<void Function(double)?>(named: 'onProgress'),
        ),
      ).thenThrow(_statusError(500));

      final ProviderContainer container = _makeContainer(repo);
      addTearDown(container.dispose);

      await container
          .read(supplementNotifierProvider.notifier)
          .register('/tmp/x.jpg');
      expect(
        container.read(supplementNotifierProvider),
        isA<SupplementError>(),
      );

      container.read(supplementNotifierProvider.notifier).reset();
      expect(
        container.read(supplementNotifierProvider),
        isA<SupplementIdle>(),
      );
    });
  });

  group('SupplementNotifier._mapDioError (한국어 매핑)', () {
    test('400 → 이미지 형식/크기 문제', () async {
      expect(
        await _runAndGetErrorMessage(_MockRepo(), _statusError(400)),
        '이미지 형식 또는 크기에 문제가 있습니다.',
      );
    });

    test('401 → 다시 로그인 안내', () async {
      expect(
        await _runAndGetErrorMessage(_MockRepo(), _statusError(401)),
        '다시 로그인해주세요.',
      );
    });

    test('403 → 동의 재확인 안내', () async {
      expect(
        await _runAndGetErrorMessage(_MockRepo(), _statusError(403)),
        '필요한 동의를 다시 확인해주세요.',
      );
    });

    test('422 → OCR/LLM 실패 안내', () async {
      expect(
        await _runAndGetErrorMessage(_MockRepo(), _statusError(422)),
        '영양제 정보를 인식하지 못했습니다. 다른 사진으로 시도해주세요.',
      );
    });

    test('429 → 분당 한도 안내', () async {
      expect(
        await _runAndGetErrorMessage(_MockRepo(), _statusError(429)),
        '잠시 후 다시 시도해주세요. (분당 요청 한도 초과)',
      );
    });

    test('500 → 서버 오류 안내', () async {
      expect(
        await _runAndGetErrorMessage(_MockRepo(), _statusError(500)),
        '서버 오류입니다. 잠시 후 다시 시도해주세요.',
      );
    });

    test('connectionTimeout → 네트워크 안내', () async {
      expect(
        await _runAndGetErrorMessage(_MockRepo(), _timeoutError()),
        '네트워크 연결이 느립니다. Wi-Fi 환경에서 시도해주세요.',
      );
    });

    test('DioException without statusCode → 일반 예상치 못한 오류', () async {
      expect(
        await _runAndGetErrorMessage(
          _MockRepo(),
          DioException(
            requestOptions: RequestOptions(path: '/x'),
            type: DioExceptionType.unknown,
          ),
        ),
        '예상치 못한 오류가 발생했습니다.',
      );
    });

    test('Non-DioException → 일반 예상치 못한 오류', () async {
      expect(
        await _runAndGetErrorMessage(_MockRepo(), Exception('boom')),
        '예상치 못한 오류가 발생했습니다.',
      );
    });
  });
}
