// widgets/common/empty_state.dart — 빈 화면 3 종 통일
//
// 참조: mobile/CLAUDE.md §3.5 빈 화면 약속 / §6.3 만들 것
// 사용자와 같이 디자인 결정 진행 중 — 마지막 디자인 협의 시점에 다시 손볼 것.
//
// 3 가지 유형 (CLAUDE.md §3.5):
//   firstTime    → 처음 켰을 때
//   syncFail     → 동기화 실패
//   noPermission → 권한 없음

import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';

enum EmptyKind { firstTime, syncFail, noPermission }

class EmptyState extends StatelessWidget {
  final EmptyKind kind;
  final VoidCallback onAction;

  const EmptyState({super.key, required this.kind, required this.onAction});

  IconData get _icon {
    switch (kind) {
      case EmptyKind.firstTime:
        return Icons.auto_awesome_rounded;
      case EmptyKind.syncFail:
        return Icons.cloud_off_rounded;
      case EmptyKind.noPermission:
        return Icons.lock_outline_rounded;
    }
  }

  String get _headline {
    switch (kind) {
      case EmptyKind.firstTime:
        return '아직 기록이 없어요';
      case EmptyKind.syncFail:
        return '동기화에 실패했어요';
      case EmptyKind.noPermission:
        return '권한이 필요해요';
    }
  }

  String get _hint {
    switch (kind) {
      case EmptyKind.firstTime:
        return '지금 사진 한 장 찍어볼까요?';
      case EmptyKind.syncFail:
        return '잠시 후 다시 시도해 주세요';
      case EmptyKind.noPermission:
        return '설정에서 허용 후 다시 와 주세요';
    }
  }

  String get _actionLabel {
    switch (kind) {
      case EmptyKind.firstTime:
        return '카메라 열기';
      case EmptyKind.syncFail:
        return '다시 시도';
      case EmptyKind.noPermission:
        return '설정 열기';
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppCard(
      color: AppColor.brandSoft,
      padding: const EdgeInsets.all(AppSpace.xl),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: <Widget>[
          Icon(_icon, size: 40, color: AppColor.brand),
          const SizedBox(height: AppSpace.md),
          Text(_headline, style: AppText.subtitle, textAlign: TextAlign.center),
          const SizedBox(height: AppSpace.xs),
          Text(
            _hint,
            style: AppText.body.copyWith(color: AppColor.inkSecondary),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpace.lg),
          AppSecondaryButton(label: _actionLabel, onPressed: onAction),
        ],
      ),
    );
  }
}
