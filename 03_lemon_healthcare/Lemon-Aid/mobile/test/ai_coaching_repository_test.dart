import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/features/ai_coaching/ai_coaching_models.dart';
import 'package:lemon_aid_mobile/features/ai_coaching/ai_coaching_repository.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';

/// Configurable [http.BaseClient] fake so tests do not depend on a real socket.
class _FakeClient extends http.BaseClient {
  _FakeClient(this.handler);

  final Future<http.StreamedResponse> Function(http.Request request) handler;
  final List<http.Request> requests = <http.Request>[];

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final http.Request typed = request as http.Request;
    requests.add(typed);
    return handler(typed);
  }
}

http.StreamedResponse _jsonResponse(Map<String, dynamic> body, int status) {
  return http.StreamedResponse(
    Stream<List<int>>.value(utf8.encode(jsonEncode(body))),
    status,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

Map<String, dynamic> _coachingResponse() {
  return <String, dynamic>{
    'status': 'ok',
    'approval_status': 'not_required',
    'requires_user_approval': false,
    'message': '오늘 단백질이 조금 부족했어요.',
    'findings': <Map<String, dynamic>>[
      <String, dynamic>{
        'nutrient': 'protein',
        'level': 'low',
        'message': '단백질이 권장량보다 적어요.',
      },
    ],
    'recommendations': <Map<String, dynamic>>[
      <String, dynamic>{
        'category': 'meal',
        'title': '저녁에 단백질 반찬 추가하기',
        'rationale': '오늘 단백질 섭취가 적었어요.',
        'priority': 1,
      },
      <String, dynamic>{
        'category': 'meal',
        'title': '물 한 컵 더 마시기',
        'rationale': '수분 섭취를 챙겨요.',
        'priority': 3,
      },
    ],
    'actions': <Map<String, dynamic>>[
      <String, dynamic>{
        'action_type': 'log_meal',
        'title': '저녁 식사 기록하기',
        'requires_user_approval': true,
      },
    ],
    'safety_warnings': <String>[],
  };
}

HomeMeal _meal() {
  return const HomeMeal(
    id: 'meal-1',
    status: 'confirmed',
    mealType: 'lunch',
    eatenAt: null,
    foodItems: <HomeFoodItem>[
      HomeFoodItem(
        displayName: '닭가슴살 샐러드',
        kcal: 320,
        carbG: 12,
        proteinG: 30,
        fatG: 10,
      ),
    ],
    nutrition: HomeMealNutrition(kcal: 320, carbG: 12, proteinG: 30, fatG: 10),
  );
}

HomeSupplement _supplement() {
  return const HomeSupplement(
    id: 'supp-1',
    displayName: '비타민 D',
    manufacturer: 'Lemon Lab',
    schedule: HomeSupplementSchedule(
      frequency: 'daily',
      timeOfDay: <String>['morning'],
      timesPerDay: 2,
    ),
  );
}

AiCoachingRepository _repositoryFor(_FakeClient client) {
  return AiCoachingRepository(
    apiClient: ApiClient(
      baseUrl: 'https://api.example.com/api/v1',
      httpClient: client,
    ),
  );
}

void main() {
  group('AiCoachingRepository.runDailyCoaching', () {
    test('posts a spec-shaped AgentInput payload and parses AgentOutput', () async {
      final _FakeClient client = _FakeClient((http.Request request) async {
        return _jsonResponse(_coachingResponse(), 200);
      });
      final AiCoachingRepository repository = _repositoryFor(client);

      final DailyCoachingResult result = await repository.runDailyCoaching(
        day: DateTime(2026, 6, 11),
        meals: <HomeMeal>[_meal()],
        supplements: <HomeSupplement>[_supplement()],
      );

      // Path: ApiClient base already ends at /api/v1.
      expect(client.requests, hasLength(1));
      final http.Request sent = client.requests.single;
      expect(sent.method, 'POST');
      expect(sent.url.path, '/api/v1/ai-agent/daily-coaching');

      final Map<String, dynamic> body =
          jsonDecode(sent.body) as Map<String, dynamic>;
      expect(body['user_id'], 'mobile-client');
      expect((body['request_id'] as String).isNotEmpty, isTrue);

      final Map<String, dynamic> payload =
          body['payload'] as Map<String, dynamic>;
      expect(payload['date'], '2026-06-11');
      expect(payload['health_trends'], isEmpty);

      final List<dynamic> sources = payload['sources'] as List<dynamic>;
      expect(sources, hasLength(2));
      final Map<String, dynamic> foodSource =
          sources.first as Map<String, dynamic>;
      expect(foodSource['source_type'], 'food_user_input');
      expect(foodSource['user_confirmed'], true);

      final List<dynamic> foods = payload['foods'] as List<dynamic>;
      expect(foods, hasLength(1));
      final Map<String, dynamic> food = foods.single as Map<String, dynamic>;
      expect(food['name'], '닭가슴살 샐러드');
      expect(food['meal_type'], isNotEmpty);
      final List<dynamic> nutrients = food['nutrients'] as List<dynamic>;
      final Map<String, dynamic> protein = nutrients
          .cast<Map<String, dynamic>>()
          .firstWhere((Map<String, dynamic> n) => n['name'] == 'protein');
      expect(protein['amount'], 30);
      expect(protein['unit'], 'g');

      final List<dynamic> supplements =
          payload['supplements'] as List<dynamic>;
      expect(supplements, hasLength(1));
      final Map<String, dynamic> supplement =
          supplements.single as Map<String, dynamic>;
      expect(supplement['product_name'], '비타민 D');
      expect(supplement['times_per_day'], 2);
      expect(supplement['user_confirmed'], true);

      final Map<String, dynamic> context =
          body['context'] as Map<String, dynamic>;
      final Map<String, dynamic> profile =
          context['profile'] as Map<String, dynamic>;
      expect(profile['goals'], <String>['meal_management']);

      // Parsing: recommendations + actions merged, sorted by priority, max 5.
      expect(result.status, 'ok');
      expect(result.message, '오늘 단백질이 조금 부족했어요.');
      expect(result.findings.single.nutrient, 'protein');
      expect(result.items, hasLength(3));
      // priority 1 recommendation comes first, then priority 3, then action.
      expect(result.items[0].title, '저녁에 단백질 반찬 추가하기');
      expect(result.items[1].title, '물 한 컵 더 마시기');
      expect(result.items[2].title, '저녁 식사 기록하기');
      expect(result.items[2].requiresUserApproval, isTrue);
    });

    test('caps the merged checklist at five items by priority', () async {
      final _FakeClient client = _FakeClient((http.Request request) async {
        final Map<String, dynamic> payload = _coachingResponse()
          ..['recommendations'] = <Map<String, dynamic>>[
            for (int i = 0; i < 6; i += 1)
              <String, dynamic>{
                'category': 'meal',
                'title': 'rec-$i',
                'rationale': 'r',
                'priority': i,
              },
          ]
          ..['actions'] = <Map<String, dynamic>>[];
        return _jsonResponse(payload, 200);
      });
      final AiCoachingRepository repository = _repositoryFor(client);

      final DailyCoachingResult result = await repository.runDailyCoaching(
        day: DateTime(2026, 6, 11),
        meals: <HomeMeal>[],
        supplements: <HomeSupplement>[],
      );

      expect(result.items, hasLength(5));
      expect(result.items.first.title, 'rec-0');
      expect(result.items.last.title, 'rec-4');
    });

    test(
      'grants sensitive-health consent once on 403 consent_required and retries',
      () async {
        final List<String> calledPaths = <String>[];
        final _FakeClient client = _FakeClient((http.Request request) async {
          calledPaths.add(request.url.path);
          if (request.url.path.endsWith('/ai-agent/daily-coaching') &&
              calledPaths
                      .where((String p) => p.endsWith('/daily-coaching'))
                      .length ==
                  1) {
            // First attempt is gated on the sensitive-health consent.
            return _jsonResponse(
              <String, dynamic>{
                'detail': <String, dynamic>{
                  'code': 'consent_required',
                  'message': '민감 건강정보 분석 동의가 필요해요.',
                  'required_consents': <String>['sensitive_health_analysis'],
                },
              },
              403,
            );
          }
          if (request.url.path.endsWith('/sensitive_health_analysis')) {
            return _jsonResponse(<String, dynamic>{'granted': true}, 201);
          }
          return _jsonResponse(_coachingResponse(), 200);
        });
        final AiCoachingRepository repository = _repositoryFor(client);

        final DailyCoachingResult result = await repository.runDailyCoaching(
          day: DateTime(2026, 6, 11),
          meals: <HomeMeal>[],
          supplements: <HomeSupplement>[],
        );

        expect(calledPaths, <String>[
          '/api/v1/ai-agent/daily-coaching',
          '/api/v1/me/privacy/consents/sensitive_health_analysis',
          '/api/v1/ai-agent/daily-coaching',
        ]);
        expect(result.status, 'ok');
      },
    );
  });
}
