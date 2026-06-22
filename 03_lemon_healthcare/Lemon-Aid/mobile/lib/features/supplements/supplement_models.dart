import '../../shared/models/json_readers.dart';

Map<String, Object?> _readOptionalJsonMap(
  Map<String, dynamic> json,
  String key,
) {
  final Object? value = json[key];
  if (value == null) {
    return const <String, Object?>{};
  }
  if (value is Map<String, dynamic>) {
    return Map<String, Object?>.from(value);
  }
  if (value is Map<Object?, Object?>) {
    return Map<String, Object?>.from(value);
  }
  throw FormatException('Expected optional object field "$key".');
}

Map<String, dynamic>? _jsonMapFromValue(Object? value) {
  if (value == null) return null;
  if (value is Map<String, dynamic>) return value;
  if (value is Map<Object?, Object?>) return Map<String, dynamic>.from(value);
  return null;
}

Map<String, dynamic> _firstJsonMap(Iterable<Object?> values) {
  for (final Object? value in values) {
    final Map<String, dynamic>? map = _jsonMapFromValue(value);
    if (map != null) return map;
  }
  return const <String, dynamic>{};
}

List<Map<String, dynamic>> _jsonMapListFromValue(Object? value) {
  if (value is! List) return const <Map<String, dynamic>>[];
  final List<Map<String, dynamic>> rows = <Map<String, dynamic>>[];
  for (final Object? row in value) {
    final Map<String, dynamic>? map = _jsonMapFromValue(row);
    if (map != null) rows.add(map);
  }
  return rows;
}

List<Map<String, dynamic>> _firstJsonMapList(Iterable<Object?> values) {
  for (final Object? value in values) {
    final List<Map<String, dynamic>> rows = _jsonMapListFromValue(value);
    if (rows.isNotEmpty) return rows;
  }
  return const <Map<String, dynamic>>[];
}

String? _firstNonEmptyString(Map<String, dynamic> json, List<String> keys) {
  for (final String key in keys) {
    final Object? value = json[key];
    if (value is String && value.trim().isNotEmpty) return value.trim();
  }
  return null;
}

double? _optionalDoubleFromAny(Object? value) {
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value.trim());
  return null;
}

String _stableFallbackId(String prefix, int index) => '$prefix-${index + 1}';

Map<String, dynamic>? _normalizeIngredientCandidateRow(
  Map<String, dynamic> row,
) {
  final String? displayName = _firstNonEmptyString(row, const <String>[
    'display_name',
    'name',
    'nutrient_name',
    'ingredient_name',
    'original_name',
  ]);
  if (displayName == null) return null;
  return <String, dynamic>{
    ...row,
    'display_name': displayName,
    'original_name': _firstNonEmptyString(row, const <String>[
      'original_name',
      'visible_name',
      'raw_name',
      'name',
    ]),
    'nutrient_code': _firstNonEmptyString(row, const <String>[
      'nutrient_code',
      'code',
    ]),
    'amount': _optionalDoubleFromAny(row['amount']),
    'unit': _firstNonEmptyString(row, const <String>['unit', 'amount_unit']),
    'confidence': _optionalDoubleFromAny(row['confidence']) ?? 0.55,
    'source':
        _firstNonEmptyString(row, const <String>['source']) ??
        'ocr_structured_fallback',
    'daily_value_percent': _optionalDoubleFromAny(row['daily_value_percent']),
  };
}

List<SupplementIngredientCandidate> _parseIngredientCandidates(
  List<Map<String, dynamic>> rows,
) {
  final List<SupplementIngredientCandidate> out =
      <SupplementIngredientCandidate>[];
  for (final Map<String, dynamic> row in rows) {
    final Map<String, dynamic>? normalized = _normalizeIngredientCandidateRow(
      row,
    );
    if (normalized == null) continue;
    out.add(SupplementIngredientCandidate.fromJson(normalized));
  }
  return out;
}

Map<String, dynamic>? _normalizeLabelSectionRow(
  Map<String, dynamic> row,
  int index,
) {
  final String? textBundle = _firstNonEmptyString(row, const <String>[
    'text_bundle',
    'text',
    'text_excerpt',
    'ocr_text',
  ]);
  final String sectionType =
      _firstNonEmptyString(row, const <String>[
        'section_type',
        'type',
        'label',
      ]) ??
      'unknown';
  if (textBundle == null && sectionType == 'unknown') return null;
  return <String, dynamic>{
    ...row,
    'section_id':
        _firstNonEmptyString(row, const <String>['section_id', 'id']) ??
        _stableFallbackId('section', index),
    'section_type': sectionType,
    'heading_text': _firstNonEmptyString(row, const <String>[
      'heading_text',
      'heading',
      'title',
    ]),
    'text_bundle': textBundle,
    'confidence': _optionalDoubleFromAny(row['confidence']),
    'requires_review': row['requires_review'] == true,
    'evidence_refs': row['evidence_refs'] is List ? row['evidence_refs'] : null,
  };
}

List<SupplementPreviewLabelSection> _parseLabelSections(
  List<Map<String, dynamic>> rows,
) {
  final List<SupplementPreviewLabelSection> out =
      <SupplementPreviewLabelSection>[];
  for (int i = 0; i < rows.length; i++) {
    final Map<String, dynamic>? normalized = _normalizeLabelSectionRow(
      rows[i],
      i,
    );
    if (normalized == null) continue;
    out.add(SupplementPreviewLabelSection.fromJson(normalized));
  }
  return out;
}

Map<String, dynamic>? _normalizeEvidenceSpanRow(
  Map<String, dynamic> row,
  int index,
) {
  final String? textExcerpt = _firstNonEmptyString(row, const <String>[
    'text_excerpt',
    'text_bundle',
    'text',
    'ocr_text',
  ]);
  if (textExcerpt == null) return null;
  return <String, dynamic>{
    ...row,
    'span_id':
        _firstNonEmptyString(row, const <String>['span_id', 'id']) ??
        _stableFallbackId('span', index),
    'source_type':
        _firstNonEmptyString(row, const <String>['source_type', 'source']) ??
        'ocr',
    'section_type':
        _firstNonEmptyString(row, const <String>[
          'section_type',
          'type',
          'label',
        ]) ??
        'unknown',
    'text_excerpt': textExcerpt,
    'page_index': row['page_index'],
    'cell_ref': _firstNonEmptyString(row, const <String>['cell_ref']),
    'confidence': _optionalDoubleFromAny(row['confidence']),
  };
}

List<SupplementPreviewEvidenceSpan> _parseEvidenceSpans(
  List<Map<String, dynamic>> rows,
) {
  final List<SupplementPreviewEvidenceSpan> out =
      <SupplementPreviewEvidenceSpan>[];
  for (int i = 0; i < rows.length; i++) {
    final Map<String, dynamic>? normalized = _normalizeEvidenceSpanRow(
      rows[i],
      i,
    );
    if (normalized == null) continue;
    out.add(SupplementPreviewEvidenceSpan.fromJson(normalized));
  }
  return out;
}

DateTime _parsePreviewExpiresAt(Map<String, dynamic> json) {
  final String? value = _firstNonEmptyString(json, const <String>[
    'expires_at',
  ]);
  if (value == null) return DateTime.now().add(const Duration(hours: 1));
  return DateTime.parse(value);
}

/// One locally selected supplement image and its intended label role.
class SupplementImageUpload {
  /// Creates a local supplement image upload descriptor.
  const SupplementImageUpload({required this.path, this.role = 'unknown'});

  /// Local image path selected by the user.
  final String path;

  /// Client-side image role hint sent to the backend.
  final String role;
}

/// Lightweight backend-created multi-image analysis session.
class SupplementAnalysisSession {
  /// Creates a supplement analysis session descriptor.
  const SupplementAnalysisSession({
    required this.analysisGroupId,
    required this.status,
    required this.imageCount,
    required this.maxImages,
    required this.missingRequiredSections,
    required this.actionRequired,
  });

  /// Backend group id used by subsequent image uploads.
  final String analysisGroupId;

  /// Session lifecycle status.
  final String status;

  /// Number of images currently tied to this session.
  final int imageCount;

  /// Maximum image count accepted by the backend.
  final int maxImages;

  /// Required label sections still expected from the user.
  final List<String> missingRequiredSections;

  /// Next action required before relying on this session.
  final String actionRequired;

  /// Parses a backend-created analysis session response.
  factory SupplementAnalysisSession.fromJson(Map<String, dynamic> json) {
    return SupplementAnalysisSession(
      analysisGroupId: readString(json, 'analysis_group_id'),
      status: readOptionalString(json, 'status') ?? 'created',
      imageCount: readOptionalInt(json, 'image_count') ?? 0,
      maxImages: readOptionalInt(json, 'max_images') ?? 6,
      missingRequiredSections: readOptionalStringList(
        json,
        'missing_required_sections',
      ),
      actionRequired:
          readOptionalString(json, 'action_required') ??
          'additional_label_image_required',
    );
  }
}

/// Review-only food candidate returned from the meal image endpoint.
class MealFoodCandidate {
  /// Creates a meal food candidate.
  const MealFoodCandidate({
    required this.displayName,
    this.portionAmount,
    this.portionUnit,
    this.kcal,
    this.carbG,
    this.proteinG,
    this.fatG,
    this.sodiumMg,
    required this.confidence,
    required this.source,
  });

  /// Candidate food name that must be reviewed by the user.
  final String displayName;

  /// Optional portion amount.
  final double? portionAmount;

  /// Optional portion unit.
  final String? portionUnit;

