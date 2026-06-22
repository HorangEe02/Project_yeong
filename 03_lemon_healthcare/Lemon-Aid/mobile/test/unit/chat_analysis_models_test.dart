import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/chat/chat_analysis_models.dart';
import 'package:lemon_aid_mobile/features/chat/chat_models.dart';

void main() {
  group('ChatTodayAnalysis.fromJson', () {
    test('parses a ready snapshot with a score', () {
      final ChatTodayAnalysis today = ChatTodayAnalysis.fromJson(
        <String, dynamic>{
          'status': 'ready_for_analysis',
          'score': 76,
          'score_name': '오늘 현재 분석 점수',
          'strengths': <String>['food_records_available'],
          'priority_adjustments': <String>['sodium_high'],
          'recommended_foods': <String>['grilled fish'],
          'checklist_actions': <String>['check soup and sauce intake'],
          'missing_records': <String>[],
          'stale': false,
        },
      );

      expect(today.status, 'ready_for_analysis');
      expect(today.score, 76);
      expect(today.scoreName, '오늘 현재 분석 점수');
      expect(today.isPending, isFalse);
      expect(today.strengths, <String>['food_records_available']);
      expect(today.priorityAdjustments, <String>['sodium_high']);
      expect(today.missingRecords, isEmpty);
    });

    test('treats analysis_pending or null score as pending', () {
      final ChatTodayAnalysis pending = ChatTodayAnalysis.fromJson(
        <String, dynamic>{
          'status': 'analysis_pending',
          'score': null,
          'missing_records': <String>['food_records'],
        },
      );
      expect(pending.isPending, isTrue);
      expect(pending.score, isNull);
      expect(pending.missingRecords, <String>['food_records']);
    });

    test('falls back to empty values on missing or mistyped fields', () {
      final ChatTodayAnalysis empty = ChatTodayAnalysis.fromJson(
        <String, dynamic>{
          'status': 123,
          'score': 'not-a-number',
          'strengths': 'oops',
          'priority_adjustments': <dynamic>[1, 2, 'sodium_high'],
        },
      );
      expect(empty.status, '');
      expect(empty.score, isNull);
      expect(empty.scoreName, '');
      expect(empty.strengths, isEmpty);
      // Non-string entries are dropped; the valid one survives.
      expect(empty.priorityAdjustments, <String>['sodium_high']);
      expect(empty.isPending, isTrue);
    });

    test('coerces a numeric (double) score to int', () {
      final ChatTodayAnalysis today = ChatTodayAnalysis.fromJson(
        <String, dynamic>{'status': 'ready_for_analysis', 'score': 72.0},
      );
      expect(today.score, 72);
    });
  });

  group('ChatSmartAnalysis.fromJson', () {
    test('parses coverage flags and counts covered axes', () {
      final ChatSmartAnalysis smart = ChatSmartAnalysis.fromJson(
        <String, dynamic>{
          'readiness_level': 'level_2_recent_pattern',
          'coverage': <String, dynamic>{
            'food': true,
            'supplement': false,
            'checklist': true,
            'chat_signals': false,
          },
          'nutrient_priorities': <String>['protein_low'],
          'strengths': <String>['food_records_available'],
        },
      );
      expect(smart.readinessLevel, 'level_2_recent_pattern');
      expect(smart.coveredCount, 2);
      expect(smart.nutrientPriorities, <String>['protein_low']);
      expect(smart.isEmpty, isFalse);
    });

    test('falls back to empty on missing or mistyped fields', () {
      final ChatSmartAnalysis empty = ChatSmartAnalysis.fromJson(
        <String, dynamic>{'coverage': 'nope', 'readiness_level': 7},
      );
      expect(empty.readinessLevel, '');
      expect(empty.coverage, isEmpty);
      expect(empty.coveredCount, 0);
      expect(empty.isEmpty, isTrue);
    });
  });

  group('ChatbotResponse approval branch', () {
    Map<String, dynamic> baseResponse() {
      return <String, dynamic>{
        'request_id': 'r-1',
        'message': '분석을 정리했어요.',
        'provider': 'sglang',
        'used_tools': <String>['app_health_analysis'],
        'answerability': 'answerable',
      };
    }

    test('isApprovedAnalysisResult requires approved + persisted side effect', () {
      final ChatbotResponse approved = ChatbotResponse.fromJson(
        baseResponse()
          ..['approval_preview'] = <String, dynamic>{
            'approval_state': 'approved',
            'analysis_kind': 'today_analysis',
            'side_effects': <String>['analysis_result_persisted'],
          },
      );
      expect(approved.isApprovedAnalysisResult, isTrue);
      expect(approved.isTodayAnalysisKind, isTrue);

      final ChatbotResponse approvalRequired = ChatbotResponse.fromJson(
        baseResponse()
          ..['approval_preview'] = <String, dynamic>{
            'approval_state': 'approval_required',
            'side_effects': <String>[],
          },
      );
      expect(approvalRequired.isApprovedAnalysisResult, isFalse);

      final ChatbotResponse approvedNoPersist = ChatbotResponse.fromJson(
        baseResponse()
          ..['approval_preview'] = <String, dynamic>{
            'approval_state': 'approved',
            'side_effects': <String>[],
          },
      );
      expect(approvedNoPersist.isApprovedAnalysisResult, isFalse);
    });

    test('isTodayAnalysisKind respects health_analysis kind', () {
      final ChatbotResponse health = ChatbotResponse.fromJson(
        baseResponse()
          ..['approval_preview'] = <String, dynamic>{
            'approval_state': 'approved',
            'analysis_kind': 'health_analysis',
            'side_effects': <String>['analysis_result_persisted'],
          },
      );
      expect(health.isTodayAnalysisKind, isFalse);
    });
  });
}
