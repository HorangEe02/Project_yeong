// utils/design_tokens_v2.dart — Lemon Aid 디자인 시스템 v2.0
//
// Flat 2.0 + 카드 기반.
// 채택 근거: UX_DIARY §14.10 (앱 정체성→시각 언어 도출).
//
// 사용: import '../utils/design_tokens_v2.dart' as ds2;
//       Container(color: ds2.AppColor.brand, ...)

import 'package:flutter/material.dart';

class AppColor {
  // 배경 ─────────────────────────────────────
  static const Color bg = Color(0xFFFFFFFF);
  static const Color surface = Color(0xFFFFFFFF); // 카드 표면
  static const Color sunken = Color(0xFFF7F8FA); // 인풋 베이스
  static const Color section = Color(0xFFF2F4F6); // 섹션 구분 배경

  // 보더 ─────────────────────────────────────
  static const Color border = Color(0xFFEEF1F6);
  static const Color borderStrong = Color(0xFFDEE2E8);

  // 잉크 ─────────────────────────────────────
  static const Color ink = Color(0xFF191F28);
  static const Color inkSecondary = Color(0xFF4E5968);
  static const Color inkTertiary = Color(0xFF8B95A1);
  static const Color inkDisabled = Color(0xFFC5C8CE);

  // 브랜드 ───────────────────────────────────
  // 메인 컬러 확정 (UX_DIARY §14.12, 2026-05-18 갱신)
  // 블루 폐기 → 워드마크 "레몬·에이드" 중간 점 색 (Lemon Yellow) 으로 통일
  // 일관성 §17: brand = yellow 로 통합. 모든 CTA / 활성 / 강조에 사용.
  // ⚠️ brand 계열은 사용자 테마 선택(BrandTheme)에 따라 런타임에 교체된다.
  //    BrandThemeNotifier 가 select/restore 시 아래 값을 갱신하고, app.dart 루트가
  //    ValueKey(brandTheme) 로 전체 트리를 재빌드해 적용한다. 그래서 const 가 아니다.
  static Color brand = const Color(0xFFFFC700); // ★ Lemon Aid 메인 (테마 기본=옐로)
  static Color brandPressed = const Color(0xFFE5B300); // 눌림 (어두운 톤)
  static Color brandDeep = const Color(0xFFC99100); // 깊은 톤 (텍스트 on brand)
  static Color brandSoft = const Color(0xFFFFF6CC); // chip 배경 / 옅은 강조
  static Color brandTint = const Color(0xFFFFF0A8); // 더 옅은 (선택 배경)

  // 액센트 ───────────────────────────────────
  // 호환성 유지 — yellow = brand 동의어
  static Color yellow = const Color(0xFFFFC700); // = brand (테마 따라 교체)
  static Color yellowSoft = const Color(0xFFFFF6CC); // = brandSoft
  static const Color kakao = Color(0xFFFEE500); // 카카오 브랜드 가이드
  static const Color appleBlack = Color(0xFF1A1F2E);

  // 시맨틱 — Claude 디자인 시안(2026-05-12) 톤 매칭
  static const Color success = Color(0xFF22B07D); // Claude LA.success
  static const Color successSoft = Color(0xFFE6F5EE); // 옅은 초록 배경 (chip·badge)
  static const Color warning = Color(0xFFFF9500);
  static const Color warningSoft = Color(0xFFFFEACC); // 옅은 주황 배경
  static const Color danger = Color(0xFFEF4452); // Claude LA.danger
  static const Color dangerSoft = Color(0xFFFDE7E9);
  // "확인 필요" — OCR 신뢰도 낮음 / 의료 면책 등 (signup_flow_screen.dart 사용)
  static const Color review = Color(0xFFB86A00);
  static const Color reviewSoft = Color(0xFFFFE9C4);
  static const Color info = Color(0xFF2CA8E0);
  static const Color infoSoft = Color(0xFFDAF1FB);
}

class AppShadow {
  // ─── 베이스 (Flat 2.0) 그림자 ─────────────────
  // Elev 1 — 카드 기본
  static const List<BoxShadow> elev1 = [
    BoxShadow(
      color: Color.fromRGBO(0, 0, 0, 0.04),
      blurRadius: 12,
      offset: Offset(0, 4),
    ),
  ];