  /// Optional kcal estimate.
  final double? kcal;

  /// Optional carbohydrate estimate.
  final double? carbG;

  /// Optional protein estimate.
  final double? proteinG;

  /// Optional fat estimate.
  final double? fatG;

  /// Optional sodium estimate.
  final double? sodiumMg;

  /// Detector confidence.
  final double confidence;

  /// Candidate source such as `vision` or `manual`.
  final String source;

  /// Parses a meal food candidate.
  factory MealFoodCandidate.fromJson(Map<String, dynamic> json) {
    return MealFoodCandidate(
      displayName: readString(json, 'display_name'),
      portionAmount: readOptionalDouble(json, 'portion_amount'),
      portionUnit: readOptionalString(json, 'portion_unit'),
      kcal: readOptionalDouble(json, 'kcal'),
      carbG: readOptionalDouble(json, 'carb_g'),
      proteinG: readOptionalDouble(json, 'protein_g'),
      fatG: readOptionalDouble(json, 'fat_g'),
      sodiumMg: readOptionalDouble(json, 'sodium_mg'),
      confidence: readDouble(json, 'confidence'),
      source: readString(json, 'source'),
    );
  }
}

/// Sanitized meal image pipeline metadata for OCR/YOLO/Ollama smoke tests.
class FoodImagePipelineMetadata {
  /// Creates food image pipeline metadata.
  const FoodImagePipelineMetadata({
    required this.intakeCompleted,
    this.detectorModel,
    this.classifierModel,
    required this.detectorUsed,
    required this.classifierUsed,
    required this.rawImageStored,
    required this.rawProviderPayloadStored,
    required this.requiresManualEntry,
  });

  /// Whether upload validation and hashing completed.
  final bool intakeCompleted;

  /// Sanitized detector model label.
  final String? detectorModel;

  /// Sanitized classifier model label.
  final String? classifierModel;

  /// Whether the detector ran.
  final bool detectorUsed;

  /// Whether a classifier ran.
  final bool classifierUsed;

  /// Whether raw image bytes were retained.
  final bool rawImageStored;

  /// Whether provider payloads were retained.
  final bool rawProviderPayloadStored;

  /// Whether the user should manually complete food details.
  final bool requiresManualEntry;

  /// Parses sanitized meal pipeline metadata.
  factory FoodImagePipelineMetadata.fromJson(Map<String, dynamic> json) {
    return FoodImagePipelineMetadata(
      intakeCompleted: json['intake_completed'] != false,
      detectorModel: readOptionalString(json, 'detector_model'),
      classifierModel: readOptionalString(json, 'classifier_model'),
      detectorUsed: json['detector_used'] == true,
      classifierUsed: json['classifier_used'] == true,
      rawImageStored: json['raw_image_stored'] == true,
      rawProviderPayloadStored: json['raw_provider_payload_stored'] == true,
      requiresManualEntry: json['requires_manual_entry'] == true,
    );
  }
}

/// Meal image analysis response before user confirmation.
class MealImageAnalysisPreview {
  /// Creates a meal image analysis preview.
  const MealImageAnalysisPreview({
    required this.analysisId,
    required this.mealId,
    required this.status,
    required this.mealType,
    required this.eatenAt,
    required this.foodCandidates,
    required this.nutritionEstimateSummary,
    required this.warningCodes,
    required this.pipelineMetadata,
    required this.algorithmVersion,
    this.createdAt,
  });

  /// Food image analysis id.
  final String analysisId;

  /// Linked meal preview id.
  final String mealId;

  /// Preview status.
  final String status;

  /// Meal bucket selected by the user.
  final String mealType;

  /// Meal timestamp returned by the backend.
  final DateTime eatenAt;

  /// Review-only detected food candidates.
  final List<MealFoodCandidate> foodCandidates;

  /// Bounded nutrition estimate summary.
  final Map<String, Object?> nutritionEstimateSummary;

  /// Stable warning codes.
  final List<String> warningCodes;

  /// Sanitized pipeline metadata.
  final FoodImagePipelineMetadata pipelineMetadata;

  /// Backend algorithm contract version.
  final String algorithmVersion;

  /// Optional backend creation timestamp.
  final DateTime? createdAt;

  /// Parses a meal image analysis preview.
  factory MealImageAnalysisPreview.fromJson(Map<String, dynamic> json) {
    final String? createdAt = readOptionalString(json, 'created_at');
    return MealImageAnalysisPreview(
      analysisId: readString(json, 'analysis_id'),
      mealId: readString(json, 'meal_id'),
      status: readString(json, 'status'),
      mealType: readString(json, 'meal_type'),
      eatenAt: DateTime.parse(readString(json, 'eaten_at')),
      foodCandidates: readOptionalList(json, 'food_candidates')
          .whereType<Map<String, dynamic>>()
          .map(MealFoodCandidate.fromJson)
          .toList(growable: false),
      nutritionEstimateSummary: _readOptionalJsonMap(
        json,
        'nutrition_estimate_summary',
      ),
      warningCodes: readOptionalStringList(json, 'warning_codes'),
      pipelineMetadata: FoodImagePipelineMetadata.fromJson(
        readObject(json, 'pipeline_metadata'),
      ),
      algorithmVersion: readString(json, 'algorithm_version'),
      createdAt: createdAt == null ? null : DateTime.parse(createdAt),
    );
  }
}

/// User-confirmed meal food item input.
class MealFoodItemInput {
  /// Creates a confirmed meal food item input.
  const MealFoodItemInput({
    required this.displayName,
    this.portionAmount,
    this.portionUnit,
    this.kcal,
    this.carbG,
    this.proteinG,
    this.fatG,
    this.sodiumMg,
    this.confidence,
    this.foodCatalogItemId,
    this.source = 'manual',
  });

  /// Food name confirmed by the user.
  final String displayName;

  /// Portion amount confirmed by the user.
  final double? portionAmount;

  /// Portion unit confirmed by the user.
  final String? portionUnit;

  /// Confirmed kcal value.
  final double? kcal;

  /// Confirmed carbohydrate grams.
  final double? carbG;

  /// Confirmed protein grams.
  final double? proteinG;

  /// Confirmed fat grams.
  final double? fatG;

  /// Confirmed sodium milligrams.
  final double? sodiumMg;

  /// Optional detector confidence retained for traceability.
  final double? confidence;

  /// Curated food catalog item id when picked from the direct-input search.
  final String? foodCatalogItemId;

  /// Confirmed row source.
  final String source;

  /// Creates a confirmation input seeded from backend detector output.
  factory MealFoodItemInput.fromCandidate(MealFoodCandidate candidate) {
    return MealFoodItemInput(
      displayName: candidate.displayName,
      portionAmount: candidate.portionAmount,
      portionUnit: candidate.portionUnit,
      kcal: candidate.kcal,
      carbG: candidate.carbG,
      proteinG: candidate.proteinG,
      fatG: candidate.fatG,
      sodiumMg: candidate.sodiumMg,
      confidence: candidate.confidence,
      source: candidate.source,
    );
  }

  /// Serializes the confirmed item for the backend API.
  Map<String, Object?> toJson() {
    return <String, Object?>{
      'display_name': displayName,
      if (portionAmount != null) 'portion_amount': portionAmount,
      if (portionUnit != null) 'portion_unit': portionUnit,
      if (kcal != null) 'kcal': kcal,
      if (carbG != null) 'carb_g': carbG,
      if (proteinG != null) 'protein_g': proteinG,
      if (fatG != null) 'fat_g': fatG,
      if (sodiumMg != null) 'sodium_mg': sodiumMg,
      if (confidence != null) 'confidence': confidence,
      if (foodCatalogItemId != null) 'food_catalog_item_id': foodCatalogItemId,
      'source': source,
    };
  }
}

/// User-confirmed meal preview registration request.
class MealConfirmationRequest {
  /// Creates a meal confirmation request.
  const MealConfirmationRequest({
    this.analysisId,
    required this.foodItems,
    this.mealType,
    this.eatenAt,
  });

  /// Optional food image analysis preview id.
  final String? analysisId;

  /// User-confirmed food rows.
  final List<MealFoodItemInput> foodItems;

  /// Optional meal bucket override.
  final String? mealType;

  /// Optional meal timestamp override.
  final DateTime? eatenAt;

  /// Serializes the request for the backend API.
  Map<String, Object?> toJson() {
    return <String, Object?>{
      if (analysisId != null) 'analysis_id': analysisId,
      'food_items': foodItems
          .map((MealFoodItemInput item) => item.toJson())
          .toList(growable: false),
      if (mealType != null) 'meal_type': mealType,
      if (eatenAt != null) 'eaten_at': eatenAt!.toUtc().toIso8601String(),
      'user_confirmed': true,
    };
  }
}

/// Persisted user-confirmed meal food item.
class MealFoodItemResponse {
  /// Creates a meal food item response.
  const MealFoodItemResponse({
    required this.id,
    required this.displayName,
    this.portionAmount,
    this.portionUnit,
    this.kcal,
    this.carbG,
    this.proteinG,
    this.fatG,
    this.sodiumMg,
    this.confidence,
    required this.source,
  });

  /// Persisted row id.
  final String id;

  /// User-confirmed food name.
  final String displayName;

  /// User-confirmed portion amount.
  final double? portionAmount;

  /// User-confirmed portion unit.
  final String? portionUnit;

  /// Confirmed kcal value.
  final double? kcal;

  /// Confirmed carbohydrate grams.
  final double? carbG;

  /// Confirmed protein grams.
  final double? proteinG;

