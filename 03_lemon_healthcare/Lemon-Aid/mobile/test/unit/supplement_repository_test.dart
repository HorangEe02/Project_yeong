import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';

void main() {
  test(
    'uses configured OCR provider by default on supplement upload',
    () async {
      final File image = _writeTinyPng();
      addTearDown(() {
        if (image.existsSync()) {
          image.deleteSync();
        }
      });
      late http.MultipartRequest capturedRequest;
      final ApiClient apiClient = ApiClient(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: _CaptureMultipartClient(
          onRequest: (http.MultipartRequest request) {
            capturedRequest = request;
          },
        ),
      );
      addTearDown(apiClient.close);
      final BackendLemonAidRepository repository = BackendLemonAidRepository(
        apiClient: apiClient,
      );

      await repository.analyzeSupplementImage(image.path);

      expect(capturedRequest.fields['ocr_provider'], 'configured');
      expect(
        capturedRequest.fields['client_request_id'],
        startsWith('mobile-'),
      );
      expect(capturedRequest.files.single.field, 'image');
      expect(capturedRequest.files.single.contentType.mimeType, 'image/png');
    },
  );

  test('passes selected OCR provider on supplement image upload', () async {
    final File image = _writeTinyPng();
    addTearDown(() {
      if (image.existsSync()) {
        image.deleteSync();
      }
    });
    late http.MultipartRequest capturedRequest;
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: _CaptureMultipartClient(
        onRequest: (http.MultipartRequest request) {
          capturedRequest = request;
        },
      ),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    await repository.analyzeSupplementImage(
      image.path,
      ocrProvider: 'google_vision',
    );

    expect(capturedRequest.fields['ocr_provider'], 'google_vision');
    expect(capturedRequest.files.single.field, 'image');
    expect(capturedRequest.files.single.contentType.mimeType, 'image/png');
  });

  test('uploads meal images to the food analysis endpoint', () async {
    final File image = _writeTinyPng(fileName: 'meal.png');
    addTearDown(() {
      if (image.existsSync()) {
        image.deleteSync();
      }
    });
    late http.MultipartRequest capturedRequest;
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: _CaptureMultipartClient(
        responseBody: _mealPreviewResponse,
        onRequest: (http.MultipartRequest request) {
          capturedRequest = request;
        },
      ),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final MealImageAnalysisPreview response = await repository.analyzeMealImage(
      image.path,
      mealType: 'lunch',
    );

    expect(capturedRequest.url.path, '/api/v1/meals/analyze-image');
    expect(capturedRequest.fields['meal_type'], 'lunch');
    expect(
      capturedRequest.fields['client_request_id'],
      startsWith('mobile-meal-'),
    );
    expect(capturedRequest.files.single.field, 'image');
    expect(capturedRequest.files.single.contentType.mimeType, 'image/png');
    expect(response.foodCandidates.single.displayName, '비빔밥');
    expect(response.pipelineMetadata.detectorUsed, isTrue);
  });

  test(
    'confirms meal image preview through meal confirmation endpoint',
    () async {
      late http.Request capturedRequest;
      final ApiClient apiClient = ApiClient(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: _CaptureJsonClient(
          responseBody: _mealRecordResponse,
          onRequest: (http.Request request) {
            capturedRequest = request;
          },
        ),
      );
      addTearDown(apiClient.close);
      final BackendLemonAidRepository repository = BackendLemonAidRepository(
        apiClient: apiClient,
      );

      final MealRecordResponse response = await repository
          .confirmMealImagePreview(
            '00000000-0000-0000-0000-000000000201',
            const MealConfirmationRequest(
              analysisId: '00000000-0000-0000-0000-000000000101',
              mealType: 'lunch',
              foodItems: <MealFoodItemInput>[
                MealFoodItemInput(
                  displayName: '비빔밥',
                  kcal: 520,
                  confidence: 0.88,
                  source: 'vision',
                ),
              ],
            ),
          );

      final Map<String, dynamic> body =
          jsonDecode(capturedRequest.body) as Map<String, dynamic>;
      expect(
        capturedRequest.url.path,
        '/api/v1/meals/00000000-0000-0000-0000-000000000201/confirm',
      );
      expect(body['analysis_id'], '00000000-0000-0000-0000-000000000101');
      expect(body['user_confirmed'], isTrue);
      expect(
        (body['food_items'] as List<Object?>).single,
        containsPair('display_name', '비빔밥'),
      );
      expect(response.status, 'confirmed');
      expect(response.foodItems.single.displayName, '비빔밥');
    },
  );

  test('uploads multiple supplement images with role metadata', () async {
    final File front = _writeTinyPng(fileName: 'front.png');
    final File facts = _writeTinyPng(fileName: 'facts.png');
    addTearDown(() {
      for (final File image in <File>[front, facts]) {
        if (image.existsSync()) {
          image.deleteSync();
        }
      }
    });
    final _SessionFlowClient flowClient = _SessionFlowClient();
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: flowClient,
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final SupplementMultiImageAnalysisPreview response = await repository
        .analyzeSupplementImages(<SupplementImageUpload>[
          SupplementImageUpload(path: front.path, role: 'front_label'),
          SupplementImageUpload(path: facts.path, role: 'supplement_facts'),
        ], ocrProvider: 'clova');

    expect(
      flowClient.requests.map((http.BaseRequest request) => request.url.path),
      <String>[
        '/api/v1/supplements/analysis-sessions',
        '/api/v1/supplements/analysis-sessions/multi-test/images',
        '/api/v1/supplements/analysis-sessions/multi-test/images',
        '/api/v1/supplements/analysis-sessions/multi-test/finalize',
      ],
    );
    final http.MultipartRequest frontRequest =
        flowClient.requests[1] as http.MultipartRequest;
    final http.MultipartRequest factsRequest =
        flowClient.requests[2] as http.MultipartRequest;
    expect(frontRequest.fields['ocr_provider'], 'clova');
    expect(frontRequest.fields['image_role'], 'front_label');
    expect(frontRequest.fields['client_request_id'], startsWith('mobile-'));
    expect(factsRequest.fields['ocr_provider'], 'clova');
    expect(factsRequest.fields['image_role'], 'supplement_facts');
    expect(
      <String>[
        frontRequest.files.single.field,
        factsRequest.files.single.field,
      ],
      <String>['image', 'image'],
    );
    expect(response.analysisGroupId, 'multi-test');
    expect(response.imageCount, 2);
    expect(
      response.primaryPreview?.analysisId,
      '00000000-0000-0000-0000-000000000001',
    );
  });

  test(
    'one-shot single-product batch posts all images in one analyze-multi request',
    () async {
      final File front = _writeTinyPng(fileName: 'one-front.png');
      final File facts = _writeTinyPng(fileName: 'one-facts.png');
      addTearDown(() {
        for (final File image in <File>[front, facts]) {
          if (image.existsSync()) {
            image.deleteSync();
          }
        }
      });
      final _OneShotFlowClient oneShotClient = _OneShotFlowClient();
      final ApiClient apiClient = ApiClient(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: oneShotClient,
      );
      addTearDown(apiClient.close);
      final BackendLemonAidRepository repository = BackendLemonAidRepository(
        apiClient: apiClient,
      );

      final SupplementMultiImageAnalysisPreview response = await repository
          .analyzeSupplementImagesOneShot(<SupplementImageUpload>[
            SupplementImageUpload(path: front.path, role: 'front_label'),
            SupplementImageUpload(path: facts.path, role: 'intake_method'),
          ], ocrProvider: 'clova');

      // Exactly ONE request to the fusion route (not the 4-call session flow).
      expect(
        oneShotClient.requests.map((http.BaseRequest r) => r.url.path),
        <String>['/api/v1/supplements/analyze-multi'],
      );
      final http.MultipartRequest request =
          oneShotClient.requests.single as http.MultipartRequest;
      expect(request.fields['ocr_provider'], 'clova');
      expect(request.fields['merge_strategy'], 'single_product');
      expect(
        request.fields['image_roles_json'],
        jsonEncode(<String>['front_label', 'intake_method']),
      );
      // Both images travel in one multipart request under the 'images' field.
      expect(
        request.files.map((http.MultipartFile f) => f.field).toList(),
        <String>['images', 'images'],
      );
      expect(response.analysisGroupId, 'multi-test');
    },
  );

  test('rejects unsupported multi-image role before upload', () async {
    final File image = _writeTinyPng();
    addTearDown(() {
      if (image.existsSync()) {
        image.deleteSync();
      }
    });
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: _CaptureMultipartClient(onRequest: (_) {}),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    expect(
      () => repository.analyzeSupplementImages(<SupplementImageUpload>[
        SupplementImageUpload(path: image.path, role: 'free_text'),
      ]),
      throwsArgumentError,
    );
  });

  test(
    'finalizes an existing multi-image supplement analysis session',
    () async {
      late http.Request capturedRequest;
      final ApiClient apiClient = ApiClient(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: _CaptureJsonClient(
          responseBody: _multiPreviewResponse,
          onRequest: (http.Request request) {
            capturedRequest = request;
          },
        ),
      );
      addTearDown(apiClient.close);
      final BackendLemonAidRepository repository = BackendLemonAidRepository(
        apiClient: apiClient,
      );

      final SupplementMultiImageAnalysisPreview response = await repository
          .finalizeSupplementAnalysisSession('multi-test');

      expect(
        capturedRequest.url.path,
        '/api/v1/supplements/analysis-sessions/multi-test/finalize',
      );
      expect(capturedRequest.body, isEmpty);
      expect(response.analysisGroupId, 'multi-test');
      expect(response.primaryPreview?.analysisId, isNotEmpty);
    },
  );

  test('rejects blank multi-image analysis group before finalize', () async {
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: _CaptureJsonClient(onRequest: (_) {}),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    expect(
      () => repository.finalizeSupplementAnalysisSession(' '),
      throwsArgumentError,
    );
  });

  test(
    'sniffs image content type when selected path has no extension',
    () async {
      final File image = _writeTinyPng(fileName: 'label');
      addTearDown(() {
        if (image.existsSync()) {
          image.deleteSync();
        }
      });
      late http.MultipartRequest capturedRequest;
      final ApiClient apiClient = ApiClient(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: _CaptureMultipartClient(
          onRequest: (http.MultipartRequest request) {
            capturedRequest = request;
          },
        ),
      );
      addTearDown(apiClient.close);
      final BackendLemonAidRepository repository = BackendLemonAidRepository(
        apiClient: apiClient,
      );

      await repository.analyzeSupplementImage(image.path);

      expect(capturedRequest.files.single.contentType.mimeType, 'image/png');
    },
  );

  test('adds development gateway token header on supplement upload', () async {
    final File image = _writeTinyPng();
    addTearDown(() {
      if (image.existsSync()) {
        image.deleteSync();
      }
    });
    late http.MultipartRequest capturedRequest;
    final ApiClient apiClient = ApiClient(
      baseUrl: 'https://example.ngrok.app/api/v1',
      devGatewayToken: 'debug-gateway-token',
      httpClient: _CaptureMultipartClient(
        onRequest: (http.MultipartRequest request) {
          capturedRequest = request;
        },
      ),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    await repository.analyzeSupplementImage(image.path);

    expect(
      capturedRequest.headers['X-Lemon-Dev-Gateway-Token'],
      'debug-gateway-token',
    );
    expect(capturedRequest.headers, isNot(contains('Authorization')));
  });

  test('adds configured JWT bearer token on supplement upload', () async {
    final File image = _writeTinyPng();
    addTearDown(() {
      if (image.existsSync()) {
        image.deleteSync();
      }
    });
    late http.MultipartRequest capturedRequest;
    final ApiClient apiClient = ApiClient(
      baseUrl: 'https://api.example.com/api/v1',
      bearerToken: 'jwt-access-token',
      httpClient: _CaptureMultipartClient(
        onRequest: (http.MultipartRequest request) {
          capturedRequest = request;
        },
      ),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    await repository.analyzeSupplementImage(image.path);

    expect(capturedRequest.headers['Authorization'], 'Bearer jwt-access-token');
    expect(capturedRequest.fields['ocr_provider'], 'configured');
  });

  test(
    'requests local Ollama explanation through the existing endpoint',
    () async {
      late http.Request capturedRequest;
      final ApiClient apiClient = ApiClient(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: _CaptureJsonClient(
          onRequest: (http.Request request) {
            capturedRequest = request;
          },
        ),
      );
      addTearDown(apiClient.close);
      final BackendLemonAidRepository repository = BackendLemonAidRepository(
        apiClient: apiClient,
      );
      final SupplementImpactPreviewResponse preview =
          SupplementImpactPreviewResponse.fromJson(_impactPreviewResponse);

      final SupplementRecommendationExplainResponse response = await repository
          .explainSupplementRecommendation(preview, useLocalLlm: true);

      final Map<String, dynamic> body =
          jsonDecode(capturedRequest.body) as Map<String, dynamic>;
      expect(
        capturedRequest.url.path,
        '/api/v1/supplements/recommendations/explain',
      );
      expect(body['use_local_llm'], isTrue);
      expect(response.llmUsed, isTrue);
      expect(response.sourceCitations.single.sourcePath, 'vitamin-d.md');
    },
  );

  test(
    'uses latest recommendation endpoint for default impact preview',
    () async {
      late http.Request capturedRequest;
      final ApiClient apiClient = ApiClient(
        baseUrl: 'http://localhost:8000/api/v1',
        httpClient: _CaptureJsonClient(
          responseBody: _impactPreviewResponse,
          onRequest: (http.Request request) {
            capturedRequest = request;
          },
        ),
      );
      addTearDown(apiClient.close);
      final BackendLemonAidRepository repository = BackendLemonAidRepository(
        apiClient: apiClient,
      );

      final SupplementImpactPreviewResponse response = await repository
          .previewSupplementImpact(const SupplementImpactPreviewRequest());

      expect(capturedRequest.method, 'GET');
      expect(
        capturedRequest.url.path,
        '/api/v1/supplements/recommendations/latest',
      );
      expect(capturedRequest.body, isEmpty);
      expect(response.calculationVersion, 'supplement-impact-v1.0.0');
    },
  );

  test('rejects unsupported selected supplement impact preview', () async {
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: _CaptureJsonClient(onRequest: (_) {}),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    expect(
      () => repository.previewSupplementImpact(
        const SupplementImpactPreviewRequest(
          selectedSupplementIds: <String>[
            '00000000-0000-0000-0000-000000000001',
          ],
          includeAllActiveSupplements: false,
        ),
      ),
      throwsA(isA<UnsupportedError>()),
    );
  });

  test('requests local Ollama explanation for analysis preview', () async {
    late http.Request capturedRequest;
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: _CaptureJsonClient(
        onRequest: (http.Request request) {
          capturedRequest = request;
        },
      ),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final SupplementRecommendationExplainResponse response = await repository
        .explainSupplementAnalysis(
          '00000000-0000-0000-0000-000000000001',
          useLocalLlm: true,
        );

    final Map<String, dynamic> body =
        jsonDecode(capturedRequest.body) as Map<String, dynamic>;
    expect(
      capturedRequest.url.path,
      '/api/v1/supplements/analyses/00000000-0000-0000-0000-000000000001/explain',
    );
    expect(body['locale'], 'ko-KR');
    expect(body['use_local_llm'], isTrue);
    expect(response.llmUsed, isTrue);
    expect(response.sourceCitations.single.title, '비타민 D');
  });

  test('posts comprehensive diet analysis with persona and ingredients', () async {
    late http.Request capturedRequest;
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: _CaptureJsonClient(
        responseBody: _comprehensiveResponse,
        onRequest: (http.Request request) {
          capturedRequest = request;
        },
      ),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final ComprehensiveDietAnalysis analysis = await repository
        .analyzeComprehensive(
          ingredients: <Map<String, Object?>>[
            <String, Object?>{
              'display_name': '탄수화물',
              'nutrient_code': 'carbohydrate_g',
              'amount': 78,
              'unit': 'g',
            },
          ],
        );

    final Map<String, dynamic> body =
        jsonDecode(capturedRequest.body) as Map<String, dynamic>;
    expect(
      capturedRequest.url.path,
      '/api/v1/supplements/analyze/comprehensive',
    );
    expect(body['persona'], 'B');
    expect(body.containsKey('user_profile'), isFalse);
    expect((body['ingredients'] as List<Object?>).single, <String, Object?>{
      'display_name': '탄수화물',
      'nutrient_code': 'carbohydrate_g',
      'amount': 78,
      'unit': 'g',
    });
    expect(analysis.dietScore, 78);
    expect(analysis.cautionaryComponents.single.component, '카페인');
  });

  test('looks up KDRIs with profile query params (public route)', () async {
    late http.Request capturedRequest;
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: _CaptureJsonClient(
        responseBody: _kdrisResponse,
        onRequest: (http.Request request) {
          capturedRequest = request;
        },
      ),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final KdriLookupResult result = await repository.lookupKdris(
      age: 30,
      sex: 'female',
    );

    expect(capturedRequest.method, 'GET');
    expect(capturedRequest.url.path, '/api/v1/nutrition/kdris');
    expect(capturedRequest.url.queryParameters['age'], '30');
    expect(capturedRequest.url.queryParameters['sex'], 'female');
    expect(
      capturedRequest.url.queryParameters['pregnancy_status'],
      'none',
    );
    expect(result.references, hasLength(1));
    expect(result.references.single.nutrientCode, 'vitamin_c_mg');
    expect(result.references.single.ulAmount, 2000);
    expect(result.datasetStatus, 'sample');
  });

  test('rejects unsupported sex and out-of-range age before KDRIs call', () {
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: _CaptureJsonClient(onRequest: (_) {}),
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    expect(
      () => repository.lookupKdris(age: 30, sex: 'other'),
      throwsArgumentError,
    );
    expect(
      () => repository.lookupKdris(age: 0, sex: 'male'),
      throwsArgumentError,
    );
  });
}

final Map<String, Object?> _kdrisResponse = <String, Object?>{
  'query': <String, Object?>{
    'age': 30,
    'sex': 'female',
    'pregnancy_status': 'none',
  },
  'references': <Object?>[
    <String, Object?>{
      'nutrient_code': 'vitamin_c_mg',
      'nutrient_name': 'Vitamin C',
      'nutrient_name_ko': '비타민 C',
      'sex': 'female',
      'age_min': 19,
      'age_max': 64,
      'pregnancy_status': 'none',
      'reference_type': 'RDA',
      'reference_amount': 100,
      'reference_unit': 'mg',
      'ul_amount': 2000,
      'ul_unit': 'mg',
      'source_note': 'sample',
      'review_status': 'reviewed',
    },
  ],
  'dataset_status': 'sample',
  'dataset_version': 'kdris-2020-sample',
  'source_manifest_version': 'v1',
  'note': '참고용 기준값이에요.',
};

class _CaptureMultipartClient extends http.BaseClient {
  _CaptureMultipartClient({
    required this.onRequest,
    Map<String, Object?>? responseBody,
  }) : responseBody = responseBody ?? _previewResponse;

  final void Function(http.MultipartRequest request) onRequest;
  final Map<String, Object?> responseBody;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    onRequest(request as http.MultipartRequest);
    return http.StreamedResponse(
      Stream<List<int>>.value(utf8.encode(jsonEncode(responseBody))),
      202,
      headers: <String, String>{'content-type': 'application/json'},
    );
  }
}

class _CaptureJsonClient extends http.BaseClient {
  _CaptureJsonClient({
    required this.onRequest,
    Map<String, Object?>? responseBody,
  }) : responseBody = responseBody ?? _explainResponse;

  final void Function(http.Request request) onRequest;
  final Map<String, Object?> responseBody;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final http.Request jsonRequest = request as http.Request;
    onRequest(jsonRequest);
    return http.StreamedResponse(
      Stream<List<int>>.value(utf8.encode(jsonEncode(responseBody))),
      200,
      headers: <String, String>{'content-type': 'application/json'},
    );
  }
}

