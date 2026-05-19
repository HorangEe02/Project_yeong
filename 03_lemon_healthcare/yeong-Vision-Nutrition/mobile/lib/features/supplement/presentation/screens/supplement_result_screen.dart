/// 영양제 등록 결과 화면 — 성분 + KDRIs 진단 + 면책/응급/상담 안내.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../shared/widgets/consult_professional.dart';
import '../../../../shared/widgets/disclaimer.dart';
import '../../../../shared/widgets/emergency_resources.dart';
import '../../domain/supplement_models.dart';
import '../providers/supplement_notifier.dart';
import '../widgets/ingredient_card.dart';

class SupplementResultScreen extends ConsumerWidget {
  const SupplementResultScreen({super.key, required this.response});

  final SupplementResponse response;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ThemeData theme = Theme.of(context);
    final Map<String, NutrientDiagnosis> diagnosisByCode =
        <String, NutrientDiagnosis>{
      for (final NutrientDiagnosis d in response.diagnosis.diagnoses)
        d.code: d,
    };

    return Scaffold(
      appBar: AppBar(
        title: Text(response.productName ?? '영양제 등록 결과'),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: <Widget>[
            if (response.manufacturer != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  '제조사: ${response.manufacturer}',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ),
            _SummaryCard(diagnosis: response.diagnosis),
            const SizedBox(height: 16),
            if (response.ingredients.isNotEmpty) ...<Widget>[
              Text('성분별 진단', style: theme.textTheme.titleMedium),
              const SizedBox(height: 8),
              for (final Ingredient ingredient in response.ingredients)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: IngredientCard(
                    ingredient: ingredient,
                    diagnosis: diagnosisByCode[ingredient.code],
                  ),
                ),
            ],
            if (response.unmatchedIngredientNames.isNotEmpty) ...<Widget>[
              const SizedBox(height: 16),
              Text(
                '권장량 정보 없는 성분',
                style: theme.textTheme.titleMedium,
              ),
              const SizedBox(height: 4),
              Text(
                '아직 표준 권장량이 등록되지 않은 성분입니다.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: <Widget>[
                  for (final String name in response.unmatchedIngredientNames)
                    Chip(label: Text(name)),
                ],
              ),
            ],
            const SizedBox(height: 24),
            const MedicalDisclaimer(variant: DisclaimerVariant.supplement),
            const SizedBox(height: 16),
            EmergencyResources(items: response.emergencyResources),
            const SizedBox(height: 16),
            ConsultProfessional(
              message: response.consultProfessionalMessageKo,
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: () {
                ref.read(supplementNotifierProvider.notifier).reset();
                context.go('/');
              },
              icon: const Icon(Icons.refresh),
              label: const Text('다시 등록'),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.diagnosis});

  final DiagnosisResult diagnosis;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('요약', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            Row(
              children: <Widget>[
                _CountChip(
                  label: '부족',
                  count: diagnosis.deficientCount,
                  color: Colors.red.shade100,
                  textColor: Colors.red.shade900,
                ),
                const SizedBox(width: 8),
                _CountChip(
                  label: '적정',
                  count: diagnosis.adequateCount,
                  color: Colors.green.shade100,
                  textColor: Colors.green.shade900,
                ),
                const SizedBox(width: 8),
                _CountChip(
                  label: '주의',
                  count: diagnosis.riskyCount,
                  color: theme.colorScheme.errorContainer,
                  textColor: theme.colorScheme.onErrorContainer,
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              diagnosis.summaryMessageKo,
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _CountChip extends StatelessWidget {
  const _CountChip({
    required this.label,
    required this.count,
    required this.color,
    required this.textColor,
  });

  final String label;
  final int count;
  final Color color;
  final Color textColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Text(
        '$label $count',
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: textColor,
              fontWeight: FontWeight.bold,
            ),
      ),
    );
  }
}