  /// Confirmed fat grams.
  final double? fatG;

  /// Confirmed sodium milligrams.
  final double? sodiumMg;

  /// Optional detector confidence retained for traceability.
  final double? confidence;

  /// Confirmed row source.
  final String source;

  /// Parses a backend meal food item response.
  factory MealFoodItemResponse.fromJson(Map<String, dynamic> json) {
    return MealFoodItemResponse(
      id: readString(json, 'id'),
      displayName: readString(json, 'display_name'),
      portionAmount: readOptionalDouble(json, 'portion_amount'),
      portionUnit: readOptionalString(json, 'portion_unit'),
      kcal: readOptionalDouble(json, 'kcal'),
      carbG: readOptionalDouble(json, 'carb_g'),
      proteinG: readOptionalDouble(json, 'protein_g'),
      fatG: readOptionalDouble(json, 'fat_g'),
      sodiumMg: readOptionalDouble(json, 'sodium_mg'),
      confidence: readOptionalDouble(json, 'confidence'),
      source: readString(json, 'source'),
    );
  }
}

/// Persisted user-confirmed meal response.
class MealRecordResponse {
  /// Creates a meal record response.
  const MealRecordResponse({
    required this.id,
    required this.status,
    required this.mealType,
    required this.eatenAt,
    required this.foodItems,
    required this.nutritionSummary,
    required this.confirmedAt,
    required this.createdAt,
  });

  /// Persisted meal id.
  final String id;

  /// Meal lifecycle status.
  final String status;

  /// User-confirmed meal bucket.
  final String mealType;

  /// User-confirmed meal timestamp.
  final DateTime eatenAt;

  /// Confirmed food items.
  final List<MealFoodItemResponse> foodItems;

  /// Bounded confirmed nutrition summary.
  final Map<String, Object?> nutritionSummary;

  /// Confirmation timestamp.
  final DateTime confirmedAt;

  /// Server-side creation timestamp.
  final DateTime createdAt;

  /// Parses a backend meal confirmation response.
  factory MealRecordResponse.fromJson(Map<String, dynamic> json) {
    return MealRecordResponse(
      id: readString(json, 'id'),
      status: readString(json, 'status'),
      mealType: readString(json, 'meal_type'),
      eatenAt: DateTime.parse(readString(json, 'eaten_at')),
      foodItems: readList(json, 'food_items')
          .whereType<Map<String, dynamic>>()
          .map(MealFoodItemResponse.fromJson)
          .toList(growable: false),
      nutritionSummary: _readOptionalJsonMap(json, 'nutrition_summary'),
      confirmedAt: DateTime.parse(readString(json, 'confirmed_at')),
      createdAt: DateTime.parse(readString(json, 'created_at')),
    );
  }
}

/// Multi-image supplement analysis response before user confirmation.
class SupplementMultiImageAnalysisPreview {
  /// Creates a multi-image analysis preview.
  const SupplementMultiImageAnalysisPreview({
    required this.analysisGroupId,
    required this.imageCount,
    required this.previews,
    this.mergedPreview,
    required this.missingRequiredSections,
    required this.actionRequired,
    required this.pipelineMetadata,
    required this.expiresAt,
    this.resultMode = 'single_product',
  });

  /// Ephemeral backend group id for the uploaded batch.
  final String analysisGroupId;

  /// Number of accepted images in the batch.
  final int imageCount;

  /// Per-image analysis previews.
  final List<SupplementAnalysisPreview> previews;

  /// Backend-assembled merged review preview using bounded per-image evidence.
  final SupplementAnalysisPreview? mergedPreview;

  /// Required label sections still missing after aggregating the batch.
  final List<String> missingRequiredSections;

  /// Batch-level next action before relying on the preview.
  final String actionRequired;

  /// Sanitized aggregate OCR, YOLO, and parser metadata.
  final SupplementImagePipelineMetadata pipelineMetadata;

  /// Earliest preview expiration time when provided by the backend.
  final DateTime? expiresAt;

  /// How the batch was analyzed: 'single_product' (one merged preview) or
  /// 'distinct_products' (each preview is its own supplement → one tab each).
  final String resultMode;

  /// Whether each image is a distinct supplement reviewed in a separate tab.
  bool get isDistinctProducts => resultMode == 'distinct_products';

  /// Parses a backend multi-image analysis preview.
  factory SupplementMultiImageAnalysisPreview.fromJson(
    Map<String, dynamic> json,
  ) {
    return SupplementMultiImageAnalysisPreview(
      analysisGroupId: readString(json, 'analysis_group_id'),
      imageCount: readOptionalInt(json, 'image_count') ?? 1,
      previews: readList(json, 'previews')
          .whereType<Map<String, dynamic>>()
          .map(SupplementAnalysisPreview.fromJson)
          .toList(growable: false),
      mergedPreview: readOptionalObject(json, 'merged_preview') == null
          ? null
          : SupplementAnalysisPreview.fromJson(
              readObject(json, 'merged_preview'),
            ),
      missingRequiredSections: readOptionalStringList(
        json,
        'missing_required_sections',
      ),
      actionRequired: readOptionalString(json, 'action_required') ?? 'none',
      pipelineMetadata: readOptionalObject(json, 'pipeline_metadata') == null
          ? SupplementImagePipelineMetadata.intakeOnly
          : SupplementImagePipelineMetadata.fromJson(
              readObject(json, 'pipeline_metadata'),
            ),
      expiresAt: readOptionalString(json, 'expires_at') == null
          ? null
          : DateTime.parse(readString(json, 'expires_at')),
      resultMode: readOptionalString(json, 'result_mode') ?? 'single_product',
    );
  }

  /// First preview that can seed the existing single-preview review flow.
  SupplementAnalysisPreview? get primaryPreview {
    final List<SupplementAnalysisPreview> candidates =
        <SupplementAnalysisPreview>[?mergedPreview, ...previews]
            .where((SupplementAnalysisPreview preview) {
              return preview.hasReviewContent;
            })
            .toList(growable: false);
    if (candidates.isNotEmpty) {
      candidates.sort((
        SupplementAnalysisPreview left,
        SupplementAnalysisPreview right,
      ) {
        return right.reviewContentScore.compareTo(left.reviewContentScore);
      });
      return candidates.first;
    }
    return mergedPreview ?? (previews.isEmpty ? null : previews.first);
  }
}

/// Supplement OCR and parsing preview before user confirmation.
class SupplementAnalysisPreview {
  /// Creates an analysis preview.
  const SupplementAnalysisPreview({
    required this.analysisId,
    required this.status,
    required this.parsedProduct,
    required this.ingredientCandidates,
    this.suggestedCategoryKeys = const <String>[],
    required this.layoutAvailable,
    required this.layoutFallbackReason,
    required this.labelSections,
    required this.intakeMethod,
    required this.precautions,
    required this.functionalClaims,
    required this.evidenceSpans,
    required this.imageQualityReport,
    required this.analysisScope,
    required this.actionRequired,
    required this.detectedProductRegions,
    required this.selectedRegionId,
    required this.missingRequiredSections,
    required this.imageRole,
    required this.multiImageGroupId,
    required this.sourceType,
    required this.identityConflict,
    this.pipelineMetadata = SupplementImagePipelineMetadata.intakeOnly,
    this.rawOcrText,
    required this.lowConfidenceFields,
    required this.warnings,
    required this.algorithmVersion,
    required this.sourceManifestVersion,
    required this.expiresAt,
  });

  /// Temporary analysis identifier.
  final String analysisId;

  /// Preview status, such as `requires_confirmation`.
  final String status;

  /// Product-level parsed fields.
  final SupplementParsedProduct parsedProduct;

  /// Candidate ingredients requiring user review.
  final List<SupplementIngredientCandidate> ingredientCandidates;

  /// Curated category keys derived from the recognized ingredient names,
  /// used to pre-select the category dropdown on the confirmation screen.
  final List<String> suggestedCategoryKeys;

  /// Whether coordinate-derived layout sections are available.
  final bool layoutAvailable;

  /// Safe fallback reason when layout parsing is unavailable.
  final String? layoutFallbackReason;

  /// Bounded label sections for mobile confirmation.
  final List<SupplementPreviewLabelSection> labelSections;

  /// Label-supported intake method candidate.
  final SupplementPreviewIntakeMethod intakeMethod;

  /// Label-supported precaution candidates.
  final List<SupplementPreviewPrecaution> precautions;

  /// Label-supported functional claim candidates.
  final List<SupplementPreviewFunctionalClaim> functionalClaims;

  /// Short redacted evidence excerpts.
  final List<SupplementPreviewEvidenceSpan> evidenceSpans;

  /// Redacted image-quality report returned by the backend.
  final SupplementImageQualityReport? imageQualityReport;

  /// Scope that the preview can safely represent.
  final String analysisScope;

  /// Next user action required before relying on the preview.
  final String actionRequired;

  /// Bounded product or label regions for review UI.
  final List<SupplementDetectedProductRegion> detectedProductRegions;

  /// Backend-selected region id when safe.
  final String? selectedRegionId;

  /// Label sections that need additional image evidence.
  final List<String> missingRequiredSections;

  /// Inferred role of the uploaded image.
  final String imageRole;

  /// Optional multi-image group id.
  final String? multiImageGroupId;

  /// Conservative source classification.
  final String sourceType;

  /// Optional review-only barcode/label identity conflict.
  final SupplementIdentityConflict? identityConflict;

  /// Non-sensitive OCR, YOLO, and parser pipeline metadata.
  final SupplementImagePipelineMetadata pipelineMetadata;