class _SessionFlowClient extends http.BaseClient {
  final List<http.BaseRequest> requests = <http.BaseRequest>[];

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    requests.add(request);
    final String path = request.url.path;
    if (request is http.Request &&
        path == '/api/v1/supplements/analysis-sessions') {
      return _jsonResponse(_sessionResponse, 201);
    }
    if (request is http.MultipartRequest &&
        path == '/api/v1/supplements/analysis-sessions/multi-test/images') {
      return _jsonResponse(_multiPreviewResponse, 202);
    }
    if (request is http.Request &&
        path == '/api/v1/supplements/analysis-sessions/multi-test/finalize') {
      return _jsonResponse(_multiPreviewResponse, 200);
    }
    return _jsonResponse(<String, Object?>{
      'detail': 'unexpected request',
    }, 500);
  }

  http.StreamedResponse _jsonResponse(
    Map<String, Object?> body,
    int statusCode,
  ) {
    return http.StreamedResponse(
      Stream<List<int>>.value(utf8.encode(jsonEncode(body))),
      statusCode,
      headers: <String, String>{'content-type': 'application/json'},
    );
  }
}

class _OneShotFlowClient extends http.BaseClient {
  final List<http.BaseRequest> requests = <http.BaseRequest>[];

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    requests.add(request);
    if (request is http.MultipartRequest &&
        request.url.path == '/api/v1/supplements/analyze-multi') {
      return http.StreamedResponse(
        Stream<List<int>>.value(utf8.encode(jsonEncode(_multiPreviewResponse))),
        202,
        headers: <String, String>{'content-type': 'application/json'},
      );
    }
    return http.StreamedResponse(
      Stream<List<int>>.value(
        utf8.encode(
          jsonEncode(<String, Object?>{'detail': 'unexpected request'}),
        ),
      ),
      500,
      headers: <String, String>{'content-type': 'application/json'},
    );
  }
}

