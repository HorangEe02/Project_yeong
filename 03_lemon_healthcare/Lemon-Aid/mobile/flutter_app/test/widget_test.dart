import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/app.dart';
import 'package:lemon_healthcare/features/chat/data/chat_repository.dart';
import 'package:lemon_healthcare/features/chat/domain/chat_models.dart';

void main() {
  testWidgets('app shell shows mobile agent UI and opens chatbot',
      (WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(900, 1200));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    appRouter.go('/');
    await tester.pumpWidget(const ProviderScope(child: LemonAidApp()));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('lemon-mobile-viewport')), findsOneWidget);
    expect(find.text('오늘의 Agent'), findsOneWidget);
    expect(find.text('기록과 약속을 카드로 확인합니다'), findsOneWidget);
    expect(find.text('영양제'), findsOneWidget);
    expect(find.text('Agent'), findsOneWidget);
    expect(find.text('챗봇'), findsWidgets);

    await tester.tap(find.text('챗봇').last);
    await tester.pumpAndSettle();

    expect(find.text('레몬봇'), findsOneWidget);
    expect(find.text('영양·식단 궁금한 거 편하게 물어봐요'), findsOneWidget);
    expect(find.text('메시지를 입력하세요'), findsOneWidget);
    expect(
      find.text('오늘 확정한 음식, 영양제 기록을 기준으로 확인할 점을 물어보세요.'),
      findsOneWidget,
    );
  });

  testWidgets('chat screen sends message to agent API and renders answer',
      (WidgetTester tester) async {
    final _FakeChatRepository repository = _FakeChatRepository();

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          chatRepositoryProvider.overrideWithValue(repository),
        ],
        child: const LemonAidApp(),
      ),
    );
    await tester.pumpAndSettle();

    if (find.byType(EditableText).evaluate().isEmpty) {
      await tester.tap(find.text('챗봇').last);
      await tester.pumpAndSettle();
    }
    await tester.enterText(
      find.byType(EditableText),
      '리튬 약을 먹는데 셀레늄 영양제 같이 먹어도 돼?',
    );
    await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
    await tester.pumpAndSettle();

    expect(repository.grantedConsent, isTrue);
    expect(repository.sentRequests, hasLength(1));
    expect(repository.sentRequests.single.message, contains('셀레늄'));
    await tester.drag(find.byType(ListView), const Offset(0, 800));
    await tester.pumpAndSettle();
    expect(find.textContaining('리튬은 혈중 농도'), findsOneWidget);
    await tester.drag(find.byType(ListView), const Offset(0, -800));
    await tester.pumpAndSettle();
    expect(find.text('sglang'), findsOneWidget);
    expect(find.textContaining('medlineplus-lithium'), findsWidgets);
    await tester.drag(find.byType(ListView), const Offset(0, -320));
    await tester.pumpAndSettle();

    expect(find.text('Analysis preview'), findsOneWidget);
    expect(find.textContaining('analysis_pending'), findsOneWidget);
    expect(find.textContaining('level_2_recent_pattern'), findsOneWidget);
    expect(find.textContaining('check soup and sauce intake'), findsOneWidget);
    expect(find.text('Approval required'), findsOneWidget);
    expect(find.textContaining('No side effects'), findsOneWidget);
  });

  testWidgets('chat screen renders pure unknown answerability fixture',
      (WidgetTester tester) async {
    final _UnknownChatRepository repository = _UnknownChatRepository();

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          chatRepositoryProvider.overrideWithValue(repository),
        ],
        child: const LemonAidApp(),
      ),
    );
    await tester.pumpAndSettle();

    if (find.byType(EditableText).evaluate().isEmpty) {
      await tester.tap(find.text('챗봇').last);
      await tester.pumpAndSettle();
    }
    await tester.enterText(
      find.byType(EditableText),
      'iron food support question without reviewed source',
    );
    await tester.tap(find.byIcon(Icons.arrow_upward_rounded));
    await tester.pumpAndSettle();

    expect(repository.grantedConsent, isTrue);
    expect(repository.sentRequests.single.message, contains('iron food'));
    expect(find.textContaining('reviewed source is not available'),
        findsOneWidget);
    expect(find.text('검수 지식 없음'), findsWidgets);
    expect(find.text('stub'), findsOneWidget);
  });

  testWidgets('supplement flow uses routine record and analysis UI',
      (WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(430, 932));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    appRouter.go('/');
    await tester.pumpWidget(const ProviderScope(child: LemonAidApp()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('영양제'));
    await tester.pumpAndSettle();

    expect(find.text('복용 루틴과 식단 기준을 함께 봅니다'), findsOneWidget);
    expect(find.text('3/6개 항목 확인됨'), findsOneWidget);
    expect(find.text('아침'), findsOneWidget);
    expect(find.text('점심'), findsOneWidget);
    expect(find.text('아침 루틴'), findsOneWidget);

    await tester.drag(find.byType(ListView), const Offset(0, -520));
    await tester.pumpAndSettle();

    expect(find.text('저녁 루틴'), findsOneWidget);

    await tester.drag(find.byType(ListView), const Offset(0, -360));
    await tester.pumpAndSettle();

    await tester.tap(find.text('분석 보기'));
    await tester.pumpAndSettle();

    expect(find.text('식단과 영양제 기준을 나눠 봅니다'), findsOneWidget);
    expect(find.text('식단 분석'), findsOneWidget);
    expect(find.text('영양제 분석'), findsOneWidget);
    expect(find.text('식단 + 영양제 통합 분석'), findsOneWidget);
    expect(find.text('이 결과로 질문하기'), findsWidgets);
  });
}