  /// Full OCR source text, present only when the backend opt-in
  /// `store_raw_ocr_text` is enabled; otherwise null.
  final String? rawOcrText;

  /// Field names that need extra attention.
  final List<String> lowConfidenceFields;

  /// Safe preview warnings returned by the backend.
  final List<String> warnings;

  /// Parsing contract version.
  final String algorithmVersion;

  /// Reference source manifest version.
  final String? sourceManifestVersion;

  /// Preview expiration time.
  final DateTime expiresAt;

  /// Whether the preview contains structured review content worth displaying.
  bool get hasReviewContent {
    return ingredientCandidates.isNotEmpty ||
        labelSections.isNotEmpty ||
        (parsedProduct.productName?.trim().isNotEmpty ?? false) ||
        (parsedProduct.manufacturer?.trim().isNotEmpty ?? false) ||
        (intakeMethod.text?.trim().isNotEmpty ?? false) ||
        precautions.isNotEmpty ||
        functionalClaims.isNotEmpty;
  }

  /// Weighted score used to pick the richest preview in a multi-image response.
  int get reviewContentScore {
    int score = 0;
    score += ingredientCandidates.length * 1000;
    score += labelSections.length * 120;
    score += evidenceSpans.length * 30;
    score += pipelineMetadata.sectionCount * 80;
    if (pipelineMetadata.ocrTextPresent) score += 150;
    if (pipelineMetadata.llmParserUsed) score += 80;
    if (parsedProduct.productName?.trim().isNotEmpty == true) score += 120;
    if (parsedProduct.manufacturer?.trim().isNotEmpty == true) score += 40;
    if (intakeMethod.text?.trim().isNotEmpty == true) score += 80;
    score += precautions.length * 60;
    score += functionalClaims.length * 40;
    if (actionRequired == 'additional_label_image_required') score -= 120;
    if (actionRequired == 'blocked') score -= 400;
    return score;
  }

  /// Parses a backend supplement analysis preview.
  factory SupplementAnalysisPreview.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> parsedSnapshot = _firstJsonMap(<Object?>[
      json['parsed_snapshot'],
      json['snapshot'],
    ]);
    final Map<String, dynamic> parsedProductJson = _firstJsonMap(<Object?>[
      json['parsed_product'],
      parsedSnapshot['parsed_product'],
      parsedSnapshot['product'],
    ]);
    final List<Map<String, dynamic>> ingredientRows =
        _firstJsonMapList(<Object?>[
          json['ingredient_candidates'],
          parsedSnapshot['ingredient_candidates'],
          json['ingredients'],
          parsedSnapshot['ingredients'],
        ]);
    final List<Map<String, dynamic>> labelSectionRows =
        _firstJsonMapList(<Object?>[
          json['label_sections'],
          parsedSnapshot['label_sections'],
          parsedSnapshot['sections'],
        ]);
    final List<Map<String, dynamic>> evidenceRows = _firstJsonMapList(<Object?>[
      json['evidence_spans'],
      parsedSnapshot['evidence_spans'],
      parsedSnapshot['evidence'],
    ]);
    final List<String> missingRequiredSections = <String>{
      ...readOptionalStringList(json, 'missing_required_sections'),
      ...readOptionalStringList(parsedSnapshot, 'missing_required_sections'),
    }.toList(growable: false);
    return SupplementAnalysisPreview(
      analysisId: readString(json, 'analysis_id'),
      status: readString(json, 'status'),
      parsedProduct: SupplementParsedProduct.fromJson(parsedProductJson),
      ingredientCandidates: _parseIngredientCandidates(ingredientRows),
      suggestedCategoryKeys: readOptionalStringList(
        json,
        'suggested_category_keys',
      ),
      layoutAvailable: json['layout_available'] == true,
      layoutFallbackReason: readOptionalString(json, 'layout_fallback_reason'),
      labelSections: _parseLabelSections(labelSectionRows),
      intakeMethod: readOptionalObject(json, 'intake_method') == null
          ? SupplementPreviewIntakeMethod.empty
          : SupplementPreviewIntakeMethod.fromJson(
              readObject(json, 'intake_method'),
            ),
      precautions: readOptionalList(json, 'precautions')
          .whereType<Map<String, dynamic>>()
          .map(SupplementPreviewPrecaution.fromJson)
          .toList(growable: false),
      functionalClaims: readOptionalList(json, 'functional_claims')
          .whereType<Map<String, dynamic>>()
          .map(SupplementPreviewFunctionalClaim.fromJson)
          .toList(growable: false),
      evidenceSpans: _parseEvidenceSpans(evidenceRows),
      imageQualityReport:
          readOptionalObject(json, 'image_quality_report') == null
          ? null
          : SupplementImageQualityReport.fromJson(
              readObject(json, 'image_quality_report'),
            ),
      analysisScope: readOptionalString(json, 'analysis_scope') ?? 'unknown',
      actionRequired: readOptionalString(json, 'action_required') ?? 'none',
      detectedProductRegions: readOptionalList(json, 'detected_product_regions')
          .whereType<Map<String, dynamic>>()
          .map(SupplementDetectedProductRegion.fromJson)
          .toList(growable: false),
      selectedRegionId: readOptionalString(json, 'selected_region_id'),
      missingRequiredSections: missingRequiredSections,
      imageRole: readOptionalString(json, 'image_role') ?? 'unknown',
      multiImageGroupId: readOptionalString(json, 'multi_image_group_id'),
      sourceType: readOptionalString(json, 'source_type') ?? 'uploaded_image',
      identityConflict: readOptionalObject(json, 'identity_conflict') == null
          ? null
          : SupplementIdentityConflict.fromJson(
              readObject(json, 'identity_conflict'),
            ),
      pipelineMetadata: readOptionalObject(json, 'pipeline_metadata') == null
          ? SupplementImagePipelineMetadata.intakeOnly
          : SupplementImagePipelineMetadata.fromJson(
              readObject(json, 'pipeline_metadata'),
            ),
      rawOcrText: readOptionalString(json, 'raw_ocr_text'),
      lowConfidenceFields: readOptionalStringList(
        json,
        'low_confidence_fields',
      ),
      warnings: readOptionalStringList(json, 'warnings'),
      algorithmVersion: readString(json, 'algorithm_version'),
      sourceManifestVersion: readOptionalString(
        json,
        'source_manifest_version',
      ),
      expiresAt: _parsePreviewExpiresAt(json),
    );
  }

  /// Whether image risk metadata needs user attention.
  bool get requiresImageAction => actionRequired != 'none';

  /// Whether the current image action blocks direct supplement registration.
  bool get blocksRegistrationForImageRisk {
    return actionRequired == 'product_region_selection_required' ||
        actionRequired == 'additional_label_image_required' ||
        actionRequired == 'blocked';
  }

  /// Whether registration should show an extra image-risk confirmation dialog.
  bool get promptsImageRiskConfirmation {
    return actionRequired == 'retake_recommended' ||
        actionRequired == 'review_required' ||
        identityConflict != null;
  }

  /// Human-readable action label for compact preview UI.
  String get imageActionLabel {
    if (actionRequired == 'product_region_selection_required') {
      return 'Select product region';
    }
    if (actionRequired == 'additional_label_image_required') {
      return 'Add supplement facts image';
    }
    if (actionRequired == 'retake_recommended') {
      return 'Retake recommended';
    }
    if (actionRequired == 'review_required') {
      return 'Image review required';
    }
    if (actionRequired == 'blocked') {
      return 'Image blocked';
    }
    return 'No image action';
  }
}

/// Non-sensitive image analysis pipeline metadata.
class SupplementImagePipelineMetadata {
  /// Creates image analysis pipeline metadata.
  const SupplementImagePipelineMetadata({
    required this.intakeCompleted,
    this.imageCount = 1,
    this.imageRole = 'unknown',
    required this.visionRoiUsed,
    this.ocrStatus = 'skipped',
    this.visionStatus = 'skipped',
    this.llmStatus = 'skipped',
    required this.ocrProvider,
    this.ocrTextPresent = false,
    this.ocrConfidenceBucket = 'none',
    this.roiCount = 0,
    this.sectionCount = 0,
    required this.llmParserUsed,
    this.parserContractVersion,
    this.missingRequiredSections = const <String>[],
    required this.rawImageStored,
    required this.rawOcrTextStored,
  });

  /// Default metadata for legacy intake-only previews.
  static const SupplementImagePipelineMetadata intakeOnly =
      SupplementImagePipelineMetadata(
        intakeCompleted: true,
        imageCount: 1,
        imageRole: 'unknown',
        visionRoiUsed: false,
        ocrStatus: 'skipped',
        visionStatus: 'skipped',
        llmStatus: 'skipped',
        ocrProvider: 'intake-only',
        ocrTextPresent: false,
        ocrConfidenceBucket: 'none',
        roiCount: 0,
        sectionCount: 0,
        llmParserUsed: false,
        parserContractVersion: null,
        missingRequiredSections: <String>[],
        rawImageStored: false,
        rawOcrTextStored: false,
      );

  /// Whether validated image intake completed.
  final bool intakeCompleted;

  /// Number of uploaded images represented by this preview.
  final int imageCount;

  /// Inferred role for this image or capture group.
  final String imageRole;

  /// Whether backend YOLO ROI metadata was used before OCR.
  final bool visionRoiUsed;

  /// OCR stage status for LED-only client display.
  final String ocrStatus;

  /// Vision ROI stage status for LED-only client display.
  final String visionStatus;

