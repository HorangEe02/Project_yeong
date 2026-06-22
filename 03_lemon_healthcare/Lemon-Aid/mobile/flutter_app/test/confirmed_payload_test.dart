import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/features/ai_coaching/domain/ai_coaching_models.dart';
import 'package:lemon_healthcare/features/activity/domain/activity_models.dart';
import 'package:lemon_healthcare/features/chat/domain/chat_models.dart';
import 'package:lemon_healthcare/features/food/domain/confirmed_food_entry.dart';
import 'package:lemon_healthcare/features/supplement/domain/supplement_analysis_preview.dart';
import 'package:lemon_healthcare/shared/dev/dev_confirmed_samples.dart';
import 'package:lemon_healthcare/shared/state/confirmed_entry_store.dart';

void main() {
  test('confirmed food entry does not invent nutrients', () {
    final ConfirmedFoodEntry entry = ConfirmedFoodEntry(
      name: 'rice bowl',
      mealType: 'lunch',
      servingLabel: '1 bowl',
      memo: 'manual entry',
      photoName: 'food-photo.jpg',
    );

    expect(entry.toAgentSourceJson()['source_type'], 'food_user_input');
    expect(entry.toAgentSourceJson()['user_confirmed'], isTrue);
    expect(entry.toAgentFoodJson().containsKey('nutrients'), isFalse);
  });

  test('daily coaching request uses confirmed food and supplement inputs', () {
    final ConfirmedFoodEntry food = ConfirmedFoodEntry(
      name: 'rice bowl',
      mealType: 'lunch',
      servingLabel: '1 bowl',
      memo: '',
      photoName: null,
    );
    final SupplementConfirmedInput supplement = SupplementConfirmedInput(
      analysisId: 'analysis-1',
      displayName: 'Vitamin D',
      manufacturer: '',
      ingredients: <SupplementConfirmedIngredientInput>[
        SupplementConfirmedIngredientInput(
          displayName: 'Vitamin D',
          nutrientCode: 'vitamin_d',
          amount: 10,
          unit: 'mcg',
        ),
      ],
      serving: SupplementServingInput(
        amount: 1,
        unit: 'tablet',
        dailyServings: 1,
      ),
      intakeSchedule: null,
    );

    final DailyCoachingRequest request =
        DailyCoachingRequest.fromConfirmedInputs(
      foods: <ConfirmedFoodEntry>[food],
      supplements: <SupplementConfirmedInput>[supplement],
    );
    final Map<String, dynamic> payload =
        request.toJson()['payload'] as Map<String, dynamic>;

    expect(payload['foods'], hasLength(1));
    expect(payload['supplements'], hasLength(1));
    expect(payload['supplements'].first['product_name'], 'Vitamin D');
    expect(payload['supplements'].first.containsKey('display_name'), isFalse);
    expect(payload['supplements'].first['times_per_day'], 1);
    expect(
      payload['supplements'].first['ingredients'].first['name'],
      'Vitamin D',
    );
    expect(payload.toString().contains('raw_ocr_text'), isFalse);
    expect(payload.toString().contains('user_confirmed: true'), isTrue);
  });

  test('daily coaching response parses recommendations and existing fields',
      () {
    final DailyCoachingResponse response = DailyCoachingResponse.fromJson(
      <String, dynamic>{
        'request_id': 'response-1',
        'status': 'completed',
        'approval_status': 'confirmed',
        'message': '오늘의 요약: 확인된 입력 기준입니다.',
        'provider': 'sglang',
        'used_tools': <String>['daily_health_agent', 'agent_memory'],
        'findings': <Map<String, dynamic>>[
          <String, dynamic>{
            'nutrient': 'vitamin d',
            'total_amount': 25,
            'unit': 'mcg',
            'level': 'high',
          },
        ],
        'recommendations': <Map<String, dynamic>>[
          <String, dynamic>{
            'category': 'reduce',
            'title': 'Reduce vitamin d',
            'rationale': 'vitamin d intake is above the target range.',
            'priority': 8,
          },
        ],
        'safety_warnings': <String>['현재 입력 기준입니다.'],
      },
    );

    expect(response.requestId, 'response-1');
    expect(response.provider, 'sglang');
    expect(response.usedAgentMemory, isTrue);
    expect(response.findings, hasLength(1));
    expect(response.recommendations, hasLength(1));
    expect(response.safetyWarnings, hasLength(1));
  });

  test('dev sample seeds confirmed entries without food nutrients', () {
    seedDevConfirmedEntries();

    final DailyCoachingRequest request =
        DailyCoachingRequest.fromConfirmedInputs(
      foods: ConfirmedEntryStore.instance.foods,
      supplements: ConfirmedEntryStore.instance.supplements,
    );
    final Map<String, dynamic> payload =
        request.toJson()['payload'] as Map<String, dynamic>;

    expect(payload['foods'], hasLength(1));
    expect(payload['supplements'], hasLength(1));
    expect(payload.toString().contains('nutrients'), isFalse);
    expect(payload.toString().contains('raw_ocr_text'), isFalse);
    ConfirmedEntryStore.instance.clear();
  });

  test('daily coaching request includes confirmed activity context only', () {
    final ConfirmedActivityEntry confirmed = ConfirmedActivityEntry(
      date: DateTime(2026, 5, 21),
      steps: 7200,
      activeMinutes: 34,
      activityEnergyKcal: 220,
      workoutType: 'walk',
      source: 'manual',
      userConfirmed: true,
    );
    final ConfirmedActivityEntry preview = ConfirmedActivityEntry(
      date: DateTime(2026, 5, 21),
      steps: 5000,
      activeMinutes: 20,
      activityEnergyKcal: 120,
      workoutType: 'run',
      source: 'health_connect_preview',
      userConfirmed: false,
    );

    final DailyCoachingRequest request =
        DailyCoachingRequest.fromConfirmedInputs(
      foods: <ConfirmedFoodEntry>[],
      supplements: <SupplementConfirmedInput>[],
      activities: <ConfirmedActivityEntry>[confirmed, preview],
    );
    final Map<String, dynamic> payload =
        request.toJson()['payload'] as Map<String, dynamic>;
    final List<dynamic> healthTrends =
        payload['health_trends'] as List<dynamic>;

    expect(healthTrends, hasLength(1));
    expect(healthTrends.first['metric'], 'activity_context');
    expect(healthTrends.first['steps'], 7200);
    expect(healthTrends.first['active_minutes'], 34);
    expect(healthTrends.first['activity_energy_kcal'], 220);
    expect(healthTrends.first['workout_type'], 'walk');
    expect(healthTrends.first['source'], 'manual');
    expect(healthTrends.first['user_confirmed'], isTrue);
    expect(payload.toString().contains('health_connect_preview'), isFalse);
    expect(payload.toString().contains('sleep'), isFalse);
    expect(payload.toString().contains('route'), isFalse);
    expect(payload.toString().contains('blood_glucose'), isFalse);
    expect(payload.toString().contains('blood_pressure'), isFalse);
  });

  test('chatbot response parses source families and ctas', () {
    final ChatbotResponse response = ChatbotResponse.fromJson(
      <String, dynamic>{
        'request_id': 'chat-response-1',
        'message': '오늘의 요약: 현재 입력 기준입니다.',
        'provider': 'sglang',
        'used_tools': <String>['chatbot_agent', 'agent_memory'],
        'safety_warnings': <String>[],
        'source_families': <String>[
          'supplement_reference',
          'nutrition_reference',
        ],
        'sources': <Map<String, dynamic>>[
          <String, dynamic>{
            'source_id': 'mfds-drug-safety',
            'source_family': 'drug_safety_boundary',
            'review_status': 'reviewed',
            'version_label': '2026-05 MVP source registry',
            'reviewed_at': '2026-05-29',
            'expires_at': '2026-11-29',
            'source_url': 'https://nedrug.mfds.go.kr',
            'boundary_code': 'p0_grapefruit_statin',
          },
        ],
        'requires_user_approval': false,
        'ctas': <String>[
          'add_checklist_item',
          'ask_about_this_result',
          'unsupported_action',
        ],
      },
    );

    expect(response.requestId, 'chat-response-1');
    expect(response.usedAgentMemory, isTrue);
    expect(response.sourceFamilies, <String>[
      'supplement_reference',
      'nutrition_reference',
    ]);
    expect(response.sources.single.boundaryCode, 'p0_grapefruit_statin');
    expect(response.ctas, <ChatbotCta>[
      ChatbotCta.addChecklistItem,
      ChatbotCta.askAboutThisResult,
    ]);
    expect(response.hasCtas, isTrue);
  });

  test('chatbot response preserves day05 analysis and approval contract', () {
    final ChatbotResponse response = ChatbotResponse.fromJson(
      <String, dynamic>{
        'request_id': 'chat-response-2',
        'message': 'Analysis preview is ready.',
        'provider': 'sglang',
        'used_tools': <String>['chatbot_agent', 'agent_memory'],
        'safety_warnings': <String>[],
        'source_families': <String>[],
        'answerability': 'needs_more_info',
        'sources': <Map<String, dynamic>>[],
        'requires_user_approval': true,
        'ctas': <String>[
          'run_or_refresh_analysis',
          'ask_about_this_result',
          'complete_missing_record',
        ],
        'analysis_snapshot': <String, dynamic>{
          'today_analysis': <String, dynamic>{
            'schema_version': 'today-analysis-snapshot-v1',
            'status': 'analysis_pending',
            'missing_records': <String>['food_records'],
          },
          'smart_analysis': <String, dynamic>{
            'schema_version': 'health-analysis-snapshot-v1',
            'readiness_level': 'level_2_recent_pattern',
          },
        },
        'today_analysis': <String, dynamic>{
          'schema_version': 'today-analysis-snapshot-v1',
          'status': 'analysis_pending',
          'missing_records': <String>['food_records'],
        },
        'smart_analysis': <String, dynamic>{
          'schema_version': 'health-analysis-snapshot-v1',
          'readiness_level': 'level_2_recent_pattern',
          'coverage': <String, dynamic>{'food': true},
        },
        'checklist_candidates': <Map<String, dynamic>>[
          <String, dynamic>{
            'candidate_id': 'checklist-candidate-v1-1',
            'kind': 'today_practice',
            'title': 'check soup and sauce intake',
            'source': 'today_analysis',
            'approval_state': 'approval_required',
            'side_effect': 'none',
            'deferred_action': 'add_today_practice',
          },
        ],
        'approval_preview': <String, dynamic>{
          'schema_version': 'approval-preview-v1',
          'required': true,
          'approval_state': 'approval_required',
          'will_persist': false,
          'will_schedule_notification': false,
          'will_add_today_practice': false,
          'side_effects': <String>[],
          'actions': <Map<String, dynamic>>[
            <String, dynamic>{
              'action': 'add_today_practice',
              'candidate_id': 'checklist-candidate-v1-1',
              'status': 'approval_required',
              'side_effect': 'none',
            },
          ],
        },
      },
    );

    expect(response.rawCtas, <String>[
      'run_or_refresh_analysis',
      'ask_about_this_result',
      'complete_missing_record',
    ]);
    expect(response.ctas, <ChatbotCta>[
      ChatbotCta.runOrRefreshAnalysis,
      ChatbotCta.askAboutThisResult,
      ChatbotCta.completeMissingRecord,
    ]);
    expect(
      response.analysisSnapshot['today_analysis'],
      response.todayAnalysis,
    );
    expect(response.todayAnalysis['missing_records'], <String>['food_records']);
    expect(response.smartAnalysis['coverage'], <String, dynamic>{'food': true});
    expect(
      response.checklistCandidates.single.rawJson['source'],
      'today_analysis',
    );
    expect(
      response.checklistCandidates.single.title,
      'check soup and sauce intake',
    );
    expect(response.approvalPreview.requiredApproval, isTrue);
    expect(response.approvalPreview.willPersist, isFalse);
    expect(
      response.approvalPreview.actions.single.action,
      'add_today_practice',
    );
    expect(response.hasAnalysisPreview, isTrue);
  });
}
