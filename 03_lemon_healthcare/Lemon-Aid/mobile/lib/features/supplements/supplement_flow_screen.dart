import 'dart:io';

import 'package:camera/camera.dart' as camera;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import '../../app_controller.dart';
import '../../core/api/api_error.dart';
import '../../shared/widgets/error_panel.dart';
import '../../utils/device_env.dart';
import 'camera_readiness.dart';
import 'supplement_models.dart';

/// Supplement capture, OCR text review, and registration screen.
class SupplementFlowScreen extends StatefulWidget {
  /// Creates the supplement flow screen.
  const SupplementFlowScreen({
    required this.controller,
    this.onClose,
    ImagePicker? imagePicker,
    CameraReadinessProbe? cameraReadinessProbe,
    super.key,
  }) : _imagePicker = imagePicker,
       _cameraReadinessProbe = cameraReadinessProbe;

  /// App flow controller.
  final AppController controller;

  /// Called when the fullscreen capture flow should return to the dashboard.
  final VoidCallback? onClose;
  final ImagePicker? _imagePicker;
  final CameraReadinessProbe? _cameraReadinessProbe;

  @override
  State<SupplementFlowScreen> createState() => _SupplementFlowScreenState();
}

class _SupplementFlowScreenState extends State<SupplementFlowScreen> {
  static const double _lowConfidenceThreshold = 0.75;
  static const int _maxSelectedGalleryImages = 6;

  late final ImagePicker _imagePicker;
  late final CameraReadinessProbe _cameraReadinessProbe;
  final TextEditingController _ocrTextController = TextEditingController();
  final TextEditingController _displayNameController = TextEditingController();
  final TextEditingController _manufacturerController = TextEditingController();
  final TextEditingController _servingAmountController =
      TextEditingController();
  final TextEditingController _servingUnitController = TextEditingController();
  final TextEditingController _dailyServingsController =
      TextEditingController();
  final TextEditingController _frequencyController = TextEditingController(
    text: 'daily',
  );
  final TextEditingController _timeOfDayController = TextEditingController();
  final List<_IngredientDraft> _ingredientDrafts = <_IngredientDraft>[];
  String? _seededAnalysisId;
  _SelectedLabelImage? _selectedImage;
  List<_SelectedLabelImage> _selectedImages = const <_SelectedLabelImage>[];
  _SupplementFlowStage _stage = _SupplementFlowStage.idle;
  CameraReadinessSnapshot _cameraReadiness = CameraReadinessSnapshot.probing(
    platform: defaultTargetPlatform,
  );