  /// Local parser stage status for LED-only client display.
  final String llmStatus;

  /// OCR-like provider label selected by the backend, if any.
  final String? ocrProvider;

  /// Whether OCR produced non-empty text without exposing the raw text.
  final bool ocrTextPresent;

  /// Coarse OCR confidence bucket returned by the backend.
  final String ocrConfidenceBucket;

  /// Number of safe ROI candidates represented by this preview.
  final int roiCount;

  /// Number of bounded label sections available for review.
  final int sectionCount;

  /// Whether the structured parser ran after OCR text extraction.
  final bool llmParserUsed;

  /// Backend parser contract or algorithm version.
  final String? parserContractVersion;

  /// Required label sections still missing from the evidence.
  final List<String> missingRequiredSections;

  /// Whether raw image bytes were retained.
  final bool rawImageStored;

  /// Whether raw OCR text was retained.
  final bool rawOcrTextStored;

  /// Parses sanitized pipeline metadata.
  factory SupplementImagePipelineMetadata.fromJson(Map<String, dynamic> json) {
    final int imageCount = readOptionalInt(json, 'image_count') ?? 1;
    final int roiCount = readOptionalInt(json, 'roi_count') ?? 0;
    final int sectionCount = readOptionalInt(json, 'section_count') ?? 0;
    return SupplementImagePipelineMetadata(
      intakeCompleted: json['intake_completed'] != false,
      imageCount: imageCount < 1 ? 1 : imageCount,
      imageRole: readOptionalString(json, 'image_role') ?? 'unknown',
      visionRoiUsed: json['vision_roi_used'] == true,
      ocrStatus: _normalizeStageStatus(readOptionalString(json, 'ocr_status')),
      visionStatus: _normalizeStageStatus(
        readOptionalString(json, 'vision_status'),
      ),
      llmStatus: _normalizeStageStatus(readOptionalString(json, 'llm_status')),
      ocrProvider: readOptionalString(json, 'ocr_provider'),
      ocrTextPresent: json['ocr_text_present'] == true,
      ocrConfidenceBucket: _normalizeConfidenceBucket(
        readOptionalString(json, 'ocr_confidence_bucket'),
      ),
      roiCount: roiCount < 0 ? 0 : roiCount,
      sectionCount: sectionCount < 0 ? 0 : sectionCount,
      llmParserUsed: json['llm_parser_used'] == true,
      parserContractVersion: readOptionalString(
        json,
        'parser_contract_version',
      ),
      missingRequiredSections: readOptionalStringList(
        json,
        'missing_required_sections',
      ),
      rawImageStored: json['raw_image_stored'] == true,
      rawOcrTextStored: json['raw_ocr_text_stored'] == true,
    );
  }

  static String _normalizeConfidenceBucket(String? value) {
    switch (value) {
      case 'unknown':
      case 'low':
      case 'medium':
      case 'high':
        return value!;
      case 'none':
      default:
        return 'none';
    }
  }

  static String _normalizeStageStatus(String? value) {
    switch (value) {
      case 'success':
      case 'warning':
      case 'failed':
      case 'skipped':
        return value!;
      default:
        return 'skipped';
    }
  }
}

/// Redacted deterministic image-quality report.
class SupplementImageQualityReport {
  /// Creates an image-quality report.
  const SupplementImageQualityReport({
    required this.status,
    required this.issues,
    required this.metrics,
    required this.detectedRois,
    required this.retakeReasons,
  });

  /// Aggregate quality status.
  final String status;

  /// Bounded quality issues.
  final List<SupplementImageQualityIssue> issues;

  /// Numeric quality metrics without raw image or OCR text.
  final Map<String, Object?> metrics;

  /// Sanitized ROI metadata.
  final List<SupplementImageQualityRegion> detectedRois;

  /// Reason codes that should prompt a better image.
  final List<String> retakeReasons;

  /// Parses a backend image-quality report.
  factory SupplementImageQualityReport.fromJson(Map<String, dynamic> json) {
    return SupplementImageQualityReport(
      status: readString(json, 'status'),
      issues: readOptionalList(json, 'issues')
          .whereType<Map<String, dynamic>>()
          .map(SupplementImageQualityIssue.fromJson)
          .toList(growable: false),
      metrics: _readOptionalJsonMap(json, 'metrics'),
      detectedRois: readOptionalList(json, 'detected_rois')
          .whereType<Map<String, dynamic>>()
          .map(SupplementImageQualityRegion.fromJson)
          .toList(growable: false),
      retakeReasons: readOptionalStringList(json, 'retake_reasons'),
    );
  }
}

/// One bounded image-quality issue.
class SupplementImageQualityIssue {
  /// Creates an image-quality issue.
  const SupplementImageQualityIssue({
    required this.reasonCode,
    required this.severity,
    required this.message,
    required this.evidence,
  });

  /// Stable reason code.
  final String reasonCode;

  /// Review severity.
  final String severity;

  /// Safe user-facing message.
  final String message;

  /// Numeric or categorical evidence only.
  final Map<String, Object?> evidence;

  /// Parses a backend quality issue.
  factory SupplementImageQualityIssue.fromJson(Map<String, dynamic> json) {
    return SupplementImageQualityIssue(
      reasonCode: readString(json, 'reason_code'),
      severity: readString(json, 'severity'),
      message: readString(json, 'message'),
      evidence: _readOptionalJsonMap(json, 'evidence'),
    );
  }
}

/// Sanitized image-quality ROI metadata.
class SupplementImageQualityRegion {
  /// Creates a quality-region object.
  const SupplementImageQualityRegion({
    required this.label,
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    required this.confidence,
    required this.areaRatio,
  });

  /// Detector or annotation label.
  final String? label;

  /// Left coordinate in input-image pixels.
  final int x;

  /// Top coordinate in input-image pixels.
  final int y;

  /// Region width in pixels.
  final int width;

  /// Region height in pixels.
  final int height;

  /// Detector confidence.
  final double confidence;

  /// Region area divided by full image area.
  final double? areaRatio;

  /// Parses backend ROI metadata.
  factory SupplementImageQualityRegion.fromJson(Map<String, dynamic> json) {
    return SupplementImageQualityRegion(
      label: readOptionalString(json, 'label'),
      x: readInt(json, 'x'),
      y: readInt(json, 'y'),
      width: readInt(json, 'width'),
      height: readInt(json, 'height'),
      confidence: readDouble(json, 'confidence'),
      areaRatio: readOptionalDouble(json, 'area_ratio'),
    );
  }
}

/// Selectable product or label region for review UI.
class SupplementDetectedProductRegion {
  /// Creates a selectable detected product region.
  const SupplementDetectedProductRegion({
    required this.regionId,
    required this.label,
    required this.x,
    required this.y,
    required this.width,
    required this.height,
    required this.confidence,
    required this.areaRatio,
    required this.selected,
  });

  /// Request-local region id.
  final String regionId;

  /// Detector or annotation label.
  final String? label;

  /// Left coordinate in input-image pixels.
  final int x;

  /// Top coordinate in input-image pixels.
  final int y;

  /// Region width in pixels.
  final int width;

  /// Region height in pixels.
  final int height;

  /// Detector confidence.
  final double confidence;

  /// Region area divided by full image area.
  final double? areaRatio;

  /// Whether this region was selected by the backend.
  final bool selected;

  /// Parses backend selectable ROI metadata.
  factory SupplementDetectedProductRegion.fromJson(Map<String, dynamic> json) {
    return SupplementDetectedProductRegion(
      regionId: readString(json, 'region_id'),
      label: readOptionalString(json, 'label'),
      x: readInt(json, 'x'),
      y: readInt(json, 'y'),
      width: readInt(json, 'width'),
      height: readInt(json, 'height'),
      confidence: readDouble(json, 'confidence'),
      areaRatio: readOptionalDouble(json, 'area_ratio'),
      selected: json['selected'] == true,
    );
  }
}

/// Review-only barcode and parsed-label identity conflict.
class SupplementIdentityConflict {
  /// Creates an identity-conflict object.
  const SupplementIdentityConflict({
    required this.conflictType,
    required this.severity,
    required this.message,
    required this.evidence,
  });

  /// Stable conflict code.
  final String conflictType;

  /// Review severity.
  final String severity;

  /// Safe user-facing message.
  final String message;

  /// Redacted numeric or categorical evidence.
  final Map<String, Object?> evidence;

  /// Parses backend identity-conflict metadata.
  factory SupplementIdentityConflict.fromJson(Map<String, dynamic> json) {
    return SupplementIdentityConflict(
      conflictType: readString(json, 'conflict_type'),
      severity: readString(json, 'severity'),
      message: readString(json, 'message'),
      evidence: _readOptionalJsonMap(json, 'evidence'),
    );
  }
}

/// Product-level supplement fields parsed from label text.
class SupplementParsedProduct {
  /// Creates parsed product fields.
  const SupplementParsedProduct({
    required this.productName,
    required this.manufacturer,
    required this.servingSize,
    required this.dailyServings,
  });

  /// Product name candidate.
  final String? productName;

  /// Manufacturer candidate.
  final String? manufacturer;

  /// Serving-size label text.
  final String? servingSize;

  /// Daily serving count candidate.
  final double? dailyServings;

  /// Empty parsed product fallback.
  static const SupplementParsedProduct empty = SupplementParsedProduct(
    productName: null,
    manufacturer: null,
    servingSize: null,
    dailyServings: null,
  );

