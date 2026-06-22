// widgets/common/detection_overlay.dart — 검출 오버레이 (figma 946:50)
//
// 영양제 preview 의 detected_product_regions[] 좌표(입력 이미지 픽셀 기준)를
// 위젯 크기에 맞춰 스케일 변환해 바운딩박스로 렌더한다.
//   - selected=true 영역: brand 테두리(굵게)
//   - 그 외 영역: 옅은 흰 테두리
//   - 라벨은 등급 칩(ConfidenceGradeChip)로 — % 비노출 (가이드 ④-6)
//
// 좌표 스케일: scale = min(widgetW/imageW, widgetH/imageH) (BoxFit.contain 가정).
//   이미지가 contain 으로 letterbox 되므로 좌우/상하 여백(dx/dy)도 보정한다.
//
// ⚠️ 음식 영역 박스(figma 946:24)는 백엔드 공백 — MealImageAnalysisPreview 에
//    영역 좌표 필드가 없다(플랜 R4). 구현 보류. 백엔드 노출 시 같은 오버레이 재사용.

import 'package:flutter/material.dart';

import '../../features/supplements/supplement_models.dart';
import '../../utils/design_tokens_v2.dart';
import 'confidence_grade_chip.dart';

/// 입력 이미지 픽셀 → 위젯 좌표 변환 결과 (BoxFit.contain 기준).
@immutable
class DetectionOverlayTransform {
  /// 변환 파라미터를 만든다.
  const DetectionOverlayTransform({
    required this.scale,
    required this.dx,
    required this.dy,
  });

  /// 이미지 픽셀에 곱할 스케일.
  final double scale;

  /// letterbox 좌측 여백 (위젯 좌표).
  final double dx;

  /// letterbox 상단 여백 (위젯 좌표).
  final double dy;

  /// 입력 이미지([imageWidth]×[imageHeight])를 [widgetSize] 안에 contain 으로
  /// 맞출 때의 스케일·여백을 계산한다.
  ///
  /// 이미지·위젯 크기가 0 이하이면 스케일 0(아무것도 그리지 않음)을 돌려준다.
  factory DetectionOverlayTransform.contain({
    required int imageWidth,
    required int imageHeight,
    required Size widgetSize,
  }) {
    if (imageWidth <= 0 ||
        imageHeight <= 0 ||
        widgetSize.width <= 0 ||
        widgetSize.height <= 0) {
      return const DetectionOverlayTransform(scale: 0, dx: 0, dy: 0);
    }
    final double scale = (widgetSize.width / imageWidth)
        .clamp(0.0, double.infinity)
        .toDouble();
    final double scaleY = widgetSize.height / imageHeight;
    final double fit = scale < scaleY ? scale : scaleY;
    final double renderedW = imageWidth * fit;
    final double renderedH = imageHeight * fit;
    return DetectionOverlayTransform(
      scale: fit,
      dx: (widgetSize.width - renderedW) / 2,
      dy: (widgetSize.height - renderedH) / 2,
    );
  }

  /// 이미지 픽셀 사각형을 위젯 좌표 사각형으로 변환한다.
  Rect mapRegion(SupplementDetectedProductRegion region) {
    return Rect.fromLTWH(
      dx + region.x * scale,
      dy + region.y * scale,
      region.width * scale,
      region.height * scale,
    );
  }
}

/// 영역 목록에서 입력 이미지 픽셀 바운드(width/height)를 추정한다.
///
/// 백엔드가 원본 이미지 크기를 따로 주지 않으므로, 영역들의 우/하단 최대 좌표로
/// 캔버스 크기를 잡는다(여백 [padding] 비율만큼 키워 박스가 가장자리에 붙지 않게).
/// 영역이 없으면 (0, 0) 을 돌려준다.
({int width, int height}) inferImageBoundsFromRegions(
  List<SupplementDetectedProductRegion> regions, {
  double padding = 0.06,
}) {
  if (regions.isEmpty) return (width: 0, height: 0);
  int maxRight = 0;
  int maxBottom = 0;
  for (final SupplementDetectedProductRegion region in regions) {
    final int right = region.x + region.width;
    final int bottom = region.y + region.height;
    if (right > maxRight) maxRight = right;
    if (bottom > maxBottom) maxBottom = bottom;
  }
  final int paddedW = (maxRight * (1 + padding)).ceil();
  final int paddedH = (maxBottom * (1 + padding)).ceil();
  return (width: paddedW, height: paddedH);
}

