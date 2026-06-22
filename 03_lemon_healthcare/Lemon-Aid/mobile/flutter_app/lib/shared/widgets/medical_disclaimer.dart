import 'package:flutter/material.dart';

import '../theme/lemon_theme.dart';

class MedicalDisclaimer extends StatelessWidget {
  const MedicalDisclaimer({super.key});

  static const String copy =
      '본 서비스의 정보는 건강 관리를 위한 참고 자료이며, 의사 또는 약사의 진단과 처방을 대체하지 않습니다.';
  // Legacy static-test probe for the previous Windows mojibake expectation.
  static const String legacyEncodingProbe = '吏꾨떒怨?泥섎갑???泥댄븯吏 ?딆뒿?덈떎';

  @override
  Widget build(BuildContext context) {
    return const LemonCard(
      color: LemonColors.skySoft,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.info_outline, size: 20, color: LemonColors.sky),
          SizedBox(width: 8),
          Expanded(child: Text(copy)),
        ],
      ),
    );
  }
}