  /// Parses backend parsed-product fields.
  factory SupplementParsedProduct.fromJson(Map<String, dynamic> json) {
    return SupplementParsedProduct(
      productName: readOptionalString(json, 'product_name'),
      manufacturer: readOptionalString(json, 'manufacturer'),
      servingSize: readOptionalString(json, 'serving_size'),
      dailyServings: readOptionalDouble(json, 'daily_servings'),
    );
  }
}

/// Ingredient candidate extracted from preview text.
class SupplementIngredientCandidate {
  /// Creates an ingredient candidate.
  const SupplementIngredientCandidate({
    required this.displayName,
    required this.nutrientCode,
    required this.amount,
    required this.unit,
    required this.confidence,
    required this.source,
    this.originalName,
    this.dailyValuePercent,
  });

  /// Ingredient display name.
  final String displayName;

  /// Original ingredient name visible on the label, when provided by analysis.
  final String? originalName;

  /// Internal nutrient code when mapped.
  final String? nutrientCode;

  /// Amount per serving.
  final double? amount;

  /// Ingredient unit.
  final String? unit;

  /// Extraction confidence from 0.0 to 1.0.
  final double confidence;

  /// Source that produced this candidate.
  final String source;

  /// Label %DV (영양성분기준치) when parsed from the label, else null.
  final double? dailyValuePercent;

  /// Parses a backend ingredient candidate.
  factory SupplementIngredientCandidate.fromJson(Map<String, dynamic> json) {
    return SupplementIngredientCandidate(
      displayName: readString(json, 'display_name'),
      originalName: readOptionalString(json, 'original_name'),
      nutrientCode: readOptionalString(json, 'nutrient_code'),
      amount: readOptionalDouble(json, 'amount'),
      unit: readOptionalString(json, 'unit'),
      confidence: readDouble(json, 'confidence'),
      source: readString(json, 'source'),
      dailyValuePercent: readOptionalDouble(json, 'daily_value_percent'),
    );
  }
}

/// Short bounded evidence excerpt for supplement preview review.
class SupplementPreviewEvidenceSpan {
  /// Creates an evidence span.
  const SupplementPreviewEvidenceSpan({
    required this.spanId,
    required this.sourceType,
    required this.sectionType,
    required this.textExcerpt,
    required this.pageIndex,
    required this.cellRef,
    required this.confidence,
  });

  /// Stable evidence id.
  final String spanId;

  /// Evidence source bucket.
  final String sourceType;

  /// Normalized label section type.
  final String sectionType;

  /// Short redacted text excerpt.
  final String textExcerpt;

  /// Optional zero-based page index.
  final int? pageIndex;

  /// Optional layout cell reference.
  final String? cellRef;

  /// Optional OCR/layout confidence.
  final double? confidence;

  /// Parses a backend evidence span.
  factory SupplementPreviewEvidenceSpan.fromJson(Map<String, dynamic> json) {
    return SupplementPreviewEvidenceSpan(
      spanId: readString(json, 'span_id'),
      sourceType: readString(json, 'source_type'),
      sectionType: readString(json, 'section_type'),
      textExcerpt: readString(json, 'text_excerpt'),
      pageIndex: readOptionalInt(json, 'page_index'),
      cellRef: readOptionalString(json, 'cell_ref'),
      confidence: readOptionalDouble(json, 'confidence'),
    );
  }
}

/// Bounded label section summary for supplement preview review.
class SupplementPreviewLabelSection {
  /// Creates a label section preview.
  const SupplementPreviewLabelSection({
    required this.sectionId,
    required this.sectionType,
    required this.headingText,
    required this.textBundle,
    required this.confidence,
    required this.requiresReview,
    required this.evidenceRefs,
  });

  /// Stable section id.
  final String sectionId;

  /// Normalized section type.
  final String sectionType;

  /// Optional section heading.
  final String? headingText;

  /// Bounded section text bundle.
  final String? textBundle;

  /// Optional section confidence.
  final double? confidence;

  /// Whether the section should be reviewed.
  final bool requiresReview;

  /// Evidence ids supporting the section.
  final List<String> evidenceRefs;

  /// Parses a backend label section preview.
  factory SupplementPreviewLabelSection.fromJson(Map<String, dynamic> json) {
    return SupplementPreviewLabelSection(
      sectionId: readString(json, 'section_id'),
      sectionType: readString(json, 'section_type'),
      headingText: readOptionalString(json, 'heading_text'),
      textBundle: readOptionalString(json, 'text_bundle'),
      confidence: readOptionalDouble(json, 'confidence'),
      requiresReview: json['requires_review'] == true,
      evidenceRefs: readOptionalStringList(json, 'evidence_refs'),
    );
  }
}

/// Conservative structured intake method parsed from label text.
class SupplementPreviewStructuredIntakeMethod {
  /// Creates a structured intake method.
  const SupplementPreviewStructuredIntakeMethod({
    required this.frequency,
    required this.timesPerDay,
    required this.amountPerTime,
    required this.amountUnit,
    required this.timeOfDay,
    required this.withFood,
  });

  /// Empty structured intake fallback.
  static const SupplementPreviewStructuredIntakeMethod empty =
      SupplementPreviewStructuredIntakeMethod(
        frequency: 'unknown',
        timesPerDay: null,
        amountPerTime: null,
        amountUnit: null,
        timeOfDay: <String>[],
        withFood: 'unknown',
      );

  /// Frequency candidate.
  final String frequency;

  /// Candidate daily intake count.
  final double? timesPerDay;

  /// Candidate amount per intake.
  final double? amountPerTime;

  /// Candidate amount unit.
  final String? amountUnit;

  /// Optional time-of-day labels.
  final List<String> timeOfDay;

  /// Label-supported food timing marker.
  final String withFood;

  /// Parses a backend structured intake method.
  factory SupplementPreviewStructuredIntakeMethod.fromJson(
    Map<String, dynamic> json,
  ) {
    return SupplementPreviewStructuredIntakeMethod(
      frequency: readString(json, 'frequency'),
      timesPerDay: readOptionalDouble(json, 'times_per_day'),
      amountPerTime: readOptionalDouble(json, 'amount_per_time'),
      amountUnit: readOptionalString(json, 'amount_unit'),
      timeOfDay: readOptionalStringList(json, 'time_of_day'),
      withFood: readString(json, 'with_food'),
    );
  }
}

/// Label-supported intake method preview.
class SupplementPreviewIntakeMethod {
  /// Creates an intake method preview.
  const SupplementPreviewIntakeMethod({
    required this.text,
    required this.structured,
    required this.confidence,
    required this.requiresReview,
    required this.evidenceRefs,
  });

  /// Empty intake method fallback.
  static const SupplementPreviewIntakeMethod empty =
      SupplementPreviewIntakeMethod(
        text: null,
        structured: SupplementPreviewStructuredIntakeMethod.empty,
        confidence: null,
        requiresReview: false,
        evidenceRefs: <String>[],
      );

  /// Bounded raw label instruction text.
  final String? text;

  /// Conservative structured candidate.
  final SupplementPreviewStructuredIntakeMethod structured;

  /// Optional confidence.
  final double? confidence;

  /// Whether this field should be reviewed.
  final bool requiresReview;

  /// Evidence ids supporting this field.
  final List<String> evidenceRefs;

  /// Parses a backend intake method preview.
  factory SupplementPreviewIntakeMethod.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic>? structured = readOptionalObject(
      json,
      'structured',
    );
    return SupplementPreviewIntakeMethod(
      text: readOptionalString(json, 'text'),
      structured: structured == null
          ? SupplementPreviewStructuredIntakeMethod.empty
          : SupplementPreviewStructuredIntakeMethod.fromJson(structured),
      confidence: readOptionalDouble(json, 'confidence'),
      requiresReview: json['requires_review'] == true,
      evidenceRefs: readOptionalStringList(json, 'evidence_refs'),
    );
  }
}

/// Label-supported precaution preview.
class SupplementPreviewPrecaution {
  /// Creates a precaution preview.
  const SupplementPreviewPrecaution({
    required this.text,
    required this.category,
    required this.severity,
    required this.confidence,
    required this.requiresReview,
    required this.evidenceRefs,
  });

  /// Bounded precaution text.
  final String text;

  /// Conservative category.
  final String category;

  /// Label warning severity marker.
  final String severity;

  /// Optional confidence.
  final double? confidence;

  /// Whether this row should be reviewed.
  final bool requiresReview;

  /// Evidence ids supporting this precaution.
  final List<String> evidenceRefs;

  /// Parses a backend precaution preview.
  factory SupplementPreviewPrecaution.fromJson(Map<String, dynamic> json) {
    return SupplementPreviewPrecaution(
      text: readString(json, 'text'),
      category: readString(json, 'category'),
      severity: readString(json, 'severity'),
      confidence: readOptionalDouble(json, 'confidence'),
      requiresReview: json['requires_review'] == true,
      evidenceRefs: readOptionalStringList(json, 'evidence_refs'),
    );
  }
}

/// Label-supported functional claim preview.
class SupplementPreviewFunctionalClaim {
  /// Creates a functional claim preview.
  const SupplementPreviewFunctionalClaim({
    required this.text,
    required this.claimType,
    required this.confidence,
    required this.requiresReview,
    required this.evidenceRefs,
  });

  /// Bounded label claim text.
  final String text;

  /// Conservative claim type.
  final String claimType;

  /// Optional confidence.
  final double? confidence;

  /// Whether this row should be reviewed.
  final bool requiresReview;

  /// Evidence ids supporting this claim.
  final List<String> evidenceRefs;

