/// 영양제 사진 등록 화면 — 권한 → 카메라/갤러리 → 크롭 → 업로드.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_cropper/image_cropper.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../../../shared/widgets/app_error.dart';
import '../../../../shared/widgets/disclaimer.dart';
import '../providers/supplement_notifier.dart';
import '../widgets/source_selector.dart';
import '../widgets/upload_progress.dart';

class SupplementCaptureScreen extends ConsumerWidget {
  const SupplementCaptureScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Success 시 결과 화면으로 자동 이동. Idle 로 리셋 후 push 해
    // 사용자가 result 에서 뒤로 가면 다시 SourceSelector 가 보이도록.
    ref.listen<SupplementState>(
      supplementNotifierProvider,
      (SupplementState? _, SupplementState next) {
        if (next is SupplementSuccess) {
          ref.read(supplementNotifierProvider.notifier).reset();
          context.pushReplacement('/supplement/result', extra: next.response);
        }
      },
    );

    final SupplementState state = ref.watch(supplementNotifierProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('영양제 등록')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: <Widget>[
              Expanded(child: _body(context, ref, state)),
              const SizedBox(height: 12),
              const MedicalDisclaimer(variant: DisclaimerVariant.supplement),
            ],
          ),
        ),
      ),
    );
  }

  Widget _body(BuildContext context, WidgetRef ref, SupplementState state) {
    switch (state) {
      case SupplementIdle():
        return SourceSelector(
          onCamera: () => _pickAndUpload(context, ref, ImageSource.camera),
          onGallery: () => _pickAndUpload(context, ref, ImageSource.gallery),
        );
      case SupplementUploading(:final double progress):
        return UploadProgress(progress: progress);
      case SupplementError(:final String message):
        return AppError(
          message: message,
          onRetry: () =>
              ref.read(supplementNotifierProvider.notifier).reset(),
        );
      case SupplementSuccess():
        return const SizedBox.shrink();
    }
  }

  Future<void> _pickAndUpload(
    BuildContext context,
    WidgetRef ref,
    ImageSource source,
  ) async {
    final Permission permission =
        source == ImageSource.camera ? Permission.camera : Permission.photos;
    final PermissionStatus status = await permission.request();
    if (!status.isGranted) {
      if (!context.mounted) return;
      await _showPermissionDeniedDialog(context, source);
      return;
    }

    final ImagePicker picker = ImagePicker();
    final XFile? pickedFile = await picker.pickImage(
      source: source,
      maxWidth: 2048,
      imageQuality: 85,
    );
    if (pickedFile == null) return;

    final CroppedFile? cropped = await ImageCropper().cropImage(
      sourcePath: pickedFile.path,
      compressFormat: ImageCompressFormat.jpg,
      compressQuality: 85,
      uiSettings: <PlatformUiSettings>[
        AndroidUiSettings(
          toolbarTitle: '영양제 라벨 영역 조정',
          lockAspectRatio: false,
          aspectRatioPresets: const <CropAspectRatioPreset>[
            CropAspectRatioPreset.square,
            CropAspectRatioPreset.original,
            CropAspectRatioPreset.ratio4x3,
          ],
        ),
        IOSUiSettings(title: '영양제 라벨 영역 조정'),
      ],
    );
    if (cropped == null) return;

    if (!context.mounted) return;
    await ref
        .read(supplementNotifierProvider.notifier)
        .register(cropped.path);
  }

  Future<void> _showPermissionDeniedDialog(
    BuildContext context,
    ImageSource source,
  ) {
    final String what = source == ImageSource.camera ? '카메라' : '사진 보관함';
    return showDialog<void>(
      context: context,
      builder: (BuildContext ctx) => AlertDialog(
        title: Text('$what 권한이 필요합니다'),
        content: Text(
          '$what 사용을 허용하면 영양제 라벨 사진을 등록할 수 있습니다. '
          '설정에서 권한을 변경해주세요.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(ctx);
              openAppSettings();
            },
            child: const Text('설정으로 이동'),
          ),
        ],
      ),
    );
  }
}