  @override
  void initState() {
    super.initState();
    _imagePicker = widget._imagePicker ?? ImagePicker();
    _cameraReadinessProbe =
        widget._cameraReadinessProbe ?? const CameraReadinessProbe();
    _refreshCameraReadiness();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _recoverLostImage();
    });
  }

  @override
  void dispose() {
    _ocrTextController.dispose();
    _displayNameController.dispose();
    _manufacturerController.dispose();
    _servingAmountController.dispose();
    _servingUnitController.dispose();
    _dailyServingsController.dispose();
    _frequencyController.dispose();
    _timeOfDayController.dispose();
    for (final _IngredientDraft draft in _ingredientDrafts) {
      draft.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final SupplementAnalysisPreview? preview =
        widget.controller.analysisPreview;
    if (preview != null) {
      _seedFromPreview(preview);
    }

    if (!widget.controller.hasMinimumConsents) {
      return _BlackConsentRequired(
        busy: widget.controller.busy,
        apiError: widget.controller.apiError,
        onGrant: widget.controller.grantMinimumConsents,
        onErrorDismissed: widget.controller.clearMessages,
        onClose: widget.onClose,
      );
    }

    if (preview == null) {
      return _BlackCaptureSurface(
        busy: widget.controller.busy,
        selectedImage: _selectedImage,
        selectedImageCount: _selectedImages.isEmpty
            ? (_selectedImage == null ? 0 : 1)
            : _selectedImages.length,
        stage: _stage,
        cameraReadiness: _cameraReadiness,
        onRefreshCameraReadiness: _refreshCameraReadiness,
        onCamera: _captureLiveImage,
        onGallery: () => _pickImage(ImageSource.gallery),
        onAnalyze: _analyzeSelectedImage,
        onRetake: _resetSelectedImage,
        apiError: widget.controller.apiError,
        onErrorDismissed: widget.controller.clearMessages,
        onClose: widget.onClose,
      );
    }

    return ColoredBox(
      color: const Color(0xFFF4F6F3),
      child: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
          children: <Widget>[
            _ReviewTopBar(onClose: widget.onClose),
            if (widget.controller.apiError != null) ...<Widget>[
              const SizedBox(height: 12),
              ErrorPanel(
                error: widget.controller.apiError!,
                onDismissed: widget.controller.clearMessages,
              ),
            ],
            const SizedBox(height: 16),
            _ProcessingTimeline(
              stage: _stage,
              preview: preview,
              busy: widget.controller.busy,
            ),
            const SizedBox(height: 16),
            _PreviewCard(
              preview: preview,
              requestedOcrProvider:
                  widget.controller.lastRequestedOcrProvider ?? 'configured',
            ),
            const SizedBox(height: 16),
            _OcrTextCard(
              controller: _ocrTextController,
              busy: widget.controller.busy,
              onSubmit: _submitOcrText,
            ),
            const SizedBox(height: 16),
            _RegistrationCard(
              displayNameController: _displayNameController,
              manufacturerController: _manufacturerController,
              servingAmountController: _servingAmountController,
              servingUnitController: _servingUnitController,
              dailyServingsController: _dailyServingsController,
              frequencyController: _frequencyController,
              timeOfDayController: _timeOfDayController,
              ingredientDrafts: _ingredientDrafts,
              preview: preview,
              busy: widget.controller.busy,
              evidenceSpans: preview.evidenceSpans,
              onIngredientSelectionChanged: _setIngredientSelected,
              onAddIngredient: _addManualIngredient,
              onRemoveIngredient: _removeIngredient,
              onRegister: _registerSupplement,
            ),
            if (widget.controller.lastRegisteredSupplement != null) ...<Widget>[
              const SizedBox(height: 16),
              _RegisteredCard(
                response: widget.controller.lastRegisteredSupplement!,
              ),
            ],
            if (widget.controller.supplementImpactPreview != null) ...<Widget>[
              const SizedBox(height: 16),
              _SupplementImpactCard(
                preview: widget.controller.supplementImpactPreview!,
                explanation: widget.controller.supplementExplanation,
                busy: widget.controller.busy,
                onRefresh: widget.controller.refreshSupplementRecommendation,
                onExplain: () =>
                    widget.controller.explainSupplementRecommendation(),
                onExplainWithOllama: () => widget.controller
                    .explainSupplementRecommendation(useLocalLlm: true),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _recoverLostImage() async {
    try {
      final LostDataResponse response = await _imagePicker.retrieveLostData();
      final List<XFile>? files = response.files;
      final List<XFile> recoveredFiles = files != null && files.isNotEmpty
          ? files
          : response.file == null
          ? const <XFile>[]
          : <XFile>[response.file!];
      if (!mounted || recoveredFiles.isEmpty) {
        return;
      }
      _setSelectedImages(
        recoveredFiles
            .take(_maxSelectedGalleryImages)
            .map(
              (XFile file) => _SelectedLabelImage(
                path: file.path,
                source: 'android_lost_data',
                recoveredFromLostData: true,
              ),
            )
            .toList(growable: false),
      );
    } catch (_) {
      // The plugin may be unavailable in widget tests; recovery is best-effort.
    }
  }

  Future<void> _refreshCameraReadiness() async {
    setState(() {
      _cameraReadiness = CameraReadinessSnapshot.probing(
        platform: defaultTargetPlatform,
      );
    });
    final CameraReadinessSnapshot snapshot = await _cameraReadinessProbe
        .check();
    if (!mounted) {
      return;
    }
    setState(() {
      _cameraReadiness = snapshot;
    });
  }

  Future<void> _pickImage(ImageSource source) async {
    if (source == ImageSource.gallery) {
      await _pickGalleryImages();
      return;
    }
    XFile? image;
    try {
      image = await _imagePicker.pickImage(
        source: source,
        maxWidth: 2400,
        imageQuality: 95,
        requestFullMetadata: true,
      );
    } catch (_) {
      if (mounted) {
        _showSnackBar(
          source == ImageSource.camera
              ? '시뮬레이터에서는 실제 카메라를 사용할 수 없어요. 갤러리 사진으로 테스트해주세요.'
              : '사진을 불러오지 못했어요. 다른 이미지로 다시 시도해주세요.',
        );
      }
      return;
    }
    if (image == null) return;
    final XFile selectedImage = image;
    _setSelectedImage(
      path: selectedImage.path,
      source: source == ImageSource.camera ? 'camera' : 'gallery',
    );
  }

  Future<void> _pickGalleryImages() async {
    List<XFile> images;
    try {
      images = await _imagePicker.pickMultiImage(
        maxWidth: 2400,
        imageQuality: 95,
        limit: _maxSelectedGalleryImages,
        requestFullMetadata: false,
      );
    } catch (_) {
      if (mounted) {
        _showSnackBar('사진을 불러오지 못했어요. 다른 이미지로 다시 시도해주세요.');
      }
      return;
    }
    if (images.isEmpty) return;
    _setSelectedImages(
      images
          .take(_maxSelectedGalleryImages)
          .map(
            (XFile image) => _SelectedLabelImage(
              path: image.path,
              source: 'gallery',
              recoveredFromLostData: false,
            ),
          )
          .toList(growable: false),
    );
  }

  Future<void> _captureLiveImage() async {
    if (!_cameraReadiness.canOpenCamera) {
      _showSnackBar(_cameraReadiness.guidance);
      return;
    }
    String? imagePath;
    try {
      imagePath = await Navigator.of(context).push<String>(
        MaterialPageRoute<String>(
          fullscreenDialog: true,
          builder: (BuildContext context) {
            return const _LiveCameraCaptureScreen();
          },
        ),
      );
    } on camera.CameraException catch (error) {
      setState(() {
        _cameraReadiness = CameraReadinessSnapshot.fromError(
          platform: defaultTargetPlatform,
          error: error,
        );
      });
      _showSnackBar(_cameraErrorMessage(error.code));
      return;
    }
    if (imagePath == null || !mounted) {
      return;
    }
    _setSelectedImage(path: imagePath, source: 'camera');
  }

  void _setSelectedImage({required String path, required String source}) {
    _setSelectedImages(<_SelectedLabelImage>[
      _SelectedLabelImage(
        path: path,
        source: source,
        recoveredFromLostData: false,
      ),
    ]);
  }

  void _setSelectedImages(List<_SelectedLabelImage> images) {
    if (images.isEmpty) return;
    setState(() {
      _selectedImages = images;
      _selectedImage = images.first;
      _stage = _SupplementFlowStage.imageSelected;
      _seededAnalysisId = null;
    });
    widget.controller.clearSupplementFlow();
  }

  String _cameraErrorMessage(String code) {
    return switch (code) {
      'CameraAccessDenied' ||
      'CameraAccessDeniedWithoutPrompt' ||
      'CameraAccessRestricted' => '카메라 권한을 허용해야 라벨을 직접 촬영할 수 있어요.',
      'NoCameraAvailable' =>
        '이 실행 환경에서는 카메라를 찾을 수 없어요. 실제 기기에서 촬영하거나 갤러리를 사용해주세요.',
      _ => '카메라를 열지 못했어요. 실제 기기 권한과 연결 상태를 확인해주세요.',
    };
  }

  void _resetSelectedImage() {
    widget.controller.clearSupplementFlow();
    setState(() {
      _selectedImage = null;
      _selectedImages = const <_SelectedLabelImage>[];
      _stage = _SupplementFlowStage.idle;
      _seededAnalysisId = null;
    });
  }

  Future<void> _analyzeSelectedImage() async {
    final _SelectedLabelImage? image = _selectedImage;
    final List<_SelectedLabelImage> images = _selectedImages.isEmpty
        ? (image == null
              ? const <_SelectedLabelImage>[]
              : <_SelectedLabelImage>[image])
        : _selectedImages;
    if (images.isEmpty) {
      _showSnackBar('Select a label image before analysis.');
      return;
    }
    setState(() {
      _stage = _SupplementFlowStage.uploading;
    });
    HapticFeedback.mediumImpact();
    await Future<void>.delayed(Duration.zero);
    if (!mounted) {
      return;
    }
    setState(() {
      _stage = _SupplementFlowStage.ocrProcessing;
    });
    if (images.length > 1) {
      await widget.controller.analyzeImages(
        images
            .map((item) => SupplementImageUpload(path: item.path))
            .toList(growable: false),
      );
    } else {
      await widget.controller.analyzeImage(images.first.path);
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _stage = widget.controller.analysisPreview == null
          ? _SupplementFlowStage.imageSelected
          : _SupplementFlowStage.confirmationRequired;
    });
  }

  Future<void> _submitOcrText() async {
    final String ocrText = _ocrTextController.text.trim();
    if (ocrText.isEmpty) {
      _showSnackBar('Enter OCR text before parsing.');
      return;
    }
    setState(() {
      _stage = _SupplementFlowStage.structuring;
    });
    await widget.controller.parseOcrText(ocrText);
    if (!mounted) {
      return;
    }
    setState(() {
      _stage = widget.controller.analysisPreview == null
          ? _SupplementFlowStage.imageSelected
          : _SupplementFlowStage.confirmationRequired;
    });
  }

  Future<void> _registerSupplement() async {
    final String displayName = _displayNameController.text.trim();
    if (displayName.isEmpty) {
      _showSnackBar('Display name is required.');
      return;
    }
    final SupplementAnalysisPreview? preview =
        widget.controller.analysisPreview;
    if (preview?.blocksRegistrationForImageRisk ?? false) {
      _showSnackBar('Resolve the image review action before registration.');
      return;
    }
    if (preview?.promptsImageRiskConfirmation ?? false) {
      final bool continueRegistration = await _confirmImageRiskSelection(
        preview!,
      );
      if (!continueRegistration) {
        return;
      }
    }

    final List<_IngredientDraft> selectedDrafts = _ingredientDrafts
        .where((_IngredientDraft draft) => draft.selected)
        .toList(growable: false);
    if (selectedDrafts.any((_IngredientDraft draft) => draft.requiresReview)) {
      final bool continueRegistration = await _confirmLowConfidenceSelection();
      if (!continueRegistration) {
        return;
      }
    }

    final List<UserSupplementIngredientInput> ingredients = selectedDrafts
        .map(_ingredientFromDraft)
        .whereType<UserSupplementIngredientInput>()
        .toList(growable: false);
    if (ingredients.isEmpty) {
      _showSnackBar('At least one ingredient is required.');
      return;
    }

    final UserSupplementCreate request = UserSupplementCreate(
      analysisId: preview?.analysisId,
      displayName: displayName,
      manufacturer: _emptyToNull(_manufacturerController.text),
      ingredients: ingredients,
      serving: SupplementServing(
        amount: _parseOptionalDouble(_servingAmountController.text),
        unit: _emptyToNull(_servingUnitController.text),
        dailyServings: _parseOptionalDouble(_dailyServingsController.text) ?? 1,
      ),
      intakeSchedule: SupplementIntakeSchedule(
        frequency: _frequencyController.text.trim().isEmpty
            ? 'daily'
            : _frequencyController.text.trim(),
        timeOfDay: _splitCsv(_timeOfDayController.text),
      ),
    );

    setState(() {
      _stage = _SupplementFlowStage.registering;
    });
    await widget.controller.registerSupplement(
      request,
      refreshImpact: true,
      explainWithLocalLlm: true,
    );
    if (widget.controller.lastRegisteredSupplement == null) {
      if (!mounted) {
        return;
      }
      setState(() {
        _stage = _SupplementFlowStage.confirmationRequired;
      });
      return;
    }
    _ocrTextController.clear();
    _seededAnalysisId = null;
    if (!mounted) {
      return;
    }
    setState(() {
      _stage = _SupplementFlowStage.registered;
      _selectedImage = null;
    });
    setState(() {
      _stage = widget.controller.supplementImpactPreview == null
          ? _SupplementFlowStage.registered
          : _SupplementFlowStage.impactReady;
    });
  }

  UserSupplementIngredientInput? _ingredientFromDraft(_IngredientDraft draft) {
    if (!draft.selected) {
      return null;
    }
    final String displayName = draft.displayNameController.text.trim();
    if (displayName.isEmpty) {
      return null;
    }

    return UserSupplementIngredientInput(
      displayName: displayName,
      originalName: draft.originalName,
      nutrientCode: _emptyToNull(draft.nutrientCodeController.text),
      amount: _parseOptionalDouble(draft.amountController.text),
      unit: _emptyToNull(draft.unitController.text),
      confidence: draft.confidence,
      source: draft.source,
      dailyValuePercent: draft.dailyValuePercent,
    );
  }

  void _seedFromPreview(SupplementAnalysisPreview preview) {
    if (_seededAnalysisId == preview.analysisId) {
      return;
    }
    _seededAnalysisId = preview.analysisId;
    _displayNameController.text = preview.parsedProduct.productName ?? '';
    _manufacturerController.text = preview.parsedProduct.manufacturer ?? '';
    _servingUnitController.text = preview.parsedProduct.servingSize ?? '';
    final double? previewDailyServings =
        preview.parsedProduct.dailyServings ??
        preview.intakeMethod.structured.timesPerDay;
    _dailyServingsController.text = previewDailyServings?.toString() ?? '1';
    if (preview.intakeMethod.structured.frequency != 'unknown') {
      _frequencyController.text = preview.intakeMethod.structured.frequency;
    }
    _timeOfDayController.text = preview.intakeMethod.structured.timeOfDay.join(
      ', ',
    );

    for (final _IngredientDraft draft in _ingredientDrafts) {
      draft.dispose();
    }
    _ingredientDrafts
      ..clear()
      ..addAll(
        preview.ingredientCandidates.isEmpty
            ? <_IngredientDraft>[_IngredientDraft.manual()]
            : <_IngredientDraft>[
                for (final MapEntry<int, SupplementIngredientCandidate> entry
                    in preview.ingredientCandidates
                        .take(5)
                        .toList(growable: false)
                        .asMap()
                        .entries)
                  _IngredientDraft.fromCandidate(
                    entry.value,
                    requiresReview: _candidateRequiresReview(
                      preview,
                      entry.key,
                    ),
                  ),
              ],
      );
  }

  void _addManualIngredient() {
    setState(() {
      _ingredientDrafts.add(_IngredientDraft.manual());
    });
  }

  void _removeIngredient(_IngredientDraft draft) {
    setState(() {
      _ingredientDrafts.remove(draft);
      draft.dispose();
    });
  }

  void _setIngredientSelected(_IngredientDraft draft, bool selected) {
    setState(() {
      draft.selected = selected;
    });
  }

  bool _candidateRequiresReview(SupplementAnalysisPreview preview, int index) {
    final SupplementIngredientCandidate candidate =
        preview.ingredientCandidates[index];
    if (candidate.confidence < _lowConfidenceThreshold) {
      return true;
    }
    return preview.lowConfidenceFields.any((String field) {
      return field == 'ingredients' ||
          field == 'ingredient_candidates' ||
          field == 'ingredients.$index' ||
          field == 'ingredient_candidates.$index' ||
          field.startsWith('ingredients.$index.') ||
          field.startsWith('ingredient_candidates.$index.');
    });
  }

  Future<bool> _confirmLowConfidenceSelection() async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('확인 필요 항목 포함'),
          content: const Text(
            '선택한 성분 중 확인 필요로 표시된 값이 있습니다. 라벨을 직접 확인한 뒤 저장하세요.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('확인 후 저장'),
            ),
          ],
        );
      },
    );
    return confirmed == true;
  }

  Future<bool> _confirmImageRiskSelection(
    SupplementAnalysisPreview preview,
  ) async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('Image review required'),
          content: Text(
            '${preview.imageActionLabel}. Confirm the label directly before saving.',
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Confirmed'),
            ),
          ],
        );
      },
    );
    return confirmed == true;
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}

