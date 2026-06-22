import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

import '../../../core/config/app_config.dart';
import '../../../core/network/lemon_api_client.dart';
import '../domain/supplement_analysis_preview.dart';

class SupplementCaptureRepository {
  SupplementCaptureRepository({
    LemonApiClient? client,
    AppConfig? config,
  }) : _client = client ??
            LemonApiClient(config: config ?? AppConfig.fromEnvironment());

  final LemonApiClient _client;

  Future<void> grantOcrImageProcessingConsent() async {
    await _client.postJson(
      '/api/v1/me/privacy/consents/ocr_image_processing',
      <String, dynamic>{},
    );
  }

  Future<void> grantSensitiveHealthAnalysisConsent() async {
    await _client.postJson(
      '/api/v1/me/privacy/consents/sensitive_health_analysis',
      <String, dynamic>{},
    );
  }

  Future<SupplementAnalysisPreview> analyzeLabelImage(XFile image) async {
    final List<int> bytes = await image.readAsBytes();
    final FormData formData = FormData.fromMap(<String, dynamic>{
      'client_request_id':
          'mobile-supplement-${DateTime.now().millisecondsSinceEpoch}',
      'image': MultipartFile.fromBytes(bytes, filename: image.name),
    });
    final Response<Map<String, dynamic>> response = await _client.postMultipart(
      '/api/v1/supplements/analyze',
      formData,
    );
    return SupplementAnalysisPreview.fromJson(
      response.data ?? <String, dynamic>{},
    );
  }

  Future<void> saveConfirmedSupplement(SupplementConfirmedInput input) async {
    await grantSensitiveHealthAnalysisConsent();
    await _client.postJson(
      '/api/v1/supplements',
      input.toJson(),
    );
  }
}
