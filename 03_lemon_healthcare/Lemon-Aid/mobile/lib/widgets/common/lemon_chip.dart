// widgets/common/lemon_chip.dart — Pill chip Default/Selected
//
// 다이어리 §14.6 Chip 명세:
//   pill / 36dp / Default(line border) / Selected(brand tint + brand text)

import 'package:flutter/material.dart';
import '../../utils/tokens.dart';

class LemonChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback? onTap;
  final Widget? leading;
  final double height;

  const LemonChip({
    super.key,
    required this.label,
    this.selected = false,
    this.onTap,
    this.leading,
    this.height = 36,
  });

  @override
  Widget build(BuildContext context) {
    final bg = selected ? LemonColors.brandTint : LemonColors.bgElev;
    final fg = selected ? LemonColors.brandStrong : LemonColors.ink;
    final border = selected ? LemonColors.brand : LemonColors.line;
    final borderWidth = selected ? 1.5 : 1.0;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(LemonRadius.pill),
        onTap: onTap,
        child: Container(
          height: height,
          padding: const EdgeInsets.symmetric(horizontal: 14),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(LemonRadius.pill),
            border: Border.all(color: border, width: borderWidth),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (leading != null) ...[leading!, const SizedBox(width: 6)],
              Text(
                label,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                  color: fg,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
