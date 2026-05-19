/// 영양제 사진 등록 — backend `POST /api/v1/supplements/register` Dio multipart wrapper.
library;

import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/network/dio_provider.dart';
import '../domain/supplement_models.dart';

part 'supplement_repository.g.dart';

class SupplementRepository {
  const SupplementRepository(this._dio);

  final Dio _dio;

  /// 영양제 라벨 이미지를 업로드하고 분석 결과를 받는다.
  ///
  /// [imagePath] 는 로컬 파일 경로 (image_cropper 결과). multipart field
  /// 이름은 백엔드 ``supplements.register_supplement`` 와 동일한 ``image``.
  /// [onProgress] 는 0.0~1.0 진행률 (multipart 송신 단계 — LLM 분석 시간은
  /// 미포함, UploadProgress 위젯에서 1.0 도달 후 "분석 중" 안내).
  ///
  /// DioException 은 raw rethrow — 사용자 친화 매핑은 SupplementNotifier
  /// 에서 처리 (auth_repository 의 InvalidCredentialsException 패턴과
  /// 달리 supplement 는 status code 종류가 많아 notifier 일원화가 깔끔).
  Future<SupplementResponse> register({
    required String imagePath,
    void Function(double progress)? onProgress,
  }) async {
    final FormData formData = FormData.fromMap(<String, dynamic>{
      'image': await MultipartFile.fromFile(
        imagePath,
        filename: 'supplement.jpg',
      ),
    });

    final Response<Map<String, dynamic>> response =
        await _dio.post<Map<String, dynamic>>(
      '/api/v1/supplements/register',
      data: formData,
      onSendProgress: (int sent, int total) {
        if (total > 0 && onProgress != null) {
          onProgress(sent / total);
        }
      },
    );

    final Map<String, dynamic>? data = response.data;
    if (data == null) {
      throw DioException(
        requestOptions: response.requestOptions,
        response: response,
        type: DioExceptionType.unknown,
        error: 'Empty response body',
      );
    }
    return SupplementResponse.fromJson(data);
  }
}

@riverpod
SupplementRepository supplementRepository(SupplementRepositoryRef ref) {
  return SupplementRepository(ref.watch(dioProvider));
}
