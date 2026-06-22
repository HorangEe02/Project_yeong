// features/chat/widgets/chat_analysis_card.dart — 챗 인라인 분석 결과 카드
//
// 승인 루프 완료(approved + analysis_result_persisted) 응답 직후 봇 말풍선
// 아래에 분석 스냅샷을 축약 카드로 인라인 렌더한다. figma C(620:2)·S-09(800:23)
// 축약 레이아웃 참조. (가이드 05 잔여 (a))
//
// 의료법 가드:
//   - 점수는 서버가 준 값만 노출. status='analysis_pending'/score=null 이면
//     점수 날조 금지 → "기록 보완" 안내 1줄 + missing_records 매핑.
//   - 등급 칩만(좋음/보통/확인 필요), % 비노출.
//   - 하단 면책 푸터 고정. "진단/처방/치료/효능" 금칙어 사용 금지.
//   - priority_adjustments / strengths / missing_records 등 서버 코드 문자열은
//     안전한 한국어 라벨로만 매핑하고, 매핑 없는 코드는 표시에서 제외.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../utils/design_tokens_v2.dart';
import '../chat_analysis_models.dart';
import '../chat_models.dart';

/// 챗 인라인 분석 결과 카드.
///
/// [isToday] 가 true 면 [today] 기반 점수 카드, 아니면 [smart] 기반 준비도 카드를
/// 렌더한다. [candidates] 는 표시 전용 후보 칩(탭 시 [onCandidateTap] 으로 해당
/// 문구를 챗에 전송 — 서버 실행 라우트 없음, 로컬 저장 금지).
class ChatAnalysisCard extends StatelessWidget {
  /// Creates the inline analysis card.
  const ChatAnalysisCard({
    required this.isToday,
    required this.today,
    required this.smart,
    required this.candidates,
    this.onCandidateTap,
    super.key,
  });

  /// Whether to render the today-analysis layout (else smart analysis).
  final bool isToday;

  /// Today-analysis snapshot view.
  final ChatTodayAnalysis today;

  /// Smart-analysis snapshot view.
  final ChatSmartAnalysis smart;

  /// Checklist candidates (display-only, capped at three).
  final List<ChatbotChecklistCandidate> candidates;

  /// Sends a candidate title to the chat input when tapped; null disables taps.
  final ValueChanged<String>? onCandidateTap;

  static const String _disclaimer = '건강 참고용이며 의료 행위를 대신하지 않아요.';

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
            color: AppColor.surface,
            borderRadius: BorderRadius.circular(AppRadius.md),
            border: Border.all(color: AppColor.border, width: 1),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const _CardHeader(),
              const SizedBox(height: AppSpace.md),
              if (isToday) ..._todayBody() else ..._smartBody(),
              ..._candidateSection(),
              const SizedBox(height: AppSpace.md),
              const _DisclaimerFooter(text: _disclaimer),
            ],
          ),
        ),
      ),
    );
  }

  // ── today_analysis ─────────────────────────────
  List<Widget> _todayBody() {
    if (today.isPending) {
      return <Widget>[_PendingNotice(missingRecords: today.missingRecords)];
    }
    final List<String> strengths = _mapCodes(today.strengths, _strengthLabels);
    final List<String> priorities = _mapCodes(
      today.priorityAdjustments,
      _axisLabels,
    );
    return <Widget>[
      _ScoreRow(score: today.score, scoreName: today.scoreName),
      if (strengths.isNotEmpty) ...<Widget>[
        const SizedBox(height: AppSpace.md),
        _SummaryRows(label: '잘하고 있어요', items: strengths),
      ],
      if (priorities.isNotEmpty) ...<Widget>[
        const SizedBox(height: AppSpace.sm),
        _SummaryRows(label: '이런 점을 살펴보면 좋아요', items: priorities),
      ],
    ];
  }

  // ── smart_analysis ─────────────────────────────
  List<Widget> _smartBody() {
    if (smart.isEmpty) {
      return const <Widget>[_PendingNotice(missingRecords: <String>[])];
    }
    final List<String> priorities = _mapCodes(
      smart.nutrientPriorities,
      _axisLabels,
    );
    return <Widget>[
      _ReadinessRow(
        readinessLevel: smart.readinessLevel,
        coveredCount: smart.coveredCount,
      ),
      if (priorities.isNotEmpty) ...<Widget>[
        const SizedBox(height: AppSpace.md),
        _SummaryRows(label: '챙기면 좋은 영양', items: priorities),
      ],
    ];
  }

  List<Widget> _candidateSection() {
    final List<ChatbotChecklistCandidate> shown = candidates
        .where((ChatbotChecklistCandidate c) => c.title.trim().isNotEmpty)
        .take(3)
        .toList(growable: false);
    if (shown.isEmpty) {
      return const <Widget>[];
    }
    return <Widget>[
      const SizedBox(height: AppSpace.md),
      _CandidateChips(candidates: shown, onTap: onCandidateTap),
    ];
  }

  /// Maps server codes to safe Korean labels, dropping unmapped codes.
  static List<String> _mapCodes(
    List<String> codes,
    Map<String, String> labels,
  ) {
    final List<String> mapped = <String>[];
    for (final String code in codes) {
      final String? label = labels[code];
      if (label != null && !mapped.contains(label)) {
        mapped.add(label);
      }
    }
    return mapped;
  }

  /// Strength code → Korean label.
  static const Map<String, String> _strengthLabels = <String, String>{
    'food_records_available': '식사 기록을 남기고 있어요',
    'supplement_check_available': '영양제 섭취를 확인하고 있어요',
    'supplements_confirmed': '영양제를 등록해 두었어요',
    'checklist_available': '실천 체크리스트가 있어요',
    'chat_signals_available': '대화로 알려준 정보가 있어요',
  };

  /// Nutrient-axis code → Korean label.
  static const Map<String, String> _axisLabels = <String, String>{
    'sodium_high': '나트륨이 조금 높았어요',
    'carbohydrate_high': '탄수화물이 조금 많았어요',
    'protein_low': '단백질이 부족했어요',
    'fat_high': '지방이 조금 많았어요',
    'sugar_high': '당이 조금 많았어요',
    'fiber_low': '식이섬유가 부족했어요',
  };
}