final Map<String, Object?> _sessionResponse = <String, Object?>{
  'analysis_group_id': 'multi-test',
  'status': 'created',
  'image_count': 0,
  'max_images': 6,
  'missing_required_sections': <String>[
    'product_name',
    'supplement_facts',
    'intake_method',
    'precautions',
  ],
  'action_required': 'additional_label_image_required',
};

final Map<String, Object?> _previewResponse = <String, Object?>{
  'analysis_id': '00000000-0000-0000-0000-000000000001',
  'status': 'requires_confirmation',
  'parsed_product': <String, Object?>{},
  'ingredient_candidates': <Object?>[],
  'pipeline_metadata': <String, Object?>{
    'intake_completed': true,
    'vision_roi_used': false,
    'ocr_provider': 'intake-only',
    'llm_parser_used': false,
    'raw_image_stored': false,
    'raw_ocr_text_stored': false,
  },
  'matched_product_candidates': <Object?>[],
  'low_confidence_fields': <Object?>[],
  'warnings': <Object?>[],
  'algorithm_version': 'test',
  'source_manifest_version': null,
  'expires_at': '2026-05-21T00:00:00Z',
};

final Map<String, Object?> _multiPreviewResponse = <String, Object?>{
  'analysis_group_id': 'multi-test',
  'image_count': 2,
  'previews': <Object?>[
    _previewResponse,
    <String, Object?>{
      ..._previewResponse,
      'analysis_id': '00000000-0000-0000-0000-000000000002',
      'image_role': 'supplement_facts',
    },
  ],
  'missing_required_sections': <String>['intake_method'],
  'action_required': 'additional_label_image_required',
  'pipeline_metadata': <String, Object?>{
    'intake_completed': true,
    'image_count': 2,
    'image_role': 'mixed',
    'vision_roi_used': false,
    'ocr_provider': 'intake-only',
    'llm_parser_used': false,
    'missing_required_sections': <String>['intake_method'],
    'raw_image_stored': false,
    'raw_ocr_text_stored': false,
  },
  'expires_at': '2026-05-21T00:00:00Z',
};