class _BlackConsentRequired extends StatelessWidget {
  const _BlackConsentRequired({
    required this.busy,
    required this.apiError,
    required this.onGrant,
    required this.onErrorDismissed,
    required this.onClose,
  });

  final bool busy;
  final ApiError? apiError;
  final VoidCallback onGrant;
  final VoidCallback onErrorDismissed;
  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Colors.black,
      child: SafeArea(
        child: Column(
          children: <Widget>[
            _CaptureTopBar(title: '영양제 촬영', onClose: onClose),
            if (apiError != null)
              ErrorPanel(error: apiError!, onDismissed: onErrorDismissed),
            const Spacer(),
            const Icon(
              Icons.verified_user_outlined,
              color: Color(0xFFFFC400),
              size: 56,
            ),
            const SizedBox(height: 18),
            const Text(
              '동의가 필요해요',
              style: TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 10),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 44),
              child: Text(
                'OCR 이미지 처리와 건강 분석 동의 후 영양제 라벨을 분석할 수 있어요.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Color(0xFFC8C8C8),
                  fontSize: 15,
                  height: 1.35,
                ),
              ),
            ),
            const Spacer(),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: busy ? null : onGrant,
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFFFFC400),
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(vertical: 18),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
                  ),
                  icon: busy
                      ? const SizedBox.square(
                          dimension: 18,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.black,
                          ),
                        )
                      : const Icon(Icons.verified_user_outlined),
                  label: const Text(
                    '동의하고 계속',
                    style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BlackCaptureSurface extends StatelessWidget {
  const _BlackCaptureSurface({
    required this.busy,
    required this.selectedImage,
    required this.selectedImageCount,
    required this.stage,
    required this.cameraReadiness,
    required this.onRefreshCameraReadiness,
    required this.onCamera,
    required this.onGallery,
    required this.onAnalyze,
    required this.onRetake,
    required this.apiError,
    required this.onErrorDismissed,
    required this.onClose,
  });

  final bool busy;
  final _SelectedLabelImage? selectedImage;
  final int selectedImageCount;
  final _SupplementFlowStage stage;
  final CameraReadinessSnapshot cameraReadiness;
  final VoidCallback onRefreshCameraReadiness;
  final VoidCallback onCamera;
  final VoidCallback onGallery;
  final VoidCallback onAnalyze;
  final VoidCallback onRetake;
  final ApiError? apiError;
  final VoidCallback onErrorDismissed;
  final VoidCallback? onClose;

  bool get _processing {
    return stage == _SupplementFlowStage.uploading ||
        stage == _SupplementFlowStage.ocrProcessing ||
        stage == _SupplementFlowStage.structuring;
  }

  @override
  Widget build(BuildContext context) {
    final _SelectedLabelImage? image = selectedImage;
    return ColoredBox(
      color: Colors.black,
      child: SafeArea(
        child: Column(
          children: <Widget>[
            _CaptureTopBar(
              title: image == null ? '영양제 촬영' : '미리보기',
              closeIcon: image == null
                  ? Icons.close_rounded
                  : Icons.arrow_back_rounded,
              onClose: image == null ? onClose : onRetake,
            ),
            if (apiError != null)
              ErrorPanel(error: apiError!, onDismissed: onErrorDismissed),
            const SizedBox(height: 16),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: image == null
                    ? _CameraEnvironmentFrame(
                        readiness: cameraReadiness,
                        onRefresh: onRefreshCameraReadiness,
                      )
                    : SupplementLabelPreviewFrame(imagePath: image.path),
              ),
            ),
            if (_processing) ...<Widget>[
              const SizedBox(height: 14),
              const _CaptureStatusPill(
                icon: Icons.manage_search_rounded,
                label: 'OCR 분석 중이에요',
              ),
            ],
            const SizedBox(height: 18),
            if (image == null)
              _CaptureControls(
                busy: busy,
                canOpenCamera: cameraReadiness.canOpenCamera,
                preferGalleryFallback: cameraReadiness.preferGalleryFallback,
                onCamera: onCamera,
                onGallery: onGallery,
              )
            else
              _PreviewControls(
                busy: busy,
                source: image.source,
                imageCount: selectedImageCount,
                recoveredFromLostData: image.recoveredFromLostData,
                onRetake: onRetake,
                onAnalyze: onAnalyze,
              ),
            const SizedBox(height: 18),
          ],
        ),
      ),
    );
  }
}

class _CaptureTopBar extends StatelessWidget {
  const _CaptureTopBar({
    required this.title,
    required this.onClose,
    this.closeIcon = Icons.close_rounded,
  });

  final String title;
  final VoidCallback? onClose;
  final IconData closeIcon;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
      child: Row(
        children: <Widget>[
          _RoundCaptureIcon(icon: closeIcon, onTap: onClose),
          const Spacer(),
          Text(
            title,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
          const Spacer(),
          const SizedBox(width: 52, height: 52),
        ],
      ),
    );
  }
}

class _LiveCameraCaptureScreen extends StatefulWidget {
  const _LiveCameraCaptureScreen();

  @override
  State<_LiveCameraCaptureScreen> createState() =>
      _LiveCameraCaptureScreenState();
}

