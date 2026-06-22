import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/supplements/image_quality_probe.dart';

/// 결정론적 픽스처: 모든 픽셀이 같은 값인 평탄 격자(가장자리 없음 → 흐림).
ImageLumaGrid _flatGrid(int value, {int side = 8}) {
  return ImageLumaGrid(
    width: side,
    height: side,
    luma: List<int>.filled(side * side, value),
  );
}

/// 결정론적 픽스처: 체스판 패턴(강한 가장자리 → 선명).
ImageLumaGrid _checkerGrid({int side = 8, int low = 0, int high = 255}) {
  final List<int> luma = <int>[];
  for (int y = 0; y < side; y++) {
    for (int x = 0; x < side; x++) {
      luma.add((x + y).isEven ? high : low);
    }
  }
  return ImageLumaGrid(width: side, height: side, luma: luma);
}

void main() {
  group('meanBrightness', () {
    test('flat dark grid is below the brightness threshold', () {
      final ImageLumaGrid grid = _flatGrid(20);
      expect(meanBrightness(grid), 20);
      final ImageQualityProbeResult result = probeImageQuality(grid);
      expect(result.brightness.passed, isFalse);
    });

    test('flat bright grid passes the brightness check', () {
      final ImageLumaGrid grid = _flatGrid(180);
      expect(meanBrightness(grid), 180);
      final ImageQualityProbeResult result = probeImageQuality(grid);
      expect(result.brightness.passed, isTrue);
    });
  });

  group('laplacianVariance', () {
    test('flat grid has zero variance and fails the sharpness check', () {
      final ImageLumaGrid grid = _flatGrid(128);
      expect(laplacianVariance(grid), 0);
      final ImageQualityProbeResult result = probeImageQuality(grid);
      expect(result.sharpness.passed, isFalse);
    });

    test('high-contrast checker grid passes the sharpness check', () {
      final ImageLumaGrid grid = _checkerGrid();
      expect(
        laplacianVariance(grid),
        greaterThan(kSharpnessVarianceThreshold),
      );
      final ImageQualityProbeResult result = probeImageQuality(grid);
      expect(result.sharpness.passed, isTrue);
    });
  });

  group('probeImageQuality boundaries', () {
    test('metric exactly at the threshold passes (inclusive)', () {
      final ImageLumaGrid grid = _flatGrid(60);
      final ImageQualityProbeResult result = probeImageQuality(
        grid,
        brightnessThreshold: 60,
      );
      expect(result.brightness.metric, 60);
      expect(result.brightness.passed, isTrue);
    });

    test('one below the threshold fails', () {
      final ImageLumaGrid grid = _flatGrid(59);
      final ImageQualityProbeResult result = probeImageQuality(
        grid,
        brightnessThreshold: 60,
      );
      expect(result.brightness.passed, isFalse);
    });

    test('too-small grid is treated as passing (soft advisory)', () {
      const ImageLumaGrid grid = ImageLumaGrid(
        width: 2,
        height: 2,
        luma: <int>[0, 0, 0, 0],
      );
      expect(grid.isProbeable, isFalse);
      final ImageQualityProbeResult result = probeImageQuality(grid);
      expect(result.allPassed, isTrue);
      expect(result.failingChecks, isEmpty);
    });

    test('failingChecks lists both checks when both are below threshold', () {
      final ImageLumaGrid grid = _flatGrid(10);
      final ImageQualityProbeResult result = probeImageQuality(grid);
      expect(
        result.failingChecks,
        containsAll(<QualityCheck>[
          QualityCheck.sharpness,
          QualityCheck.brightness,
        ]),
      );
    });
  });

  group('lumaFromRgb', () {
    test('pure white maps to 255 and pure black to 0', () {
      expect(lumaFromRgb(255, 255, 255), 255);
      expect(lumaFromRgb(0, 0, 0), 0);
    });

    test('clamps within 0..255 using BT.601 weights', () {
      final int gray = lumaFromRgb(128, 128, 128);
      expect(gray, inInclusiveRange(127, 128));
    });
  });
}
