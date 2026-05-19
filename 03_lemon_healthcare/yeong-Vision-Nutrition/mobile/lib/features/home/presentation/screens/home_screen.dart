/// 임시 홈 화면 — 면책 표시 + 로그아웃 버튼 + 영양제 등록 (M-3 placeholder).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../features/auth/presentation/providers/auth_notifier.dart';
import '../../../../shared/widgets/disclaimer.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('레몬헬스케어'),
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: '로그아웃',
            onPressed: () async {
              await ref.read(authNotifierProvider.notifier).logout();
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    '환영합니다',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text('만성질환자 중심의 AI 헬스케어 — Vision Nutrition'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('영양제 등록은 Phase M-3 에서 활성화됩니다.'),
                ),
              );
            },
            icon: const Icon(Icons.medication),
            label: const Text('영양제 등록'),
          ),
          const SizedBox(height: 32),
          const MedicalDisclaimer(),
        ],
      ),
    );
  }
}
