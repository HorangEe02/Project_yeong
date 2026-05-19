/// ``AuthRepository`` 단위 테스트 — Dio mock 으로 status code 분기 매핑 검증.
library;

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/features/auth/data/auth_repository.dart';
import 'package:lemon_healthcare/features/auth/domain/auth_errors.dart';
import 'package:lemon_healthcare/features/auth/domain/auth_models.dart';
import 'package:mocktail/mocktail.dart';

class _MockDio extends Mock implements Dio {}

ProfileInput _sampleProfile() => const ProfileInput(
      age: 30,
      sex: Sex.male,
      heightCm: 175,
      weightKg: 70,
    );

RegisterRequest _sampleRegister() => RegisterRequest(
      email: 'a@b.com',
      password: 'Password123!',
      profile: _sampleProfile(),
      consents: const <ConsentAccept>[
        ConsentAccept(consentType: 'service_terms', accepted: true),
        ConsentAccept(consentType: 'general_profile', accepted: true),
      ],
    );

Response<Map<String, dynamic>> _tokenResponseJson() =>
    Response<Map<String, dynamic>>(
      requestOptions: RequestOptions(path: '/x'),
      statusCode: 200,
      data: <String, dynamic>{
        'access_token': 'AT',
        'refresh_token': 'RT',
        'token_type': 'bearer',
        'expires_in_seconds': 900,
      },
    );

void main() {
  setUpAll(() {
    registerFallbackValue(RequestOptions(path: '/fallback'));
  });

  group('AuthRepository.login', () {
    test('200 → TokenResponse 매핑', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
        ),
      ).thenAnswer((_) async => _tokenResponseJson());

      final TokenResponse result = await AuthRepository(dio).login(
        const LoginRequest(email: 'a@b.com', password: 'p'),
      );
      expect(result.accessToken, equals('AT'));
      expect(result.refreshToken, equals('RT'));
    });

    test('401 → InvalidCredentialsException', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
        ),
      ).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/api/v1/auth/login'),
          response: Response<dynamic>(
            requestOptions: RequestOptions(path: '/api/v1/auth/login'),
            statusCode: 401,
            data: <String, dynamic>{'detail': 'Invalid credentials'},
          ),
        ),
      );

      expect(
        () => AuthRepository(dio).login(
          const LoginRequest(email: 'a@b.com', password: 'p'),
        ),
        throwsA(isA<InvalidCredentialsException>()),
      );
    });
  });

  group('AuthRepository.register', () {
    test('200 → TokenResponse', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
        ),
      ).thenAnswer((_) async => _tokenResponseJson());

      final TokenResponse result =
          await AuthRepository(dio).register(_sampleRegister());
      expect(result.accessToken, equals('AT'));
    });

    test('409 → EmailAlreadyExistsException', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
        ),
      ).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/api/v1/auth/register'),
          response: Response<dynamic>(
            requestOptions: RequestOptions(path: '/api/v1/auth/register'),
            statusCode: 409,
            data: <String, dynamic>{'detail': 'Email already registered'},
          ),
        ),
      );

      expect(
        () => AuthRepository(dio).register(_sampleRegister()),
        throwsA(isA<EmailAlreadyExistsException>()),
      );
    });

    test('422 + detail.code=consent_required → ConsentRequiredException', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
        ),
      ).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/api/v1/auth/register'),
          response: Response<dynamic>(
            requestOptions: RequestOptions(path: '/api/v1/auth/register'),
            statusCode: 422,
            data: <String, dynamic>{
              'detail': <String, dynamic>{
                'code': 'consent_required',
                'missing': <String>['chronic_disease', 'medications'],
              },
            },
          ),
        ),
      );

      try {
        await AuthRepository(dio).register(_sampleRegister());
        fail('ConsentRequiredException 가 raise 되어야 함');
      } on ConsentRequiredException catch (e) {
        expect(e.missing, equals(<String>['chronic_disease', 'medications']));
      }
    });
  });

  group('AuthRepository.refresh', () {
    test('200 → TokenResponse', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
        ),
      ).thenAnswer((_) async => _tokenResponseJson());

      final TokenResponse result = await AuthRepository(dio).refresh('RT');
      expect(result.accessToken, equals('AT'));
    });

    test('401 → RefreshFailedException', () async {
      final _MockDio dio = _MockDio();
      when(
        () => dio.post<Map<String, dynamic>>(
          any(),
          data: any<dynamic>(named: 'data'),
        ),
      ).thenThrow(
        DioException(
          requestOptions: RequestOptions(path: '/api/v1/auth/refresh'),
          response: Response<dynamic>(
            requestOptions: RequestOptions(path: '/api/v1/auth/refresh'),
            statusCode: 401,
          ),
        ),
      );

      expect(
        () => AuthRepository(dio).refresh('RT'),
        throwsA(isA<RefreshFailedException>()),
      );
    });
  });
}
