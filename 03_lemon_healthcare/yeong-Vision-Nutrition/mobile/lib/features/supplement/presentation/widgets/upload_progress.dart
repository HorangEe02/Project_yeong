/// 영양제 업로드 진행률 — multipart 송신 중 + 분석 대기 안내.
library;

import 'package:flutter/material.dart';

class UploadProgress extends StatelessWidget {
  const UploadProgress({super.key, required this.progress});

  /// 0.0 ~ 1.0. 1.0 도달 후 백엔드가 OCR + LLM 처리 (약 3-5초) → "분석 중" 표시.
  final double progress;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final bool analyzing = progress >= 1.0;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: <Widget>[
          SizedBox(
            width: 80,
            height: 80,
            child: CircularProgressIndicator(
              value: analyzing || progress <= 0 ? null : progress,
              strokeWidth: 6,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            analyzing
                ? '분석 중입니다...\n잠시만 기다려주세요'
                : '업로드 중... ${(progress * 100).toInt()}%',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge,
          ),
          const SizedBox(height: 16),
          if (analyzing)
            Text(
              '영양제 성분 인식과 분석에는 약 5초가 소요됩니다.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
        ],
      ),
    );
  }
}
