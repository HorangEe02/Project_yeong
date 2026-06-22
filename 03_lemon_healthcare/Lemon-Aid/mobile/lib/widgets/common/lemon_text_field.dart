// widgets/common/lemon_text_field.dart — 라벨 + 입력 + helper/error 통합
//
// 다이어리 §14.6 TextField 명세:
//   높이 56 / radius 12 / border 1.5 line / focus brand 2px / error danger 2px
//
// 사용:
//   LemonTextField(label: '이메일', hint: 'name@email.com')
//   LemonTextField(label: '비밀번호', obscure: true, error: '비번이 짧아요')

import 'package:flutter/material.dart';
import '../../utils/tokens.dart';

class LemonTextField extends StatefulWidget {
  final String label;
  final String? hint;
  final String? helper;
  final String? error;
  final TextEditingController? controller;
  final bool obscure;
  final bool obscureToggle;
  final TextInputType keyboardType;
  final TextInputAction textInputAction;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final Widget? suffix;
  final int? maxLength;
  final bool enabled;
  final bool autofocus;
  final List<String>? autofillHints;

  const LemonTextField({
    super.key,
    required this.label,
    this.hint,
    this.helper,
    this.error,
    this.controller,
    this.obscure = false,
    this.obscureToggle = false,
    this.keyboardType = TextInputType.text,
    this.textInputAction = TextInputAction.next,
    this.onChanged,
    this.onSubmitted,
    this.suffix,
    this.maxLength,
    this.enabled = true,
    this.autofocus = false,
    this.autofillHints,
  });

  @override
  State<LemonTextField> createState() => _LemonTextFieldState();
}

class _LemonTextFieldState extends State<LemonTextField> {
  bool _obscured = true;

  @override
  void initState() {
    super.initState();
    _obscured = widget.obscure;
  }

  @override
  Widget build(BuildContext context) {
    final hasError = widget.error != null;
    final showSuffix = widget.suffix != null || widget.obscureToggle;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 6, left: 4),
          child: Text(
            widget.label,
            style: LemonText.caption.copyWith(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: LemonColors.inkSoft,
            ),
          ),
        ),
        TextField(
          controller: widget.controller,
          obscureText: widget.obscure ? _obscured : false,
          keyboardType: widget.keyboardType,
          textInputAction: widget.textInputAction,
          onChanged: widget.onChanged,
          onSubmitted: widget.onSubmitted,
          enabled: widget.enabled,
          autofocus: widget.autofocus,
          maxLength: widget.maxLength,
          autofillHints: widget.autofillHints,
          style: LemonText.body.copyWith(fontSize: 17),
          decoration: InputDecoration(
            hintText: widget.hint,
            hintStyle: LemonText.body.copyWith(
              color: LemonColors.inkMute,
              fontSize: 17,
            ),
            filled: true,
            fillColor: widget.enabled ? LemonColors.bgElev : LemonColors.line,
            counterText: '',
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 14,
            ),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(LemonRadius.md),
              borderSide: const BorderSide(color: LemonColors.line, width: 1.5),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(LemonRadius.md),
              borderSide: BorderSide(
                color: hasError ? LemonColors.danger : LemonColors.line,
                width: 1.5,
              ),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(LemonRadius.md),
              borderSide: BorderSide(
                color: hasError ? LemonColors.danger : LemonColors.brand,
                width: 2,
              ),
            ),
            errorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(LemonRadius.md),
              borderSide: const BorderSide(color: LemonColors.danger, width: 2),
            ),
            suffixIcon: showSuffix
                ? Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: widget.obscureToggle
                        ? IconButton(
                            icon: Icon(
                              _obscured
                                  ? Icons.visibility_off
                                  : Icons.visibility,
                              color: LemonColors.inkMute,
                              size: 22,
                            ),
                            onPressed: () =>
                                setState(() => _obscured = !_obscured),
                          )
                        : widget.suffix,
                  )
                : null,
          ),
        ),
        if (widget.error != null)
          Padding(
            padding: const EdgeInsets.only(top: 4, left: 4),
            child: Row(
              children: [
                const Icon(
                  Icons.error_outline,
                  size: 14,
                  color: LemonColors.danger,
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    widget.error!,
                    style: LemonText.caption.copyWith(
                      color: LemonColors.danger,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
          )
        else if (widget.helper != null)
          Padding(
            padding: const EdgeInsets.only(top: 4, left: 4),
            child: Text(widget.helper!, style: LemonText.caption),
          ),
      ],
    );
  }
}
