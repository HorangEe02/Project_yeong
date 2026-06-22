// features/chat/chat_models.dart — 레몬봇 챗 API 데이터 모델
//
// 백엔드 `/ai-agent/chat` 계약을 표현하는 순수 Dart 모델.
// 모든 fromJson 은 null-safe 하게 작성해 서버 응답 변동에 견디게 한다.
//
// 의료법 가드: 사용자 노출 라벨은 "확인"·"안내"·"근거" 사용
// (진단/처방/치료/효능·효과 금지).

import 'chat_analysis_models.dart';

/// One conversation turn carried in the chatbot request history.
class ChatTurn {
  /// Creates a conversation turn.
  ///
  /// Args:
  ///   role: Either `user` or `assistant`.
  ///   content: Message text for the turn.
  ///   createdAt: Local timestamp; serialized as ISO 8601.
  ChatTurn({
    required this.role,
    required this.content,
    required this.createdAt,
  });

  /// Either `user` or `assistant`.
  final String role;

  /// Message text for the turn.
  final String content;

  /// Timestamp serialized as ISO 8601 in the request payload.
  final DateTime createdAt;

  /// Serializes the turn for the request `conversation` array.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'role': role,
      'content': content,
      'created_at': createdAt.toIso8601String(),
    };
  }
}

/// Decoded `/ai-agent/chat` response.
class ChatbotResponse {
  /// Creates a chatbot response.
  ChatbotResponse({
    required this.requestId,
    required this.message,
    required this.provider,
    required this.usedTools,
    required this.safetyWarnings,
    required this.sourceFamilies,
    required this.answerability,
    required this.sources,
    required this.requiresUserApproval,
    required this.ctas,
    required this.analysisSnapshot,
    required this.todayAnalysis,
    required this.smartAnalysis,
    required this.checklistCandidates,
    required this.approvalPreview,
  });

  /// Parses a response from a decoded JSON object.
  factory ChatbotResponse.fromJson(Map<String, dynamic> json) {
    return ChatbotResponse(
      requestId: json['request_id'] as String? ?? '',
      message: json['message'] as String? ?? '',
      provider: json['provider'] as String? ?? 'unknown',
      usedTools: _stringList(json['used_tools']),
      safetyWarnings: _stringList(json['safety_warnings']),
      sourceFamilies: _stringList(json['source_families']),
      answerability: json['answerability'] as String? ?? 'answerable',
      sources: _sourceList(json['sources']),
      requiresUserApproval: json['requires_user_approval'] as bool? ?? false,
      ctas: _stringList(json['ctas']),
      analysisSnapshot: _objectMap(json['analysis_snapshot']),
      todayAnalysis: _objectMap(json['today_analysis']),
      smartAnalysis: _objectMap(json['smart_analysis']),
      checklistCandidates: _checklistCandidateList(
        json['checklist_candidates'],
      ),
      approvalPreview: ChatbotApprovalPreview.fromJson(
        _objectMap(json['approval_preview']),
      ),
    );
  }

  /// Server-echoed request id.
  final String requestId;

  /// Assistant message text rendered in the chat bubble.
  final String message;

  /// Provider that produced the answer.
  final String provider;

  /// Tools the agent used while answering.
  final List<String> usedTools;

  /// Safety warning strings surfaced by the agent.
  final List<String> safetyWarnings;

  /// Source family identifiers backing the answer.
  final List<String> sourceFamilies;

  /// One of `answerable`, `needs_more_info`, `unknown_no_reviewed_source`.
  final String answerability;

  /// Reviewed sources backing the answer.
  final List<ChatbotSource> sources;

  /// Whether the answer requires an explicit user approval before any action.
  final bool requiresUserApproval;

  /// Up to three suggested follow-up prompts.
  final List<String> ctas;

  /// Raw analysis snapshot payload (kept opaque for the chat tab).
  final Map<String, dynamic> analysisSnapshot;

  /// Raw today-analysis payload.
  final Map<String, dynamic> todayAnalysis;

  /// Raw smart-analysis payload.
  final Map<String, dynamic> smartAnalysis;

  /// Checklist candidates suggested by the agent.
  final List<ChatbotChecklistCandidate> checklistCandidates;

  /// Approval preview describing a gated analysis run.
  final ChatbotApprovalPreview approvalPreview;

  /// Whether the agent retrieved any reviewed source.
  bool get hasReviewedSources => sources.isNotEmpty;