final Map<String, Object?> _mealPreviewResponse = <String, Object?>{
  'analysis_id': '00000000-0000-0000-0000-000000000101',
  'meal_id': '00000000-0000-0000-0000-000000000201',
  'status': 'requires_confirmation',
  'meal_type': 'lunch',
  'eaten_at': '2026-05-28T03:00:00Z',
  'food_candidates': <Object?>[
    <String, Object?>{
      'display_name': '비빔밥',
      'portion_amount': null,
      'portion_unit': null,
      'kcal': null,
      'carb_g': null,
      'protein_g': null,
      'fat_g': null,
      'sodium_mg': null,
      'confidence': 0.88,
      'source': 'vision',
    },
  ],
  'nutrition_estimate_summary': <String, Object?>{
    'status': 'detected_review_required',
    'items': <Object?>[],
    'totals': <String, Object?>{},
    'detector_used': true,
  },
  'warning_codes': <String>['food_detection_review_required'],
  'pipeline_metadata': <String, Object?>{
    'intake_completed': true,
    'detector_model': 'food_yolo_local:best.pt',
    'classifier_model': null,
    'detector_used': true,
    'classifier_used': false,
    'raw_image_stored': false,
    'raw_provider_payload_stored': false,
    'requires_manual_entry': false,
  },
  'algorithm_version': 'food-image-preview-v1.0.0',
  'created_at': '2026-05-28T03:00:01Z',
};

