import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/theme/lemon_theme.dart';
import '../../../shared/widgets/medical_disclaimer.dart';
import '../data/chat_repository.dart';
import '../domain/chat_models.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  static const List<String> _suggestions = <String>[
    '비타민 D 얼마나 먹어야 해?',
    '오메가-3 같이 먹어도 돼?',
    '오늘 점심 어떻게 먹으면 좋아?',
    '나트륨 줄이는 팁 알려줘',
  ];

  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ChatTurn> _conversation = <ChatTurn>[];
  ChatbotResponse? _lastResponse;
  bool _isSending = false;
  bool _hasError = false;

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _sendText(String text) async {
    final String message = text.trim();
    if (message.isEmpty || _isSending) {
      return;
    }

    HapticFeedback.selectionClick();
    final List<ChatTurn> requestConversation =
        List<ChatTurn>.unmodifiable(_conversation);
    setState(() {
      _isSending = true;
      _hasError = false;
      _controller.clear();
      _conversation.add(
        ChatTurn(role: 'user', content: message, createdAt: DateTime.now()),
      );
    });
    _scrollToBottom();

    try {
      final ChatRepository repository = ref.read(chatRepositoryProvider);
      await repository.grantSensitiveHealthAnalysisConsent();
      final ChatbotResponse response = await repository.sendMessage(
        ChatbotRequest.compose(
          message: message,
          conversation: requestConversation,
        ),
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _conversation.add(
          ChatTurn(
            role: 'assistant',
            content: response.message,
            createdAt: DateTime.now(),
          ),
        );
        _lastResponse = response;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _hasError = true;
        _conversation.add(
          ChatTurn(
            role: 'assistant',
            content: '챗봇 응답을 받지 못했습니다. 백엔드 연결과 인증 상태를 확인해 주세요.',
            createdAt: DateTime.now(),
          ),
        );
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSending = false;
        });
        _scrollToBottom();
      }
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) {
        return;
      }
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOutCubic,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: LemonColors.canvas,
      body: Column(
        children: <Widget>[
          _ChatHeader(
            provider: _lastResponse?.provider,
            onBack: () => context.go('/'),
          ),
          Expanded(
            child: ListView(
              controller: _scrollController,
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 18),
              children: <Widget>[
                if (_conversation.isEmpty) ...<Widget>[
                  const _IntroCard(),
                  const SizedBox(height: 14),
                ],
                if (_conversation.isEmpty)
                  _SuggestionGrid(
                    suggestions: _suggestions,
                    onSelected: _sendText,
                  ),
                const SizedBox(height: 12),
                if (_conversation.isEmpty) const _EmptyChatState(),
                for (final ChatTurn turn in _conversation) ...<Widget>[
                  _ChatBubble(turn: turn),
                  const SizedBox(height: 10),
                ],
                if (_isSending) const _TypingBubble(),
                if (_hasError) const _ChatErrorPanel(),
                if (_lastResponse != null) ...<Widget>[
                  const SizedBox(height: 4),
                  _AgentStatusPanel(response: _lastResponse!),
                  if (_lastResponse!.hasReviewedSources) ...<Widget>[
                    const SizedBox(height: 10),
                    _SourceBasisPanel(sources: _lastResponse!.sources),
                  ],
                  if (_lastResponse!.needsAnswerabilityNotice) ...<Widget>[
                    const SizedBox(height: 10),
                    _AnswerabilityNoticePanel(response: _lastResponse!),
                  ],
                  if (_lastResponse!.hasAnalysisPreview) ...<Widget>[
                    const SizedBox(height: 10),
                    _AnalysisPreviewPanel(response: _lastResponse!),
                  ],
                  if (_lastResponse!.hasCtas) ...<Widget>[
                    const SizedBox(height: 10),
                    _ChatCtaPanel(
                      ctas: _lastResponse!.ctas,
                      onSelected: _handleCta,
                    ),
                  ],
                ],
                const SizedBox(height: 12),
                const MedicalDisclaimer(),
              ],
            ),
          ),
          _InputBar(
            controller: _controller,
            disabled: _isSending,
            onSend: _sendText,
          ),
        ],
      ),
    );
  }

  void _handleCta(ChatbotCta cta) {
    switch (cta) {
      case ChatbotCta.completeMissingRecord:
        context.go('/food-capture');
      case ChatbotCta.runOrRefreshAnalysis:
        _setInput('오늘 분석을 다시 실행해줘');
      case ChatbotCta.addChecklistItem:
        _showChecklistEditSheet();
      case ChatbotCta.askAboutThisResult:
        _setInput('이 결과로 질문하기: ');
    }
  }

  void _setInput(String value) {
    _controller.text = value;
    _controller.selection = TextSelection.collapsed(offset: value.length);
  }

  void _showChecklistEditSheet() {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: LemonColors.paper,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (BuildContext context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  '체크리스트 편집',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  '챗봇 제안은 바로 저장하지 않고 편집 화면에서 확인한 뒤 추가합니다.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 16),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close_rounded),
                    label: const Text('닫기'),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _ChatHeader extends StatelessWidget {
  const _ChatHeader({
    required this.provider,
    required this.onBack,
  });

  final String? provider;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: LemonColors.lemon,
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: Color(0x22FFCE00),
            blurRadius: 16,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(8, 12, 16, 16),
          child: Row(
            children: <Widget>[
              IconButton(
                tooltip: '뒤로',
                onPressed: onBack,
                icon: const Icon(Icons.arrow_back_rounded),
              ),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: const Color(0x66FFFFFF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: const SizedBox(
                  width: 44,
                  height: 44,
                  child:
                      Icon(Icons.chat_bubble_rounded, color: LemonColors.ink),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      '레몬봇',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontSize: 18,
                          ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '영양·식단 궁금한 거 편하게 물어봐요',
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            color: LemonColors.ink,
                          ),
                    ),
                  ],
                ),
              ),
              if (provider != null)
                LemonPill(
                  label: provider!,
                  color: LemonColors.leaf,
                  backgroundColor: LemonColors.leafSoft,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _IntroCard extends StatelessWidget {
  const _IntroCard();

  @override
  Widget build(BuildContext context) {
    return LemonCard(
      child: Row(
        children: <Widget>[
          DecoratedBox(
            decoration: BoxDecoration(
              color: LemonColors.lemonSoft,
              borderRadius: BorderRadius.circular(18),
            ),
            child: const SizedBox(
              width: 64,
              height: 64,
              child: Icon(
                Icons.emoji_food_beverage_rounded,
                color: LemonColors.warning,
                size: 34,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              '안녕하세요. 오늘 어떤 점이 궁금하세요?',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
        ],
      ),
    );
  }
}

class _SuggestionGrid extends StatelessWidget {
  const _SuggestionGrid({
    required this.suggestions,
    required this.onSelected,
  });

  final List<String> suggestions;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text(
            '이런 걸 물어보면 좋아요',
            style: Theme.of(context).textTheme.labelMedium,
          ),
        ),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: <Widget>[
            for (final String suggestion in suggestions)
              ActionChip(
                label: Text(suggestion),
                backgroundColor: LemonColors.paper,
                side: const BorderSide(color: LemonColors.line),
                onPressed: () => onSelected(suggestion),
              ),
          ],
        ),
      ],
    );
  }
}

class _AgentStatusPanel extends StatelessWidget {
  const _AgentStatusPanel({required this.response});

  final ChatbotResponse response;

  @override
  Widget build(BuildContext context) {
    final String memoryLabel =
        response.usedAgentMemory ? 'memory 사용' : 'memory 미사용';

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: <Widget>[
        LemonPill(
          label: memoryLabel,
          color: LemonColors.sky,
          backgroundColor: LemonColors.skySoft,
        ),
        LemonPill(
          label: _answerabilityLabel(response.answerability),
          color: LemonColors.inkMuted,
          backgroundColor: LemonColors.paper,
        ),
        for (final String sourceFamily in response.sourceFamilies)
          LemonPill(
            label: _sourceFamilyLabel(sourceFamily),
            color: LemonColors.leaf,
            backgroundColor: LemonColors.leafSoft,
          ),
        if (response.sources.isNotEmpty &&
            response.sources.first.sourceId.isNotEmpty)
          LemonPill(
            label: response.sources.first.sourceId,
            color: LemonColors.leaf,
            backgroundColor: LemonColors.leafSoft,
          ),
        if (response.requiresUserApproval)
          const LemonPill(
            label: '승인 필요',
            color: LemonColors.warning,
            backgroundColor: LemonColors.warningSoft,
          ),
      ],
    );
  }
}

