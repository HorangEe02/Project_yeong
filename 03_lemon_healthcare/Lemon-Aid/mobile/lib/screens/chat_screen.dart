// screens/chat_screen.dart — 챗 탭 (LADS v2)
//
// 디자인:
//   - 상단: brand 옅은 헤더 + "레몬봇" 마스코트 + 부제
//   - 본문: 인사 + 추천 질문 칩 + 메시지 리스트 (실제 백엔드 응답)
//   - 하단: 입력바 (둥근 chip 스타일, 우측 brand 전송)
//
// 의료법 가드: "처방"·"진단"·"치료" 금지 → "확인"·"안내"·"도움" 사용
// 데이터 소스: ChatRepository (`/ai-agent/chat`). 디자인·위젯 구조는 보존하고
// 데이터만 mock 에서 실제 API 로 교체.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app_controller.dart';
import '../app_providers.dart';
import '../core/api/api_error.dart';
import '../features/chat/chat_models.dart';
import '../features/chat/chat_repository.dart';
import '../features/chat/widgets/chat_analysis_card.dart';
import '../utils/design_tokens_v2.dart';

class ChatScreen extends ConsumerStatefulWidget {
  /// Creates the chat tab.
  ///
  /// Args:
  ///   controller: Optional app controller that may provide a one-shot
  ///     supplement explanation draft from the analysis result flow.
  ///   repository: Optional repository override for tests; defaults to the
  ///     [chatRepositoryProvider] value.
  const ChatScreen({this.controller, this.repository, super.key});

  /// App controller used to consume analysis-to-chat explanation drafts.
  final AppController? controller;

  /// Optional repository override; tests inject a fake here.
  final ChatRepository? repository;

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollCtl = ScrollController();
  final List<_Message> _messages = [];
  final List<ChatTurn> _history = [];
  bool _thinking = false;
  int? _appliedDraftId;

  static const List<String> _suggestions = [
    '비타민 D 얼마나 먹어야 해?',
    '오메가-3 같이 먹어도 돼?',
    '오늘 점심 어떻게 먹으면 좋아?',
    '나트륨 줄이는 팁 알려줘',
  ];

  ChatRepository get _repository =>
      widget.repository ?? ref.read(chatRepositoryProvider);

  void _send(String text) {
    final body = text.trim();
    if (body.isEmpty || _thinking) return;
    HapticFeedback.selectionClick();
    setState(() {
      _messages.add(_Message.user(body));
      _controller.clear();
      _thinking = true;
    });
    _scrollToBottom();
    _dispatch(message: body);
  }

  /// Sends [message] to the backend and renders the response or an error.
  ///
  /// When [analysisRunApproval] is set, the same message is resent to resume a
  /// gated analysis run after the user approved it.
  Future<void> _dispatch({
    required String message,
    Map<String, dynamic>? analysisRunApproval,
  }) async {
    final List<ChatTurn> sentHistory = List<ChatTurn>.of(_history);
    try {
      final ChatbotResponse response = await _repository.sendMessage(
        message: message,
        conversation: sentHistory,
        analysisRunApproval: analysisRunApproval,
      );
      if (!mounted) return;
      // Only record the turn pair in history after a successful exchange so a
      // failed send does not poison later requests.
      _history
        ..add(
          ChatTurn(role: 'user', content: message, createdAt: DateTime.now()),
        )
        ..add(
          ChatTurn(
            role: 'assistant',
            content: response.message,
            createdAt: DateTime.now(),
          ),
        );
      setState(() {
        _messages.add(_Message.bot(response, sourcePrompt: message));
        _thinking = false;
      });
    } on ApiError catch (error) {
      if (!mounted) return;
      setState(() {
        _messages.add(_Message.error(_errorMessage(error)));
        _thinking = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _messages.add(_Message.error('잠시 문제가 생겼어요. 잠시 뒤 다시 시도해주세요.'));
        _thinking = false;
      });
    }
    _scrollToBottom();
  }