  /// Whether the answer is fully answerable from reviewed knowledge.
  bool get isAnswerable => answerability == 'answerable';

  /// Whether the response gates an analysis run behind explicit approval.
  bool get needsAnalysisApproval {
    return requiresUserApproval &&
        approvalPreview.approvalState == 'approval_required';
  }

  /// Whether this response is the completed leg of an approval loop that
  /// persisted an analysis result (guide 05 (a) render gate).
  ///
  /// True only when the approval preview reports `approved` and the persisted
  /// side effect is present, so ordinary chat turns never surface the card.
  bool get isApprovedAnalysisResult {
    return approvalPreview.approvalState == 'approved' &&
        approvalPreview.sideEffects.contains('analysis_result_persisted');
  }

  /// Typed view of the `today_analysis` block.
  ChatTodayAnalysis get today => ChatTodayAnalysis.fromJson(todayAnalysis);

  /// Typed view of the `smart_analysis` block.
  ChatSmartAnalysis get smart => ChatSmartAnalysis.fromJson(smartAnalysis);

  /// Whether the persisted approval was a today-analysis run.
  ///
  /// Falls back to whichever snapshot carries content when the kind is absent.
  bool get isTodayAnalysisKind {
    final String kind = approvalPreview.analysisKind;
    if (kind == 'today_analysis') {
      return true;
    }
    if (kind == 'health_analysis') {
      return false;
    }
    // No kind echoed: prefer today when it has content, else smart.
    return !today.isEmpty || smart.isEmpty;
  }
}

/// A single checklist candidate suggested by the agent.
class ChatbotChecklistCandidate {
  /// Creates a checklist candidate.
  ChatbotChecklistCandidate({
    required this.candidateId,
    required this.kind,
    required this.title,
    required this.source,
    required this.approvalState,
    required this.sideEffect,
    required this.deferredAction,
  });

  /// Parses a checklist candidate from a decoded JSON object.
  factory ChatbotChecklistCandidate.fromJson(Map<String, dynamic> json) {
    return ChatbotChecklistCandidate(
      candidateId: json['candidate_id'] as String? ?? '',
      kind: json['kind'] as String? ?? '',
      title: json['title'] as String? ?? '',
      source: json['source'] as String? ?? '',
      approvalState: json['approval_state'] as String? ?? '',
      sideEffect: json['side_effect'] as String? ?? '',
      deferredAction: json['deferred_action'] as String? ?? '',
    );
  }

  /// Stable candidate identifier.
  final String candidateId;

  /// Candidate kind discriminator.
  final String kind;

  /// Human-readable candidate title.
  final String title;

  /// Source label for the candidate.
  final String source;

  /// Approval state for the candidate.
  final String approvalState;

  /// Declared side effect.
  final String sideEffect;

  /// Deferred action identifier.
  final String deferredAction;
}

/// Approval preview describing a gated analysis run.
///
/// Backend contract:
///   `{required, approval_state, analysis_kind, snapshot_preview, side_effects}`.
class ChatbotApprovalPreview {
  /// Creates an approval preview.
  ChatbotApprovalPreview({
    required this.hasPreview,
    required this.requiredApproval,
    required this.approvalState,
    required this.analysisKind,
    required this.snapshotPreview,
    required this.sideEffects,
  });

  /// Returns an empty preview that gates nothing.
  factory ChatbotApprovalPreview.empty() {
    return ChatbotApprovalPreview(
      hasPreview: false,
      requiredApproval: false,
      approvalState: '',
      analysisKind: '',
      snapshotPreview: const <String, dynamic>{},
      sideEffects: const <String>[],
    );
  }

  /// Parses an approval preview from a decoded JSON object.
  factory ChatbotApprovalPreview.fromJson(Map<String, dynamic> json) {
    if (json.isEmpty) {
      return ChatbotApprovalPreview.empty();
    }
    return ChatbotApprovalPreview(
      hasPreview: true,
      requiredApproval: json['required'] as bool? ?? false,
      approvalState: json['approval_state'] as String? ?? '',
      analysisKind: json['analysis_kind'] as String? ?? '',
      snapshotPreview: _objectMap(json['snapshot_preview']),
      sideEffects: _stringList(json['side_effects']),
    );
  }

  /// Whether the server sent a non-empty preview.
  final bool hasPreview;

  /// Whether approval is required before running the analysis.
  final bool requiredApproval;

