// 등급 라벨 → 시맨틱 색 매핑 단위 테스트 (가이드 06 §2.4·⑦).
//
// 홈 점수 카드(health_hero_card)와 오늘의 분석(score_screen)이 이 헬퍼
// 하나를 공유하므로, 매핑 검증은 두 화면의 등급 색 정합 검증을 겸한다.

import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/shared/score_label_colors.dart';
import 'package:lemon_aid_mobile/utils/design_tokens_v2.dart';

void main() {
  test('maps the five server labels to the three semantic tokens', () {
    expect(scoreLabelColor('excellent'), AppColor.success);
    expect(scoreLabelColor('good'), AppColor.success);
    expect(scoreLabelColor('moderate'), AppColor.warning);
    expect(scoreLabelColor('warning'), AppColor.danger);
    expect(scoreLabelColor('needs_attention'), AppColor.danger);

    expect(scoreLabelSoftColor('excellent'), AppColor.successSoft);
    expect(scoreLabelSoftColor('good'), AppColor.successSoft);
    expect(scoreLabelSoftColor('moderate'), AppColor.warningSoft);
    expect(scoreLabelSoftColor('warning'), AppColor.dangerSoft);
    expect(scoreLabelSoftColor('needs_attention'), AppColor.dangerSoft);
  });

  test('falls back to brand colors for null or unknown labels', () {
    // 서버가 신규 라벨을 내려도 화면이 깨지지 않도록 브랜드 색 폴백.
    expect(scoreLabelColor(null), AppColor.brand);
    expect(scoreLabelColor('brand_new_label'), AppColor.brand);
    expect(scoreLabelSoftColor(null), AppColor.brandSoft);
    expect(scoreLabelSoftColor('brand_new_label'), AppColor.brandSoft);
  });
}