final Map<String, Object?> _mealRecordResponse = <String, Object?>{
  'id': '00000000-0000-0000-0000-000000000201',
  'status': 'confirmed',
  'meal_type': 'lunch',
  'eaten_at': '2026-05-28T03:00:00Z',
  'food_items': <Object?>[
    <String, Object?>{
      'id': '00000000-0000-0000-0000-000000000301',
      'display_name': '비빔밥',
      'portion_amount': null,
      'portion_unit': null,
      'kcal': 520,
      'carb_g': null,
      'protein_g': null,
      'fat_g': null,
      'sodium_mg': null,
      'confidence': 0.88,
      'source': 'vision',
    },
  ],
  'nutrition_summary': <String, Object?>{
    'status': 'user_confirmed',
    'items_count': 1,
    'totals': <String, Object?>{'kcal': 520},
  },
  'confirmed_at': '2026-05-28T03:05:00Z',
  'created_at': '2026-05-28T03:00:01Z',
};

final Map<String, Object?> _impactPreviewResponse = <String, Object?>{
  'calculation_version': 'supplement-impact-v1.0.0',
  'reference_version': '2025',
  'source_manifest_version': null,
  'data_status': 'partial',
  'current_supplement_contributions': <Object?>[],
  'deficiency_support_candidates': <Object?>[],
  'excess_or_duplicate_risks': <Object?>[],
  'missing_profile_fields': <Object?>[],
  'safe_user_message': 'Review current supplement intake.',
  'clinical_disclaimer': 'Reference information only.',
  'warnings': <Object?>[],
  'requires_user_confirmation': true,
};

