/// 영양제 등록 상태 Notifier — sealed state + DioException → 한국어 매핑.
library;

import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../data/supplement_repository.dart';
import '../../domain/supplement_models.dart';

part 'supplement_notifier.g.dart';

/// 등록 흐름의 4 상태 — sealed 라서 SupplementCaptureScreen 의
/// `switch` 가 누락된 case 를 컴파일타임에 감지.
sealed class SupplementState {
  const SupplementState();
}

class SupplementIdle extends SupplementState {
  const SupplementIdle();
}

class SupplementUploading extends SupplementState {
  const SupplementUploading(this.progress);

  /// 0.0 ~ 1.0. multipart 송신 진행률 — LLM 분석 시간은 미포함.
  final double progress;
}

class SupplementSuccess extends SupplementState {
  const SupplementSuccess(this.response);

  final SupplementResponse response;
}

class SupplementError extends SupplementState {
  const SupplementError(this.message);

  /// 사용자 노출 한국어 메시지. raw status code 또는 영어 detail X.
  final String message;
}

@riverpod
class SupplementNotifier extends _$SupplementNotifier {
  @override
  SupplementState build() => const SupplementIdle();

  /// 카메라/갤러리 + image_cropper 결과 [imagePath] 를 업로드.
  Future<void> register(String imagePath) async {
    state = const SupplementUploading(0);
    try {
      final SupplementResponse response =
          await ref.read(supplementRepositoryProvider).register(
                imagePath: imagePath,
                onProgress: (double progress) {
                  state = SupplementUploading(progress);
                },
              );
      state = SupplementSuccess(response);
    } on DioException catch (e) {
      state = SupplementError(_mapDioError(e));
    } catch (_) {
      state = const SupplementError('예상치 못한 오류가 발생했습니다.');
    }
  }

  /// "다시 등록" / 에러 후 복귀 — Idle 로 리셋.
  void reset() {
    state = const SupplementIdle();
  }

  /// DioException → 사용자 친화 한국어 메시지.
  ///
  /// 백엔드 supplements 엔드포인트 매핑:
  ///   400 → 이미지 검증 실패 (포맷·크기·security 차단)
  ///   401 → AuthInterceptor refresh 실패 잔여 (logout 곧 발생)
  ///   403 → ConsentService.require() — 만성질환/복약 동의 누락
  ///   422 → OCR/LLM/MFDS 매칭 실패
  ///   429 → check_register_rate_limit (10/min)
  ///   5xx → 서버 오류
  String _mapDioError(DioException e) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.sendTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return '네트워크 연결이 느립니다. Wi-Fi 환경에서 시도해주세요.';
    }
    final int? code = e.response?.statusCode;
    switch (code) {
      case 400:
        return '이미지 형식 또는 크기에 문제가 있습니다.';
      case 401:
        return '다시 로그인해주세요.';
      case 403:
        return '필요한 동의를 다시 확인해주세요.';
      case 422:
        return '영양제 정보를 인식하지 못했습니다. 다른 사진으로 시도해주세요.';
      case 429:
        return '잠시 후 다시 시도해주세요. (분당 요청 한도 초과)';
      case 500:
      case 502:
      case 503:
      case 504:
        return '서버 오류입니다. 잠시 후 다시 시도해주세요.';
      default:
        return '예상치 못한 오류가 발생했습니다.';
    }
  }
}
