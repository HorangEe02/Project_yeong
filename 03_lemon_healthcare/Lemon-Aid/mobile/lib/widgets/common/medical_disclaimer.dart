// widgets/common/medical_disclaimer.dart
//
// §14 의료 컴플라이언스 의무 — 모든 추천 화면 하단에 포함
// 디자인 토큰 단일 출처: design_tokens_v2 (SoT v1.1 §9.4)

import 'package:flutter/material.dart';
import '../../utils/design_tokens_v2.dart';

class MedicalDisclaimer extends StatelessWidget {
  /// 표준 / 컴팩트 / 카드 인라인 변형
  final DisclaimerVariant variant;

  const MedicalDisclaimer({
    super.key,
    this.variant = DisclaimerVariant.standard,
  });

  // 의료 컴플라이언스 표준 면책 문구 (§14) — 문구 변경 시 금칙어 가드 테스트 확인
  static const String medicalDisclaimerText =
      "본 서비스에서 제공하는 정보는 일반적인 건강 관리를 위한 참고 자료이며,\n"
      "의사·약사·영양사의 전문적 진단이나 처방을 대체하지 않습니다.";

  // 분석/점수 요약 화면용 면책 문구 (해요체 · 브랜드 톤) — figma Main.
  // 화면 톤(해요체)을 유지하기 위해 표준 문구와 별도로 둔다.
  // 문구 변경 시 금칙어 가드 테스트(score_screen_test) 화이트리스트도 함께 갱신.
  static const String summaryDisclaimerText =
      '이 분석은 건강 관리를 돕는 참고 정보예요.\n의사·약사·영양사의 진단을 대신하진 않아요.';

  @override
  Widget build(BuildContext context) {
    switch (variant) {
      case DisclaimerVariant.standard:
        return _standard();
      case DisclaimerVariant.summary:
        return _summary();
      case DisclaimerVariant.compact:
        return _compact();
      case DisclaimerVariant.inline:
        return _inline();
    }
  }

  Widget _standard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.lg),
      margin: const EdgeInsets.symmetric(
        horizontal: AppSpace.lg,
        vertical: AppSpace.xl,
      ),
      decoration: BoxDecoration(
        color: AppColor.reviewSoft,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: AppColor.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.info_outline, color: AppColor.review, size: 20),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Text(
              medicalDisclaimerText,
              style: AppText.caption.copyWith(
                color: AppColor.inkSecondary,
                height: 1.5,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // 분석/점수 요약 화면 하단 (해요체 · 브랜드 톤 pill). figma Main 톤 유지.
  Widget _summary() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.brandSoft,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.info_outline, color: AppColor.brandDeep, size: 18),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: Text(
              summaryDisclaimerText,
              style: AppText.caption.copyWith(color: AppColor.ink, height: 1.5),
            ),
          ),
        ],
      ),
    );
  }

  Widget _compact() {
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.lg,
        vertical: AppSpace.sm,
      ),
      child: Text(
        "* 참고용 정보입니다. 전문가 상담을 권유드려요.",
        style: AppText.caption,
        textAlign: TextAlign.center,
      ),
    );
  }

  Widget _inline() {
    return Text(
      "참고용",
      style: AppText.caption.copyWith(
        color: AppColor.review,
        fontWeight: FontWeight.w600,
      ),
    );
  }
}

enum DisclaimerVariant {
  /// 화면 하단 표준 면책 박스 (가장 자주 사용)
  standard,

  /// 분석/점수 요약 화면 하단 (해요체 · 브랜드 톤 pill)
  summary,

  /// 화면 하단 작은 한 줄
  compact,

  /// 카드 안 인라인 라벨
  inline,
}
