import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/widgets/common/confidence_grade_chip.dart';

void main() {
  group('ConfidenceGrade.fromConfidence', () {
    test('maps high confidence (>= 0.85) to 높음', () {
      expect(ConfidenceGrade.fromConfidence(0.85), ConfidenceGrade.high);
      expect(ConfidenceGrade.fromConfidence(0.92), ConfidenceGrade.high);
      expect(ConfidenceGrade.fromConfidence(1), ConfidenceGrade.high);
      expect(ConfidenceGrade.high.label, '높음');
    });

    test('maps medium confidence (>= 0.6) to 보통', () {
      expect(ConfidenceGrade.fromConfidence(0.6), ConfidenceGrade.medium);
      expect(ConfidenceGrade.fromConfidence(0.84), ConfidenceGrade.medium);
      expect(ConfidenceGrade.medium.label, '보통');
    });

    test('maps low/unknown confidence to 직접 확인 필요', () {
      expect(ConfidenceGrade.fromConfidence(0.59), ConfidenceGrade.low);
      expect(ConfidenceGrade.fromConfidence(0), ConfidenceGrade.low);
      expect(ConfidenceGrade.fromConfidence(null), ConfidenceGrade.low);
      expect(ConfidenceGrade.low.label, '직접 확인 필요');
    });

    test('marks only the low grade for the LowConfidenceBanner', () {
      expect(ConfidenceGrade.fromConfidence(0.9).isLowConfidence, isFalse);
      expect(ConfidenceGrade.fromConfidence(0.7).isLowConfidence, isFalse);
      expect(ConfidenceGrade.fromConfidence(0.4).isLowConfidence, isTrue);
      expect(ConfidenceGrade.fromConfidence(null).isLowConfidence, isTrue);
    });
  });
}