  /// Resends the gated message with an approval payload to run the analysis.
  void _approveAnalysis(_Message message) {
    final ChatbotResponse? response = message.response;
    if (response == null || _thinking) return;
    HapticFeedback.selectionClick();
    final String userPrompt = message.approvalSourcePrompt ?? '';
    setState(() {
      message.approvalResolved = true;
      _thinking = true;
    });
    _scrollToBottom();
    _dispatch(
      message: userPrompt,
      analysisRunApproval: <String, dynamic>{
        'approved': true,
        'analysis_kind': response.approvalPreview.analysisKind,
      },
    );
  }

  /// Dismisses the approval card without running the analysis.
  void _declineAnalysis(_Message message) {
    setState(() {
      message.approvalResolved = true;
    });
  }

  String _errorMessage(ApiError error) {
    if (error.code == 'network_unavailable' || error.statusCode == 0) {
      return '인터넷 연결을 확인한 뒤 다시 시도해주세요.';
    }
    final String detail = error.message.trim();
    if (detail.isEmpty) {
      return '답변을 가져오지 못했어요. 잠시 뒤 다시 시도해주세요.';
    }
    return detail;
  }

  @override
  void initState() {
    super.initState();
    _schedulePendingDraft();
  }

  @override
  void didUpdateWidget(ChatScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    _schedulePendingDraft();
  }

  void _schedulePendingDraft() {
    final ChatExplanationDraft? draft =
        widget.controller?.pendingChatExplanationDraft;
    if (draft == null || draft.id == _appliedDraftId) return;
    _appliedDraftId = draft.id;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      // Preserve the analysis-to-chat draft: render the user prompt and the
      // precomputed safe explanation, and seed the conversation history so the
      // user's next live question carries this turn as context for the backend.
      final DateTime now = DateTime.now();
      _history
        ..add(ChatTurn(role: 'user', content: draft.userPrompt, createdAt: now))
        ..add(
          ChatTurn(
            role: 'assistant',
            content: draft.assistantMessage,
            createdAt: now,
          ),
        );
      setState(() {
        _messages
          ..add(_Message.user(draft.userPrompt))
          ..add(_Message.text(draft.assistantMessage));
      });
      widget.controller?.markChatExplanationDraftDelivered(draft.id);
      _scrollToBottom();
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtl.hasClients) {
        _scrollCtl.animateTo(
          _scrollCtl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 240),
          curve: Curves.easeOutCubic,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    _schedulePendingDraft();
    return Scaffold(
      backgroundColor: AppColor.section,
      body: Column(
        children: [
          _ChatHeader(),
          Expanded(
            child: ListView(
              controller: _scrollCtl,
              padding: const EdgeInsets.fromLTRB(
                AppSpace.page,
                AppSpace.lg,
                AppSpace.page,
                AppSpace.lg,
              ),
              children: [
                _IntroCard(),
                const SizedBox(height: AppSpace.md),
                if (_messages.isEmpty)
                  _SuggestionGrid(suggestions: _suggestions, onTap: _send),
                for (final m in _messages) ...[
                  _MessageBubble(message: m),
                  ..._buildMessageExtras(m),
                  const SizedBox(height: AppSpace.sm),
                ],
                if (_thinking) const _TypingBubble(),
              ],
            ),
          ),
          const _ChatDisclaimerLine(),
          _InputBar(
            controller: _controller,
            onSend: _send,
            disabled: _thinking,
          ),
        ],
      ),
    );
  }

  /// Builds the metadata widgets rendered beneath an assistant message:
  /// an answerability caption, reviewed-source chips, suggestion (CTA) chips,
  /// and an analysis-approval card when a run is gated.
  List<Widget> _buildMessageExtras(_Message message) {
    final ChatbotResponse? response = message.response;
    if (response == null) {
      return const <Widget>[];
    }
    final List<Widget> extras = <Widget>[];

    if (!response.isAnswerable) {
      extras
        ..add(const SizedBox(height: AppSpace.xs))
        ..add(_AnswerabilityCaption(answerability: response.answerability));
    }

    if (response.sources.isNotEmpty) {
      extras
        ..add(const SizedBox(height: AppSpace.xs))
        ..add(_SourceChips(sources: response.sources));
    }

    if (response.needsAnalysisApproval && !message.approvalResolved) {
      extras
        ..add(const SizedBox(height: AppSpace.sm))
        ..add(
          _ApprovalCard(
            preview: response.approvalPreview,
            onApprove: () => _approveAnalysis(message),
            onDecline: () => _declineAnalysis(message),
          ),
        );
    }

    // Inline analysis card — only after a completed approval loop persisted a
    // result (guide 05 (a)); ordinary chat turns never surface it to avoid noise.
    if (response.isApprovedAnalysisResult) {
      extras
        ..add(const SizedBox(height: AppSpace.sm))
        ..add(
          ChatAnalysisCard(
            isToday: response.isTodayAnalysisKind,
            today: response.today,
            smart: response.smart,
            candidates: response.checklistCandidates,
            onCandidateTap: _thinking ? null : _send,
          ),
        );
    }

    if (response.ctas.isNotEmpty) {
      extras
        ..add(const SizedBox(height: AppSpace.sm))
        ..add(_CtaChips(ctas: response.ctas, onTap: _thinking ? null : _send));
    }

    return extras;
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollCtl.dispose();
    super.dispose();
  }
}

