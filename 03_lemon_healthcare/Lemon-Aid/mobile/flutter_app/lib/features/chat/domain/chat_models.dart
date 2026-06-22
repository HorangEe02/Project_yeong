class ChatTurn {
  ChatTurn({
    required this.role,
    required this.content,
    required this.createdAt,
  });

  final String role;
  final String content;
  final DateTime createdAt;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'role': role,
      'content': content,
      'created_at': createdAt.toIso8601String(),
    };
  }
}

class ChatbotRequest {
  ChatbotRequest({
    required this.requestId,
    required this.userId,
    required this.message,
    required this.conversation,
    required this.context,
  });

  factory ChatbotRequest.compose({
    required String message,
    required List<ChatTurn> conversation,
  }) {
    return ChatbotRequest(
      requestId: 'mobile-chat-${DateTime.now().millisecondsSinceEpoch}',
      userId: 'mobile-client-placeholder',
      message: message,
      conversation: conversation,
      context: <String, dynamic>{
        'profile': <String, dynamic>{
          'goals': <String>['meal_management'],
        },
      },
    );
  }

  final String requestId;
  final String userId;
  final String message;
  final List<ChatTurn> conversation;
  final Map<String, dynamic> context;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'request_id': requestId,
      'user_id': userId,
      'message': message,
      'conversation': conversation
          .map((ChatTurn turn) => turn.toJson())
          .toList(growable: false),
      'context': context,
    };
  }
}

class ChatbotResponse {
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
    List<String>? rawCtas,
    Map<String, dynamic>? analysisSnapshot,
    Map<String, dynamic>? todayAnalysis,
    Map<String, dynamic>? smartAnalysis,
    List<ChatbotChecklistCandidate>? checklistCandidates,
    ChatbotApprovalPreview? approvalPreview,
  })  : rawCtas = rawCtas ??
            ctas.map((ChatbotCta cta) => cta.name).toList(growable: false),
        analysisSnapshot = analysisSnapshot ?? <String, dynamic>{},
        todayAnalysis = todayAnalysis ?? <String, dynamic>{},
        smartAnalysis = smartAnalysis ?? <String, dynamic>{},
        checklistCandidates =
            checklistCandidates ?? <ChatbotChecklistCandidate>[],
        approvalPreview = approvalPreview ?? ChatbotApprovalPreview.empty();

  factory ChatbotResponse.fromJson(Map<String, dynamic> json) {
    final List<String> rawCtas = _stringList(json['ctas']);
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
      ctas: _ctaList(rawCtas),
      rawCtas: rawCtas,
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

  final String requestId;
  final String message;
  final String provider;
  final List<String> usedTools;
  final List<String> safetyWarnings;
  final List<String> sourceFamilies;
  final String answerability;
  final List<ChatbotSource> sources;
  final bool requiresUserApproval;
  final List<ChatbotCta> ctas;
  final List<String> rawCtas;
  final Map<String, dynamic> analysisSnapshot;
  final Map<String, dynamic> todayAnalysis;
  final Map<String, dynamic> smartAnalysis;
  final List<ChatbotChecklistCandidate> checklistCandidates;
  final ChatbotApprovalPreview approvalPreview;

  bool get usedAgentMemory => usedTools.contains('agent_memory');
  bool get hasReviewedSources => sources.isNotEmpty;
  bool get hasCtas => ctas.isNotEmpty;
  bool get hasAnalysisPreview {
    return analysisSnapshot.isNotEmpty ||
        todayAnalysis.isNotEmpty ||
        smartAnalysis.isNotEmpty ||
        checklistCandidates.isNotEmpty ||
        approvalPreview.hasPreview;
  }
}

enum ChatbotCta {
  completeMissingRecord,
  runOrRefreshAnalysis,
  addChecklistItem,
  askAboutThisResult,
}

ChatbotCta? _chatbotCtaFromJson(String value) {
  return switch (value) {
    'complete_missing_record' => ChatbotCta.completeMissingRecord,
    'run_or_refresh_analysis' => ChatbotCta.runOrRefreshAnalysis,
    'add_checklist_item' => ChatbotCta.addChecklistItem,
    'ask_about_this_result' => ChatbotCta.askAboutThisResult,
    _ => null,
  };
}

class ChatbotChecklistCandidate {
  ChatbotChecklistCandidate({
    required this.rawJson,
    required this.candidateId,
    required this.kind,
    required this.title,
    required this.source,
    required this.approvalState,
    required this.sideEffect,
    required this.deferredAction,
  });

  factory ChatbotChecklistCandidate.fromJson(Map<String, dynamic> json) {
    return ChatbotChecklistCandidate(
      rawJson: Map<String, dynamic>.unmodifiable(json),
      candidateId: json['candidate_id'] as String? ?? '',
      kind: json['kind'] as String? ?? '',
      title: json['title'] as String? ?? '',
      source: json['source'] as String? ?? '',
      approvalState: json['approval_state'] as String? ?? '',
      sideEffect: json['side_effect'] as String? ?? '',
      deferredAction: json['deferred_action'] as String? ?? '',
    );
  }

