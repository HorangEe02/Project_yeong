import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kReleaseMode, TargetPlatform;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../app_controller.dart';
import '../app_providers.dart';
import '../core/storage/local_prefs.dart';
import '../features/auth/token_session.dart';
import '../features/consent/consent_models.dart';
import '../features/profile/profile_interests_screen.dart';
import '../features/profile/profile_models.dart';
import '../shared/theme/brand_theme_controller.dart';
import '../utils/brand_palette.dart';
import '../utils/design_tokens_v2.dart';
import '../widgets/settings/settings_widgets.dart';

/// Source-style settings screen wired to the current auth and consent state.
class SettingsScreen extends ConsumerStatefulWidget {
  /// Creates the settings screen.
  ///
  /// Args:
  ///   controller: Current app controller for consent state.
  ///   session: Current token session controller for dev/JWT access.
  const SettingsScreen({
    required this.controller,
    required this.session,
    super.key,
  });

  /// App controller used by the existing consent flow.
  final AppController controller;

  /// Token session used by the existing backend auth contract.
  final TokenSessionController session;

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final TextEditingController _tokenController = TextEditingController();
  String? _tokenError;

  String? _displayName;
  String? _profileSummary;
  String? _interestSummary;
  int? _daysWithApp;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadProfileHeader());
  }

  Future<void> _loadProfileHeader() async {
    final LocalPrefs? prefs = await ref.read(localPrefsProvider.future);
    final String? name = prefs?.profileDisplayName();
    // 가입 경과일 — 최초 실행일 기준(auth 도입 전 임시 산정).
    final int? days = prefs?.daysWithApp(DateTime.now());
    BodyProfileSnapshot? snapshot;
    try {
      snapshot = await ref.read(profileRepositoryProvider).fetchLatest();
    } on Object {
      // 스냅샷 조회 실패(ApiError·FormatException 등 무엇이든)는 헤더를
      // 비우지 않는다 — 로컬 이름/경과일은 이미 확보돼 있으므로 그대로
      // 반영하고 신체 요약만 비운다(기본 안내 문구로 강하).
      snapshot = null;
    }
    if (!mounted) return;
    setState(() {
      _displayName = name;
      _profileSummary = snapshot?.summaryLine();
      _interestSummary = prefs == null ? null : profileInterestsSummary(prefs);
      _daysWithApp = days;
    });
  }

  Future<void> _openProfileInterests(BuildContext context) async {
    await context.push('/shell/settings/profile-interests');
    if (!mounted) return;
    await _loadProfileHeader();
  }

  /// 앱 버전 — 설정 푸터와 서비스 정보 시트가 공유한다.
  static const String _appVersion = 'v1.0.0';

  /// 표준 의료 면책 문장(대시보드와 동일 — 진단/처방은 부정 맥락 화이트리스트).
  static const String _medicalDisclaimer =
      '레몬에이드는 건강 관리를 도와드리는 서비스로\n의사·약사·영양사의 진단을 대신하진 않아요.';

  /// 서비스 정보 시트 — 앱 소개·의료 면책·버전(콘텐츠 우리 소유).
  ///
  /// 데이터 내보내기/도움말·문의는 각각 백엔드 export 라우트·문의 채널이
  /// 정해지지 않아(공백) 임의 버튼을 만들지 않는다(날조 금지).
  Future<void> _showServiceInfoSheet(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: AppColor.surface,
      showDragHandle: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (BuildContext sheetContext) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpace.page,
              AppSpace.sm,
              AppSpace.page,
              AppSpace.xl,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text('서비스 정보', style: AppText.title.copyWith(fontSize: 20)),
                const SizedBox(height: AppSpace.md),
                Text(
                  '레몬에이드는 만성질환을 가진 분들이 식단·영양제·활동을 쉽게 '
                  '기록하고, 건강 관리에 참고할 정보를 받아보도록 돕는 앱이에요.',
                  style: AppText.body.copyWith(
                    color: AppColor.inkSecondary,
                    height: 1.55,
                  ),
                ),
                const SizedBox(height: AppSpace.lg),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(AppSpace.cardInside),
                  decoration: BoxDecoration(
                    color: AppColor.brandSoft,
                    borderRadius: BorderRadius.circular(AppRadius.md),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Icon(
                        Icons.info_outline,
                        color: AppColor.brandDeep,
                        size: 18,
                      ),
                      const SizedBox(width: AppSpace.sm),
                      Expanded(
                        child: Text(
                          _medicalDisclaimer,
                          style: AppText.caption.copyWith(
                            color: AppColor.ink,
                            height: 1.5,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpace.lg),
                Center(
                  child: Text(
                    '$_appVersion · Lemon Aid',
                    style: AppText.caption.copyWith(
                      color: AppColor.inkTertiary,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  void dispose() {
    _tokenController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bool ocrConsentGranted =
        widget.controller.consentState?.isGranted(AppController.ocrConsent) ??
        false;
    final bool healthConsentGranted =
        widget.controller.consentState?.isGranted(
          AppController.healthConsent,
        ) ??
        false;

    return Scaffold(
      backgroundColor: AppColor.section,
      body: Column(
        children: [
          _ProfileHeader(
            displayName: _displayName,
            summary: _profileSummary,
            daysWithApp: _daysWithApp,
            onEdit: () => context.go('/shell/settings/profile-edit'),
          ),
          Expanded(
            child: Transform.translate(
              offset: const Offset(0, -36),
              child: Container(
                decoration: const BoxDecoration(
                  color: AppColor.section,
                  borderRadius: BorderRadius.only(
                    topLeft: Radius.circular(28),
                    topRight: Radius.circular(28),
                  ),
                ),
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpace.page,
                    AppSpace.lg,
                    AppSpace.page,
                    AppSpace.xl + 80,
                  ),
                  children: [
                    // 1. 내 건강
                    const SectionLabel('내 건강'),
                    SettingsCard(
                      children: [
                        SettingsRow(
                          icon: Icons.medical_services_rounded,
                          iconBg: AppColor.successSoft,
                          iconColor: AppColor.success,
                          title: '만성질환·복약 정보',
                          subtitle: '복약 교차 점검에 쓰여요',
                          onTap: () =>
                              context.go('/shell/settings/health-profile'),
                        ),
                        const SettingsDivider(),
                        SettingsRow(
                          icon: Icons.flag_rounded,
                          iconBg: Color(0xFFE8EDFF),
                          iconColor: Color(0xFF4D7BFF),
                          title: '관심 목적',
                          subtitle: _interestSummary ?? '관리 목적을 설정해주세요',
                          onTap: () => _openProfileInterests(context),
                        ),
                        const SettingsDivider(),
                        SettingsRow(
                          icon: Icons.straighten_rounded,
                          iconBg: AppColor.warningSoft,
                          iconColor: AppColor.warning,
                          title: '신체 정보',
                          subtitle: '키·몸무게·성별·나이',
                          onTap: () =>
                              context.go('/shell/settings/profile-edit'),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpace.lg),
                    // 2. 기기 연동 (신규) — 건강 데이터 라우트/백엔드 미구현이라
                    // 탭 시 "준비 중" 안내만(날조 금지).
                    const SectionLabel('기기 연동'),
                    SettingsCard(
                      children: [
                        SettingsRow(
                          icon: Icons.watch_rounded,
                          iconBg: AppColor.brandSoft,
                          iconColor: AppColor.brandDeep,
                          // iOS = 애플 워치(HealthKit), Android = 갤럭시 워치(Health Connect)
                          title: defaultTargetPlatform == TargetPlatform.iOS
                              ? '애플 워치 연동'
                              : '갤럭시 워치 연동',
                          subtitle: '걸음·심박·활동량 자동 기록',
                          trailing: const _StatusChip(label: '미연동'),
                          onTap: _showComingSoon,
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpace.lg),
                    // 3. 알림
                    const SectionLabel('알림'),
                    SettingsCard(
                      children: [
                        SettingsRow(
                          icon: Icons.notifications_rounded,
                          iconBg: AppColor.brandSoft,
                          iconColor: AppColor.brandDeep,
                          title: '알림 설정',
                          subtitle: '복약 시간 · 평가 리포트',
                          onTap: () => context.go(
                            '/shell/settings/notification-settings',
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpace.lg),
                    // 4. 테마 색상 (메인 하단 → 여기로 이동)
                    const SectionLabel('테마 색상'),
                    Consumer(
                      builder:
                          (BuildContext context, WidgetRef ref, Widget? child) {
                            final BrandTheme current = ref.watch(
                              brandThemeProvider,
                            );
                            return SettingsCard(
                              children: [
                                _ThemeSwatchRow(
                                  current: current,
                                  onSelect: (BrandTheme t) => ref
                                      .read(brandThemeProvider.notifier)
                                      .select(t),
                                ),
                              ],
                            );
                          },
                    ),
                    const SizedBox(height: AppSpace.lg),
                    // 5. 계정
                    const SectionLabel('계정'),
                    SettingsCard(
                      children: [
                        SettingsRow(
                          icon: Icons.person_rounded,
                          iconBg: const Color(0xFFEDEFF3),
                          iconColor: AppColor.inkSecondary,
                          title: '내 정보',
                          subtitle: widget.session.devBypassActive
                              ? '로컬 dev bypass 사용 중'
                              : widget.session.bearerToken == null
                              ? '외부 JWT 토큰 미설정'
                              : '외부 JWT 토큰 저장됨',
                        ),
                        const SettingsDivider(),
                        SettingsRow(
                          icon: Icons.shield_rounded,
                          iconBg: ocrConsentGranted && healthConsentGranted
                              ? AppColor.successSoft
                              : AppColor.warningSoft,
                          iconColor: ocrConsentGranted && healthConsentGranted
                              ? AppColor.success
                              : AppColor.warning,
                          title: '동의 관리',
                          subtitle: ocrConsentGranted && healthConsentGranted
                              ? 'OCR 이미지 · 민감 건강 분석 동의 완료'
                              : 'OCR 이미지 · 민감 건강 분석 동의 필요',
                          onTap: () => context.go('/shell/settings/policies'),
                        ),
                        const SettingsDivider(),
                        SettingsRow(
                          icon: Icons.download_rounded,
                          iconBg: const Color(0xFFEDEFF3),
                          iconColor: AppColor.inkSecondary,
                          title: '데이터 내보내기',
                          subtitle: '내 기록을 파일로 받아볼 수 있어요',
                          onTap: _showComingSoon,
                        ),
                        // ── dev 전용: 동의 상태 카드 + JWT 토큰 카드 ──
                        // release 동의는 policies 화면이 담당하므로 메인 카드는
                        // 디버그/dev 빌드에서만 노출(가이드 08 컨텍스트 유지).
                        if (!kReleaseMode) ...[
                          const SizedBox(height: AppSpace.md),
                          _ConsentStatusCard(
                            consentState: widget.controller.consentState,
                            busy: widget.controller.busy,
                            onGrant: widget.controller.grantMinimumConsents,
                            onReload: widget.controller.bootstrap,
                          ),
                          const SizedBox(height: AppSpace.md),
                          _TokenAccessCard(
                            controller: _tokenController,
                            errorText: _tokenError,
                            session: widget.session,
                            onSave: _saveToken,
                            onClear: widget.session.bearerToken == null
                                ? null
                                : widget.session.clearBearerToken,
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: AppSpace.lg),
                    // 6. 안내
                    const SectionLabel('안내'),
                    SettingsCard(
                      children: [
                        SettingsRow(
                          icon: Icons.info_outline_rounded,
                          iconBg: const Color(0xFFEDEFF3),
                          iconColor: AppColor.inkSecondary,
                          title: '서비스 정보',
                          subtitle: '앱 소개와 의료 면책 안내',
                          onTap: () => _showServiceInfoSheet(context),
                        ),
                        const SettingsDivider(),
                        SettingsRow(
                          icon: Icons.help_outline_rounded,
                          iconBg: const Color(0xFFEDEFF3),
                          iconColor: AppColor.inkSecondary,
                          title: '도움말·문의',
                          subtitle: '궁금한 점을 알려주세요',
                          onTap: _showComingSoon,
                        ),
                        const SettingsDivider(),
                        SettingsRow(
                          icon: Icons.gavel_rounded,
                          iconBg: const Color(0xFFEDEFF3),
                          iconColor: AppColor.inkSecondary,
                          title: '약관 · 개인정보',
                          subtitle: '약관·정책과 동의 관리',
                          onTap: () => context.go('/shell/settings/policies'),
                        ),
                        const SettingsDivider(),
                        SettingsRow(
                          icon: Icons.person_off_rounded,
                          iconBg: AppColor.dangerSoft,
                          iconColor: AppColor.danger,
                          title: '회원 탈퇴',
                          subtitle: '계정과 데이터를 삭제해요',
                          onTap: () => context.go('/shell/settings/withdraw'),
                        ),
                      ],
                    ),
                    // ── dev 전용: OCR 테스트 더미 행 ──
                    if (!kReleaseMode) ...[
                      const SizedBox(height: AppSpace.lg),
                      const SectionLabel('OCR 테스트'),
                      SettingsCard(
                        children: [
                          SettingsRow(
                            icon: Icons.camera_alt_rounded,
                            iconBg: AppColor.brandSoft,
                            iconColor: AppColor.brandDeep,
                            title: '촬영 환경',
                            subtitle: 'Android Studio AVD와 live flag 사용',
                          ),
                          const SettingsDivider(),
                          const SettingsRow(
                            icon: Icons.photo_library_rounded,
                            iconBg: AppColor.successSoft,
                            iconColor: AppColor.success,
                            title: '갤러리 입력',
                            subtitle: '선택 이미지는 앱 캐시에 복사 후 OCR 업로드',
                          ),
                          const SettingsDivider(),
                          const SettingsRow(
                            icon: Icons.psychology_rounded,
                            iconBg: AppColor.warningSoft,
                            iconColor: AppColor.warning,
                            title: '로컬 LLM 설명',
                            subtitle: 'Ollama 사용 여부는 백엔드 설정을 따름',
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: AppSpace.lg),
                    // 7. 로그아웃 (단독, danger 톤) — Figma 780:23 중앙정렬
                    SettingsCard(
                      children: [
                        GestureDetector(
                          onTap: widget.session.clearBearerToken,
                          behavior: HitTestBehavior.opaque,
                          child: const Padding(
                            padding: EdgeInsets.symmetric(
                              vertical: AppSpace.sm,
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.logout_rounded,
                                  color: AppColor.danger,
                                  size: 20,
                                ),
                                SizedBox(width: AppSpace.sm),
                                Text(
                                  '로그아웃',
                                  style: TextStyle(
                                    color: AppColor.danger,
                                    fontSize: 16,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: 0,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpace.lg),
                    Center(
                      child: Text(
                        '$_appVersion · Lemon Aid',
                        style: AppText.caption.copyWith(
                          color: AppColor.inkTertiary,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 백엔드 라우트가 아직 없는 항목의 안전한 안내(날조 금지 — 가짜 호출 X).
  ///
  /// 워치 연동·데이터 내보내기·도움말 문의 등은 라우트/채널이 정해지지
  /// 않아(백엔드 공백) SnackBar 로 "준비 중" 안내만 한다.
  void _showComingSoon() {
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(const SnackBar(content: Text('아직 준비 중이에요')));
  }

  Future<void> _saveToken() async {
    setState(() {
      _tokenError = null;
    });
    try {
      await widget.session.saveBearerToken(_tokenController.text);
      _tokenController.clear();
      if (mounted) FocusScope.of(context).unfocus();
    } on ArgumentError {
      setState(() {
        _tokenError = '토큰을 입력해주세요.';
      });
    }
  }
}

/// 기기 연동 상태 칩 (예: '미연동'). 중립 톤(section 배경 + 3차 잉크).
class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 6),
      decoration: BoxDecoration(
        color: AppColor.section,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        label,
        style: AppText.micro.copyWith(
          color: AppColor.inkTertiary,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
      ),
    );
  }
}

class _ConsentStatusCard extends StatelessWidget {
  const _ConsentStatusCard({
    required this.consentState,
    required this.busy,
    required this.onGrant,
    required this.onReload,
  });

  final ConsentState? consentState;
  final bool busy;
  final Future<void> Function() onGrant;
  final Future<void> Function() onReload;

  @override
  Widget build(BuildContext context) {
    final bool ocrGranted =
        consentState?.isGranted(AppController.ocrConsent) ?? false;
    final bool healthGranted =
        consentState?.isGranted(AppController.healthConsent) ?? false;
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColor.sunken,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '필수 동의 상태',
            style: AppText.caption.copyWith(
              color: AppColor.ink,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: AppSpace.sm),
          _ConsentPill(label: 'OCR 이미지 처리', granted: ocrGranted),
          const SizedBox(height: AppSpace.xs),
          _ConsentPill(label: '민감 건강 분석', granted: healthGranted),
          const SizedBox(height: AppSpace.sm),
          Row(
            children: [
              Expanded(
                child: FilledButton(
                  onPressed: busy ? null : onGrant,
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColor.brand,
                    foregroundColor: AppColor.ink,
                  ),
                  child: const Text('필수 동의 허용'),
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              OutlinedButton(
                onPressed: busy ? null : onReload,
                child: const Text('새로고침'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ConsentPill extends StatelessWidget {
  const _ConsentPill({required this.label, required this.granted});

  final String label;
  final bool granted;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(
          granted
              ? Icons.check_circle_rounded
              : Icons.radio_button_unchecked_rounded,
          color: granted ? AppColor.success : AppColor.inkTertiary,
          size: 18,
        ),
        const SizedBox(width: AppSpace.xs),
        Expanded(
          child: Text(
            label,
            style: AppText.caption.copyWith(
              color: AppColor.ink,
              fontWeight: FontWeight.w700,
              letterSpacing: 0,
            ),
          ),
        ),
        Text(
          granted ? '허용됨' : '필요',
          style: AppText.micro.copyWith(
            color: granted ? AppColor.success : AppColor.inkTertiary,
            fontWeight: FontWeight.w800,
            letterSpacing: 0,
          ),
        ),
      ],
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  const _ProfileHeader({
    required this.displayName,
    required this.summary,
    required this.daysWithApp,
    required this.onEdit,
  });

  final String? displayName;
  final String? summary;
  // 함께한 일수(가입 경과일 임시 산정). null 이면 경과일 라인 숨김.
  final int? daysWithApp;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final String name = (displayName == null || displayName!.isEmpty)
        ? '레몬 회원님'
        : '$displayName님';
    final int? days = daysWithApp;
    final String subtitle = summary ?? '신체 정보를 입력하면 분석이 더 정확해져요';
    return Container(
      width: double.infinity,
      color: AppColor.brand,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.page,
            AppSpace.xxl,
            AppSpace.page,
            AppSpace.xxl + 40,
          ),
          child: Row(
            children: [
              CircleAvatar(
                radius: 42,
                backgroundColor: AppColor.brandTint,
                child: const Icon(
                  Icons.person_rounded,
                  color: AppColor.ink,
                  size: 38,
                ),
              ),
              const SizedBox(width: AppSpace.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      style: const TextStyle(
                        color: AppColor.ink,
                        fontSize: 26,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0,
                      ),
                    ),
                    if (days != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        '레몬에이드와 함께한 지 $days일째',
                        style: TextStyle(
                          color: AppColor.brandDeep,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0,
                        ),
                      ),
                    ],
                    const SizedBox(height: 6),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: AppColor.ink,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0,
                      ),
                    ),
                  ],
                ),
              ),
              DecoratedBox(
                decoration: BoxDecoration(
                  color: AppColor.brandTint,
                  shape: BoxShape.circle,
                ),
                child: IconButton(
                  onPressed: onEdit,
                  icon: const Icon(Icons.edit_rounded),
                  color: AppColor.ink,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 4색 브랜드 테마 스와치 행 (Figma S-13).
///
/// 옐로/퍼플/그린/블루 스와치 4개를 가로로 나열한다.
/// 선택된 항목은 검정 외곽선 + 체크 아이콘으로 표시.
class _ThemeSwatchRow extends StatelessWidget {
  const _ThemeSwatchRow({required this.current, required this.onSelect});

  final BrandTheme current;
  final ValueChanged<BrandTheme> onSelect;

  @override
  Widget build(BuildContext context) {
    // Figma 780:23 — 라운드 사각 스와치 + 라벨(옐로/퍼플/그린/블루) 균등 배치.
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpace.sm),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: BrandTheme.values.map((BrandTheme t) {
          final bool selected = t == current;
          return GestureDetector(
            onTap: () => onSelect(t),
            behavior: HitTestBehavior.opaque,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    color: t.color,
                    borderRadius: BorderRadius.circular(AppRadius.md),
                    border: Border.all(
                      color: selected ? AppColor.ink : Colors.transparent,
                      width: 3,
                    ),
                  ),
                  child: selected
                      ? const Icon(
                          Icons.check_rounded,
                          color: Colors.black,
                          size: 24,
                        )
                      : null,
                ),
                const SizedBox(height: AppSpace.sm),
                Text(
                  t.label,
                  style: AppText.caption.copyWith(
                    color: selected ? AppColor.ink : AppColor.inkTertiary,
                    fontWeight: selected ? FontWeight.w700 : FontWeight.w600,
                    letterSpacing: 0,
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _TokenAccessCard extends StatelessWidget {
  const _TokenAccessCard({
    required this.controller,
    required this.session,
    required this.onSave,
    required this.onClear,
    this.errorText,
  });

  final TextEditingController controller;
  final TokenSessionController session;
  final VoidCallback onSave;
  final VoidCallback? onClear;
  final String? errorText;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColor.sunken,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'API access',
            style: AppText.caption.copyWith(
              color: AppColor.ink,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: AppSpace.sm),
          TextField(
            controller: controller,
            obscureText: true,
            decoration: InputDecoration(
              hintText: 'JWT bearer token',
              errorText: errorText,
              filled: true,
              fillColor: AppColor.surface,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppRadius.md),
                borderSide: BorderSide.none,
              ),
            ),
          ),
          const SizedBox(height: AppSpace.sm),
          Row(
            children: [
              Expanded(
                child: FilledButton(
                  onPressed: onSave,
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColor.brand,
                    foregroundColor: AppColor.ink,
                  ),
                  child: const Text('저장'),
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              OutlinedButton(onPressed: onClear, child: const Text('삭제')),
            ],
          ),
        ],
      ),
    );
  }
}
