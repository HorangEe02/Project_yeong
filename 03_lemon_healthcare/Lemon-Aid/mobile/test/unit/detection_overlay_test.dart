import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/widgets/common/detection_overlay.dart';

SupplementDetectedProductRegion _region({
  required int x,
  required int y,
  required int width,
  required int height,
  bool selected = false,
  double confidence = 0.9,
}) {
  return SupplementDetectedProductRegion(
    regionId: 'r-$x-$y',
    label: 'label',
    x: x,
    y: y,
    width: width,
    height: height,
    confidence: confidence,
    areaRatio: null,
    selected: selected,
  );
}

void main() {
  group('DetectionOverlayTransform.contain', () {
    test('scales square image into a square widget 1:1 with no letterbox', () {
      final DetectionOverlayTransform transform =
          DetectionOverlayTransform.contain(
            imageWidth: 100,
            imageHeight: 100,
            widgetSize: const Size(200, 200),
          );
      expect(transform.scale, 2.0);
      expect(transform.dx, 0);
      expect(transform.dy, 0);
    });

    test('letterboxes a portrait image inside a square widget', () {
      // 100x200 image into 200x200 widget → scale 1.0 (height bound), dx=50.
      final DetectionOverlayTransform transform =
          DetectionOverlayTransform.contain(
            imageWidth: 100,
            imageHeight: 200,
            widgetSize: const Size(200, 200),
          );
      expect(transform.scale, 1.0);
      expect(transform.dx, 50);
      expect(transform.dy, 0);
    });

    test('maps a region into widget pixels at the right scale and offset', () {
      final DetectionOverlayTransform transform =
          DetectionOverlayTransform.contain(
            imageWidth: 100,
            imageHeight: 200,
            widgetSize: const Size(200, 200),
          );
      final Rect rect = transform.mapRegion(
        _region(x: 10, y: 20, width: 30, height: 40),
      );
      // scale 1.0, dx 50, dy 0.
      expect(rect.left, 60);
      expect(rect.top, 20);
      expect(rect.width, 30);
      expect(rect.height, 40);
    });

    test('returns a zero scale for degenerate sizes', () {
      final DetectionOverlayTransform transform =
          DetectionOverlayTransform.contain(
            imageWidth: 0,
            imageHeight: 200,
            widgetSize: const Size(200, 200),
          );
      expect(transform.scale, 0);
    });
  });

  group('inferImageBoundsFromRegions', () {
    test('returns zero bounds for an empty list', () {
      final ({int width, int height}) bounds = inferImageBoundsFromRegions(
        const <SupplementDetectedProductRegion>[],
      );
      expect(bounds.width, 0);
      expect(bounds.height, 0);
    });

    test('uses the right/bottom extent plus padding', () {
      final ({int width, int height}) bounds = inferImageBoundsFromRegions(
        <SupplementDetectedProductRegion>[
          _region(x: 0, y: 0, width: 100, height: 50),
          _region(x: 80, y: 40, width: 120, height: 60),
        ],
        padding: 0,
      );
      // max right = 80+120 = 200, max bottom = 40+60 = 100.
      expect(bounds.width, 200);
      expect(bounds.height, 100);
    });
  });

  testWidgets('DetectionOverlay renders nothing when there are no regions', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const Directionality(
        textDirection: TextDirection.ltr,
        child: SizedBox(
          width: 200,
          height: 200,
          child: DetectionOverlay(
            regions: <SupplementDetectedProductRegion>[],
            imageWidth: 100,
            imageHeight: 100,
          ),
        ),
      ),
    );
    expect(find.byType(CustomPaint), findsNothing);
  });

  testWidgets('DetectionOverlay paints boxes when regions are present', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: SizedBox(
          width: 200,
          height: 200,
          child: DetectionOverlay(
            regions: <SupplementDetectedProductRegion>[
              _region(x: 10, y: 10, width: 40, height: 40, selected: true),
            ],
            imageWidth: 100,
            imageHeight: 100,
          ),
        ),
      ),
    );
    expect(find.byType(CustomPaint), findsWidgets);
  });
}