final Map<String, Object?> _explainResponse = <String, Object?>{
  'safe_user_message': 'Local explanation is ready.',
  'explanation_bullets': <String>['Review duplicate supplement sources.'],
  'clinical_disclaimer': 'Reference information only.',
  'blocked_terms_detected': <Object?>[],
  'llm_used': true,
  'source_citations': <Object?>[
    <String, Object?>{
      'title': '비타민 D',
      'source_path': 'vitamin-d.md',
      'heading': '확인 필요',
      'excerpt': '비타민 D는 개인 상태와 함께 확인합니다.',
      'score': 9.0,
    },
  ],
  'warnings': <Object?>[],
};

final Map<String, Object?> _comprehensiveResponse = <String, Object?>{
  'diet_score': 78,
  'diet_score_label': '균형이 잘 잡혔어요',
  'diet_score_message': '나트륨만 조금 줄이면 좋아요.',
  'diet_score_confidence': 0.9,
  'deficient_nutrients': <Object?>[],
  'excessive_nutrients': <Object?>[],
  'cautionary_components': <Object?>[
    <String, Object?>{
      'component': '카페인',
      'reason': '늦은 시간 섭취',
      'severity': 'high',
      'message': '저녁 섭취는 피하는 게 좋아요.',
      'source_citation': 'caffeine.md',
    },
  ],
  'purpose_targets': <Object?>[],
  'chronic_disease_indications': <Object?>[],
  'warnings': <Object?>[],
};

File _writeTinyPng({String fileName = 'label.png'}) {
  final Directory directory = Directory.systemTemp.createTempSync(
    'lemon-aid-repository-test-',
  );
  final File file = File('${directory.path}/$fileName');
  addTearDown(() {
    if (directory.existsSync()) {
      directory.deleteSync(recursive: true);
    }
  });
  file.writeAsBytesSync(
    base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
    ),
  );
  return file;
}
