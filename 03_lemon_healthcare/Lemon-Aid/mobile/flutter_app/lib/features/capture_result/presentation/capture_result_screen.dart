import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/theme/lemon_theme.dart';

class CaptureResultScreen extends StatelessWidget {
  const CaptureResultScreen({
    super.key,
    required this.type,
    required this.title,
    required this.subtitle,
    required this.details,
  });

  final String type;
  final String title;
  final String subtitle;
  final List<String> details;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: LemonColors.canvas,
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 20, 0, 32),
          children: <Widget>[
            Text(
              '오늘의 Agent',
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: LemonColors.warning,
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              '식단과 영양제 기준을 나눠 봅니다',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 6),
            Text('3/6개 항목 확인됨', style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 14),
            _AnalysisCard(
              icon: Icons.restaurant_rounded,
              iconColor: LemonColors.ink,
              iconBackground: LemonColors.lemon,
              title: '식단 분석',
              body:
                  '아침 식단은 당 함량을 낮추는 방향이 좋고, 점심은 탄수화물 양을 평소보다 한 숟갈 줄이는 흐름이 좋습니다.',
              rows: const <_AnalysisRow>[
                _AnalysisRow(
                  icon: Icons.warning_amber_rounded,
                  label: '식단 주의',
                  value: '탄수화물 양 조절',
                ),
                _AnalysisRow(
                  icon: Icons.water_drop_rounded,
                  label: '실천 방향',
                  value: '식전 물 먼저 마시기',
                ),
              ],
              onChatTap: () => context.go('/chat'),
            ),
            const SizedBox(height: 12),
            _AnalysisCard(
              icon: Icons.medication_liquid_rounded,
              iconColor: LemonColors.ink,
              iconBackground: LemonColors.leaf,
              title: '영양제 분석',
              body: '오메가-3는 식사 직후, 마그네슘은 저녁 식후로 유지하면 현재 루틴 안에서 이해하기 쉽습니다.',
              rows: const <_AnalysisRow>[
                _AnalysisRow(
                  icon: Icons.access_time_rounded,
                  label: '복용 흐름',
                  value: '식후 중심으로 정리',
                ),
                _AnalysisRow(
                  icon: Icons.fact_check_rounded,
                  label: '확인 결과',
                  value: '겹치는 성분 없음',
                ),
              ],
              onChatTap: () => context.go('/chat'),
            ),
            const SizedBox(height: 12),
            _AnalysisCard(
              icon: Icons.query_stats_rounded,
              iconColor: LemonColors.ink,
              iconBackground: LemonColors.lemon,
              title: '식단 + 영양제 통합 분석',
              body:
                  '식단의 당과 탄수화물 조절을 먼저 잡고, 영양제는 식사 직후 복용 흐름으로 연결하면 오늘 루틴이 안정적입니다.',
              rows: const <_AnalysisRow>[
                _AnalysisRow(
                  icon: Icons.restaurant_menu_rounded,
                  label: '식단 연결',
                  value: '당 함량 낮추기',
                ),
                _AnalysisRow(
                  icon: Icons.medication_liquid_rounded,
                  label: '복용 연결',
                  value: '식후 루틴 유지',
                ),
              ],
              onChatTap: () => context.go('/chat'),
            ),
          ],
        ),
      ),
    );
  }
}

class _AnalysisCard extends StatelessWidget {
  const _AnalysisCard({
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.title,
    required this.body,
    required this.rows,
    required this.onChatTap,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String title;
  final String body;
  final List<_AnalysisRow> rows;
  final VoidCallback onChatTap;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0xFFFFF8DF),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: iconBackground,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: SizedBox(
                    width: 44,
                    height: 44,
                    child: Icon(icon, color: iconColor, size: 25),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontSize: 18,
                        ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            Text(
              body,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    fontSize: 14,
                    color: LemonColors.ink,
                  ),
            ),
            const SizedBox(height: 10),
            for (final _AnalysisRow row in rows) ...<Widget>[
              row,
              const SizedBox(height: 4),
            ],
            const SizedBox(height: 2),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: onChatTap,
                style: TextButton.styleFrom(
                  minimumSize: const Size(0, 32),
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  visualDensity: VisualDensity.compact,
                ),
                icon: const Icon(Icons.chat_bubble_outline_rounded, size: 18),
                label: const Text('이 결과로 질문하기'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AnalysisRow extends StatelessWidget {
  const _AnalysisRow({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Icon(icon, color: LemonColors.warning, size: 18),
        const SizedBox(width: 10),
        SizedBox(
          width: 86,
          child: Text(
            label,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: LemonColors.warning,
                  fontWeight: FontWeight.w900,
                ),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: LemonColors.inkMuted,
                  fontWeight: FontWeight.w900,
                ),
          ),
        ),
      ],
    );
  }
}
