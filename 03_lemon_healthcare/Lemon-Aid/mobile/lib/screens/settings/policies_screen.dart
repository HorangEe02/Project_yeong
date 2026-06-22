// screens/settings/policies_screen.dart — 약관·정책 + 동의 관리 (figma 957:108)
//
// 가이드 08 (f) step 30. 약관·개인정보 처리방침 정적 목록 + 동의 관리(사용자
// 노출 6종 토글). grant=POST, revoke=DELETE /me/privacy/consents/{type}.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_providers.dart';
import '../../core/api/api_error.dart';
import '../../features/privacy/privacy_repository.dart';
import '../../utils/design_tokens_v2.dart';
import '../../widgets/settings/settings_widgets.dart';

/// 약관·정책 정적 항목 (제목 + 구분 아이콘).
class _PolicyItem {
  const _PolicyItem(this.title, this.icon);

  final String title;
  final IconData icon;
}

const List<_PolicyItem> _kPolicyItems = <_PolicyItem>[
  _PolicyItem('서비스 이용약관', Icons.description_outlined),
  _PolicyItem('개인정보 처리방침', Icons.lock_outline),
  _PolicyItem('민감정보(건강) 처리 동의', Icons.medical_services_rounded),
  _PolicyItem('오픈소스 라이선스', Icons.code_rounded),
];

/// 약관·정책 + 동의 관리 화면.
class PoliciesScreen extends ConsumerStatefulWidget {
  /// 화면을 생성한다.
  const PoliciesScreen({super.key});

  @override
  ConsumerState<PoliciesScreen> createState() => _PoliciesScreenState();
}

class _PoliciesScreenState extends ConsumerState<PoliciesScreen> {
  Map<String, bool> _granted = <String, bool>{};
  bool _loading = true;
  String? _busyCode;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    try {
      final Map<String, bool> consents = await ref
          .read(privacyRepositoryProvider)
          .consents();
      if (!mounted) return;
      setState(() {
        _granted = consents;
        _loading = false;
      });
    } on ApiError {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  Future<void> _toggleConsent(UserConsentType type, bool grant) async {
    setState(() => _busyCode = type.code);
    final PrivacyRepository repo = ref.read(privacyRepositoryProvider);
    try {
      if (grant) {
        await repo.grant(type);
      } else {
        await repo.revoke(type);
      }
      if (!mounted) return;
      setState(() {
        _granted[type.code] = grant;
        _busyCode = null;
      });
    } on ApiError catch (error) {
      if (!mounted) return;
      setState(() => _busyCode = null);
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColor.section,
      appBar: AppBar(
        backgroundColor: AppColor.section,
        elevation: 0,
        title: const Text(
          '약관 · 개인정보',
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontWeight: FontWeight.w800,
            color: AppColor.ink,
          ),
        ),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(AppSpace.page),
          children: <Widget>[
            const SectionLabel('약관 · 정책'),
            SettingsCard(
              children: <Widget>[
                for (int i = 0; i < _kPolicyItems.length; i += 1) ...<Widget>[
                  SettingsRow(
                    icon: _kPolicyItems[i].icon,
                    iconBg: const Color(0xFFEDEFF3),
                    iconColor: AppColor.inkSecondary,
                    title: _kPolicyItems[i].title,
                    onTap: () {},
                  ),
                  if (i < _kPolicyItems.length - 1) const SettingsDivider(),
                ],
              ],
            ),
            const SizedBox(height: AppSpace.lg),
            const SectionLabel('동의 관리'),
            if (_loading)
              const Padding(
                padding: EdgeInsets.all(AppSpace.lg),
                child: Center(child: CircularProgressIndicator()),
              )
            else
              SettingsCard(
                children: <Widget>[
                  for (
                    int i = 0;
                    i < UserConsentType.values.length;
                    i += 1
                  ) ...<Widget>[
                    _ConsentToggleRow(
                      type: UserConsentType.values[i],
                      granted:
                          _granted[UserConsentType.values[i].code] ?? false,
                      busy: _busyCode == UserConsentType.values[i].code,
                      onChanged: (bool v) =>
                          _toggleConsent(UserConsentType.values[i], v),
                    ),
                    if (i < UserConsentType.values.length - 1)
                      const SettingsDivider(),
                  ],
                ],
              ),
            const SizedBox(height: AppSpace.xl),
            Center(
              child: Text(
                'Lemon Aid · 버전 1.0.0 (최신)',
                style: AppText.caption.copyWith(
                  color: AppColor.inkTertiary,
                  fontWeight: FontWeight.w600,
                  letterSpacing: 0,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ConsentToggleRow extends StatelessWidget {
  const _ConsentToggleRow({
    required this.type,
    required this.granted,
    required this.busy,
    required this.onChanged,
  });

  final UserConsentType type;
  final bool granted;
  final bool busy;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.md),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Text(
              type.label,
              style: AppText.subtitle.copyWith(
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          if (busy)
            const SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(strokeWidth: 2.4),
            )
          else
            Switch(
              value: granted,
              activeTrackColor: AppColor.brand,
              onChanged: onChanged,
            ),
        ],
      ),
    );
  }
}