// ─── 데이터 모델 ───
enum _MessageKind { user, bot, error }

class _Message {
  _Message._({
    required this.text,
    required this.kind,
    this.response,
    this.approvalSourcePrompt,
  });

  /// A user-authored message bubble (right aligned, brand background).
  factory _Message.user(String text) =>
      _Message._(text: text, kind: _MessageKind.user);

  /// A plain assistant text bubble without response metadata.
  factory _Message.text(String text) =>
      _Message._(text: text, kind: _MessageKind.bot);

  /// An assistant message backed by a full [ChatbotResponse].
  ///
  /// The originating user prompt is captured so a gated analysis run can be
  /// resumed by resending the same message with an approval payload.
  factory _Message.bot(ChatbotResponse response, {String? sourcePrompt}) =>
      _Message._(
        text: response.message,
        kind: _MessageKind.bot,
        response: response,
        approvalSourcePrompt: sourcePrompt,
      );

  /// A user-friendly error bubble.
  factory _Message.error(String text) =>
      _Message._(text: text, kind: _MessageKind.error);

  final String text;
  final _MessageKind kind;

  /// Full backend response for assistant bubbles, when available.
  final ChatbotResponse? response;

  /// User prompt that produced [response]; used to resume a gated analysis run.
  final String? approvalSourcePrompt;

  /// Whether the approval card on this message has been acted on.
  bool approvalResolved = false;

  bool get mine => kind == _MessageKind.user;
}

