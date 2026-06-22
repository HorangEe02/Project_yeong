// widgets/settings/settings_widgets.dart — 설정 공용 위젯 (메인 + 서브화면 공유)
//
// 가이드 08 0단계 step 3: settings_screen.dart 안에 있던 _SettingsCard /
// _SettingsRow / _SectionLabel / _SettingsDivider 를 서브화면에서도 쓰도록
// 공용 위젯으로 승격한다. SettingsRow 에 onTap 을 추가해 라우팅을 배선한다.

import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';

/// 섹션 라벨 (예: '내 건강').
class SectionLabel extends StatelessWidget {
  /// 라벨을 생성한다.
  const SectionLabel(this.label, {super.key});

  /// 표시 텍스트.
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 6, bottom: AppSpace.sm),
      child: Text(
        label,
        style: AppText.caption.copyWith(
          color: AppColor.inkTertiary,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
      ),
    );
  }
}

/// 흰 카드 컨테이너 (행 묶음).
class SettingsCard extends StatelessWidget {
  /// 카드를 생성한다.
  const SettingsCard({required this.children, super.key});

  /// 카드 내부 자식들.
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.cardInside,
        vertical: AppSpace.md,
      ),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.xl),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color.fromRGBO(140, 155, 175, 0.14),
            blurRadius: 18,
            offset: Offset(0, 6),
          ),
        ],
      ),
      child: Column(children: children),
    );
  }
}

/// 설정 행. [onTap] 이 있으면 탭 가능 + 우측 chevron 노출.
class SettingsRow extends StatelessWidget {
  /// 행을 생성한다.
  const SettingsRow({
    required this.icon,
    required this.iconBg,
    required this.iconColor,
    required this.title,
    this.subtitle,
    this.onTap,
    this.trailing,
    this.titleColor,
    super.key,
  });

  /// 좌측 아이콘.
  final IconData icon;

  /// 아이콘 배경색.
  final Color iconBg;

  /// 아이콘 전경색.
  final Color iconColor;

  /// 제목.
  final String title;

  /// 부제. null 이면 부제 줄을 렌더하지 않는다.
  final String? subtitle;

  /// 탭 콜백. null 이면 정적 행(chevron 없음).
  final VoidCallback? onTap;

  /// chevron 대신 표시할 우측 위젯 (상태 칩 등).
  final Widget? trailing;

  /// 제목 색 (danger 톤 로그아웃 등). null 이면 기본 ink.
  final Color? titleColor;

  @override
  Widget build(BuildContext context) {
    final Widget content = Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.md),
      child: Row(
        children: <Widget>[
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: iconBg,
              borderRadius: BorderRadius.circular(AppRadius.md),
            ),
            child: Icon(icon, color: iconColor, size: 24),
          ),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  title,
                  style: AppText.subtitle.copyWith(
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                    color: titleColor,
                  ),
                ),
                if (subtitle != null) ...<Widget>[
                  const SizedBox(height: 4),
                  Text(
                    subtitle!,
                    style: AppText.caption.copyWith(
                      color: AppColor.inkTertiary,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (trailing != null)
            trailing!
          else if (onTap != null)
            const Icon(
              Icons.chevron_right_rounded,
              color: AppColor.inkTertiary,
            ),
        ],
      ),
    );
    if (onTap == null) return content;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadius.md),
        child: content,
      ),
    );
  }
}

/// 행 사이 디바이더.
class SettingsDivider extends StatelessWidget {
  /// 디바이더를 생성한다.
  const SettingsDivider({super.key});

  @override
  Widget build(BuildContext context) {
    return const Divider(height: 1, color: AppColor.border);
  }
}
