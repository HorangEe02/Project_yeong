import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/dev/dev_confirmed_samples.dart';
import '../../../shared/state/confirmed_entry_store.dart';
import '../../../shared/theme/lemon_theme.dart';
import '../../../shared/widgets/medical_disclaimer.dart';
import '../data/ai_coaching_repository.dart';
import '../domain/ai_coaching_models.dart';

class DailyCoachingScreen extends StatefulWidget {
  const DailyCoachingScreen({super.key});

  @override
  State<DailyCoachingScreen> createState() => _DailyCoachingScreenState();
}

class _DailyCoachingScreenState extends State<DailyCoachingScreen> {
  final AiCoachingRepository _repository = AiCoachingRepository();
  DailyCoachingResponse? _response;
  Object? _error;
  bool _isLoading = false;

  Future<void> _runConfirmedFlow() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      await _repository.grantSensitiveHealthAnalysisConsent();
      final DailyCoachingResponse response = await _repository.runDailyCoaching(
        DailyCoachingRequest.fromConfirmedInputs(
          foods: ConfirmedEntryStore.instance.foods,
          supplements: ConfirmedEntryStore.instance.supplements,
          activities: ConfirmedEntryStore.instance.activities,
        ),
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _response = response;
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error;
      });
    } finally {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  Future<void> _seedDevSampleAndRun() async {
    seedDevConfirmedEntries();
    setState(() {
      _response = null;
      _error = null;
    });
    await _runConfirmedFlow();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
          children: <Widget>[
            Row(
              children: <Widget>[
                IconButton(
                  onPressed: () => context.go('/'),
                  icon: const Icon(Icons.arrow_back_rounded),
                ),
                Expanded(
                  child: Text(
                    'Daily coaching',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            LemonCard(
              color: LemonColors.lemonSoft,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const Icon(
                    Icons.psychology_alt_rounded,
                    color: LemonColors.leaf,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          '확정 입력 기반 코칭',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '음식 ${ConfirmedEntryStore.instance.foods.length}개, '
                          '영양제 ${ConfirmedEntryStore.instance.supplements.length}개',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: _isLoading ? null : _runConfirmedFlow,
              icon: _isLoading
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.auto_awesome_rounded),
              label: Text(_isLoading ? '요청 중' : '코칭 요청'),
            ),
            if (kDebugMode) ...<Widget>[
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: _isLoading ? null : _seedDevSampleAndRun,
                icon: const Icon(Icons.science_rounded),
                label: const Text('개발용 샘플로 LLM 코칭 실행'),
              ),
            ],
            const SizedBox(height: 16),
            if (_error != null) const _ErrorPanel(),
            if (_response != null) _CoachingResult(response: _response!),
            const SizedBox(height: 24),
            const MedicalDisclaimer(),
          ],
        ),
      ),
    );
  }
}

class _CoachingResult extends StatelessWidget {
  const _CoachingResult({required this.response});

  final DailyCoachingResponse response;

  @override
  Widget build(BuildContext context) {
    final String memoryLabel = response.usedAgentMemory ? '사용' : '미사용';
    final List<String> visibleWarnings = _visibleSafetyWarnings(
      response.safetyWarnings,
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: <Widget>[
            LemonPill(
              label: response.provider,
              color: LemonColors.leaf,
              backgroundColor: LemonColors.leafSoft,
            ),
            LemonPill(
              label: 'memory $memoryLabel',
              color: LemonColors.sky,
              backgroundColor: LemonColors.skySoft,
            ),
          ],
        ),
        const SizedBox(height: 12),
        _CoachingSection(
          icon: Icons.summarize_rounded,
          title: '오늘의 요약',
          child: Text(
            response.message,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
        ),
        const SizedBox(height: 12),
        _CoachingSection(
          icon: Icons.check_circle_outline_rounded,
          title: '권장 행동',
          child: _RecommendationList(
            recommendations: response.recommendations,
          ),
        ),
        const SizedBox(height: 12),
        _CoachingSection(
          icon: Icons.info_outline_rounded,
          title: '참고 및 주의',
          child: _CautionList(
            findings: response.findings,
            warnings: visibleWarnings,
          ),
        ),
      ],
    );
  }
}

class _CoachingSection extends StatelessWidget {
  const _CoachingSection({
    required this.icon,
    required this.title,
    required this.child,
  });

  final IconData icon;
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LemonCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(icon, color: LemonColors.leaf, size: 22),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          child,
        ],
      ),
    );
  }
}

class _RecommendationList extends StatelessWidget {
  const _RecommendationList({required this.recommendations});

  final List<Map<String, dynamic>> recommendations;

  @override
  Widget build(BuildContext context) {
    if (recommendations.isEmpty) {
      return Text(
        '오늘은 추가로 실행할 권장 행동이 크지 않습니다.',
        style: Theme.of(context).textTheme.bodyMedium,
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: recommendations
          .map(
            (Map<String, dynamic> recommendation) => _BulletText(
              title: _recommendationTitle(recommendation),
              body: _recommendationBody(recommendation),
            ),
          )
          .toList(growable: false),
    );
  }
}

class _CautionList extends StatelessWidget {
  const _CautionList({
    required this.findings,
    required this.warnings,
  });

  final List<Map<String, dynamic>> findings;
  final List<String> warnings;

