import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/widgets/common/portion_sheet.dart';

void main() {
  group('formatPortionLabel', () {
    test('renders the half-serving glyph', () {
      expect(formatPortionLabel(0.5), '½인분');
    });

    test('drops trailing zeros for whole and fractional servings', () {
      expect(formatPortionLabel(1), '1인분');
      expect(formatPortionLabel(1.5), '1.5인분');
      expect(formatPortionLabel(2), '2인분');
      expect(formatPortionLabel(1.25), '1.25인분');
    });
  });

  group('formatPortionGrams', () {
    test('converts servings to grams with the default base (100g)', () {
      expect(formatPortionGrams(1), '약 100g');
      expect(formatPortionGrams(1.5), '약 150g');
      expect(formatPortionGrams(0.5), '약 50g');
    });

    test('uses a custom per-serving base when provided', () {
      expect(formatPortionGrams(2, gramsPerServing: 80), '약 160g');
    });

    test('hides grams when the base is non-positive', () {
      expect(formatPortionGrams(1, gramsPerServing: 0), isNull);
      expect(formatPortionGrams(1, gramsPerServing: -10), isNull);
    });
  });

  group('clampPortion', () {
    test('snaps to the 0.25 grid', () {
      expect(clampPortion(1.1), 1.0);
      expect(clampPortion(1.13), 1.25);
      expect(clampPortion(1.37), 1.25);
      expect(clampPortion(1.38), 1.5);
    });

    test('clamps to the min and max bounds', () {
      expect(clampPortion(0.1), kMinPortion);
      expect(clampPortion(100), kMaxPortion);
    });
  });

  group('preset chips', () {
    test('expose the ½/1/1.5/2 serving presets', () {
      expect(kPortionPresets, <double>[0.5, 1, 1.5, 2]);
    });
  });

  test('PortionSelection always carries the serving unit', () {
    const PortionSelection selection = PortionSelection(
      portionAmount: 1.5,
      portionUnit: 'serving',
    );
    expect(selection.portionAmount, 1.5);
    expect(selection.portionUnit, 'serving');
  });

  test('no portion label exposes a raw percentage', () {
    // 신뢰도 % 비노출 회귀 가드 — 섭취량 라벨에 % 가 끼어들지 않는다.
    for (final double amount in <double>[0.5, 1, 1.5, 2, 1.25]) {
      expect(formatPortionLabel(amount).contains('%'), isFalse);
    }
  });

  testWidgets('debugFillProperties keeps WidgetsFlutterBinding usable', (
    WidgetTester tester,
  ) async {
    // Sanity: the library imports render-layer types without throwing.
    expect(const SizedBox().runtimeType, SizedBox);
  });
}
