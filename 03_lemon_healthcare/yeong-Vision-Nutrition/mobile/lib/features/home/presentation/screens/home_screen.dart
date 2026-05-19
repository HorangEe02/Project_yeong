/// 임시 홈 화면 — Phase M-3 진입 버튼 (라우트는 M-2/M-3 에서 연결).
library;

import 'package:flutter/material.dart';

import '../../../../shared/widgets/disclaimer.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('레몬헬스케어')),
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
              // M-3 에서 /supplement/capture 라우트로 push 연결.
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