  @override
  Widget build(BuildContext context) {
    final List<Widget> children = <Widget>[
      const _BulletText(
        title: '현재 입력된 정보 기준',
        body: '사진 인식이나 수동 입력이 틀렸다면 코칭 결과도 달라질 수 있습니다.',
      ),
      for (final Map<String, dynamic> finding in findings.take(3))
        _BulletText(
          title: _findingTitle(finding),
          body: _findingBody(finding),
        ),
      for (final String warning in warnings)
        _BulletText(
          title: '주의',
          body: warning,
        ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    );
  }
}

class _BulletText extends StatelessWidget {
  const _BulletText({
    required this.title,
    required this.body,
  });

  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Icon(Icons.circle, size: 6, color: LemonColors.leaf),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(title, style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 2),
                Text(body, style: Theme.of(context).textTheme.bodyMedium),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

String _recommendationTitle(Map<String, dynamic> recommendation) {
  final String title = recommendation['title'] as String? ?? '';
  final String category = recommendation['category'] as String? ?? '';
  final String nutrient = _nutrientFromTitle(title);

  switch (category) {
    case 'reduce':
      return '${_koNutrientLabel(nutrient)} 섭취 조정';
    case 'add_food':
      return '${_koNutrientLabel(nutrient)} 음식 보완';
    case 'consider_ingredient':
      return '${_koNutrientLabel(nutrient)} 보충 필요성 확인';
    case 'mission':
      return '오늘의 실천';
    case 'reminder':
      return '복용/기록 확인';
  }
  return title.isEmpty ? '권장 행동' : title;
}

String _recommendationBody(Map<String, dynamic> recommendation) {
  final String category = recommendation['category'] as String? ?? '';
  final bool requiresConsult =
      recommendation['requires_professional_consult'] as bool? ?? false;

  if (requiresConsult) {
    return '현재 입력 기준으로 주의가 필요할 수 있어 전문가 상담을 권장합니다.';
  }

  switch (category) {
    case 'reduce':
      return '오늘 기록에서 높은 항목이 있어 섭취량을 줄이는 방향으로 확인해 주세요.';
    case 'add_food':
      return '부족할 수 있는 항목은 보충제보다 식사에서 먼저 보완해 보세요.';
    case 'consider_ingredient':
      return '필요성과 안전성을 확인한 뒤 신중하게 보충 여부를 판단해 주세요.';
    case 'mission':
      return '부담이 작은 행동부터 오늘 안에 실행해 보세요.';
    case 'reminder':
      return '정해 둔 일정과 실제 기록이 맞는지 확인해 주세요.';
  }
  return '현재 입력 기준으로 참고할 수 있는 행동입니다.';
}

String _findingTitle(Map<String, dynamic> finding) {
  final String nutrient = finding['nutrient'] as String? ?? '';
  final String level = finding['level'] as String? ?? '';
  return '${_koNutrientLabel(nutrient)} ${_koFindingLevel(level)}';
}

String _findingBody(Map<String, dynamic> finding) {
  final num? amount = finding['total_amount'] as num?;
  final String unit = finding['unit'] as String? ?? '';
  if (amount == null) {
    return '확인된 입력을 기준으로 참고해 주세요.';
  }
  return '확인된 총량은 ${amount.toStringAsFixed(amount % 1 == 0 ? 0 : 1)}$unit입니다.';
}

List<String> _visibleSafetyWarnings(List<String> warnings) {
  bool hidInternalWarning = false;
  final List<String> visible = <String>[];

  for (final String warning in warnings) {
    if (_isInternalWarning(warning)) {
      hidInternalWarning = true;
      continue;
    }
    visible.add(warning);
  }

  if (hidInternalWarning) {
    visible.add('일부 내부 검증 문구는 안전 기준에 따라 숨겼습니다.');
  }
  return visible;
}

bool _isInternalWarning(String warning) {
  final String lowered = warning.toLowerCase();
  return lowered.contains('trace') ||
      lowered.contains('policy guard') ||
      lowered.contains('forbidden medical expression') ||
      lowered.contains('product-promotion') ||
      lowered.contains('text withheld');
}

String _nutrientFromTitle(String title) {
  final String lowered = title.toLowerCase();
  if (lowered.startsWith('reduce ')) {
    return title.substring(7);
  }
  if (lowered.startsWith('add ') && lowered.endsWith(' from food first')) {
    return lowered
        .replaceFirst('add ', '')
        .replaceFirst(' from food first', '');
  }
  if (lowered.startsWith('consider ') &&
      lowered.endsWith(' ingredient support')) {
    return lowered
        .replaceFirst('consider ', '')
        .replaceFirst(' ingredient support', '');
  }
  return title;
}

String _koFindingLevel(String level) {
  switch (level) {
    case 'low':
      return '부족 가능성';
    case 'adequate':
      return '적정 범위';
    case 'high':
      return '높은 편';
    case 'risky':
      return '주의 필요';
  }
  return '확인 필요';
}

String _koNutrientLabel(String nutrient) {
  final String normalized = nutrient.trim().toLowerCase().replaceAll('_', ' ');
  switch (normalized) {
    case 'vitamin d':
      return '비타민 D';
    case 'sodium':
      return '나트륨';
    case 'protein':
      return '단백질';
    case 'fiber':
      return '식이섬유';
    case 'magnesium':
      return '마그네슘';
    case 'calcium':
      return '칼슘';
    case 'iron':
      return '철분';
    case 'omega-3':
      return '오메가-3';
  }
  return nutrient.isEmpty ? '영양 항목' : nutrient;
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel();

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
            child: Text(
              '코칭 요청을 완료하지 못했습니다. 백엔드 연결과 인증 상태를 확인해 주세요.',
            ),
          ),
        ],
      ),
    );
  }
}