class _LiveCameraCaptureScreenState extends State<_LiveCameraCaptureScreen>
    with WidgetsBindingObserver {
  camera.CameraController? _controller;
  List<camera.CameraDescription> _cameras = const <camera.CameraDescription>[];
  int _cameraIndex = 0;
  bool _initializing = true;
  bool _initializingController = false;
  bool _takingPicture = false;
  bool _isEmulator = DeviceEnv.isEmulatorSync;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _warmDeviceEnv();
    _initializeCamera();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _disposeController();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final camera.CameraController? controller = _controller;
    if (controller == null || !controller.value.isInitialized) {
      return;
    }
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      _disposeController();
    } else if (state == AppLifecycleState.resumed) {
      _initializeSelectedCamera();
    }
  }

  @override
  Widget build(BuildContext context) {
    final camera.CameraController? controller = _controller;
    final bool previewReady =
        controller != null && controller.value.isInitialized;

    return ColoredBox(
      color: Colors.black,
      child: SafeArea(
        child: Column(
          children: <Widget>[
            _CaptureTopBar(
              title: '라벨 직접 촬영',
              closeIcon: Icons.close_rounded,
              onClose: () => Navigator.of(context).pop(),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: previewReady
                    ? _LiveCameraPreview(
                        controller: controller,
                        isEmulator: _isEmulator,
                      )
                    : _CameraUnavailableFrame(
                        initializing: _initializing,
                        message: _errorMessage,
                      ),
              ),
            ),
            const SizedBox(height: 14),
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 20),
              child: _CaptureStatusPill(
                icon: Icons.center_focus_strong_rounded,
                label: '영양제 라벨 전체가 노란 가이드 안에 들어오게 맞춰주세요',
              ),
            ),
            const SizedBox(height: 18),
            _LiveCameraControls(
              busy: _initializing || _takingPicture,
              canCapture: previewReady,
              canSwitch: _cameras.length > 1,
              onCapture: _takePicture,
              onSwitchCamera: _switchCamera,
            ),
            const SizedBox(height: 18),
          ],
        ),
      ),
    );
  }

  Future<void> _warmDeviceEnv() async {
    final bool isEmulator = await DeviceEnv.isEmulator;
    if (!mounted) {
      return;
    }
    setState(() {
      _isEmulator = isEmulator;
    });
  }

  Future<void> _initializeCamera() async {
    if (_initializingController) {
      return;
    }
    setState(() {
      _initializing = true;
      _errorMessage = null;
    });
    try {
      final List<camera.CameraDescription> cameras = await camera
          .availableCameras();
      if (cameras.isEmpty) {
        throw camera.CameraException(
          'NoCameraAvailable',
          'No camera was reported by the current device.',
        );
      }
      _cameras = cameras;
      _cameraIndex = _preferredCameraIndex(cameras);
      await _initializeSelectedCamera();
    } on camera.CameraException catch (error) {
      if (!mounted) return;
      setState(() {
        _initializing = false;
        _errorMessage = _cameraErrorMessage(error.code);
      });
    }
  }

  Future<void> _initializeSelectedCamera() async {
    if (_initializingController) {
      return;
    }
    _initializingController = true;
    await _disposeController();
    if (_cameras.isEmpty) {
      _initializingController = false;
      return;
    }
    setState(() {
      _initializing = true;
      _errorMessage = null;
    });
    final camera.CameraController controller = camera.CameraController(
      _cameras[_cameraIndex],
      camera.ResolutionPreset.high,
      enableAudio: false,
      imageFormatGroup: camera.ImageFormatGroup.jpeg,
    );
    _controller = controller;
    try {
      await controller.initialize();
      if (!mounted) return;
      setState(() {
        _initializing = false;
      });
    } on camera.CameraException catch (error) {
      await controller.dispose();
      if (!mounted) return;
      setState(() {
        _controller = null;
        _initializing = false;
        _errorMessage = _cameraErrorMessage(error.code);
      });
    } finally {
      _initializingController = false;
    }
  }

  Future<void> _takePicture() async {
    final camera.CameraController? controller = _controller;
    if (controller == null ||
        !controller.value.isInitialized ||
        _takingPicture) {
      return;
    }
    setState(() {
      _takingPicture = true;
    });
    try {
      final camera.XFile image = await controller.takePicture();
      if (!mounted) return;
      Navigator.of(context).pop(image.path);
    } on camera.CameraException catch (error) {
      if (!mounted) return;
      setState(() {
        _takingPicture = false;
        _errorMessage = _cameraErrorMessage(error.code);
      });
    }
  }

  Future<void> _switchCamera() async {
    if (_cameras.length < 2 || _initializing || _takingPicture) {
      return;
    }
    _cameraIndex = (_cameraIndex + 1) % _cameras.length;
    await _initializeSelectedCamera();
  }

  int _preferredCameraIndex(List<camera.CameraDescription> cameras) {
    final int backCameraIndex = cameras.indexWhere(
      (camera.CameraDescription description) =>
          description.lensDirection == camera.CameraLensDirection.back,
    );
    return backCameraIndex < 0 ? 0 : backCameraIndex;
  }

  Future<void> _disposeController() async {
    final camera.CameraController? controller = _controller;
    _controller = null;
    await controller?.dispose();
  }

  String _cameraErrorMessage(String code) {
    return switch (code) {
      'CameraAccessDenied' ||
      'CameraAccessDeniedWithoutPrompt' ||
      'CameraAccessRestricted' => '카메라 권한을 허용해야 직접 촬영할 수 있어요.',
      'NoCameraAvailable' =>
        '이 실행 환경에서는 카메라를 찾을 수 없어요. 실제 기기에서 촬영하거나 갤러리를 사용해주세요.',
      _ => '카메라를 열지 못했어요. 실제 기기 권한과 연결 상태를 확인해주세요.',
    };
  }
}

class _LiveCameraPreview extends StatelessWidget {
  const _LiveCameraPreview({
    required this.controller,
    required this.isEmulator,
  });

  final camera.CameraController controller;
  final bool isEmulator;

  @override
  Widget build(BuildContext context) {
    final Widget preview = FittedBox(
      fit: BoxFit.cover,
      child: SizedBox(
        width: controller.value.previewSize?.height ?? 1,
        height: controller.value.previewSize?.width ?? 1,
        child: camera.CameraPreview(controller),
      ),
    );
    return ClipRRect(
      borderRadius: BorderRadius.circular(28),
      child: Stack(
        fit: StackFit.expand,
        children: <Widget>[
          if (isEmulator)
            Transform.translate(offset: const Offset(0, 8), child: preview)
          else
            preview,
          DecoratedBox(
            decoration: BoxDecoration(
              border: Border.all(color: const Color(0xFF2B2B2B), width: 1.4),
              borderRadius: BorderRadius.circular(28),
            ),
          ),
          const _GuideCorners(),
        ],
      ),
    );
  }
}

class _CameraUnavailableFrame extends StatelessWidget {
  const _CameraUnavailableFrame({
    required this.initializing,
    required this.message,
  });

  final bool initializing;
  final String? message;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: <Widget>[
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              border: Border.all(color: const Color(0xFF2B2B2B), width: 1.4),
              borderRadius: BorderRadius.circular(28),
            ),
            child: Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    if (initializing)
                      const CircularProgressIndicator(color: Color(0xFFFFC400))
                    else
                      const Icon(
                        Icons.no_photography_outlined,
                        color: Color(0xFF777777),
                        size: 56,
                      ),
                    const SizedBox(height: 14),
                    Text(
                      initializing
                          ? '카메라를 준비하고 있어요'
                          : message ?? '카메라를 사용할 수 없어요.',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Color(0xFFC8C8C8),
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        const _GuideCorners(),
      ],
    );
  }
}

class _LiveCameraControls extends StatelessWidget {
  const _LiveCameraControls({
    required this.busy,
    required this.canCapture,
    required this.canSwitch,
    required this.onCapture,
    required this.onSwitchCamera,
  });

  final bool busy;
  final bool canCapture;
  final bool canSwitch;
  final VoidCallback onCapture;
  final VoidCallback onSwitchCamera;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: <Widget>[
          _SquareCaptureButton(
            icon: Icons.cameraswitch_rounded,
            tooltip: '카메라 전환',
            onPressed: !busy && canSwitch ? onSwitchCamera : null,
          ),
          const Spacer(),
          _ShutterButton(onPressed: !busy && canCapture ? onCapture : null),
          const Spacer(),
          const SizedBox(width: 64, height: 64),
        ],
      ),
    );
  }
}

class _RoundCaptureIcon extends StatelessWidget {
  const _RoundCaptureIcon({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 52,
      height: 52,
      child: IconButton(
        tooltip: '닫기',
        onPressed: onTap,
        style: IconButton.styleFrom(
          backgroundColor: Colors.white.withValues(alpha: 0.10),
          foregroundColor: Colors.white,
        ),
        icon: Icon(icon, size: 26),
      ),
    );
  }
}

class _CameraEnvironmentFrame extends StatelessWidget {
  const _CameraEnvironmentFrame({
    required this.readiness,
    required this.onRefresh,
  });

  final CameraReadinessSnapshot readiness;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final bool ready = readiness.kind == CameraReadinessKind.ready;
    final bool checking = readiness.kind == CameraReadinessKind.probing;
    return Stack(
      children: <Widget>[
        Positioned.fill(
          child: DecoratedBox(
            decoration: BoxDecoration(
              border: Border.all(color: const Color(0xFF2B2B2B), width: 1.4),
              borderRadius: BorderRadius.circular(28),
            ),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  if (checking)
                    const SizedBox.square(
                      dimension: 56,
                      child: CircularProgressIndicator(
                        color: Color(0xFFFFC400),
                      ),
                    )
                  else
                    Icon(
                      ready
                          ? Icons.camera_alt_rounded
                          : Icons.photo_library_outlined,
                      color: ready
                          ? const Color(0xFFFFC400)
                          : const Color(0xFF777777),
                      size: 58,
                    ),
                  const SizedBox(height: 14),
                  Text(
                    readiness.title,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 10),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 30),
                    child: Text(
                      readiness.guidance,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Color(0xFFC8C8C8),
                        fontSize: 14,
                        height: 1.35,
                      ),
                    ),
                  ),
                  if (!ready) ...<Widget>[
                    const SizedBox(height: 14),
                    TextButton.icon(
                      onPressed: checking ? null : onRefresh,
                      style: TextButton.styleFrom(
                        foregroundColor: const Color(0xFFFFC400),
                      ),
                      icon: const Icon(Icons.refresh_rounded),
                      label: const Text('카메라 다시 확인'),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
        const _GuideCorners(),
        const Positioned(
          left: 28,
          right: 28,
          bottom: 28,
          child: _CaptureStatusPill(
            icon: Icons.photo_library_outlined,
            label: '갤러리와 직접 촬영 모두 같은 OCR endpoint로 분석돼요',
          ),
        ),
      ],
    );
  }
}

/// OCR label preview frame that preserves the full selected image.
class SupplementLabelPreviewFrame extends StatelessWidget {
  /// Creates a preview frame for a selected label image.
  ///
  /// Args:
  ///   imagePath: Local image path returned by `ImagePicker`.
  const SupplementLabelPreviewFrame({required this.imagePath, super.key});

  /// Local selected image path.
  final String imagePath;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(28),
      child: ColoredBox(
        color: Colors.white,
        child: InteractiveViewer(
          maxScale: 4,
          child: Center(
            child: Image.file(
              File(imagePath),
              fit: BoxFit.contain,
              width: double.infinity,
              height: double.infinity,
            ),
          ),
        ),
      ),
    );
  }
}

class _GuideCorners extends StatelessWidget {
  const _GuideCorners();