// ═══════════════════════════════════════════
// 상단 헤더 (brand soft)
// ═══════════════════════════════════════════
class _ChatHeader extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    // Figma 773:23 — 노란 라운드 카드 + 마스코트 아바타(초록 온라인 점) + 부제.
    return SafeArea(
      bottom: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpace.page,
          AppSpace.md,
          AppSpace.page,
          AppSpace.sm,
        ),
        child: Container(
          padding: const EdgeInsets.all(AppSpace.lg),
          decoration: BoxDecoration(
            color: AppColor.brand,
            borderRadius: BorderRadius.circular(AppRadius.xl),
            boxShadow: [
              BoxShadow(
                color: AppColor.brand.withValues(alpha: 0.30),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Row(
            children: [
              // 마스코트 아바타 + 온라인 상태 점 (figma)
              SizedBox(
                width: 52,
                height: 52,
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Container(
                      width: 52,
                      height: 52,
                      padding: const EdgeInsets.all(5),
                      decoration: const BoxDecoration(
                        color: AppColor.surface,
                        shape: BoxShape.circle,
                      ),
                      child: Image.asset(
                        'assets/mascot/poses/find.png',
                        fit: BoxFit.contain,
                        errorBuilder: (context, error, stackTrace) => Icon(
                          Icons.smart_toy_rounded,
                          color: AppColor.brandDeep,
                          size: 28,
                        ),
                      ),
                    ),
                    Positioned(
                      right: 0,
                      bottom: 2,
                      child: Container(
                        width: 13,
                        height: 13,
                        decoration: BoxDecoration(
                          color: AppColor.success,
                          shape: BoxShape.circle,
                          border: Border.all(color: AppColor.brand, width: 2.5),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpace.md),
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '레몬봇',
                    style: TextStyle(
                      color: AppColor.ink,
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0,
                    ),
                  ),
                  SizedBox(height: 3),
                  Text(
                    '영양·식단 도우미 · 항상 대기 중',
                    style: TextStyle(
                      color: AppColor.ink,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 인사 — 봇 말풍선 (figma 773:23, 좌측 흰 버블)
// ═══════════════════════════════════════════
class _IntroCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.82,
        ),
        child: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpace.lg,
            vertical: AppSpace.md + 2,
          ),
          decoration: BoxDecoration(
            color: AppColor.surface,
            borderRadius: BorderRadius.circular(AppRadius.lg),
            boxShadow: const [
              BoxShadow(
                color: Color.fromRGBO(140, 155, 175, 0.14),
                blurRadius: 14,
                offset: Offset(0, 4),
              ),
            ],
          ),
          child: const Text(
            '안녕하세요! 영양·식단·복약까지,\n궁금한 걸 편하게 물어보세요.',
            style: TextStyle(
              color: AppColor.ink,
              fontSize: 15,
              fontWeight: FontWeight.w500,
              height: 1.5,
              letterSpacing: 0,
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 추천 질문 그리드
// ═══════════════════════════════════════════
class _SuggestionGrid extends StatelessWidget {
  final List<String> suggestions;
  final ValueChanged<String> onTap;
  const _SuggestionGrid({required this.suggestions, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.only(left: 4, bottom: AppSpace.sm),
          child: Text(
            '이런 걸 물어보면 좋아요',
            style: TextStyle(
              color: AppColor.inkSecondary,
              fontSize: 13,
              fontWeight: FontWeight.w700,
              letterSpacing: 0,
            ),
          ),
        ),
        // Figma 773:23 — 세로 스택 + ↗ 아이콘 (그리드 아님)
        for (final s in suggestions)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpace.sm),
            child: _SuggestChip(text: s, onTap: () => onTap(s)),
          ),
      ],
    );
  }
}

class _SuggestChip extends StatelessWidget {
  final String text;
  final VoidCallback onTap;
  const _SuggestChip({required this.text, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpace.md,
            vertical: 12,
          ),
          decoration: BoxDecoration(
            color: AppColor.surface,
            borderRadius: BorderRadius.circular(AppRadius.full),
            boxShadow: const [
              BoxShadow(
                color: Color.fromRGBO(140, 155, 175, 0.12),
                blurRadius: 10,
                offset: Offset(0, 3),
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.north_east_rounded,
                size: 16,
                color: AppColor.inkTertiary,
              ),
              const SizedBox(width: AppSpace.sm),
              Text(
                text,
                style: const TextStyle(
                  color: AppColor.ink,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 메시지 버블
// ═══════════════════════════════════════════
class _MessageBubble extends StatelessWidget {
  final _Message message;
  const _MessageBubble({required this.message});

  @override
  Widget build(BuildContext context) {
    final mine = message.mine;
    final isError = message.kind == _MessageKind.error;
    final bg = mine
        ? AppColor.brand
        : isError
        ? AppColor.dangerSoft
        : AppColor.surface;
    final fg = isError ? AppColor.danger : AppColor.ink;
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        child: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpace.md,
            vertical: 10,
          ),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(16),
              topRight: const Radius.circular(16),
              bottomLeft: Radius.circular(mine ? 16 : 4),
              bottomRight: Radius.circular(mine ? 4 : 16),
            ),
            boxShadow: (mine || isError)
                ? null
                : const [
                    BoxShadow(
                      color: Color.fromRGBO(140, 155, 175, 0.14),
                      blurRadius: 10,
                      offset: Offset(0, 3),
                    ),
                  ],
          ),
          child: Text(
            message.text,
            style: TextStyle(
              color: fg,
              // 시니어 최소치(SoT §9.1) — 주 읽기면이라 본문 15px
              fontSize: 15,
              fontWeight: mine ? FontWeight.w700 : FontWeight.w500,
              height: 1.45,
              letterSpacing: 0,
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 답변 가능성 안내 캡션 (answerability ≠ answerable)
// ═══════════════════════════════════════════
class _AnswerabilityCaption extends StatelessWidget {
  final String answerability;
  const _AnswerabilityCaption({required this.answerability});

  static const String _defaultLabel = '확인된 근거가 부족해요. 참고용으로만 봐주세요.';

  String get _label {
    switch (answerability) {
      case 'needs_more_info':
        return '조금 더 알려주시면 더 정확히 안내할 수 있어요.';
      case 'unknown_no_reviewed_source':
        return '아직 확인된 근거가 부족한 내용이에요. 참고용으로만 봐주세요.';
      default:
        return _defaultLabel;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.only(top: 1, right: 4),
              child: Icon(
                Icons.info_outline_rounded,
                size: 13,
                color: AppColor.review,
              ),
            ),
            Flexible(
              child: Text(
                _label,
                style: const TextStyle(
                  color: AppColor.review,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  height: 1.35,
                  letterSpacing: 0,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 출처 칩 (작은 inkTertiary 캡션)
// ═══════════════════════════════════════════
class _SourceChips extends StatelessWidget {
  final List<ChatbotSource> sources;
  const _SourceChips({required this.sources});

  @override
  Widget build(BuildContext context) {
    final List<ChatbotSource> visible = sources
        .where((ChatbotSource s) => s.label.isNotEmpty)
        .toList(growable: false);
    if (visible.isEmpty) {
      return const SizedBox.shrink();
    }
    return Align(
      alignment: Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        child: Wrap(
          spacing: AppSpace.xs,
          runSpacing: AppSpace.xs,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            const Padding(
              padding: EdgeInsets.only(top: 3),
              child: Text(
                '근거',
                style: TextStyle(
                  color: AppColor.inkTertiary,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0,
                ),
              ),
            ),
            // 출처 칩 탭 → 상세 바텀시트(가이드 05 ⑧). url_launcher 미도입 → 복사 전용.
            for (final ChatbotSource source in visible)
              GestureDetector(
                onTap: () => _showSourceSheet(context, source),
                child: ConstrainedBox(
                  // Cap each chip below the parent Wrap width so a long label
                  // ellipsizes instead of overflowing the row (RenderFlex fix).
                  constraints: BoxConstraints(
                    maxWidth: MediaQuery.of(context).size.width * 0.72,
                  ),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpace.sm,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: AppColor.section,
                      borderRadius: BorderRadius.circular(AppRadius.full),
                      border: Border.all(color: AppColor.border, width: 1),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        const Icon(
                          Icons.menu_book_rounded,
                          size: 12,
                          color: AppColor.inkTertiary,
                        ),
                        const SizedBox(width: 4),
                        Flexible(
                          child: Text(
                            source.label,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            softWrap: false,
                            style: const TextStyle(
                              color: AppColor.inkSecondary,
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 0,
                            ),
                          ),
                        ),
                        const SizedBox(width: 2),
                        const Icon(
                          Icons.chevron_right_rounded,
                          size: 13,
                          color: AppColor.inkTertiary,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// 출처 상세 바텀시트 — 제목/출처군/식별자/URL(복사 전용) + 안내 캡션.
void _showSourceSheet(BuildContext context, ChatbotSource source) {
  final String title = source.label;
  final String family = source.familyLabel;
  final String id = source.sourceId.trim();
  final String url = source.sourceUrl.trim();
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: AppColor.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.lg)),
    ),
    builder: (BuildContext sheetContext) {
      return SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(AppSpace.lg),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColor.borderStrong,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                  ),
                ),
              ),
              const SizedBox(height: AppSpace.lg),
              Text(
                title.isNotEmpty ? title : '출처',
                style: AppText.subtitle.copyWith(fontWeight: FontWeight.w800),
              ),
              if (family.isNotEmpty) ...<Widget>[
                const SizedBox(height: AppSpace.sm),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpace.sm,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: AppColor.section,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                    border: Border.all(color: AppColor.border, width: 1),
                  ),
                  child: Text(
                    family,
                    style: AppText.micro.copyWith(color: AppColor.inkSecondary),
                  ),
                ),
              ],
              if (id.isNotEmpty) ...<Widget>[
                const SizedBox(height: AppSpace.sm),
                Text(
                  id,
                  style: AppText.micro.copyWith(color: AppColor.inkTertiary),
                ),
              ],
              if (url.isNotEmpty) ...<Widget>[
                const SizedBox(height: AppSpace.md),
                SelectableText(
                  url,
                  style: AppText.caption.copyWith(color: AppColor.inkSecondary),
                ),
                const SizedBox(height: AppSpace.sm),
                GestureDetector(
                  onTap: () {
                    Clipboard.setData(ClipboardData(text: url));
                    HapticFeedback.selectionClick();
                    Navigator.of(sheetContext).pop();
                    ScaffoldMessenger.of(context).clearSnackBars();
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(
                          '링크를 복사했어요.',
                          style: AppText.body.copyWith(color: AppColor.bg),
                        ),
                        backgroundColor: AppColor.ink,
                        behavior: SnackBarBehavior.floating,
                      ),
                    );
                  },
                  child: Container(
                    height: 48,
                    alignment: Alignment.centerLeft,
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Icon(
                          Icons.copy_rounded,
                          size: 18,
                          color: AppColor.brandDeep,
                        ),
                        const SizedBox(width: AppSpace.xs),
                        Text(
                          'URL 복사',
                          style: AppText.caption.copyWith(
                            color: AppColor.brandDeep,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
              const SizedBox(height: AppSpace.lg),
              Text(
                '검수된 출처 기반 안내예요. 참고용으로 봐주세요.',
                style: AppText.micro.copyWith(color: AppColor.inkTertiary),
              ),
            ],
          ),
        ),
      );
    },
  );
}

// ═══════════════════════════════════════════
// 제안 칩 (CTA) — 탭하면 해당 텍스트로 전송
// ═══════════════════════════════════════════
class _CtaChips extends StatelessWidget {
  final List<String> ctas;
  final ValueChanged<String>? onTap;
  const _CtaChips({required this.ctas, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        child: Wrap(
          spacing: AppSpace.sm,
          runSpacing: AppSpace.sm,
          children: [
            for (final String cta in ctas.take(3))
              GestureDetector(
                onTap: onTap == null ? null : () => onTap!(cta),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpace.md,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: AppColor.brandSoft,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                    border: Border.all(color: AppColor.brandTint, width: 1),
                  ),
                  child: Text(
                    cta,
                    style: TextStyle(
                      color: AppColor.brandDeep,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 분석 승인 카드 (approval_required)
// ═══════════════════════════════════════════
class _ApprovalCard extends StatelessWidget {
  final ChatbotApprovalPreview preview;
  final VoidCallback onApprove;
  final VoidCallback onDecline;
  const _ApprovalCard({
    required this.preview,
    required this.onApprove,
    required this.onDecline,
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.86,
        ),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AppSpace.lg),
          decoration: BoxDecoration(
            color: AppColor.infoSoft,
            borderRadius: BorderRadius.circular(AppRadius.md),
            border: Border.all(color: AppColor.info, width: 1),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: const [
                  Icon(Icons.insights_rounded, size: 18, color: AppColor.info),
                  SizedBox(width: AppSpace.sm),
                  Text(
                    '분석을 실행할까요?',
                    style: TextStyle(
                      color: AppColor.ink,
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpace.sm),
              Text(
                '내 기록을 바탕으로 분석 결과를 정리해드려요. 실행에 동의하면 진행할게요.',
                style: const TextStyle(
                  color: AppColor.inkSecondary,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w500,
                  height: 1.4,
                  letterSpacing: 0,
                ),
              ),
              if (preview.sideEffects.isNotEmpty) ...[
                const SizedBox(height: AppSpace.xs),
                Text(
                  '예상 변경: ${preview.sideEffects.join(', ')}',
                  style: const TextStyle(
                    color: AppColor.inkTertiary,
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    height: 1.35,
                    letterSpacing: 0,
                  ),
                ),
              ],
              const SizedBox(height: AppSpace.md),
              Row(
                children: [
                  Expanded(
                    child: GestureDetector(
                      onTap: onApprove,
                      child: Container(
                        height: 42,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: AppColor.brand,
                          borderRadius: BorderRadius.circular(AppRadius.sm),
                        ),
                        child: const Text(
                          '분석 실행하기',
                          style: TextStyle(
                            color: AppColor.ink,
                            fontSize: 13.5,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0,
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: AppSpace.sm),
                  Expanded(
                    child: GestureDetector(
                      onTap: onDecline,
                      child: Container(
                        height: 42,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: AppColor.surface,
                          borderRadius: BorderRadius.circular(AppRadius.sm),
                          border: Border.all(
                            color: AppColor.borderStrong,
                            width: 1,
                          ),
                        ),
                        child: const Text(
                          '괜찮아요',
                          style: TextStyle(
                            color: AppColor.inkSecondary,
                            fontSize: 13.5,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TypingBubble extends StatefulWidget {
  const _TypingBubble();
  @override
  State<_TypingBubble> createState() => _TypingBubbleState();
}

class _TypingBubbleState extends State<_TypingBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctl;
  @override
  void initState() {
    super.initState();
    _ctl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat();
  }

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.md,
          vertical: 12,
        ),
        decoration: BoxDecoration(
          color: AppColor.surface,
          borderRadius: BorderRadius.circular(16),
          boxShadow: const [
            BoxShadow(
              color: Color.fromRGBO(140, 155, 175, 0.14),
              blurRadius: 10,
              offset: Offset(0, 3),
            ),
          ],
        ),
        child: AnimatedBuilder(
          animation: _ctl,
          builder: (context, child) {
            Widget dot(double phase) {
              final t = (_ctl.value + phase) % 1.0;
              final opacity = (t < 0.5 ? t : 1 - t) * 2;
              return Container(
                width: 6,
                height: 6,
                margin: const EdgeInsets.symmetric(horizontal: 2),
                decoration: BoxDecoration(
                  color: AppColor.inkTertiary.withValues(
                    alpha: 0.3 + 0.7 * opacity,
                  ),
                  shape: BoxShape.circle,
                ),
              );
            }

            return Row(
              mainAxisSize: MainAxisSize.min,
              children: [dot(0), dot(0.33), dot(0.66)],
            );
          },
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 입력바
// ═══════════════════════════════════════════
// 입력창 위 상시 면책 라인 (figma S-11 `773:23` — 컴플라이언스 §14).
// 응답별 근거 부족 라벨과 별개로, 챗 화면에 항상 노출한다.
class _ChatDisclaimerLine extends StatelessWidget {
  const _ChatDisclaimerLine();

  /// 컴플라이언스 표준 문구 — 변경 시 금칙어 가드 테스트 확인.
  static const String text = '레몬봇 안내는 일반 참고용이에요. 진단을 대신하지 않아요.';

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColor.section,
      padding: const EdgeInsets.fromLTRB(
        AppSpace.page,
        AppSpace.sm,
        AppSpace.page,
        0,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: <Widget>[
          const Icon(Icons.info_outline, size: 13, color: AppColor.inkTertiary),
          const SizedBox(width: 4),
          Flexible(child: Text(text, style: AppText.micro)),
        ],
      ),
    );
  }
}

class _InputBar extends StatelessWidget {
  final TextEditingController controller;
  final ValueChanged<String> onSend;
  final bool disabled;
  const _InputBar({
    required this.controller,
    required this.onSend,
    required this.disabled,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColor.section,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.page,
            AppSpace.sm,
            AppSpace.page,
            AppSpace.md,
          ),
          child: Row(
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: AppColor.surface,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                    border: Border.all(color: AppColor.border, width: 1),
                  ),
                  child: TextField(
                    controller: controller,
                    enabled: !disabled,
                    minLines: 1,
                    maxLines: 4,
                    style: const TextStyle(
                      color: AppColor.ink,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0,
                    ),
                    decoration: InputDecoration(
                      hintText: '메시지를 입력하세요',
                      hintStyle: TextStyle(
                        color: AppColor.inkTertiary,
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                      border: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 18,
                        vertical: 12,
                      ),
                    ),
                    onSubmitted: onSend,
                    textInputAction: TextInputAction.send,
                  ),
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              GestureDetector(
                onTap: disabled ? null : () => onSend(controller.text),
                child: Container(
                  // 48px 터치 타깃(시니어 최소치) + 솔리드 brand(토큰)
                  width: 48,
                  height: 48,
                  decoration: BoxDecoration(
                    color: AppColor.brand,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppColor.brand.withValues(alpha: 0.35),
                        blurRadius: 12,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  alignment: Alignment.center,
                  child: const Icon(
                    Icons.arrow_upward_rounded,
                    color: AppColor.ink,
                    size: 22,
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