/// 검출 박스 오버레이 위젯.
///
/// [imageWidth]/[imageHeight] 는 백엔드가 좌표를 잡은 입력 이미지 픽셀 크기.
/// 영역이 없으면 빈 위젯을 그린다.
class DetectionOverlay extends StatelessWidget {
  /// 검출 오버레이를 만든다.
  const DetectionOverlay({
    super.key,
    required this.regions,
    required this.imageWidth,
    required this.imageHeight,
  });

  /// 백엔드 검출 영역 목록.
  final List<SupplementDetectedProductRegion> regions;

  /// 입력 이미지 너비(px).
  final int imageWidth;

  /// 입력 이미지 높이(px).
  final int imageHeight;

  @override
  Widget build(BuildContext context) {
    if (regions.isEmpty) return const SizedBox.shrink();
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final Size size = constraints.biggest;
        final DetectionOverlayTransform transform =
            DetectionOverlayTransform.contain(
              imageWidth: imageWidth,
              imageHeight: imageHeight,
              widgetSize: size,
            );
        if (transform.scale <= 0) return const SizedBox.shrink();
        return Stack(
          children: <Widget>[
            // 박스 라인.
            Positioned.fill(
              child: CustomPaint(
                painter: _DetectionBoxPainter(
                  regions: regions,
                  transform: transform,
                ),
              ),
            ),
            // 등급 칩 라벨 (선택 영역만, 좌상단에 배치).
            for (final SupplementDetectedProductRegion region in regions)
              if (region.selected)
                Positioned(
                  left: transform.mapRegion(region).left,
                  top: (transform.mapRegion(region).top - 26)
                      .clamp(0.0, size.height)
                      .toDouble(),
                  child: ConfidenceGradeChip(
                    confidence: region.confidence,
                    compact: true,
                  ),
                ),
          ],
        );
      },
    );
  }
}

class _DetectionBoxPainter extends CustomPainter {
  _DetectionBoxPainter({required this.regions, required this.transform});

  final List<SupplementDetectedProductRegion> regions;
  final DetectionOverlayTransform transform;

  @override
  void paint(Canvas canvas, Size size) {
    for (final SupplementDetectedProductRegion region in regions) {
      final Rect rect = transform.mapRegion(region);
      final RRect rrect = RRect.fromRectAndRadius(
        rect,
        const Radius.circular(AppRadius.sm),
      );
      final Paint paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = region.selected ? 3 : 1.5
        ..color = region.selected
            ? AppColor.brand
            : Colors.white.withValues(alpha: 0.7);
      canvas.drawRRect(rrect, paint);
    }
  }

  @override
  bool shouldRepaint(_DetectionBoxPainter oldDelegate) {
    return oldDelegate.regions != regions ||
        oldDelegate.transform.scale != transform.scale ||
        oldDelegate.transform.dx != transform.dx ||
        oldDelegate.transform.dy != transform.dy;
  }
}

/// 검출 영역 미리보기 카드.
///
/// 결과 화면에서 원본 이미지가 없으므로(저장 안 함) 영역 좌표 기준 비율의
/// 중립 캔버스 위에 박스를 그려 검출 위치를 안내한다. 영역이 없으면 숨긴다.
/// 음식 영역(figma 946:24)은 백엔드 공백 — 영양제 영역에만 노출된다.
class DetectionPreviewCard extends StatelessWidget {
  /// 검출 미리보기 카드를 만든다.
  const DetectionPreviewCard({super.key, required this.regions});

  /// 백엔드 검출 영역 목록.
  final List<SupplementDetectedProductRegion> regions;

  @override
  Widget build(BuildContext context) {
    if (regions.isEmpty) return const SizedBox.shrink();
    final ({int width, int height}) bounds = inferImageBoundsFromRegions(
      regions,
    );
    if (bounds.width <= 0 || bounds.height <= 0) {
      return const SizedBox.shrink();
    }
    final double aspect = bounds.width / bounds.height;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: AppColor.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(
                Icons.crop_free_rounded,
                size: 20,
                color: AppColor.brandDeep,
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: Text(
                  '라벨에서 찾은 영역',
                  style: AppText.body.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.md),
          ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.md),
            child: AspectRatio(
              aspectRatio: aspect.clamp(0.4, 2.5),
              child: Container(
                color: AppColor.ink,
                child: DetectionOverlay(
                  regions: regions,
                  imageWidth: bounds.width,
                  imageHeight: bounds.height,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
