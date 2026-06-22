import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../shared/theme/lemon_theme.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

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
              '기록과 약속을 카드로 확인합니다',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 6),
            Text(
              '식단, 영양제, 분석을 나눠서 봅니다',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 14),
            _AgentSummaryCard(
              icon: Icons.restaurant_rounded,
              iconColor: LemonColors.sky,
              iconBackground: LemonColors.skySoft,
              label: '식단',
              value: '0 kcal',
              description: '아침, 점심, 저녁 기록',
              onTap: () => context.go('/food-capture'),
            ),
            const SizedBox(height: 12),
            _AgentSummaryCard(
              icon: Icons.medication_liquid_rounded,
              iconColor: LemonColors.leaf,
              iconBackground: LemonColors.leafSoft,
              label: '영양제',
              value: '0개',
              description: '복용 기록 추가',
              onTap: () => context.go('/supplement-capture'),
            ),
            const SizedBox(height: 12),
            _AgentSummaryCard(
              icon: Icons.speed_rounded,
              iconColor: LemonColors.warning,
              iconBackground: LemonColors.lemonSoft,
              label: '분석',
              value: '82점',
              description: '오늘 점수와 누적 흐름',
              onTap: () => context.go(
                '/entry-result'
                '?type=supplement'
                '&title=${Uri.encodeComponent('식단 + 영양제 통합 분석')}'
                '&subtitle=${Uri.encodeComponent('식단의 당과 탄수화물 조절을 먼저 잡고, 영양제는 식사 직후 복용 흐름으로 연결하면 오늘 루틴이 안정적입니다.')}'
                '&detail1=${Uri.encodeComponent('식단 주의: 탄수화물 양 조절')}'
                '&detail2=${Uri.encodeComponent('복용 연결: 식후 루틴 유지')}',
              ),
            ),
            const SizedBox(height: 16),
            const _PromiseCard(),
          ],
        ),
      ),
    );
  }
}

class _AgentSummaryCard extends StatelessWidget {
  const _AgentSummaryCard({
    required this.icon,
    required this.iconColor,
    required this.iconBackground,
    required this.label,
    required this.value,
    required this.description,
    required this.onTap,
  });

  final IconData icon;
  final Color iconColor;
  final Color iconBackground;
  final String label;
  final String value;
  final String description;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Ink(
          decoration: BoxDecoration(
            color: LemonColors.paper,
            borderRadius: BorderRadius.circular(16),
            boxShadow: const <BoxShadow>[
              BoxShadow(
                color: Color(0x12000000),
                blurRadius: 18,
                offset: Offset(0, 8),
              ),
            ],
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 18),
            child: SizedBox(
              height: 104,
              child: Row(
                children: <Widget>[
                  DecoratedBox(
                    decoration: BoxDecoration(
                      color: iconBackground,
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: SizedBox(
                      width: 58,
                      height: 58,
                      child: Icon(icon, color: iconColor, size: 30),
                    ),
                  ),
                  const SizedBox(width: 18),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          label,
                          style: Theme.of(context).textTheme.labelMedium,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          value,
                          style: Theme.of(context)
                              .textTheme
                              .headlineSmall
                              ?.copyWith(
                                fontSize: 28,
                                fontWeight: FontWeight.w900,
                              ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          description,
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ],
                    ),
                  ),
                  const Icon(
                    Icons.chevron_right_rounded,
                    color: LemonColors.inkMuted,
                    size: 30,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _PromiseCard extends StatelessWidget {
  const _PromiseCard();

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: LemonColors.paper,
        borderRadius: BorderRadius.circular(16),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x12000000),
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: const Padding(
        padding: EdgeInsets.fromLTRB(18, 18, 18, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              '오늘 하루 약속',
              style: TextStyle(
                color: LemonColors.ink,
                fontSize: 18,
                fontWeight: FontWeight.w800,
              ),
            ),
            SizedBox(height: 16),
            _PromiseRow(
              title: '아침 약속',
              description: '단 음식은 줄이고 오메가-3는 식사 직후 복용해요.',
              active: true,
            ),
            _PromiseRow(
              title: '점심 약속',
              description: '탄수화물 양을 평소보다 한 숟갈 줄이고 물을 먼저 마셔요.',
            ),
            _PromiseRow(
              title: '저녁 약속',
              description: '마그네슘은 저녁 식후로 유지하고 늦은 간식은 피합니다.',
            ),
          ],
        ),
      ),
    );
  }
}

class _PromiseRow extends StatelessWidget {
  const _PromiseRow({
    required this.title,
    required this.description,
    this.active = false,
  });

  final String title;
  final String description;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          DecoratedBox(
            decoration: BoxDecoration(
              color: active ? LemonColors.lemon : LemonColors.paper,
              shape: BoxShape.circle,
              border: Border.all(
                color: active ? LemonColors.warning : LemonColors.inkMuted,
                width: 2,
              ),
            ),
            child: SizedBox(
              width: 20,
              height: 20,
              child: active
                  ? const Icon(Icons.check_rounded, size: 14)
                  : const SizedBox.shrink(),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontSize: 14,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        fontSize: 12,
                        height: 1.35,
                      ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
