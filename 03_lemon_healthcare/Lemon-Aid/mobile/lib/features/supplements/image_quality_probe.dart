// features/supplements/image_quality_probe.dart — 업로드 전 미리보기 품질 휴리스틱
//
// figma 912:46 미리보기 품질 체크 2종(가이드 ④-4 · ⑥):
//   ① 선명도 — 라플라시안 분산(blur 추정). 분산이 낮으면 흐림.
//   ② 밝기 — 평균 휘도(저조도). 평균이 낮으면 어두움.
//
// ⚠️ 가이드 ⑥은 "차단 아님, 소프트 안내만" — 이 모듈은 판정만 하고
//    분석하기 버튼을 막지 않는다(호출부에서 안내 행만 표시).
//    과한 이미지 분석 금지 — 그레이스케일 휘도 격자(luma 0~255) 위에서만 동작.
//
// 입력은 디코드된 휘도 격자([ImageLumaGrid]). 픽셀 디코딩은 호출부(또는 테스트
// 픽스처) 책임 — 본 모듈은 순수 함수로 결정론적이며 단위 테스트가 동반된다.

import 'dart:math' as math;

/// 단일 품질 체크 항목.
enum QualityCheck {
  /// 선명도(흐림) 체크.
  sharpness,

  /// 밝기(저조도) 체크.
  brightness,
}

/// 품질 체크 한 건의 결과.
class QualityCheckResult {
  /// 체크 결과를 만든다.
  const QualityCheckResult({
    required this.check,
    required this.passed,
    required this.metric,
  });

  /// 어떤 체크인지.
  final QualityCheck check;

  /// 통과 여부 (true = 통과 ✓, false = 미달 ⚠).
  final bool passed;

  /// 판정에 사용한 원시 지표값 (선명도=분산, 밝기=평균 휘도).
  final double metric;
}

/// 미리보기 품질 체크 2종 묶음.
class ImageQualityProbeResult {
  /// 묶음 결과를 만든다.
  const ImageQualityProbeResult({
    required this.sharpness,
    required this.brightness,
  });

  /// 선명도 체크 결과.
  final QualityCheckResult sharpness;

  /// 밝기 체크 결과.
  final QualityCheckResult brightness;

  /// 두 체크 모두 통과했는지.
  bool get allPassed => sharpness.passed && brightness.passed;

  /// 미달 항목 목록 (안내 표시용).
  List<QualityCheck> get failingChecks => <QualityCheck>[
    if (!sharpness.passed) QualityCheck.sharpness,
    if (!brightness.passed) QualityCheck.brightness,
  ];
}

/// 디코드된 그레이스케일 휘도 격자 (0~255).
///
/// [luma] 길이는 [width]*[height] 와 같아야 한다.
class ImageLumaGrid {
  /// 휘도 격자를 만든다.
  const ImageLumaGrid({
    required this.width,
    required this.height,
    required this.luma,
  });

  /// 격자 너비.
  final int width;

  /// 격자 높이.
  final int height;

  /// 행 우선(row-major) 휘도값 (0~255).
  final List<int> luma;

  /// 좌표 [x],[y] 의 휘도값.
  int at(int x, int y) => luma[y * width + x];

  /// 격자가 라플라시안 계산에 충분한 크기인지(3×3 이상).
  bool get isProbeable =>
      width >= 3 && height >= 3 && luma.length == width * height;
}

/// 선명도 판정 임계값 — 라플라시안 분산이 이 값 미만이면 흐림으로 본다.
///
/// 시안 안내 수준의 보수적 기본값. 호출부에서 조정 가능.
const double kSharpnessVarianceThreshold = 60;

/// 밝기 판정 임계값 — 평균 휘도가 이 값 미만이면 저조도로 본다.
const double kBrightnessMeanThreshold = 60;

/// 휘도 격자에 대해 미리보기 품질 체크 2종을 수행한다.
///
/// 격자가 너무 작으면([ImageLumaGrid.isProbeable]==false) 두 체크 모두 통과로
/// 처리한다(소프트 안내 — 잘못된 미달 경고를 내지 않는다).
ImageQualityProbeResult probeImageQuality(
  ImageLumaGrid grid, {
  double sharpnessThreshold = kSharpnessVarianceThreshold,
  double brightnessThreshold = kBrightnessMeanThreshold,
}) {
  if (!grid.isProbeable) {
    return const ImageQualityProbeResult(
      sharpness: QualityCheckResult(
        check: QualityCheck.sharpness,
        passed: true,
        metric: double.nan,
      ),
      brightness: QualityCheckResult(
        check: QualityCheck.brightness,
        passed: true,
        metric: double.nan,
      ),
    );
  }
  final double variance = laplacianVariance(grid);
  final double mean = meanBrightness(grid);
  return ImageQualityProbeResult(
    sharpness: QualityCheckResult(
      check: QualityCheck.sharpness,
      passed: variance >= sharpnessThreshold,
      metric: variance,
    ),
    brightness: QualityCheckResult(
      check: QualityCheck.brightness,
      passed: mean >= brightnessThreshold,
      metric: mean,
    ),
  );
}

/// 평균 휘도(0~255)를 계산한다.
double meanBrightness(ImageLumaGrid grid) {
  if (grid.luma.isEmpty) return 0;
  int sum = 0;
  for (final int value in grid.luma) {
    sum += value;
  }
  return sum / grid.luma.length;
}

/// 라플라시안 분산(흐림 추정 지표)을 계산한다.
///
/// 3×3 라플라시안 커널(중앙 4, 상하좌우 -1)을 내부 픽셀에 적용한 뒤
/// 응답값의 분산을 돌려준다. 값이 클수록 가장자리가 또렷(선명)하다.
double laplacianVariance(ImageLumaGrid grid) {
  if (!grid.isProbeable) return 0;
  final List<double> responses = <double>[];
  for (int y = 1; y < grid.height - 1; y++) {
    for (int x = 1; x < grid.width - 1; x++) {
      final int center = grid.at(x, y);
      final double response =
          (4 * center -
                  grid.at(x - 1, y) -
                  grid.at(x + 1, y) -
                  grid.at(x, y - 1) -
                  grid.at(x, y + 1))
              .toDouble();
      responses.add(response);
    }
  }
  if (responses.isEmpty) return 0;
  final double mean =
      responses.reduce((double a, double b) => a + b) / responses.length;
  double sumSq = 0;
  for (final double r in responses) {
    final double diff = r - mean;
    sumSq += diff * diff;
  }
  return sumSq / responses.length;
}

/// sRGB 채널([r],[g],[b], 각 0~255)을 정수 휘도(0~255)로 변환한다 (BT.601).
int lumaFromRgb(int r, int g, int b) {
  final double luma = 0.299 * r + 0.587 * g + 0.114 * b;
  return luma.round().clamp(0, 255);
}

/// 정사각 다운샘플 격자의 한 변 권장 크기 (성능·정확도 균형).
const int kProbeGridSize = 32;

/// 0~255 휘도 1차원 리스트로 [kProbeGridSize] 정사각 격자를 만든다(테스트 보조).
ImageLumaGrid lumaGridFromSquare(List<int> luma) {
  final int side = math.sqrt(luma.length).floor();
  return ImageLumaGrid(width: side, height: side, luma: luma);
}