class _EmptyChatState extends StatelessWidget {
  const _EmptyChatState();

  @override
  Widget build(BuildContext context) {
    return LemonCard(
      color: LemonColors.lemonSoft,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Icon(Icons.auto_awesome_rounded),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              '오늘 확정한 음식, 영양제 기록을 기준으로 확인할 점을 물어보세요.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: LemonColors.ink,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatBubble extends StatelessWidget {
  const _ChatBubble({required this.turn});

  final ChatTurn turn;

  @override
  Widget build(BuildContext context) {
    final bool isUser = turn.role == 'user';
    final Color background = isUser ? LemonColors.lemon : LemonColors.paper;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * 0.78,
        ),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: background,
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(16),
              topRight: const Radius.circular(16),
              bottomLeft: Radius.circular(isUser ? 16 : 4),
              bottomRight: Radius.circular(isUser ? 4 : 16),
            ),
            border: Border.all(color: LemonColors.line),
            boxShadow: isUser
                ? null
                : const <BoxShadow>[
                    BoxShadow(
                      color: Color(0x14000000),
                      blurRadius: 10,
                      offset: Offset(0, 3),
                    ),
                  ],
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
            child: Text(
              turn.content,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: LemonColors.ink,
                    fontWeight: isUser ? FontWeight.w700 : FontWeight.w500,
                  ),
            ),
          ),
        ),
      ),
    );
  }
}

