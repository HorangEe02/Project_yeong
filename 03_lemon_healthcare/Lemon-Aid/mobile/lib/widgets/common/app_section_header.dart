// widgets/common/app_section_header.dart — 섹션 헤더
//
// 참조: mobile/CLAUDE.md §2 디자인 시스템 / §6 공용 위젯
// 사용자와 같이 디자인 결정 진행 중 — 마지막 디자인 협의 시점에 다시 손볼 것.
//
// 좌측 큰 제목 (subtitle 18pt w700) + 우측 액션 텍스트 링크 (옵션).

import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';

class AppSectionHeader extends StatelessWidget {
  final String title;
  final String? action;
  final VoidCallback? onAction;

  const AppSectionHeader({
    super.key,
    required this.title,
    this.action,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: <Widget>[
        Expanded(
          child: Text(
            title,
            style: AppText.subtitle.copyWith(fontWeight: FontWeight.w700),
          ),
        ),
        if (action != null)
          Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: onAction,
              borderRadius: BorderRadius.circular(AppRadius.xs),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpace.sm,
                  vertical: AppSpace.xs,
                ),
                child: Text(
                  action!,
                  style: TextStyle(
                    fontFamily: 'Pretendard',
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppColor.brand,
                    height: 1.4,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