  // softCard — 그레이지 톤 부드러운 카드 그림자.
  // 점수·캘린더·기록·홈 히어로 카드 공용 (단일 출처).
  static const List<BoxShadow> softCard = [
    BoxShadow(
      color: Color.fromRGBO(140, 155, 175, 0.20),
      blurRadius: 16,
      offset: Offset(0, 5),
    ),
  ];

  // Elev 2 — 떠 있는 카드 / 상단 BottomSheet
  static const List<BoxShadow> elev2 = [
    BoxShadow(
      color: Color.fromRGBO(0, 0, 0, 0.06),
      blurRadius: 20,
      offset: Offset(0, 8),
    ),
  ];

  // Elev 3 — 모달
  static const List<BoxShadow> elev3 = [
    BoxShadow(
      color: Color.fromRGBO(0, 0, 0, 0.12),
      blurRadius: 40,
      offset: Offset(0, 16),
    ),
  ];

  // ─── 액센트 (뉴모피즘) 그림자 ─────────────────
  // neuPop — "튀어나옴" : 메인 CTA, OAuth(카카오/Apple), 감성 카드.
  // 아래쪽 한 방향 그림자만 (좌상 흰색 그림자 빼서 말풍선/위쪽 요소와 겹침 방지).
  static const List<BoxShadow> neuPop = [
    BoxShadow(
      color: Color.fromRGBO(190, 200, 215, 0.45),
      blurRadius: 14,
      offset: Offset(0, 6),
    ),
  ];

  // neuPopSoft — 부드러운 버전 (캐릭터 주변 말풍선·툴팁용)
  static const List<BoxShadow> neuPopSoft = [
    BoxShadow(
      color: Color.fromRGBO(209, 217, 230, 0.55),
      blurRadius: 12,
      offset: Offset(4, 6),
    ),
    BoxShadow(color: Colors.white, blurRadius: 8, offset: Offset(-3, -3)),
  ];

  // neuInset — "눌린" 느낌. 토글 트랙, 감성 인풋 등에 사용 (CustomPaint 보조)
  // BoxShadow inset 은 Flutter 기본 미지원이라 CustomPainter 로 그려야 함 (예: SignupScreen _NeuInsetPainter)

  // ─── 내비게이션 / FAB ─────────────────────────
  // navBar — 하단 탭바 상단 방향 옅은 그림자 (main_shell _BottomBar)
  static const List<BoxShadow> navBar = [
    BoxShadow(
      color: Color.fromRGBO(140, 155, 175, 0.06),
      blurRadius: 16,
      offset: Offset(0, -2),
    ),
  ];

  // fabDepth — 중앙 카메라 FAB 깊이감(미세 검정).
  // brand 색 잔향 글로우는 동적(alpha)이라 위젯에서 AppColor.brand 로 생성.
  static const BoxShadow fabDepth = BoxShadow(
    color: Color.fromRGBO(0, 0, 0, 0.10),
    blurRadius: 6,
    offset: Offset(0, 3),
  );
}

class AppRadius {
  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double full = 999;
}

class AppSpace {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;
  static const double xxxl = 48;

  // ─── 2026-05-18: 페이지 좌우 패딩 통일 (§17 일관성) ───
  // 모든 화면의 horizontal padding 은 page 로 통일
  // 시니어 친화 + 카드 숨쉴 공간 확보
  // 2026-05-18: 20 → 24, 전체 화면 좌우 여백 살짝 더 확보 (시니어 친화 + 호흡)
  static const double page = 24; // ★ 페이지 좌우 패딩 표준
  static const double pageTop = 24; // 페이지 상단
  static const double pageBottom = 32; // 페이지 하단 (CTA 와 간격)
  static const double cardInside = 20; // 카드 안 padding
  static const double sectionGap = 28; // 섹션 사이 간격
}

class AppText {
  static const String _family = 'Pretendard';