class _TypingBubble extends StatelessWidget {
  const _TypingBubble();

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: LemonColors.paper,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: LemonColors.line),
        ),
        child: const Padding(
          padding: EdgeInsets.symmetric(horizontal: 14, vertical: 11),
          child: SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
        ),
      ),
    );
  }
}

class _SourceBasisPanel extends StatelessWidget {
  const _SourceBasisPanel({required this.sources});

  final List<ChatbotSource> sources;

  @override
  Widget build(BuildContext context) {
    return LemonCard(
      color: LemonColors.leafSoft,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            '검수 근거',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          for (final ChatbotSource source in sources)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                _sourceLabel(source),
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
        ],
      ),
    );
  }
}

class _AnswerabilityNoticePanel extends StatelessWidget {
  const _AnswerabilityNoticePanel({required this.response});

  final ChatbotResponse response;

  @override
  Widget build(BuildContext context) {
    return LemonCard(
      color: LemonColors.warningSoft,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Icon(Icons.report_problem_outlined, color: LemonColors.warning),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  _answerabilityLabel(response.answerability),
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                if (response.safetyWarnings.isNotEmpty) ...<Widget>[
                  const SizedBox(height: 6),
                  for (final String warning in response.safetyWarnings.take(2))
                    Text(
                      warning,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AnalysisPreviewPanel extends StatelessWidget {
  const _AnalysisPreviewPanel({required this.response});

  final ChatbotResponse response;

  @override
  Widget build(BuildContext context) {
    final String todayStatus =
        _stringValue(response.todayAnalysis['status'], 'unknown');
    final String readiness = _stringValue(
      response.smartAnalysis['readiness_level'],
      'unknown',
    );
    final ChatbotApprovalPreview approval = response.approvalPreview;

    return LemonCard(
      color: LemonColors.skySoft,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Icon(Icons.analytics_outlined, color: LemonColors.sky),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Analysis preview',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          _PreviewLine(label: 'Today', value: todayStatus),
          _PreviewLine(label: 'Smart', value: readiness),
          if (response.sources.isNotEmpty &&
              response.sources.first.sourceId.isNotEmpty)
            _PreviewLine(
              label: 'Source',
              value: response.sources.first.sourceId,
            ),
          if (response.checklistCandidates.isNotEmpty) ...<Widget>[
            const SizedBox(height: 8),
            Text(
              'Checklist candidates',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 4),
            for (final ChatbotChecklistCandidate candidate
                in response.checklistCandidates.take(3))
              Text(
                _candidateLabel(candidate),
                style: Theme.of(context).textTheme.bodySmall,
              ),
          ],
          if (approval.hasPreview) ...<Widget>[
            const SizedBox(height: 8),
            _PreviewLine(
              label:
                  approval.requiredApproval ? 'Approval required' : 'Approval',
              value: approval.approvalState.isEmpty
                  ? 'not_required'
                  : approval.approvalState,
            ),
            Text(
              approval.sideEffects.isEmpty
                  ? 'No side effects'
                  : 'Side effects: ${approval.sideEffects.join(', ')}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            Text(
              'Persist: ${approval.willPersist ? 'yes' : 'no'}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }
}

class _PreviewLine extends StatelessWidget {
  const _PreviewLine({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(
            width: 112,
            child: Text(
              label,
              style: Theme.of(context).textTheme.labelMedium,
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatCtaPanel extends StatelessWidget {
  const _ChatCtaPanel({
    required this.ctas,
    required this.onSelected,
  });

  final List<ChatbotCta> ctas;
  final ValueChanged<ChatbotCta> onSelected;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: <Widget>[
        for (final ChatbotCta cta in ctas)
          FilledButton.icon(
            onPressed: () => onSelected(cta),
            icon: Icon(_ctaIcon(cta), size: 18),
            label: Text(_ctaLabel(cta)),
          ),
      ],
    );
  }
}

class _InputBar extends StatelessWidget {
  const _InputBar({
    required this.controller,
    required this.disabled,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool disabled;
  final ValueChanged<String> onSend;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: LemonColors.canvas,
        border: Border(top: BorderSide(color: LemonColors.line)),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
          child: Row(
            children: <Widget>[
              Expanded(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: LemonColors.paper,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: LemonColors.line),
                  ),
                  child: TextField(
                    key: const Key('chat-message-input'),
                    controller: controller,
                    enabled: !disabled,
                    minLines: 1,
                    maxLines: 4,
                    textInputAction: TextInputAction.send,
                    onSubmitted: onSend,
                    decoration: const InputDecoration(
                      hintText: '메시지를 입력하세요',
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      contentPadding: EdgeInsets.symmetric(
                        horizontal: 18,
                        vertical: 12,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              GestureDetector(
                onTap: disabled ? null : () => onSend(controller.text),
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: disabled ? LemonColors.line : LemonColors.lemon,
                    shape: BoxShape.circle,
                    boxShadow: const <BoxShadow>[
                      BoxShadow(
                        color: Color(0x4DFFCE00),
                        blurRadius: 12,
                        offset: Offset(0, 4),
                      ),
                    ],
                  ),
                  child: SizedBox(
                    width: 46,
                    height: 46,
                    child: Icon(
                      disabled
                          ? Icons.hourglass_top_rounded
                          : Icons.arrow_upward_rounded,
                      color: LemonColors.ink,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ChatErrorPanel extends StatelessWidget {
  const _ChatErrorPanel();

  @override
  Widget build(BuildContext context) {
    return const LemonCard(
      color: LemonColors.dangerSoft,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.error_outline_rounded, color: LemonColors.danger),
          SizedBox(width: 10),
          Expanded(
            child: Text('백엔드 연결과 인증 상태를 확인해 주세요.'),
          ),
        ],
      ),
    );
  }
}

IconData _ctaIcon(ChatbotCta cta) {
  return switch (cta) {
    ChatbotCta.completeMissingRecord => Icons.add_circle_outline_rounded,
    ChatbotCta.runOrRefreshAnalysis => Icons.refresh_rounded,
    ChatbotCta.addChecklistItem => Icons.checklist_rounded,
    ChatbotCta.askAboutThisResult => Icons.chat_bubble_outline_rounded,
  };
}

String _ctaLabel(ChatbotCta cta) {
  return switch (cta) {
    ChatbotCta.completeMissingRecord => '기록 보완',
    ChatbotCta.runOrRefreshAnalysis => '분석 실행',
    ChatbotCta.addChecklistItem => '체크리스트 편집',
    ChatbotCta.askAboutThisResult => '이 결과로 질문',
  };
}

String _sourceFamilyLabel(String sourceFamily) {
  return switch (sourceFamily) {
    'nutrition_reference' => '영양 기준',
    'supplement_reference' => '영양제 참고',
    'drug_safety_boundary' => '복약 주의',
    'chronic_condition' => '만성질환 맥락',
    'general_medical' => '일반 건강정보',
    'emergency_escalation' => '응급 안내',
    'mental_health_escalation' => '안전 위기 안내',
    _ => sourceFamily.replaceAll('_', ' '),
  };
}

String _answerabilityLabel(String answerability) {
  return switch (answerability) {
    'answerable' => '검수 지식 기반',
    'answerable_with_caution' => '주의 설명',
    'needs_more_info' => '추가 정보 필요',
    'unknown_no_reviewed_source' => '검수 지식 없음',
    'medical_decision_boundary' => '의료 판단 경계',
    'urgent_escalation' => '응급 안내',
    _ => answerability.replaceAll('_', ' '),
  };
}

String _sourceLabel(ChatbotSource source) {
  final List<String> parts = <String>[
    if (source.sourceId.isNotEmpty) source.sourceId,
    if (source.boundaryCode.isNotEmpty) source.boundaryCode,
    if (source.versionLabel.isNotEmpty) source.versionLabel,
    if (source.expiresAt.isNotEmpty) 'expires ${source.expiresAt}',
  ];
  return parts.join(' | ');
}

extension on ChatbotResponse {
  bool get needsAnswerabilityNotice {
    return answerability == 'unknown_no_reviewed_source' ||
        answerability == 'medical_decision_boundary' ||
        answerability == 'urgent_escalation' ||
        answerability == 'needs_more_info';
  }
}

String _candidateLabel(ChatbotChecklistCandidate candidate) {
  final List<String> parts = <String>[
    if (candidate.title.isNotEmpty) candidate.title,
    if (candidate.approvalState.isNotEmpty) candidate.approvalState,
    if (candidate.sideEffect.isNotEmpty) 'side_effect=${candidate.sideEffect}',
  ];
  return parts.join(' | ');
}

String _stringValue(Object? value, String fallback) {
  if (value is String && value.isNotEmpty) {
    return value;
  }
  return fallback;
}