  @override
  Widget build(BuildContext context) {
    const double size = 48;
    const double inset = 24;
    const Color color = Color(0xFFFFC400);
    return Stack(
      children: const <Widget>[
        Positioned(
          left: inset,
          top: inset,
          child: _GuideCorner(size: size, color: color),
        ),
        Positioned(
          right: inset,
          top: inset,
          child: RotatedBox(
            quarterTurns: 1,
            child: _GuideCorner(size: size, color: color),
          ),
        ),
        Positioned(
          right: inset,
          bottom: inset,
          child: RotatedBox(
            quarterTurns: 2,
            child: _GuideCorner(size: size, color: color),
          ),
        ),
        Positioned(
          left: inset,
          bottom: inset,
          child: RotatedBox(
            quarterTurns: 3,
            child: _GuideCorner(size: size, color: color),
          ),
        ),
      ],
    );
  }
}

class _GuideCorner extends StatelessWidget {
  const _GuideCorner({required this.size, required this.color});

  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border(
            left: BorderSide(color: color, width: 5),
            top: BorderSide(color: color, width: 5),
          ),
        ),
      ),
    );
  }
}

class _CaptureStatusPill extends StatelessWidget {
  const _CaptureStatusPill({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.72),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: Colors.white.withValues(alpha: 0.10)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: <Widget>[
          Icon(icon, color: Colors.white, size: 20),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              label,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 15,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _CaptureControls extends StatelessWidget {
  const _CaptureControls({
    required this.busy,
    required this.canOpenCamera,
    required this.preferGalleryFallback,
    required this.onCamera,
    required this.onGallery,
  });

  final bool busy;
  final bool canOpenCamera;
  final bool preferGalleryFallback;
  final VoidCallback onCamera;
  final VoidCallback onGallery;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        children: <Widget>[
          _SquareCaptureButton(
            icon: Icons.photo_library_outlined,
            onPressed: busy ? null : onGallery,
          ),
          const Spacer(),
          _ShutterButton(onPressed: busy || !canOpenCamera ? null : onCamera),
          const Spacer(),
          SizedBox(
            width: 64,
            height: 64,
            child: preferGalleryFallback
                ? IconButton(
                    tooltip: '카메라 연결 재확인 필요',
                    onPressed: null,
                    icon: const Icon(Icons.info_outline_rounded),
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }
}

class _PreviewControls extends StatelessWidget {
  const _PreviewControls({
    required this.busy,
    required this.source,
    required this.imageCount,
    required this.recoveredFromLostData,
    required this.onRetake,
    required this.onAnalyze,
  });

  final bool busy;
  final String source;
  final int imageCount;
  final bool recoveredFromLostData;
  final VoidCallback onRetake;
  final VoidCallback onAnalyze;

  @override
  Widget build(BuildContext context) {
    final String sourceLabel = recoveredFromLostData
        ? '복구된 사진'
        : source == 'camera'
        ? '카메라 사진'
        : imageCount > 1
        ? '갤러리 사진 $imageCount장'
        : '갤러리 사진';
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: <Widget>[
          Text(
            '$sourceLabel 선택됨',
            style: const TextStyle(color: Color(0xFFC8C8C8), fontSize: 13),
          ),
          const SizedBox(height: 12),
          Row(
            children: <Widget>[
              Expanded(
                child: _DarkActionButton(
                  icon: Icons.refresh_rounded,
                  label: '다시 선택',
                  onPressed: busy ? null : onRetake,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: _YellowActionButton(
                  label: imageCount > 1 ? '$imageCount장 분석하기' : '분석하기',
                  onPressed: busy ? null : onAnalyze,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SquareCaptureButton extends StatelessWidget {
  const _SquareCaptureButton({
    required this.icon,
    required this.onPressed,
    this.tooltip = '갤러리',
  });

  final IconData icon;
  final VoidCallback? onPressed;
  final String tooltip;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 64,
      height: 64,
      child: IconButton(
        tooltip: tooltip,
        onPressed: onPressed,
        style: IconButton.styleFrom(
          backgroundColor: const Color(0xFF1B1B1B),
          foregroundColor: Colors.white,
          disabledBackgroundColor: const Color(0xFF141414),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
            side: BorderSide(color: Colors.white.withValues(alpha: 0.10)),
          ),
        ),
        icon: Icon(icon, size: 30),
      ),
    );
  }
}

class _ShutterButton extends StatelessWidget {
  const _ShutterButton({required this.onPressed});

  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 92,
      height: 92,
      child: IconButton(
        tooltip: '촬영',
        onPressed: onPressed,
        style: IconButton.styleFrom(
          backgroundColor: const Color(0xFFFFC400),
          foregroundColor: Colors.black,
          disabledBackgroundColor: const Color(0xFF725E08),
          shape: const CircleBorder(
            side: BorderSide(color: Color(0xFF8E8A76), width: 6),
          ),
        ),
        icon: const Icon(Icons.camera_alt_rounded, size: 32),
      ),
    );
  }
}

class _DarkActionButton extends StatelessWidget {
  const _DarkActionButton({
    required this.icon,
    required this.label,
    required this.onPressed,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return FilledButton.icon(
      onPressed: onPressed,
      style: FilledButton.styleFrom(
        backgroundColor: const Color(0xFF1B1B1B),
        foregroundColor: Colors.white,
        disabledBackgroundColor: const Color(0xFF141414),
        padding: const EdgeInsets.symmetric(vertical: 18),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
      icon: Icon(icon),
      label: Text(label),
    );
  }
}

class _YellowActionButton extends StatelessWidget {
  const _YellowActionButton({required this.label, required this.onPressed});

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: onPressed,
      style: FilledButton.styleFrom(
        backgroundColor: const Color(0xFFFFC400),
        foregroundColor: Colors.black,
        disabledBackgroundColor: const Color(0xFF725E08),
        padding: const EdgeInsets.symmetric(vertical: 20),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
      child: Text(
        label,
        style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _ReviewTopBar extends StatelessWidget {
  const _ReviewTopBar({required this.onClose});

  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        IconButton(
          tooltip: '닫기',
          onPressed: onClose,
          icon: const Icon(Icons.close_rounded),
        ),
        const Expanded(
          child: Text(
            '영양제 분석',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
          ),
        ),
        const SizedBox(width: 48, height: 48),
      ],
    );
  }
}

class _ProcessingTimeline extends StatelessWidget {
  const _ProcessingTimeline({
    required this.stage,
    required this.preview,
    required this.busy,
  });

  final _SupplementFlowStage stage;
  final SupplementAnalysisPreview? preview;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final List<_TimelineStep> steps = <_TimelineStep>[
      _TimelineStep('Upload', _SupplementFlowStage.uploading),
      _TimelineStep('OCR', _SupplementFlowStage.ocrProcessing),
      _TimelineStep('Section', _SupplementFlowStage.sectionClassifying),
      _TimelineStep('Structure', _SupplementFlowStage.structuring),
      _TimelineStep('Confirm', _SupplementFlowStage.confirmationRequired),
    ];
    final int activeIndex = _stageIndex(stage);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Analysis progress',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                for (int index = 0; index < steps.length; index += 1)
                  _TimelineChip(
                    label: steps[index].label,
                    completed:
                        index < activeIndex ||
                        stage == _SupplementFlowStage.impactReady,
                    active: index == activeIndex && busy,
                    reviewNeeded: _stepNeedsReview(steps[index].stage),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  int _stageIndex(_SupplementFlowStage value) {
    return switch (value) {
      _SupplementFlowStage.idle => -1,
      _SupplementFlowStage.imageSelected => -1,
      _SupplementFlowStage.uploading => 0,
      _SupplementFlowStage.ocrProcessing => 1,
      _SupplementFlowStage.sectionClassifying => 2,
      _SupplementFlowStage.structuring => 3,
      _SupplementFlowStage.confirmationRequired => 4,
      _SupplementFlowStage.registering => 4,
      _SupplementFlowStage.registered => 4,
      _SupplementFlowStage.impactReady => 4,
    };
  }

  bool _stepNeedsReview(_SupplementFlowStage step) {
    final SupplementAnalysisPreview? currentPreview = preview;
    if (currentPreview == null) {
      return false;
    }
    if (step == _SupplementFlowStage.sectionClassifying) {
      return !currentPreview.layoutAvailable ||
          currentPreview.labelSections.any(
            (SupplementPreviewLabelSection section) => section.requiresReview,
          );
    }
    if (step == _SupplementFlowStage.structuring) {
      return currentPreview.lowConfidenceFields.isNotEmpty;
    }
    return false;
  }
}

class _TimelineStep {
  const _TimelineStep(this.label, this.stage);

  final String label;
  final _SupplementFlowStage stage;
}

class _TimelineChip extends StatelessWidget {
  const _TimelineChip({
    required this.label,
    required this.completed,
    required this.active,
    required this.reviewNeeded,
  });

  final String label;
  final bool completed;
  final bool active;
  final bool reviewNeeded;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final Color color = reviewNeeded
        ? colors.errorContainer
        : completed
        ? colors.primaryContainer
        : colors.surfaceContainerHighest;
    return Chip(
      avatar: active
          ? const SizedBox.square(
              dimension: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : Icon(
              reviewNeeded
                  ? Icons.report_problem_outlined
                  : completed
                  ? Icons.check_circle_outline
                  : Icons.radio_button_unchecked,
              size: 18,
            ),
      backgroundColor: color,
      label: Text(reviewNeeded ? '$label: review' : label),
    );
  }
}

class _PreviewCard extends StatelessWidget {
  const _PreviewCard({
    required this.preview,
    required this.requestedOcrProvider,
  });

  final SupplementAnalysisPreview preview;
  final String requestedOcrProvider;

  @override
  Widget build(BuildContext context) {
    final String? ocrNotice = _ocrNoticeText(
      preview,
      requestedOcrProvider: requestedOcrProvider,
    );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('Preview', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('Status: ${preview.status}'),
            Text('Ingredients: ${preview.ingredientCandidates.length}'),
            Text('Sections: ${preview.labelSections.length}'),
            const SizedBox(height: 10),
            _AiPipelineStatus(
              metadata: preview.pipelineMetadata,
              requestedOcrProvider: requestedOcrProvider,
            ),
            if (ocrNotice != null) ...<Widget>[
              const SizedBox(height: 8),
              _LocalOcrNotice(message: ocrNotice),
            ],
            if (!preview.layoutAvailable)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: _ReviewBadge(
                  icon: Icons.view_agenda_outlined,
                  label: 'Section layout needs review',
                ),
              ),
            if (preview.requiresImageAction) ...<Widget>[
              const SizedBox(height: 8),
              _ImageRiskActionPanel(preview: preview),
            ],
            Text('Expires: ${preview.expiresAt.toLocal()}'),
            if (preview.warnings.isNotEmpty) ...<Widget>[
              const SizedBox(height: 8),
              for (final String warning in preview.warnings)
                Text('Warning: $warning'),
            ],
          ],
        ),
      ),
    );
  }
}

class _AiPipelineStatus extends StatelessWidget {
  const _AiPipelineStatus({
    required this.metadata,
    required this.requestedOcrProvider,
  });

  final SupplementImagePipelineMetadata metadata;
  final String requestedOcrProvider;

  @override
  Widget build(BuildContext context) {
    final String actualProvider = metadata.ocrProvider ?? 'none';
    final bool hasBackendText = metadata.ocrTextPresent;
    final bool parserHasReviewData =
        metadata.sectionCount > 0 || hasBackendText;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: <Widget>[
        _PipelineChip(
          icon: Icons.text_snippet_outlined,
          label: 'OCR ${_formatProviderLabel(requestedOcrProvider)}',
          value: hasBackendText
              ? _formatProviderLabel(actualProvider)
              : 'no text',
          active: hasBackendText,
        ),
        _PipelineChip(
          icon: Icons.center_focus_strong_outlined,
          label: 'YOLO ROI',
          value: metadata.visionRoiUsed ? '${metadata.roiCount} roi' : 'off',
          active: metadata.visionRoiUsed,
        ),
        _PipelineChip(
          icon: Icons.psychology_alt_outlined,
          label: 'Parser',
          value: metadata.llmParserUsed
              ? (parserHasReviewData ? 'used' : 'empty')
              : 'pending',
          active: metadata.llmParserUsed,
        ),
        _PipelineChip(
          icon: Icons.lock_outline,
          label: 'Retention',
          value: metadata.rawImageStored || metadata.rawOcrTextStored
              ? 'review'
              : 'clean',
          active: !metadata.rawImageStored && !metadata.rawOcrTextStored,
        ),
      ],
    );
  }
}

class _PipelineChip extends StatelessWidget {
  const _PipelineChip({
    required this.icon,
    required this.label,
    required this.value,
    required this.active,
  });

  final IconData icon;
  final String label;
  final String value;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Chip(
      avatar: Icon(
        icon,
        size: 16,
        color: active ? colors.primary : colors.onSurfaceVariant,
      ),
      backgroundColor: active
          ? colors.primaryContainer.withValues(alpha: 0.72)
          : colors.surfaceContainerHighest,
      label: Text(
        '$label: $value',
        style: const TextStyle(fontWeight: FontWeight.w700),
      ),
    );
  }
}

String _formatProviderLabel(String value) {
  return switch (value) {
    'configured' => 'Auto',
    'paddleocr' || 'paddleocr_local' => 'Paddle',
    'google_vision' || 'google_vision_document' => 'Vision',
    'clova' || 'clova_ocr' => 'CLOVA',
    'ollama_vision_assist' => 'Ollama Vision',
    'intake-only' => 'Intake',
    'none' => 'None',
    _ => value,
  };
}

String? _ocrNoticeText(
  SupplementAnalysisPreview preview, {
  required String requestedOcrProvider,
}) {
  if (preview.ingredientCandidates.isNotEmpty) {
    return null;
  }
  final String actualProvider = preview.pipelineMetadata.ocrProvider ?? 'none';
  final bool providerProducedText =
      actualProvider != 'none' && actualProvider != 'intake-only';
  if (!providerProducedText) {
    final String providerLabel = _formatProviderLabel(requestedOcrProvider);
    if (requestedOcrProvider == 'configured') {
      return '자동 OCR이 실행 결과 없이 intake-only로 돌아왔어요. 백엔드 OCR env, provider 권한, API base URL을 확인해주세요.';
    }
    return '$providerLabel OCR 요청은 백엔드에 도달했지만 자동 추출 결과가 없어요. provider 권한과 키 설정을 확인하거나 더 선명한 라벨 사진으로 다시 시도해주세요.';
  }
  if (!preview.pipelineMetadata.llmParserUsed) {
    final String providerLabel = _formatProviderLabel(actualProvider);
    return '$providerLabel OCR은 실행됐지만 성분 파서가 결과를 만들지 못했어요. Ollama/parser 상태를 확인하거나 성분을 직접 입력해주세요.';
  }
  final String warningText = preview.warnings.join(' ').toLowerCase();
  if (warningText.contains('automatic text extraction') ||
      warningText.contains('paddleocr') ||
      warningText.contains('ocr provider') ||
      warningText.contains('readable text')) {
    return 'OCR과 파서는 실행됐지만 성분 후보가 비어 있어요. 이미지 해상도, 라벨 구도, 도메인 파싱 규칙을 확인해주세요.';
  }
  return '사진은 업로드됐지만 성분 후보가 비어 있어요. 더 선명한 라벨 사진을 선택하거나 성분을 직접 입력해주세요.';
}

class _LocalOcrNotice extends StatelessWidget {
  const _LocalOcrNotice({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: colors.errorContainer.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: colors.error.withValues(alpha: 0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.error_outline, color: colors.error, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                color: colors.onErrorContainer,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ImageRiskActionPanel extends StatelessWidget {
  const _ImageRiskActionPanel({required this.preview});

  final SupplementAnalysisPreview preview;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    final bool blocksRegistration = preview.blocksRegistrationForImageRisk;
    final Color backgroundColor = blocksRegistration
        ? colors.errorContainer
        : colors.tertiaryContainer;
    final Color foregroundColor = blocksRegistration
        ? colors.onErrorContainer
        : colors.onTertiaryContainer;
    final List<String> reasons =
        preview.imageQualityReport?.issues
            .map((SupplementImageQualityIssue issue) => issue.reasonCode)
            .take(3)
            .toList(growable: false) ??
        const <String>[];
    return DecoratedBox(
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: DefaultTextStyle.merge(
          style: TextStyle(color: foregroundColor),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(
                    blocksRegistration
                        ? Icons.block_outlined
                        : Icons.camera_alt_outlined,
                    color: foregroundColor,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      preview.imageActionLabel,
                      style: Theme.of(
                        context,
                      ).textTheme.labelLarge?.copyWith(color: foregroundColor),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Text('Scope: ${preview.analysisScope}'),
              Text('Image role: ${preview.imageRole}'),
              if (preview.missingRequiredSections.isNotEmpty)
                Text('Missing: ${preview.missingRequiredSections.join(', ')}'),
              if (preview.detectedProductRegions.isNotEmpty)
                Text('Regions: ${preview.detectedProductRegions.length}'),
              if (reasons.isNotEmpty) Text('Reasons: ${reasons.join(', ')}'),
              if (preview.identityConflict != null)
                Text(preview.identityConflict!.message),
            ],
          ),
        ),
      ),
    );
  }
}

class _OcrTextCard extends StatelessWidget {
  const _OcrTextCard({
    required this.controller,
    required this.busy,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final bool busy;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(
              'OCR text review',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            TextField(
              controller: controller,
              minLines: 4,
              maxLines: 8,
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                hintText: 'Paste or edit OCR text from the supplement label.',
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: busy ? null : onSubmit,
              icon: const Icon(Icons.text_fields),
              label: const Text('Parse OCR text'),
            ),
          ],
        ),
      ),
    );
  }
}

class _RegistrationCard extends StatelessWidget {
  const _RegistrationCard({
    required this.displayNameController,
    required this.manufacturerController,
    required this.servingAmountController,
    required this.servingUnitController,
    required this.dailyServingsController,
    required this.frequencyController,
    required this.timeOfDayController,
    required this.ingredientDrafts,
    required this.preview,
    required this.evidenceSpans,
    required this.busy,
    required this.onIngredientSelectionChanged,
    required this.onAddIngredient,
    required this.onRemoveIngredient,
    required this.onRegister,
  });

  final TextEditingController displayNameController;
  final TextEditingController manufacturerController;
  final TextEditingController servingAmountController;
  final TextEditingController servingUnitController;
  final TextEditingController dailyServingsController;
  final TextEditingController frequencyController;
  final TextEditingController timeOfDayController;
  final List<_IngredientDraft> ingredientDrafts;
  final SupplementAnalysisPreview preview;
  final List<SupplementPreviewEvidenceSpan> evidenceSpans;
  final bool busy;
  final void Function(_IngredientDraft draft, bool selected)
  onIngredientSelectionChanged;
  final VoidCallback onAddIngredient;
  final void Function(_IngredientDraft draft) onRemoveIngredient;
  final VoidCallback onRegister;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(
              'Confirm supplement',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: displayNameController,
              decoration: const InputDecoration(
                labelText: 'Display name',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: manufacturerController,
              decoration: const InputDecoration(
                labelText: 'Manufacturer',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            Text('Ingredients', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            for (final _IngredientDraft draft in ingredientDrafts)
              _IngredientDraftTile(
                draft: draft,
                evidenceSpans: evidenceSpans,
                onSelectionChanged: (bool selected) =>
                    onIngredientSelectionChanged(draft, selected),
                onRemove: ingredientDrafts.length == 1
                    ? null
                    : () => onRemoveIngredient(draft),
              ),
            OutlinedButton.icon(
              onPressed: onAddIngredient,
              icon: const Icon(Icons.add),
              label: const Text('Add ingredient'),
            ),
            const SizedBox(height: 16),
            Text('Serving', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            Row(
              children: <Widget>[
                Expanded(
                  child: TextField(
                    controller: servingAmountController,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Amount',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: servingUnitController,
                    decoration: const InputDecoration(
                      labelText: 'Unit',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextField(
              controller: dailyServingsController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Daily servings',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: frequencyController,
              decoration: const InputDecoration(
                labelText: 'Frequency',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              controller: timeOfDayController,
              decoration: const InputDecoration(
                labelText: 'Time of day, comma-separated',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            _SectionReview(preview: preview, evidenceSpans: evidenceSpans),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: busy ? null : onRegister,
              icon: const Icon(Icons.save_outlined),
              label: const Text('Register confirmed supplement'),
            ),
          ],
        ),
      ),
    );
  }
}

class _IngredientDraftTile extends StatelessWidget {
  const _IngredientDraftTile({
    required this.draft,
    required this.evidenceSpans,
    required this.onSelectionChanged,
    required this.onRemove,
  });

  final _IngredientDraft draft;
  final List<SupplementPreviewEvidenceSpan> evidenceSpans;
  final ValueChanged<bool> onSelectionChanged;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border.all(color: Theme.of(context).colorScheme.outline),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                value: draft.selected,
                onChanged: (bool? value) => onSelectionChanged(value ?? false),
                title: Text(
                  draft.requiresReview
                      ? 'Ingredient candidate - review needed'
                      : 'Ingredient candidate',
                ),
                subtitle: Text(
                  'Confidence: ${_formatConfidence(draft.confidence)}',
                ),
                controlAffinity: ListTileControlAffinity.leading,
              ),
              if (draft.requiresReview)
                const Padding(
                  padding: EdgeInsets.only(bottom: 8),
                  child: _ReviewBadge(
                    icon: Icons.report_problem_outlined,
                    label: '확인 필요',
                  ),
                ),
              TextField(
                controller: draft.displayNameController,
                decoration: InputDecoration(
                  labelText: 'Ingredient',
                  border: const OutlineInputBorder(),
                  suffixIcon: onRemove == null
                      ? null
                      : IconButton(
                          tooltip: 'Remove ingredient',
                          onPressed: onRemove,
                          icon: const Icon(Icons.delete_outline),
                        ),
                ),
              ),
              if (draft.originalName != null &&
                  draft.originalName!.trim().isNotEmpty &&
                  draft.originalName!.trim().toLowerCase() !=
                      draft.displayNameController.text.trim().toLowerCase())
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      '원문: ${draft.originalName}',
                      style: const TextStyle(
                        color: Color(0xFF777777),
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0,
                      ),
                    ),
                  ),
                ),
              const SizedBox(height: 8),
              Row(
                children: <Widget>[
                  Expanded(
                    child: TextField(
                      controller: draft.amountController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Amount',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: draft.unitController,
                      decoration: const InputDecoration(
                        labelText: 'Unit',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextField(
                controller: draft.nutrientCodeController,
                decoration: const InputDecoration(
                  labelText: 'Nutrient code',
                  border: OutlineInputBorder(),
                ),
              ),
              if (draft.evidenceRefs.isNotEmpty) ...<Widget>[
                const SizedBox(height: 8),
                TextButton.icon(
                  onPressed: () => _showEvidenceDialog(
                    context,
                    evidenceSpans,
                    draft.evidenceRefs,
                  ),
                  icon: const Icon(Icons.article_outlined),
                  label: const Text('Evidence'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionReview extends StatelessWidget {
  const _SectionReview({required this.preview, required this.evidenceSpans});

  final SupplementAnalysisPreview preview;
  final List<SupplementPreviewEvidenceSpan> evidenceSpans;

  @override
  Widget build(BuildContext context) {
    return ExpansionPanelList.radio(
      children: <ExpansionPanelRadio>[
        ExpansionPanelRadio(
          value: 'sections',
          headerBuilder: (BuildContext context, bool isExpanded) {
            return const ListTile(title: Text('Label sections'));
          },
          body: _LabelSectionList(
            sections: preview.labelSections,
            evidenceSpans: evidenceSpans,
          ),
        ),
        ExpansionPanelRadio(
          value: 'intake',
          headerBuilder: (BuildContext context, bool isExpanded) {
            return const ListTile(title: Text('Intake method'));
          },
          body: _IntakeMethodPanel(
            intakeMethod: preview.intakeMethod,
            evidenceSpans: evidenceSpans,
          ),
        ),
        ExpansionPanelRadio(
          value: 'precautions',
          headerBuilder: (BuildContext context, bool isExpanded) {
            return const ListTile(title: Text('Precautions'));
          },
          body: _ReadOnlyRowsPanel(
            emptyText: 'No label precautions found.',
            rows: <_ReviewRow>[
              for (final SupplementPreviewPrecaution item
                  in preview.precautions)
                _ReviewRow(
                  title: item.category,
                  body: item.text,
                  requiresReview: item.requiresReview,
                  evidenceRefs: item.evidenceRefs,
                ),
            ],
            evidenceSpans: evidenceSpans,
          ),
        ),
        ExpansionPanelRadio(
          value: 'claims',
          headerBuilder: (BuildContext context, bool isExpanded) {
            return const ListTile(title: Text('Functional claims'));
          },
          body: _ReadOnlyRowsPanel(
            emptyText: 'No label functional claims found.',
            rows: <_ReviewRow>[
              for (final SupplementPreviewFunctionalClaim item
                  in preview.functionalClaims)
                _ReviewRow(
                  title: item.claimType,
                  body: item.text,
                  requiresReview: item.requiresReview,
                  evidenceRefs: item.evidenceRefs,
                ),
            ],
            evidenceSpans: evidenceSpans,
          ),
        ),
      ],
    );
  }
}

class _LabelSectionList extends StatelessWidget {
  const _LabelSectionList({
    required this.sections,
    required this.evidenceSpans,
  });

  final List<SupplementPreviewLabelSection> sections;
  final List<SupplementPreviewEvidenceSpan> evidenceSpans;

  @override
  Widget build(BuildContext context) {
    if (sections.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('No structured sections found. Review fields manually.'),
      );
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          for (final SupplementPreviewLabelSection section in sections)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: <Widget>[
                      Text(
                        section.headingText ?? section.sectionType,
                        style: Theme.of(context).textTheme.labelLarge,
                      ),
                      if (section.requiresReview)
                        const _ReviewBadge(
                          icon: Icons.report_problem_outlined,
                          label: '확인 필요',
                        ),
                    ],
                  ),
                  if (section.textBundle != null) ...<Widget>[
                    const SizedBox(height: 4),
                    Text(section.textBundle!),
                  ],
                  if (section.evidenceRefs.isNotEmpty)
                    TextButton.icon(
                      onPressed: () => _showEvidenceDialog(
                        context,
                        evidenceSpans,
                        section.evidenceRefs,
                      ),
                      icon: const Icon(Icons.article_outlined),
                      label: const Text('Evidence'),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _IntakeMethodPanel extends StatelessWidget {
  const _IntakeMethodPanel({
    required this.intakeMethod,
    required this.evidenceSpans,
  });

  final SupplementPreviewIntakeMethod intakeMethod;
  final List<SupplementPreviewEvidenceSpan> evidenceSpans;

  @override
  Widget build(BuildContext context) {
    final SupplementPreviewStructuredIntakeMethod structured =
        intakeMethod.structured;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (intakeMethod.requiresReview)
            const Padding(
              padding: EdgeInsets.only(bottom: 8),
              child: _ReviewBadge(
                icon: Icons.report_problem_outlined,
                label: '확인 필요',
              ),
            ),
          Text(intakeMethod.text ?? 'No intake method text found.'),
          const SizedBox(height: 8),
          Text('Frequency: ${structured.frequency}'),
          Text('Times per day: ${structured.timesPerDay ?? '-'}'),
          Text(
            'Amount per time: ${structured.amountPerTime ?? '-'} ${structured.amountUnit ?? ''}',
          ),
          if (intakeMethod.evidenceRefs.isNotEmpty)
            TextButton.icon(
              onPressed: () => _showEvidenceDialog(
                context,
                evidenceSpans,
                intakeMethod.evidenceRefs,
              ),
              icon: const Icon(Icons.article_outlined),
              label: const Text('Evidence'),
            ),
        ],
      ),
    );
  }
}

class _ReadOnlyRowsPanel extends StatelessWidget {
  const _ReadOnlyRowsPanel({
    required this.emptyText,
    required this.rows,
    required this.evidenceSpans,
  });

  final String emptyText;
  final List<_ReviewRow> rows;
  final List<SupplementPreviewEvidenceSpan> evidenceSpans;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) {
      return Padding(padding: const EdgeInsets.all(16), child: Text(emptyText));
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
      child: Column(
        children: <Widget>[
          for (final _ReviewRow row in rows)
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(row.title),
              subtitle: Text(row.body),
              trailing: row.requiresReview
                  ? const Icon(Icons.report_problem_outlined)
                  : null,
              onTap: row.evidenceRefs.isEmpty
                  ? null
                  : () => _showEvidenceDialog(
                      context,
                      evidenceSpans,
                      row.evidenceRefs,
                    ),
            ),
        ],
      ),
    );
  }
}

class _ReviewRow {
  const _ReviewRow({
    required this.title,
    required this.body,
    required this.requiresReview,
    required this.evidenceRefs,
  });

  final String title;
  final String body;
  final bool requiresReview;
  final List<String> evidenceRefs;
}

class _RegisteredCard extends StatelessWidget {
  const _RegisteredCard({required this.response});

  final UserSupplementResponse response;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: const Icon(Icons.check_circle_outline),
        title: Text(response.displayName),
        subtitle: Text('Registered supplement ID: ${response.id}'),
      ),
    );
  }
}

class _SupplementImpactCard extends StatelessWidget {
  const _SupplementImpactCard({
    required this.preview,
    required this.explanation,
    required this.busy,
    required this.onRefresh,
    required this.onExplain,
    required this.onExplainWithOllama,
  });

  final SupplementImpactPreviewResponse preview;
  final SupplementRecommendationExplainResponse? explanation;
  final bool busy;
  final VoidCallback onRefresh;
  final VoidCallback onExplain;
  final VoidCallback onExplainWithOllama;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Text(
              '현재 섭취 정보 기반 점검 결과',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(preview.safeUserMessage),
            const SizedBox(height: 8),
            Text('Status: ${preview.dataStatus}'),
            const SizedBox(height: 12),
            _ImpactBucket(
              title: 'Current supplement contributions',
              emptyText: 'No calculated supplement contributions.',
              children: <Widget>[
                for (final SupplementContributionAggregate item
                    in preview.currentSupplementContributions)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(item.nutrientName ?? item.nutrientCode),
                    subtitle: Text(
                      '${item.totalDailyAmount ?? '-'} ${item.referenceUnit ?? ''} · ${item.contributionCount} item(s)',
                    ),
                  ),
              ],
            ),
            _ImpactBucket(
              title: 'Deficiency overlap candidates',
              emptyText: 'No deficiency overlap candidates.',
              children: <Widget>[
                for (final SupplementNutritionInsight insight
                    in preview.deficiencySupportCandidates)
                  _InsightTile(insight: insight),
              ],
            ),
            _ImpactBucket(
              title: 'Duplicate or excess review',
              emptyText: 'No duplicate or upper-limit review items.',
              children: <Widget>[
                for (final SupplementNutritionInsight insight
                    in preview.excessOrDuplicateRisks)
                  _InsightTile(insight: insight),
              ],
            ),
            if (preview.missingProfileFields.isNotEmpty) ...<Widget>[
              const SizedBox(height: 8),
              Text(
                'Missing profile fields: ${preview.missingProfileFields.join(', ')}',
              ),
            ],
            if (preview.warnings.isNotEmpty) ...<Widget>[
              const SizedBox(height: 8),
              for (final String warning in preview.warnings)
                Text('Warning: $warning'),
            ],
            const SizedBox(height: 12),
            Text(
              preview.clinicalDisclaimer,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (explanation != null) ...<Widget>[
              const Divider(height: 24),
              Align(
                alignment: Alignment.centerLeft,
                child: Chip(
                  avatar: Icon(
                    explanation!.llmUsed
                        ? Icons.psychology_alt_outlined
                        : Icons.rule_outlined,
                    size: 18,
                  ),
                  label: Text(
                    explanation!.llmUsed
                        ? 'Ollama wording used'
                        : 'Deterministic wording used',
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Text(explanation!.safeUserMessage),
              for (final String bullet in explanation!.explanationBullets)
                Text('• $bullet'),
            ],
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                OutlinedButton.icon(
                  onPressed: busy ? null : onRefresh,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh check'),
                ),
                OutlinedButton.icon(
                  onPressed: busy ? null : onExplain,
                  icon: const Icon(Icons.notes_outlined),
                  label: const Text('Explain'),
                ),
                OutlinedButton.icon(
                  onPressed: busy ? null : onExplainWithOllama,
                  icon: const Icon(Icons.psychology_alt_outlined),
                  label: const Text('Ollama'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ImpactBucket extends StatelessWidget {
  const _ImpactBucket({
    required this.title,
    required this.emptyText,
    required this.children,
  });

  final String title;
  final String emptyText;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(title, style: Theme.of(context).textTheme.labelLarge),
          if (children.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(emptyText),
            )
          else
            ...children,
        ],
      ),
    );
  }
}

class _InsightTile extends StatelessWidget {
  const _InsightTile({required this.insight});

  final SupplementNutritionInsight insight;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(
        insight.actionLabel == 'avoid_duplicate'
            ? Icons.content_copy_outlined
            : Icons.info_outline,
      ),
      title: Text(insight.nutrientName ?? insight.nutrientCode),
      subtitle: Text(insight.userMessage),
    );
  }
}

class _IngredientDraft {
  _IngredientDraft({
    required String displayName,
    required String? nutrientCode,
    required this.originalName,
    required double? amount,
    required String? unit,
    required this.confidence,
    required this.source,
    required this.selected,
    required this.requiresReview,
    required this.evidenceRefs,
    this.dailyValuePercent,
  }) : displayNameController = TextEditingController(text: displayName),
       nutrientCodeController = TextEditingController(text: nutrientCode ?? ''),
       amountController = TextEditingController(text: amount?.toString() ?? ''),
       unitController = TextEditingController(text: unit ?? '');

  factory _IngredientDraft.fromCandidate(
    SupplementIngredientCandidate candidate, {
    required bool requiresReview,
  }) {
    return _IngredientDraft(
      displayName: candidate.displayName,
      nutrientCode: candidate.nutrientCode,
      originalName: candidate.originalName,
      amount: candidate.amount,
      unit: candidate.unit,
      confidence: candidate.confidence,
      source: candidate.source == 'user_confirmed'
          ? 'user_confirmed'
          : 'ocr_llm_preview',
      selected: !requiresReview,
      requiresReview: requiresReview,
      evidenceRefs: const <String>[],
      dailyValuePercent: candidate.dailyValuePercent,
    );
  }

  factory _IngredientDraft.manual() {
    return _IngredientDraft(
      displayName: '',
      nutrientCode: null,
      originalName: null,
      amount: null,
      unit: null,
      confidence: 1,
      source: 'user_confirmed',
      selected: true,
      requiresReview: false,
      evidenceRefs: const <String>[],
    );
  }

  final TextEditingController displayNameController;
  final TextEditingController nutrientCodeController;
  final TextEditingController amountController;
  final TextEditingController unitController;
  final String? originalName;
  final double confidence;
  final String source;
  final double? dailyValuePercent;
  bool selected;
  final bool requiresReview;
  final List<String> evidenceRefs;

  void dispose() {
    displayNameController.dispose();
    nutrientCodeController.dispose();
    amountController.dispose();
    unitController.dispose();
  }
}

String? _emptyToNull(String value) {
  final String trimmed = value.trim();
  return trimmed.isEmpty ? null : trimmed;
}

double? _parseOptionalDouble(String value) {
  final String trimmed = value.trim();
  return trimmed.isEmpty ? null : double.tryParse(trimmed);
}

List<String> _splitCsv(String value) {
  return value
      .split(',')
      .map((String item) => item.trim())
      .where((String item) => item.isNotEmpty)
      .toList(growable: false);
}

class _SelectedLabelImage {
  const _SelectedLabelImage({
    required this.path,
    required this.source,
    required this.recoveredFromLostData,
  });

  final String path;
  final String source;
  final bool recoveredFromLostData;
}

enum _SupplementFlowStage {
  idle,
  imageSelected,
  uploading,
  ocrProcessing,
  sectionClassifying,
  structuring,
  confirmationRequired,
  registering,
  registered,
  impactReady,
}

class _ReviewBadge extends StatelessWidget {
  const _ReviewBadge({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(icon, size: 16),
            const SizedBox(width: 4),
            Text(label),
          ],
        ),
      ),
    );
  }
}

String _formatConfidence(double? value) {
  if (value == null) {
    return 'unknown';
  }
  return '${(value * 100).round()}%';
}

void _showEvidenceDialog(
  BuildContext context,
  List<SupplementPreviewEvidenceSpan> spans,
  List<String> refs,
) {
  final List<SupplementPreviewEvidenceSpan> matched = spans
      .where((SupplementPreviewEvidenceSpan span) => refs.contains(span.spanId))
      .toList(growable: false);
  showDialog<void>(
    context: context,
    builder: (BuildContext context) {
      return AlertDialog(
        title: const Text('Evidence'),
        content: matched.isEmpty
            ? const Text('No bounded evidence excerpt is available.')
            : Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  for (final SupplementPreviewEvidenceSpan span in matched)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(span.textExcerpt),
                    ),
                ],
              ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      );
    },
  );
}
