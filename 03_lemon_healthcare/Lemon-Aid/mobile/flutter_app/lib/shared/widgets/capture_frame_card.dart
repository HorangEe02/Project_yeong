import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../theme/lemon_theme.dart';

class CaptureFrameCard extends StatelessWidget {
  const CaptureFrameCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.accentColor,
    required this.selectedImageName,
    required this.isSelecting,
    required this.onPick,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final Color accentColor;
  final String? selectedImageName;
  final bool isSelecting;
  final ValueChanged<ImageSource> onPick;

  @override
  Widget build(BuildContext context) {
    return LemonCard(
      color: LemonColors.ink,
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(icon, color: accentColor),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: LemonColors.paper,
                      ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: const Color(0xFFEDE7D5),
                ),
          ),
          const SizedBox(height: 14),
          AspectRatio(
            aspectRatio: 1.58,
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: const Color(0xFF2B2414),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0x66FFFDF6)),
              ),
              child: Stack(
                children: <Widget>[
                  const Center(
                    child: Icon(
                      Icons.center_focus_strong_rounded,
                      color: Color(0x99FFFDF6),
                      size: 42,
                    ),
                  ),
                  if (selectedImageName != null)
                    Center(
                      child: LemonPill(
                        label: selectedImageName!,
                        color: LemonColors.sky,
                        backgroundColor: LemonColors.skySoft,
                      ),
                    ),
                  const _GuideCorner(alignment: Alignment.topLeft),
                  const _GuideCorner(alignment: Alignment.topRight),
                  const _GuideCorner(alignment: Alignment.bottomLeft),
                  const _GuideCorner(alignment: Alignment.bottomRight),
                ],
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: <Widget>[
              Expanded(
                child: FilledButton.icon(
                  onPressed:
                      isSelecting ? null : () => onPick(ImageSource.camera),
                  icon: isSelecting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.photo_camera_rounded),
                  label: Text(isSelecting ? '여는 중' : '촬영'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed:
                      isSelecting ? null : () => onPick(ImageSource.gallery),
                  icon: const Icon(Icons.photo_library_rounded),
                  label: const Text('앨범'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _GuideCorner extends StatelessWidget {
  const _GuideCorner({required this.alignment});

  final Alignment alignment;

  @override
  Widget build(BuildContext context) {
    const BorderSide side = BorderSide(color: LemonColors.lemon, width: 3);
    final bool top = alignment.y < 0;
    final bool left = alignment.x < 0;

    return Align(
      alignment: alignment,
      child: Container(
        width: 34,
        height: 34,
        margin: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          border: Border(
            top: top ? side : BorderSide.none,
            bottom: top ? BorderSide.none : side,
            left: left ? side : BorderSide.none,
            right: left ? BorderSide.none : side,
          ),
        ),
      ),
    );
  }
}