  /// Approval state; `approval_required` gates the run.
  final String approvalState;

  /// Analysis kind echoed back on the approval resend.
  final String analysisKind;

  /// Opaque snapshot preview payload.
  final Map<String, dynamic> snapshotPreview;

  /// Declared side effects of running the analysis.
  final List<String> sideEffects;
}

/// A reviewed source backing the answer.
class ChatbotSource {
  /// Creates a source.
  ChatbotSource({
    required this.title,
    required this.sourceId,
    required this.sourceFamily,
    required this.sourceUrl,
  });

  /// Parses a source from a decoded JSON object.
  factory ChatbotSource.fromJson(Map<String, dynamic> json) {
    String pick(List<String> keys) {
      for (final String key in keys) {
        final Object? value = json[key];
        if (value is String && value.trim().isNotEmpty) {
          return value.trim();
        }
      }
      return '';
    }

    return ChatbotSource(
      // Backend emits `source_title` (section heading or document title); some
      // payloads use `title`. Reading the wrong key surfaced the raw file path.
      title: pick(<String>['source_title', 'title']),
      sourceId: json['source_id'] as String? ?? '',
      sourceFamily: json['source_family'] as String? ?? '',
      sourceUrl: json['source_url'] as String? ?? '',
    );
  }

  /// Human-readable source title.
  final String title;

  /// Stable source identifier.
  final String sourceId;

  /// Source family identifier.
  final String sourceFamily;

  /// Source URL when present.
  final String sourceUrl;

  /// Friendly source-family name for display.
  String get familyLabel {
    switch (sourceFamily.trim()) {
      case 'lemon_wiki':
        return '레몬 위키';
      case '':
        return '참고 자료';
      default:
        return sourceFamily.trim();
    }
  }

  /// Short, clean label for an inline source chip.
  ///
  /// Strips section numbering ("1.2 ") and leading symbols from the heading and
  /// never returns a raw file path, so the chip stays compact and readable.
  String get label {
    final String cleaned = _cleanTitle(title);
    if (cleaned.isNotEmpty) {
      return cleaned;
    }
    final String fromPath = _humanizePath(sourceId);
    if (fromPath.isNotEmpty) {
      return fromPath;
    }
    return familyLabel;
  }

  static String _cleanTitle(String raw) {
    final String t = raw.trim();
    final bool pathLike = t.toLowerCase().endsWith('.md') ||
        RegExp(r'^[A-Za-z0-9._/-]+$').hasMatch(t);
    if (t.isEmpty || pathLike) {
      return '';
    }
    return t
        .replaceFirst(RegExp(r'^\d+(\.\d+)*\s*'), '')
        .replaceFirst(RegExp(r'^[^가-힣A-Za-z0-9(]+'), '')
        .trim();
  }

  static String _humanizePath(String id) {
    String s = id.trim();
    if (s.isEmpty) {
      return '';
    }
    final int slash = s.lastIndexOf('/');
    if (slash >= 0) {
      s = s.substring(slash + 1);
    }
    return s
        .replaceFirst(RegExp(r'\.md$', caseSensitive: false), '')
        .replaceFirst(RegExp(r'^\d{4}-\d{2}-\d{2}-'), '')
        .replaceAll(RegExp(r'[-_]+'), ' ')
        .trim();
  }
}

List<String> _stringList(Object? value) {
  if (value is! List<dynamic>) {
    return <String>[];
  }
  return value.whereType<String>().toList(growable: false);
}

List<ChatbotSource> _sourceList(Object? value) {
  if (value is! List<dynamic>) {
    return <ChatbotSource>[];
  }
  return value
      .whereType<Map<String, dynamic>>()
      .map(ChatbotSource.fromJson)
      .toList(growable: false);
}

Map<String, dynamic> _objectMap(Object? value) {
  if (value is! Map<dynamic, dynamic>) {
    return <String, dynamic>{};
  }
  return value.map(
    (dynamic key, dynamic item) =>
        MapEntry<String, dynamic>(key.toString(), item),
  );
}

List<ChatbotChecklistCandidate> _checklistCandidateList(Object? value) {
  if (value is! List<dynamic>) {
    return <ChatbotChecklistCandidate>[];
  }
  return value
      .map(_objectMap)
      .where((Map<String, dynamic> item) => item.isNotEmpty)
      .map(ChatbotChecklistCandidate.fromJson)
      .toList(growable: false);
}