  final Map<String, dynamic> rawJson;
  final String candidateId;
  final String kind;
  final String title;
  final String source;
  final String approvalState;
  final String sideEffect;
  final String deferredAction;
}

class ChatbotApprovalPreview {
  ChatbotApprovalPreview({
    required this.rawJson,
    required this.schemaVersion,
    required this.requiredApproval,
    required this.approvalState,
    required this.willPersist,
    required this.willScheduleNotification,
    required this.willAddTodayPractice,
    required this.sideEffects,
    required this.actions,
  });

  factory ChatbotApprovalPreview.empty() {
    return ChatbotApprovalPreview(
      rawJson: <String, dynamic>{},
      schemaVersion: '',
      requiredApproval: false,
      approvalState: '',
      willPersist: false,
      willScheduleNotification: false,
      willAddTodayPractice: false,
      sideEffects: <String>[],
      actions: <ChatbotApprovalAction>[],
    );
  }

  factory ChatbotApprovalPreview.fromJson(Map<String, dynamic> json) {
    if (json.isEmpty) {
      return ChatbotApprovalPreview.empty();
    }
    return ChatbotApprovalPreview(
      rawJson: Map<String, dynamic>.unmodifiable(json),
      schemaVersion: json['schema_version'] as String? ?? '',
      requiredApproval: json['required'] as bool? ?? false,
      approvalState: json['approval_state'] as String? ?? '',
      willPersist: json['will_persist'] as bool? ?? false,
      willScheduleNotification:
          json['will_schedule_notification'] as bool? ?? false,
      willAddTodayPractice: json['will_add_today_practice'] as bool? ?? false,
      sideEffects: _stringList(json['side_effects']),
      actions: _approvalActionList(json['actions']),
    );
  }

  final Map<String, dynamic> rawJson;
  final String schemaVersion;
  final bool requiredApproval;
  final String approvalState;
  final bool willPersist;
  final bool willScheduleNotification;
  final bool willAddTodayPractice;
  final List<String> sideEffects;
  final List<ChatbotApprovalAction> actions;

  bool get hasPreview => rawJson.isNotEmpty;
}

class ChatbotApprovalAction {
  ChatbotApprovalAction({
    required this.rawJson,
    required this.action,
    required this.candidateId,
    required this.status,
    required this.sideEffect,
  });

  factory ChatbotApprovalAction.fromJson(Map<String, dynamic> json) {
    return ChatbotApprovalAction(
      rawJson: Map<String, dynamic>.unmodifiable(json),
      action: json['action'] as String? ?? '',
      candidateId: json['candidate_id'] as String? ?? '',
      status: json['status'] as String? ?? '',
      sideEffect: json['side_effect'] as String? ?? '',
    );
  }

  final Map<String, dynamic> rawJson;
  final String action;
  final String candidateId;
  final String status;
  final String sideEffect;
}

class ChatbotSource {
  ChatbotSource({
    required this.sourceId,
    required this.sourceFamily,
    required this.reviewStatus,
    required this.versionLabel,
    required this.reviewedAt,
    required this.expiresAt,
    required this.sourceUrl,
    required this.boundaryCode,
  });

  factory ChatbotSource.fromJson(Map<String, dynamic> json) {
    return ChatbotSource(
      sourceId: json['source_id'] as String? ?? '',
      sourceFamily: json['source_family'] as String? ?? '',
      reviewStatus: json['review_status'] as String? ?? '',
      versionLabel: json['version_label'] as String? ?? '',
      reviewedAt: json['reviewed_at'] as String? ?? '',
      expiresAt: json['expires_at'] as String? ?? '',
      sourceUrl: json['source_url'] as String? ?? '',
      boundaryCode: json['boundary_code'] as String? ?? '',
    );
  }

  final String sourceId;
  final String sourceFamily;
  final String reviewStatus;
  final String versionLabel;
  final String reviewedAt;
  final String expiresAt;
  final String sourceUrl;
  final String boundaryCode;
}

List<String> _stringList(Object? value) {
  if (value is! List<dynamic>) {
    return <String>[];
  }
  return value.whereType<String>().toList(growable: false);
}

List<ChatbotCta> _ctaList(List<String> value) {
  return value
      .map(_chatbotCtaFromJson)
      .whereType<ChatbotCta>()
      .toList(growable: false);
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
  return Map<String, dynamic>.unmodifiable(
    value.map(
      (dynamic key, dynamic item) => MapEntry<String, dynamic>(
        key.toString(),
        item,
      ),
    ),
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

List<ChatbotApprovalAction> _approvalActionList(Object? value) {
  if (value is! List<dynamic>) {
    return <ChatbotApprovalAction>[];
  }
  return value
      .map(_objectMap)
      .where((Map<String, dynamic> item) => item.isNotEmpty)
      .map(ChatbotApprovalAction.fromJson)
      .toList(growable: false);
}