  static const TextStyle display = TextStyle(
    fontFamily: _family,
    fontSize: 32,
    fontWeight: FontWeight.w700,
    letterSpacing: 0,
    height: 1.2,
    color: AppColor.ink,
  );
  static const TextStyle title = TextStyle(
    fontFamily: _family,
    fontSize: 24,
    fontWeight: FontWeight.w700,
    letterSpacing: 0,
    height: 1.3,
    color: AppColor.ink,
  );
  static const TextStyle subtitle = TextStyle(
    fontFamily: _family,
    fontSize: 18,
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
    height: 1.4,
    color: AppColor.ink,
  );
  static const TextStyle bodyLg = TextStyle(
    fontFamily: _family,
    fontSize: 17,
    fontWeight: FontWeight.w500,
    height: 1.5,
    color: AppColor.ink,
  );
  static const TextStyle body = TextStyle(
    fontFamily: _family,
    fontSize: 15,
    fontWeight: FontWeight.w500,
    height: 1.5,
    color: AppColor.ink,
  );
  static const TextStyle caption = TextStyle(
    fontFamily: _family,
    fontSize: 13,
    fontWeight: FontWeight.w500,
    height: 1.4,
    color: AppColor.inkSecondary,
  );
  static const TextStyle micro = TextStyle(
    fontFamily: _family,
    fontSize: 11,
    fontWeight: FontWeight.w600,
    height: 1.3,
    color: AppColor.inkTertiary,
  );
}

// ─── 공용 위젯 ───────────────────────────────────

/// AppCard — 흰 배경 + Elev 1 그림자 + 라디우스 16
/// Toss/여기어때 톤 기본 카드
class AppCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color? color;
  final VoidCallback? onTap;
  final bool elevated;

  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpace.lg),
    this.radius = AppRadius.md,
    this.color,
    this.onTap,
    this.elevated = true,
  });

  @override
  Widget build(BuildContext context) {
    final inner = Container(
      decoration: BoxDecoration(
        color: color ?? AppColor.surface,
        borderRadius: BorderRadius.circular(radius),
        boxShadow: elevated ? AppShadow.elev1 : null,
        border: elevated ? null : Border.all(color: AppColor.border, width: 1),
      ),
      padding: padding,
      child: child,
    );
    if (onTap == null) return inner;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(radius),
        child: inner,
      ),
    );
  }
}

/// AppPrimaryButton — 브랜드 솔리드 + 흰 텍스트.
///
/// 기본은 평면 (그림자 X). [accent] 가 true 면 뉴모 액센트 (neuPop) 적용.
/// Lemon Aid 디자인 시스템 v2.1:
///   - 메인 CTA(로그인·다음·계속하기), OAuth 카카오/Apple → accent: true 권장
///   - 폼 내부 보조 액션 → accent: false (평면)
class AppPrimaryButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool loading;
  final bool enabled;
  final bool accent;
  final Color? color;
  final Color? textColor;
  final double height;
  final Widget? leading;

  const AppPrimaryButton({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.enabled = true,
    this.accent = false,
    this.color,
    this.textColor,
    this.height = 54,
    this.leading,
  });

  @override
  Widget build(BuildContext context) {
    final on = enabled && !loading;
    final bg = on
        ? (color ?? AppColor.brand)
        : AppColor.brand.withValues(alpha: 0.3);
    final fg = textColor ?? Colors.white;

    final content = loading
        ? SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(
              strokeWidth: 2.4,
              valueColor: AlwaysStoppedAnimation(fg),
            ),
          )
        : Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (leading != null) ...[leading!, const SizedBox(width: 8)],
              Text(
                label,
                style: TextStyle(
                  fontFamily: 'Pretendard',
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  color: fg,
                  letterSpacing: 0,
                ),
              ),
            ],
          );

    // 평면 (기본) — Material + InkWell
    if (!accent || !on) {
      return Material(
        color: bg,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        child: InkWell(
          onTap: on ? onPressed : null,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          child: Container(
            height: height,
            alignment: Alignment.center,
            child: content,
          ),
        ),
      );
    }

    // 뉴모 액센트 — Container + neuPop. InkWell ripple 은 시각 노이즈라 GestureDetector + AnimatedContainer
    return GestureDetector(
      onTap: onPressed,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        height: height,
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          boxShadow: AppShadow.neuPop,
        ),
        alignment: Alignment.center,
        child: content,
      ),
    );
  }
}