  /// Parses a backend functional claim preview.
  factory SupplementPreviewFunctionalClaim.fromJson(Map<String, dynamic> json) {
    return SupplementPreviewFunctionalClaim(
      text: readString(json, 'text'),
      claimType: readString(json, 'claim_type'),
      confidence: readOptionalDouble(json, 'confidence'),
      requiresReview: json['requires_review'] == true,
      evidenceRefs: readOptionalStringList(json, 'evidence_refs'),
    );
  }
}

/// Request payload for parsing OCR text against an existing preview.
class SupplementOCRTextParseRequest {
  /// Creates an OCR text parse request.
  const SupplementOCRTextParseRequest({
    required this.ocrText,
    this.ocrProvider = 'manual_demo',
    this.ocrConfidence,
  });

  /// Raw OCR text held transiently by the client.
  final String ocrText;

  /// Provider label sent to the backend.
  final String ocrProvider;

  /// Optional provider confidence.
  final double? ocrConfidence;

  /// Serializes the request to backend JSON.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'ocr_text': ocrText,
      'ocr_provider': ocrProvider,
      'ocr_confidence': ocrConfidence,
    };
  }
}

/// User-confirmed supplement registration request.
class UserSupplementCreate {
  /// Creates a user-confirmed supplement registration request.
  const UserSupplementCreate({
    required this.analysisId,
    required this.displayName,
    required this.manufacturer,
    required this.ingredients,
    required this.serving,
    required this.intakeSchedule,
    this.categoryKey,
    this.precautionSnapshot = const <String>[],
    this.evidenceRefs = const <String>[],
  });

  /// Temporary analysis identifier used for traceability.
  final String? analysisId;

  /// User-confirmed supplement name.
  final String displayName;

  /// User-confirmed manufacturer.
  final String? manufacturer;

  /// User-confirmed ingredient list.
  final List<UserSupplementIngredientInput> ingredients;

  /// User-confirmed serving values.
  final SupplementServing serving;

  /// Optional user-confirmed intake schedule.
  final SupplementIntakeSchedule? intakeSchedule;

  /// User-chosen curated category key from the catalog (null when unset).
  final String? categoryKey;

  /// User-confirmed precaution sentences from the label.
  final List<String> precautionSnapshot;

  /// Preview evidence ids that support the confirmed values.
  final List<String> evidenceRefs;

  /// Serializes the request to backend JSON.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'analysis_id': analysisId,
      'display_name': displayName,
      'manufacturer': manufacturer,
      'ingredients': ingredients
          .map(
            (UserSupplementIngredientInput ingredient) => ingredient.toJson(),
          )
          .toList(growable: false),
      'serving': serving.toJson(),
      'intake_schedule': intakeSchedule?.toJson(),
      // 분류 미선택 시 키를 생략한다 — 서버는 누락을 '선택 안 함'으로 본다.
      if (categoryKey != null) 'category_key': categoryKey,
      'precaution_snapshot': precautionSnapshot,
      'evidence_refs': evidenceRefs,
      'user_confirmed': true,
    };
  }
}

/// Curated supplement category from `GET /supplements/categories`.
class SupplementCategory {
  /// Creates a curated supplement category.
  const SupplementCategory({
    required this.categoryKey,
    required this.displayName,
    required this.sortOrder,
  });

  /// Stable machine key sent back as the user's chosen category.
  final String categoryKey;

  /// User-facing category label.
  final String displayName;

  /// Catalog sort order (ascending).
  final int sortOrder;

  /// Parses one catalog row; returns null when required fields are missing.
  static SupplementCategory? fromJson(Map<String, dynamic> json) {
    final Object? key = json['category_key'];
    final Object? label = json['display_name'];
    if (key is! String || key.isEmpty || label is! String || label.isEmpty) {
      return null;
    }
    final Object? sort = json['sort_order'];
    return SupplementCategory(
      categoryKey: key,
      displayName: label,
      sortOrder: sort is int ? sort : 0,
    );
  }

  /// Parses the catalog list response (`results[]`), skipping malformed rows.
  static List<SupplementCategory> listFromJson(Map<String, dynamic> json) {
    final Object? rows = json['results'];
    if (rows is! List<dynamic>) {
      return const <SupplementCategory>[];
    }
    final List<SupplementCategory> out = <SupplementCategory>[];
    for (final Object? row in rows) {
      if (row is Map<String, dynamic>) {
        final SupplementCategory? parsed = SupplementCategory.fromJson(row);
        if (parsed != null) {
          out.add(parsed);
        }
      }
    }
    return out;
  }
}

/// User-confirmed supplement ingredient row.
class UserSupplementIngredientInput {
  /// Creates a user-confirmed ingredient input.
  const UserSupplementIngredientInput({
    required this.displayName,
    this.originalName,
    required this.nutrientCode,
    required this.amount,
    required this.unit,
    required this.confidence,
    required this.source,
    this.dailyValuePercent,
  });

  /// User-confirmed ingredient name.
  final String displayName;

  /// Original ingredient name visible on the label, when carried from analysis.
  final String? originalName;

  /// Internal nutrient code when deterministically mapped.
  final String? nutrientCode;

  /// Ingredient amount per serving.
  final double? amount;

  /// Ingredient unit.
  final String? unit;

  /// Extraction or confirmation confidence.
  final double confidence;

  /// Source marker accepted by the backend.
  final String source;

  /// User-confirmed %DV (영양성분기준치) when present on the label.
  final double? dailyValuePercent;

  /// Serializes the ingredient row to backend JSON.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'display_name': displayName,
      if (originalName != null) 'original_name': originalName,
      'nutrient_code': nutrientCode,
      'amount': amount,
      'unit': unit,
      if (dailyValuePercent != null) 'daily_value_percent': dailyValuePercent,
      'confidence': confidence,
      'source': source,
    };
  }
}

/// User-confirmed supplement serving values.
class SupplementServing {
  /// Creates serving values.
  const SupplementServing({
    required this.amount,
    required this.unit,
    required this.dailyServings,
  });

  /// Serving amount.
  final double? amount;

  /// Serving unit.
  final String? unit;

  /// Daily serving count confirmed by the user.
  final double dailyServings;

  /// Serializes serving values to backend JSON.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'amount': amount,
      'unit': unit,
      'daily_servings': dailyServings,
    };
  }
}

/// User-confirmed supplement intake schedule.
class SupplementIntakeSchedule {
  /// Creates an intake schedule.
  const SupplementIntakeSchedule({
    required this.frequency,
    required this.timeOfDay,
    this.timesPerDay,
    this.amountPerTime,
    this.amountUnit,
    this.withFood,
  });

  /// Human-readable frequency.
  final String frequency;

  /// Optional time labels such as morning or evening.
  final List<String> timeOfDay;

  /// Confirmed daily intake count carried from the label preview.
  final double? timesPerDay;

  /// Confirmed amount per intake.
  final double? amountPerTime;

  /// Confirmed intake amount unit.
  final String? amountUnit;

  /// Whether the label mentions food timing.
  final String? withFood;

  /// Serializes intake schedule to backend JSON.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'frequency': frequency,
      'time_of_day': timeOfDay,
      if (timesPerDay != null) 'times_per_day': timesPerDay,
      if (amountPerTime != null) 'amount_per_time': amountPerTime,
      if (amountUnit != null) 'amount_unit': amountUnit,
      if (withFood != null) 'with_food': withFood,
    };
  }
}

/// Persisted current-user supplement response.
class UserSupplementResponse {
  /// Creates a persisted supplement response.
  const UserSupplementResponse({
    required this.id,
    required this.displayName,
    required this.manufacturer,
    this.precautionSnapshot = const <String>[],
    this.evidenceRefs = const <String>[],
  });

  /// Persisted supplement identifier.
  final String id;

  /// User-confirmed supplement name.
  final String displayName;

  /// User-confirmed manufacturer.
  final String? manufacturer;

  /// User-confirmed precaution sentences from the label.
  final List<String> precautionSnapshot;

  /// Preview evidence ids that supported the stored supplement.
  final List<String> evidenceRefs;

  /// Parses a backend persisted supplement response.
  factory UserSupplementResponse.fromJson(Map<String, dynamic> json) {
    return UserSupplementResponse(
      id: readString(json, 'id'),
      displayName: readString(json, 'display_name'),
      manufacturer: readOptionalString(json, 'manufacturer'),
      precautionSnapshot: readOptionalStringList(json, 'precaution_snapshot'),
      evidenceRefs: readOptionalStringList(json, 'evidence_refs'),
    );
  }
}

/// Request payload for deterministic supplement impact preview.
class SupplementImpactPreviewRequest {
  /// Creates a supplement impact preview request.
  const SupplementImpactPreviewRequest({
    this.selectedSupplementIds = const <String>[],
    this.includeAllActiveSupplements = true,
  });

  /// Optional supplement id subset.
  final List<String> selectedSupplementIds;

  /// Whether to include all active supplements.
  final bool includeAllActiveSupplements;

  /// Serializes the request to backend JSON.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'selected_supplement_ids': selectedSupplementIds,
      'include_all_active_supplements': includeAllActiveSupplements,
      'profile_override': null,
    };
  }
}

/// Ingredient contribution aggregate returned by the backend.
class SupplementContributionAggregate {
  /// Creates a contribution aggregate.
  const SupplementContributionAggregate({
    required this.nutrientCode,
    required this.nutrientName,
    required this.referenceUnit,
    required this.totalDailyAmount,
    required this.contributionCount,
    required this.warnings,
  });

  /// Internal nutrient code.
  final String nutrientCode;

