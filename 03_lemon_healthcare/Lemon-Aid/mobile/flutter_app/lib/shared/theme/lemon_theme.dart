import 'package:flutter/material.dart';

class LemonColors {
  static const Color canvas = Color(0xFFF3F4F6);
  static const Color paper = Color(0xFFFFFFFF);
  static const Color lemon = Color(0xFFFFCE00);
  static const Color lemonSoft = Color(0xFFFFF8C7);
  static const Color leaf = Color(0xFF2EA354);
  static const Color leafSoft = Color(0xFFC9F2D0);
  static const Color sky = Color(0xFF2CA8E0);
  static const Color skySoft = Color(0xFFDAF1FB);
  static const Color warning = Color(0xFFFB8C00);
  static const Color warningSoft = Color(0xFFFFEACC);
  static const Color danger = Color(0xFFD9342B);
  static const Color dangerSoft = Color(0xFFFCE2E0);
  static const Color ink = Color(0xFF1B1300);
  static const Color inkMuted = Color(0xFF6A6353);
  static const Color line = Color(0xFFEBE6D4);
}

class LemonTheme {
  static ThemeData data() {
    final ColorScheme scheme = ColorScheme.fromSeed(
      seedColor: LemonColors.leaf,
      primary: LemonColors.leaf,
      secondary: LemonColors.lemon,
      surface: LemonColors.paper,
      error: LemonColors.danger,
    );

    return ThemeData(
      colorScheme: scheme,
      scaffoldBackgroundColor: LemonColors.canvas,
      useMaterial3: true,
      appBarTheme: const AppBarTheme(
        backgroundColor: LemonColors.canvas,
        foregroundColor: LemonColors.ink,
        centerTitle: false,
        elevation: 0,
        titleTextStyle: TextStyle(
          color: LemonColors.ink,
          fontSize: 20,
          fontWeight: FontWeight.w800,
        ),
      ),
      cardTheme: CardThemeData(
        color: LemonColors.paper,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
          side: const BorderSide(color: LemonColors.line),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: LemonColors.paper,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: LemonColors.line),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          backgroundColor: LemonColors.lemon,
          foregroundColor: LemonColors.ink,
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          foregroundColor: LemonColors.ink,
          side: const BorderSide(color: LemonColors.line),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(
          color: LemonColors.ink,
          fontSize: 26,
          fontWeight: FontWeight.w800,
        ),
        headlineSmall: TextStyle(
          color: LemonColors.ink,
          fontSize: 22,
          fontWeight: FontWeight.w800,
        ),
        titleMedium: TextStyle(
          color: LemonColors.ink,
          fontSize: 17,
          fontWeight: FontWeight.w800,
        ),
        bodyLarge: TextStyle(
          color: LemonColors.ink,
          fontSize: 17,
          height: 1.45,
        ),
        bodyMedium: TextStyle(
          color: LemonColors.inkMuted,
          fontSize: 15,
          height: 1.4,
        ),
        labelMedium: TextStyle(
          color: LemonColors.inkMuted,
          fontSize: 13,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class LemonCard extends StatelessWidget {
  const LemonCard({
    super.key,
    required this.child,
    this.color = LemonColors.paper,
    this.padding = const EdgeInsets.all(16),
  });

  final Widget child;
  final Color color;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: LemonColors.line),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x14000000),
            blurRadius: 12,
            offset: Offset(0, 4),
          ),
        ],
      ),
      child: Padding(
        padding: padding,
        child: child,
      ),
    );
  }
}

class LemonPill extends StatelessWidget {
  const LemonPill({
    super.key,
    required this.label,
    required this.color,
    required this.backgroundColor,
  });

  final String label;
  final Color color;
  final Color backgroundColor;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        child: Text(
          label,
          style:
              Theme.of(context).textTheme.labelMedium?.copyWith(color: color),
        ),
      ),
    );
  }
}