class _UnknownChatRepository implements ChatRepository {
  bool grantedConsent = false;
  final List<ChatbotRequest> sentRequests = <ChatbotRequest>[];

  @override
  Future<void> grantSensitiveHealthAnalysisConsent() async {
    grantedConsent = true;
  }

  @override
  Future<ChatbotResponse> sendMessage(ChatbotRequest request) async {
    sentRequests.add(request);
    return ChatbotResponse.fromJson(
      <String, dynamic>{
        'request_id': request.requestId,
        'message':
            'A reviewed source is not available yet, so the agent should say it does not know.',
        'provider': 'stub',
        'used_tools': <String>['chatbot_agent'],
        'safety_warnings': <String>[],
        'source_families': <String>[],
        'answerability': 'unknown_no_reviewed_source',
        'sources': <Map<String, dynamic>>[],
        'requires_user_approval': false,
        'ctas': <String>['ask_about_this_result'],
      },
    );
  }
}

class _FakeChatRepository implements ChatRepository {
  bool grantedConsent = false;
  final List<ChatbotRequest> sentRequests = <ChatbotRequest>[];

  @override
  Future<void> grantSensitiveHealthAnalysisConsent() async {
    grantedConsent = true;
  }

  @override
  Future<ChatbotResponse> sendMessage(ChatbotRequest request) async {
    sentRequests.add(request);
    return ChatbotResponse.fromJson(
      <String, dynamic>{
        'request_id': request.requestId,
        'message': '리튬은 혈중 농도 확인이 필요한 약입니다. 의사 또는 약사와 확인하세요.',
        'provider': 'sglang',
        'used_tools': <String>['chatbot_agent', 'agent_memory'],
        'safety_warnings': <String>['Drug interaction boundary applied'],
        'source_families': <String>['drug_safety_boundary'],
        'answerability': 'medical_decision_boundary',
        'sources': <Map<String, dynamic>>[
          <String, dynamic>{
            'source_id': 'medlineplus-lithium',
            'source_family': 'drug_safety_boundary',
            'review_status': 'reviewed',
            'version_label': '2026-05 MVP source registry',
            'reviewed_at': '2026-05-31',
            'expires_at': '2026-11-30',
            'source_url': 'https://medlineplus.gov/druginfo/meds/a681039.html',
            'boundary_code': 'p0_lithium_selenium',
          },
        ],
        'requires_user_approval': false,
        'ctas': <String>['ask_about_this_result'],
        'analysis_snapshot': <String, dynamic>{
          'today_analysis': <String, dynamic>{
            'schema_version': 'today-analysis-snapshot-v1',
            'status': 'analysis_pending',
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
  }
}