  /// Display nutrient name when available.
  final String? nutrientName;

  /// Reference unit when available.
  final String? referenceUnit;

  /// Total supplement daily amount in reference unit when available.
  final double? totalDailyAmount;

  /// Number of contributing ingredient rows.
  final int contributionCount;

  /// Safe warning codes/messages.
  final List<String> warnings;

  /// Parses a backend contribution aggregate.
  factory SupplementContributionAggregate.fromJson(Map<String, dynamic> json) {
    return SupplementContributionAggregate(
      nutrientCode: readString(json, 'nutrient_code'),
      nutrientName: readOptionalString(json, 'nutrient_name'),
      referenceUnit: readOptionalString(json, 'reference_unit'),
      totalDailyAmount: readOptionalDouble(json, 'total_daily_amount'),
      contributionCount: readInt(json, 'contribution_count'),
      warnings: readOptionalStringList(json, 'warnings'),
    );
  }
}

/// Safe deterministic supplement insight.
class SupplementNutritionInsight {
  /// Creates a nutrition insight.
  const SupplementNutritionInsight({
    required this.nutrientCode,
    required this.nutrientName,
    required this.actionLabel,
    required this.reasonCode,
    required this.supplementDailyAmount,
    required this.estimatedTotalAmount,
    required this.referenceUnit,
    required this.userMessage,
  });

  /// Internal nutrient code.
  final String nutrientCode;

  /// Nutrient display name when available.
  final String? nutrientName;

  /// Safe action label.
  final String actionLabel;

  /// Deterministic reason code.
  final String reasonCode;

  /// Supplement daily amount when available.
  final double? supplementDailyAmount;

  /// Estimated total amount when available.
  final double? estimatedTotalAmount;

  /// Reference unit when available.
  final String? referenceUnit;

  /// Safe user-facing message.
  final String userMessage;

  /// Parses a backend nutrition insight.
  factory SupplementNutritionInsight.fromJson(Map<String, dynamic> json) {
    return SupplementNutritionInsight(
      nutrientCode: readString(json, 'nutrient_code'),
      nutrientName: readOptionalString(json, 'nutrient_name'),
      actionLabel: readString(json, 'action_label'),
      reasonCode: readString(json, 'reason_code'),
      supplementDailyAmount: readOptionalDouble(
        json,
        'supplement_daily_amount',
      ),
      estimatedTotalAmount: readOptionalDouble(json, 'estimated_total_amount'),
      referenceUnit: readOptionalString(json, 'reference_unit'),
      userMessage: readString(json, 'user_message'),
    );
  }
}

/// Deterministic supplement impact preview response.
class SupplementImpactPreviewResponse {
  /// Creates a supplement impact preview response.
  const SupplementImpactPreviewResponse({
    required this.calculationVersion,
    required this.referenceVersion,
    required this.sourceManifestVersion,
    required this.dataStatus,
    required this.currentSupplementContributions,
    required this.deficiencySupportCandidates,
    required this.excessOrDuplicateRisks,
    required this.missingProfileFields,
    required this.safeUserMessage,
    required this.clinicalDisclaimer,
    required this.warnings,
    required this.requiresUserConfirmation,
    this.rawJson = const <String, dynamic>{},
  });

  /// Server calculation algorithm version.
  final String calculationVersion;

  /// KDRI reference version.
  final String referenceVersion;

  /// KDRI source manifest version.
  final String? sourceManifestVersion;

  /// Readiness status.
  final String dataStatus;

  /// Current supplement contribution aggregates.
  final List<SupplementContributionAggregate> currentSupplementContributions;

  /// Nutrients whose low intake overlaps with supplement inputs.
  final List<SupplementNutritionInsight> deficiencySupportCandidates;

  /// Duplicate or upper-limit review insights.
  final List<SupplementNutritionInsight> excessOrDuplicateRisks;

  /// Missing fields for personalized comparison.
  final List<String> missingProfileFields;

  /// Safe summary message.
  final String safeUserMessage;

  /// Clinical disclaimer.
  final String clinicalDisclaimer;

  /// Safe warning codes/messages.
  final List<String> warnings;

  /// Whether UI should ask for user review.
  final bool requiresUserConfirmation;

  /// Original backend JSON for explain requests.
  final Map<String, dynamic> rawJson;

  /// Parses a backend supplement impact preview.
  factory SupplementImpactPreviewResponse.fromJson(Map<String, dynamic> json) {
    return SupplementImpactPreviewResponse(
      calculationVersion: readString(json, 'calculation_version'),
      referenceVersion: readString(json, 'reference_version'),
      sourceManifestVersion: readOptionalString(
        json,
        'source_manifest_version',
      ),
      dataStatus: readString(json, 'data_status'),
      currentSupplementContributions:
          readOptionalList(json, 'current_supplement_contributions')
              .whereType<Map<String, dynamic>>()
              .map(SupplementContributionAggregate.fromJson)
              .toList(growable: false),
      deficiencySupportCandidates:
          readOptionalList(json, 'deficiency_support_candidates')
              .whereType<Map<String, dynamic>>()
              .map(SupplementNutritionInsight.fromJson)
              .toList(growable: false),
      excessOrDuplicateRisks:
          readOptionalList(json, 'excess_or_duplicate_risks')
              .whereType<Map<String, dynamic>>()
              .map(SupplementNutritionInsight.fromJson)
              .toList(growable: false),
      missingProfileFields: readOptionalStringList(
        json,
        'missing_profile_fields',
      ),
      safeUserMessage: readString(json, 'safe_user_message'),
      clinicalDisclaimer: readString(json, 'clinical_disclaimer'),
      warnings: readOptionalStringList(json, 'warnings'),
      requiresUserConfirmation: json['requires_user_confirmation'] == true,
      rawJson: Map<String, dynamic>.unmodifiable(json),
    );
  }

  /// Serializes the original backend response for explain requests.
  Map<String, dynamic> toJson() {
    if (rawJson.isNotEmpty) {
      return Map<String, dynamic>.from(rawJson);
    }
    return <String, dynamic>{
      'calculation_version': calculationVersion,
      'reference_version': referenceVersion,
      'source_manifest_version': sourceManifestVersion,
      'data_status': dataStatus,
      'current_supplement_contributions': <Map<String, dynamic>>[],
      'deficiency_support_candidates': <Map<String, dynamic>>[],
      'excess_or_duplicate_risks': <Map<String, dynamic>>[],
      'missing_profile_fields': missingProfileFields,
      'safe_user_message': safeUserMessage,
      'clinical_disclaimer': clinicalDisclaimer,
      'warnings': warnings,
      'requires_user_confirmation': requiresUserConfirmation,
    };
  }
}

/// Source citation used to ground a local LLM explanation.
class SupplementExplanationSourceCitation {
  /// Creates a source citation.
  const SupplementExplanationSourceCitation({
    required this.title,
    required this.sourcePath,
    this.heading,
    required this.excerpt,
    required this.score,
  });

  /// Human-readable WIKI document title.
  final String title;

  /// Relative source path from the configured WIKI root.
  final String sourcePath;

  /// Matching heading, when available.
  final String? heading;

  /// Bounded WIKI excerpt used for grounding.
  final String excerpt;

  /// Deterministic lexical retrieval score.
  final double score;

  /// Parses a backend citation response.
  factory SupplementExplanationSourceCitation.fromJson(
    Map<String, dynamic> json,
  ) {
    return SupplementExplanationSourceCitation(
      title: readString(json, 'title'),
      sourcePath: readString(json, 'source_path'),
      heading: readOptionalString(json, 'heading'),
      excerpt: readString(json, 'excerpt'),
      score: readOptionalDouble(json, 'score') ?? 0,
    );
  }
}

/// Safe explanation response for a deterministic supplement impact preview.
class SupplementRecommendationExplainResponse {
  /// Creates an explanation response.
  const SupplementRecommendationExplainResponse({
    required this.safeUserMessage,
    required this.explanationBullets,
    required this.clinicalDisclaimer,
    required this.blockedTermsDetected,
    required this.llmUsed,
    this.sourceCitations = const <SupplementExplanationSourceCitation>[],
    required this.warnings,
  });

  /// Safe summary message.
  final String safeUserMessage;

  /// Bounded explanation bullets.
  final List<String> explanationBullets;

  /// Clinical disclaimer.
  final String clinicalDisclaimer;

  /// Blocked terms detected by the backend.
  final List<String> blockedTermsDetected;

  /// Whether local LLM wording was accepted.
  final bool llmUsed;

  /// Local WIKI citations used to ground the explanation.
  final List<SupplementExplanationSourceCitation> sourceCitations;

  /// Safe warning codes/messages.
  final List<String> warnings;

  /// Parses a backend explanation response.
  factory SupplementRecommendationExplainResponse.fromJson(
    Map<String, dynamic> json,
  ) {
    return SupplementRecommendationExplainResponse(
      safeUserMessage: readString(json, 'safe_user_message'),
      explanationBullets: readOptionalStringList(json, 'explanation_bullets'),
      clinicalDisclaimer: readString(json, 'clinical_disclaimer'),
      blockedTermsDetected: readOptionalStringList(
        json,
        'blocked_terms_detected',
      ),
      llmUsed: json['llm_used'] == true,
      sourceCitations: readOptionalList(json, 'source_citations')
          .whereType<Map<String, dynamic>>()
          .map(SupplementExplanationSourceCitation.fromJson)
          .toList(growable: false),
      warnings: readOptionalStringList(json, 'warnings'),
    );
  }
}
