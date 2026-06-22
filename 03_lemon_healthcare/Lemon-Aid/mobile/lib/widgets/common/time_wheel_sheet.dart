// widgets/common/time_wheel_sheet.dart — 시간 선택 휠 바텀시트 (figma 959:24)
//
// 가이드 08 (d) step 22. 오전·오후 / 시(1~12) / 분(0~59) 3열 CupertinoPicker +
// [확인] 52px 버튼. app_modals 의 바텀시트 셸 톤(흰 카드 + 상단 핸들)과 통일.

import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';

/// 시·분 선택 결과.
@immutable
class TimeOfDayResult {
  /// 결과를 생성한다.
  const TimeOfDayResult({required this.hour, required this.minute});

  /// 24시간제 시(0~23).
  final int hour;

  /// 분(0~59).
  final int minute;
}

/// 시간 휠 바텀시트를 띄우고 선택된 시각을 돌려준다 (취소 시 null).
///
/// Args:
///   initialHour: 초기 시(0~23). 기본 8시.
///   initialMinute: 초기 분(0~59). 기본 0분.
Future<TimeOfDayResult?> showTimeWheelSheet(
  BuildContext context, {
  int initialHour = 8,
  int initialMinute = 0,
}) {
  return showModalBottomSheet<TimeOfDayResult>(
    context: context,
    backgroundColor: Colors.transparent,
    barrierColor: const Color(0x80141A2C),
    isScrollControlled: true,
    showDragHandle: false,
    builder: (BuildContext sheetContext) =>
        _TimeWheelSheet(initialHour: initialHour, initialMinute: initialMinute),
  );
}

class _TimeWheelSheet extends StatefulWidget {
  const _TimeWheelSheet({
    required this.initialHour,
    required this.initialMinute,
  });

  final int initialHour;
  final int initialMinute;

  @override
  State<_TimeWheelSheet> createState() => _TimeWheelSheetState();
}

class _TimeWheelSheetState extends State<_TimeWheelSheet> {
  late int _amPmIndex; // 0=오전, 1=오후
  late int _hour12Index; // 0..11 → 12,1..11
  late int _minuteIndex; // 0..59

  late final FixedExtentScrollController _amPmController;
  late final FixedExtentScrollController _hourController;
  late final FixedExtentScrollController _minuteController;

  @override
  void initState() {
    super.initState();
    _amPmIndex = widget.initialHour >= 12 ? 1 : 0;
    final int hour12 = widget.initialHour % 12; // 0 == 12시
    _hour12Index = hour12;
    _minuteIndex = widget.initialMinute;
    _amPmController = FixedExtentScrollController(initialItem: _amPmIndex);
    _hourController = FixedExtentScrollController(initialItem: _hour12Index);
    _minuteController = FixedExtentScrollController(initialItem: _minuteIndex);
  }

  @override
  void dispose() {
    _amPmController.dispose();
    _hourController.dispose();
    _minuteController.dispose();
    super.dispose();
  }

  int get _hour24 {
    // _hour12Index 0 → 12시(자정/정오 기준). 오전 12시=0시, 오후 12시=12시.
    final int hour12 = _hour12Index == 0 ? 12 : _hour12Index;
    if (_amPmIndex == 0) {
      return hour12 == 12 ? 0 : hour12;
    }
    return hour12 == 12 ? 12 : hour12 + 12;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(28),
          topRight: Radius.circular(28),
        ),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: Color(0x40141A2C),
            blurRadius: 40,
            spreadRadius: -10,
            offset: Offset(0, -20),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: <Widget>[
              Center(
                child: Container(
                  width: 36,
                  height: 4,
                  margin: const EdgeInsets.only(top: 4, bottom: AppSpace.lg),
                  decoration: BoxDecoration(
                    color: AppColor.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const Text(
                '알림 시간',
                style: TextStyle(
                  fontFamily: 'Pretendard',
                  fontSize: 19,
                  fontWeight: FontWeight.w800,
                  color: AppColor.ink,
                  letterSpacing: 0,
                ),
              ),
              const SizedBox(height: AppSpace.lg),
              SizedBox(
                height: 180,
                child: Row(
                  children: <Widget>[
                    Expanded(
                      child: _wheel(
                        controller: _amPmController,
                        childCount: 2,
                        labelBuilder: (int i) => i == 0 ? '오전' : '오후',
                        onChanged: (int i) => setState(() => _amPmIndex = i),
                      ),
                    ),
                    Expanded(
                      child: _wheel(
                        controller: _hourController,
                        childCount: 12,
                        labelBuilder: (int i) => '${i == 0 ? 12 : i}시',
                        onChanged: (int i) => setState(() => _hour12Index = i),
                      ),
                    ),
                    Expanded(
                      child: _wheel(
                        controller: _minuteController,
                        childCount: 60,
                        labelBuilder: (int i) =>
                            '${i.toString().padLeft(2, '0')}분',
                        onChanged: (int i) => setState(() => _minuteIndex = i),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpace.lg),
              SizedBox(
                height: 52,
                child: AppPrimaryButton(
                  label: '확인',
                  onPressed: () => Navigator.of(
                    context,
                  ).pop(TimeOfDayResult(hour: _hour24, minute: _minuteIndex)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _wheel({
    required FixedExtentScrollController controller,
    required int childCount,
    required String Function(int index) labelBuilder,
    required ValueChanged<int> onChanged,
  }) {
    return CupertinoPicker(
      scrollController: controller,
      itemExtent: 40,
      onSelectedItemChanged: onChanged,
      selectionOverlay: CupertinoPickerDefaultSelectionOverlay(
        background: AppColor.brandSoft,
      ),
      children: List<Widget>.generate(
        childCount,
        (int i) => Center(
          child: Text(
            labelBuilder(i),
            style: const TextStyle(
              fontFamily: 'Pretendard',
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppColor.ink,
            ),
          ),
        ),
      ),
    );
  }
}