/// AppSecondaryButton — 흰 배경 + 미세 뉴모피즘 액센트 (살짝 떠 있는 인상)
/// 보더 대신 옅은 양면 그림자 (neuPopSoft 보다 더 옅음) 로 카드 경계 표현.
class AppSecondaryButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final double height;
  final Widget? leading;

  const AppSecondaryButton({
    super.key,
    required this.label,
    this.onPressed,
    this.height = 54,
    this.leading,
  });

  // 흰 배경 위 흰 버튼 — flat 톤 1단 그림자 (회원가입 박스와 통일)
  static const List<BoxShadow> _secondaryShadow = [
    BoxShadow(
      color: Color.fromRGBO(140, 155, 175, 0.20),
      blurRadius: 16,
      offset: Offset(0, 5),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onPressed,
      child: Container(
        height: height,
        decoration: BoxDecoration(
          color: AppColor.surface,
          borderRadius: BorderRadius.circular(AppRadius.sm),
          boxShadow: _secondaryShadow,
        ),
        alignment: Alignment.center,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (leading != null) ...[leading!, const SizedBox(width: 8)],
            Text(
              label,
              style: const TextStyle(
                fontFamily: 'Pretendard',
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: AppColor.ink,
                letterSpacing: 0,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// AppTextField — sunken 베이스, focus 시 보더 브랜드
class AppTextField extends StatefulWidget {
  final TextEditingController controller;
  final FocusNode? focusNode;
  final String? label;
  final String? hint;
  final String? helper;
  final String? error;
  final bool ok;
  final bool obscure;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final ValueChanged<String>? onSubmitted;
  final Widget? suffix;

  const AppTextField({
    super.key,
    required this.controller,
    this.focusNode,
    this.label,
    this.hint,
    this.helper,
    this.error,
    this.ok = false,
    this.obscure = false,
    this.keyboardType,
    this.textInputAction,
    this.onSubmitted,
    this.suffix,
  });

  @override
  State<AppTextField> createState() => _AppTextFieldState();
}

class _AppTextFieldState extends State<AppTextField> {
  bool _focused = false;

  @override
  void initState() {
    super.initState();
    widget.focusNode?.addListener(_update);
  }

  @override
  void dispose() {
    widget.focusNode?.removeListener(_update);
    super.dispose();
  }

  void _update() =>
      setState(() => _focused = widget.focusNode?.hasFocus ?? false);

  @override
  Widget build(BuildContext context) {
    final isError = widget.error != null;
    final Color borderColor = isError
        ? AppColor.danger
        : widget.ok
        ? AppColor.success
        : _focused
        ? AppColor.brand
        : Colors.transparent;
    // 베이스 = 흰색 통일. error 시만 옅은 빨강 배경 (시각 단서).
    final Color bgColor = isError ? const Color(0xFFFFF5F5) : AppColor.surface;

    // 라벨 색 — 상태에 따라
    final Color labelColor = isError
        ? AppColor.danger
        : _focused
        ? AppColor.brand
        : AppColor.inkSecondary;
    final FontWeight labelWeight = (_focused || isError)
        ? FontWeight.w700
        : FontWeight.w600;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (widget.label != null) ...[
          Padding(
            padding: const EdgeInsets.only(left: 2, bottom: 8),
            child: AnimatedDefaultTextStyle(
              duration: const Duration(milliseconds: 120),
              style: TextStyle(
                fontFamily: 'Pretendard',
                fontSize: 13,
                fontWeight: labelWeight,
                color: labelColor,
                letterSpacing: 0,
                height: 1.0,
              ),
              child: Text(widget.label!),
            ),
          ),
        ],
        // 보더 — CustomPaint 4면 완전. 톤은 옅게 (focus/error/ok 시만 강조)
        _OutlinedBox(
          radius: AppRadius.sm,
          fillColor: bgColor,
          borderColor: borderColor == Colors.transparent
              ? const Color(0xFFE5E9F0) // 평소 매우 옅은 보더
              : borderColor,
          borderWidth: borderColor == Colors.transparent ? 1.2 : 1.5,
          child: TextField(
            controller: widget.controller,
            focusNode: widget.focusNode,
            obscureText: widget.obscure,
            keyboardType: widget.keyboardType,
            textInputAction: widget.textInputAction,
            onSubmitted: widget.onSubmitted,
            style: AppText.bodyLg.copyWith(
              color: AppColor.ink,
              fontWeight: FontWeight.w600,
            ),
            decoration: InputDecoration(
              hintText: widget.hint,
              hintStyle: AppText.bodyLg.copyWith(color: AppColor.inkTertiary),
              // 모든 보더 None — 외곽 AnimatedContainer 가 보더 담당
              border: InputBorder.none,
              enabledBorder: InputBorder.none,
              focusedBorder: InputBorder.none,
              errorBorder: InputBorder.none,
              focusedErrorBorder: InputBorder.none,
              disabledBorder: InputBorder.none,
              isDense: true,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 18,
                vertical: 16,
              ),
              // suffix 컨테이너 — 눈/체크 모두 동일 영역에 수직·우측 정렬
              suffixIcon:
                  widget.suffix ??
                  (widget.ok
                      ? const Padding(
                          padding: EdgeInsets.only(right: 14),
                          child: Icon(
                            Icons.check_circle_rounded,
                            color: AppColor.success,
                            size: 24,
                          ),
                        )
                      : null),
              suffixIconConstraints: const BoxConstraints(
                minWidth: 44,
                minHeight: 44,
              ),
            ),
          ),
        ),
        if (widget.error != null || widget.helper != null)
          Padding(
            padding: const EdgeInsets.only(left: 4, top: 6),
            child: Text(
              widget.error ?? widget.helper ?? '',
              style: AppText.caption.copyWith(
                color: isError ? AppColor.danger : AppColor.inkTertiary,
              ),
            ),
          ),
      ],
    );
  }
}

// ─── 완전한 라운드 보더 박스 ─────────────────────
// CustomPaint 로 4면 모두 균등하게 보더 그림 (Flutter ShapeDecoration/BoxDecoration 모서리 누락 버그 회피)
class _OutlinedBox extends StatelessWidget {
  final double radius;
  final Color fillColor;
  final Color borderColor;
  final double borderWidth;
  final Widget child;

  const _OutlinedBox({
    required this.radius,
    required this.fillColor,
    required this.borderColor,
    required this.borderWidth,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 120),
      // 배경 fill 은 평범한 decoration 으로
      decoration: BoxDecoration(
        color: fillColor,
        borderRadius: BorderRadius.circular(radius),
      ),
      // 그 위에 보더만 CustomPaint 로
      foregroundDecoration: _OutlinedBorderDecoration(
        radius: radius,
        color: borderColor,
        width: borderWidth,
      ),
      child: child,
    );
  }
}

class _OutlinedBorderDecoration extends Decoration {
  final double radius;
  final Color color;
  final double width;

  const _OutlinedBorderDecoration({
    required this.radius,
    required this.color,
    required this.width,
  });

  @override
  BoxPainter createBoxPainter([VoidCallback? onChanged]) {
    return _OutlinedBorderPainter(radius: radius, color: color, width: width);
  }
}

class _OutlinedBorderPainter extends BoxPainter {
  final double radius;
  final Color color;
  final double width;

  _OutlinedBorderPainter({
    required this.radius,
    required this.color,
    required this.width,
  });

  @override
  void paint(Canvas canvas, Offset offset, ImageConfiguration configuration) {
    final size = configuration.size!;
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = width
      ..isAntiAlias = true;
    final rect = Rect.fromLTWH(
      offset.dx + width / 2,
      offset.dy + width / 2,
      size.width - width,
      size.height - width,
    );
    final rrect = RRect.fromRectAndRadius(
      rect,
      Radius.circular(radius - width / 2),
    );
    canvas.drawRRect(rrect, paint);
  }
}