// ═══════════════════════════════════════════
// 헤더
// ═══════════════════════════════════════════
class _CardHeader extends StatelessWidget {
  const _CardHeader();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Icon(Icons.insights_rounded, size: 18, color: AppColor.brandDeep),
        const SizedBox(width: AppSpace.sm),
        const Text(
          '분석 결과 정리',
          style: TextStyle(
            color: AppColor.ink,
            fontSize: 14,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 점수 행 (점수 + 등급 칩, % 비노출)
// ═══════════════════════════════════════════
class _ScoreRow extends StatelessWidget {
  const _ScoreRow({required this.score, required this.scoreName});

  final int? score;
  final String scoreName;

  @override
  Widget build(BuildContext context) {
    final int value = score ?? 0;
    final _Grade grade = _Grade.fromScore(value);
    return Row(
      children: <Widget>[
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            color: AppColor.brandSoft,
            shape: BoxShape.circle,
            border: Border.all(color: AppColor.brandTint, width: 2),
          ),
          alignment: Alignment.center,
          child: Text(
            '$value',
            style: TextStyle(
              color: AppColor.brandDeep,
              fontSize: 22,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
        ),
        const SizedBox(width: AppSpace.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              if (scoreName.isNotEmpty)
                Text(
                  scoreName,
                  style: const TextStyle(
                    color: AppColor.inkSecondary,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 0,
                  ),
                ),
              const SizedBox(height: 6),
              _GradeChip(grade: grade),
            ],
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 준비도 행 (smart_analysis — 점수 없음)
// ═══════════════════════════════════════════
class _ReadinessRow extends StatelessWidget {
  const _ReadinessRow({
    required this.readinessLevel,
    required this.coveredCount,
  });

  final String readinessLevel;
  final int coveredCount;

  static const Map<String, String> _levelLabels = <String, String>{
    'level_0_preparing': '분석 준비 중',
    'level_1_initial': '첫 기록 단계',
    'level_2_recent_pattern': '최근 패턴 파악 중',
    'level_3_personal_baseline': '내 기준 형성 중',
    'level_4_long_term': '장기 흐름 분석',
  };

  @override
  Widget build(BuildContext context) {
    final String label = _levelLabels[readinessLevel] ?? '기록을 모으는 중';
    return Row(
      children: <Widget>[
        Container(
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
            label,
            style: TextStyle(
              color: AppColor.brandDeep,
              fontSize: 12.5,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
        ),
        const SizedBox(width: AppSpace.sm),
        Expanded(
          child: Text(
            '기록 $coveredCount/4 영역 반영',
            style: const TextStyle(
              color: AppColor.inkTertiary,
              fontSize: 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 요약 리스트 (강점 / 우선 보완 / 영양)
// ═══════════════════════════════════════════
class _SummaryRows extends StatelessWidget {
  const _SummaryRows({required this.label, required this.items});

  final String label;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          label,
          style: const TextStyle(
            color: AppColor.inkSecondary,
            fontSize: 12,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
        const SizedBox(height: 6),
        for (final String item in items.take(3))
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Padding(
                  padding: const EdgeInsets.only(top: 2, right: 6),
                  child: Icon(
                    Icons.check_circle_outline_rounded,
                    size: 14,
                    color: AppColor.brandDeep,
                  ),
                ),
                Expanded(
                  child: Text(
                    item,
                    style: const TextStyle(
                      color: AppColor.ink,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      height: 1.35,
                      letterSpacing: 0,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 점수 없음 / pending 안내 (날조 금지)
// ═══════════════════════════════════════════
class _PendingNotice extends StatelessWidget {
  const _PendingNotice({required this.missingRecords});

  final List<String> missingRecords;

  static const Map<String, String> _missingLabels = <String, String>{
    'food_records': '식사 기록',
    'supplement_check': '영양제 섭취 확인',
  };

  @override
  Widget build(BuildContext context) {
    final List<String> needed = <String>[];
    for (final String code in missingRecords) {
      final String? label = _missingLabels[code];
      if (label != null && !needed.contains(label)) {
        needed.add(label);
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: const <Widget>[
            Padding(
              padding: EdgeInsets.only(top: 1, right: 6),
              child: Icon(
                Icons.tips_and_updates_outlined,
                size: 16,
                color: AppColor.review,
              ),
            ),
            Expanded(
              child: Text(
                '기록을 조금 더 채우면 분석해드릴게요.',
                style: TextStyle(
                  color: AppColor.review,
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  height: 1.35,
                  letterSpacing: 0,
                ),
              ),
            ),
          ],
        ),
        if (needed.isNotEmpty) ...<Widget>[
          const SizedBox(height: 6),
          Padding(
            padding: const EdgeInsets.only(left: 22),
            child: Text(
              '필요한 기록: ${needed.join(', ')}',
              style: const TextStyle(
                color: AppColor.inkTertiary,
                fontSize: 12,
                fontWeight: FontWeight.w600,
                height: 1.35,
                letterSpacing: 0,
              ),
            ),
          ),
        ],
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 등급 칩 (% 비노출)
// ═══════════════════════════════════════════
enum _Grade {
  good('좋음', AppColor.success, AppColor.successSoft),
  fair('보통', AppColor.review, AppColor.reviewSoft),
  check('확인 필요', AppColor.danger, AppColor.dangerSoft);

  const _Grade(this.label, this.fg, this.bg);

  final String label;
  final Color fg;
  final Color bg;

  static _Grade fromScore(int score) {
    if (score >= 75) {
      return _Grade.good;
    }
    if (score >= 60) {
      return _Grade.fair;
    }
    return _Grade.check;
  }
}

class _GradeChip extends StatelessWidget {
  const _GradeChip({required this.grade});

  final _Grade grade;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.sm, vertical: 4),
      decoration: BoxDecoration(
        color: grade.bg,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        grade.label,
        style: TextStyle(
          color: grade.fg,
          fontSize: 12,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 체크리스트 후보 칩 (표시 전용 — 탭 시 챗 전송)
// ═══════════════════════════════════════════
class _CandidateChips extends StatelessWidget {
  const _CandidateChips({required this.candidates, required this.onTap});

  final List<ChatbotChecklistCandidate> candidates;
  final ValueChanged<String>? onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        const Text(
          '오늘 실천에 추가해볼까요?',
          style: TextStyle(
            color: AppColor.inkSecondary,
            fontSize: 12,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: AppSpace.sm,
          runSpacing: AppSpace.sm,
          children: <Widget>[
            for (final ChatbotChecklistCandidate candidate in candidates)
              GestureDetector(
                onTap: onTap == null
                    ? null
                    : () {
                        HapticFeedback.selectionClick();
                        onTap!('오늘 실천에 추가하고 싶어요: ${candidate.title}');
                      },
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpace.md,
                    vertical: 8,
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
                        Icons.add_rounded,
                        size: 14,
                        color: AppColor.inkSecondary,
                      ),
                      const SizedBox(width: 4),
                      Flexible(
                        child: Text(
                          candidate.title,
                          style: const TextStyle(
                            color: AppColor.inkSecondary,
                            fontSize: 12.5,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 6),
        const Text(
          '탭하면 오늘의 분석 탭에서 실천으로 정리할 수 있게 도와드려요.',
          style: TextStyle(
            color: AppColor.inkTertiary,
            fontSize: 11,
            fontWeight: FontWeight.w600,
            height: 1.35,
            letterSpacing: 0,
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 면책 푸터 (필수)
// ═══════════════════════════════════════════
class _DisclaimerFooter extends StatelessWidget {
  const _DisclaimerFooter({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.md,
        vertical: AppSpace.sm,
      ),
      decoration: BoxDecoration(
        color: AppColor.section,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Padding(
            padding: EdgeInsets.only(top: 1, right: 6),
            child: Icon(
              Icons.info_outline_rounded,
              size: 13,
              color: AppColor.inkTertiary,
            ),
          ),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: AppColor.inkTertiary,
                fontSize: 11,
                fontWeight: FontWeight.w600,
                height: 1.35,
                letterSpacing: 0,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
