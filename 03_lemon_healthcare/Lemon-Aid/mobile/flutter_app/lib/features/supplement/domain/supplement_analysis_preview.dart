class SupplementAnalysisPreview {
  SupplementAnalysisPreview({
    required this.analysisId,
    required this.status,
    required this.ocrProvider,
    required this.parsedProduct,
    required this.ingredientCandidates,
    required this.warnings,
  });

  factory SupplementAnalysisPreview.fromJson(Map<String, dynamic> json) {
    return SupplementAnalysisPreview(
      analysisId: json['analysis_id'] as String? ?? '',
      status: json['status'] as String? ?? 'unknown',
      ocrProvider: json['ocr_provider'] as String? ?? 'unknown',
      parsedProduct:
          SupplementParsedProduct.fromJson(_map(json['parsed_product'])),
      ingredientCandidates: _mapList(json['ingredient_candidates'])
          .map(SupplementIngredientCandidate.fromJson)
          .toList(growable: false),
      warnings: _stringList(json['warnings']),
    );
  }

  final String analysisId;
  final String status;
  final String ocrProvider;
  final SupplementParsedProduct parsedProduct;
  final List<SupplementIngredientCandidate> ingredientCandidates;
  final List<String> warnings;
}

class SupplementParsedProduct {
  SupplementParsedProduct({
    required this.productName,
    required this.manufacturer,
    required this.servingSize,
    required this.dailyServings,
  });

  factory SupplementParsedProduct.fromJson(Map<String, dynamic> json) {
    return SupplementParsedProduct(
      productName: json['product_name'] as String? ?? '',
      manufacturer: json['manufacturer'] as String? ?? '',
      servingSize: json['serving_size'] as String? ?? '',
      dailyServings: _doubleOrNull(json['daily_servings']),
    );
  }

  final String productName;
  final String manufacturer;
  final String servingSize;
  final double? dailyServings;
}

class SupplementIngredientCandidate {
  SupplementIngredientCandidate({
    required this.displayName,
    required this.nutrientCode,
    required this.amount,
    required this.unit,
    required this.confidence,
    required this.source,
  });

  factory SupplementIngredientCandidate.fromJson(Map<String, dynamic> json) {
    return SupplementIngredientCandidate(
      displayName: json['display_name'] as String? ?? '',
      nutrientCode: json['nutrient_code'] as String?,
      amount: _doubleOrNull(json['amount']),
      unit: json['unit'] as String? ?? '',
      confidence: _doubleOrNull(json['confidence']) ?? 0,
      source: json['source'] as String? ?? 'ocr_llm_preview',
    );
  }

  final String displayName;
  final String? nutrientCode;
  final double? amount;
  final String unit;
  final double confidence;
  final String source;
}

class SupplementConfirmedInput {
  SupplementConfirmedInput({
    required this.analysisId,
    required this.displayName,
    required this.manufacturer,
    required this.ingredients,
    required this.serving,
    required this.intakeSchedule,
  });

  final String analysisId;
  final String displayName;
  final String? manufacturer;
  final List<SupplementConfirmedIngredientInput> ingredients;
  final SupplementServingInput serving;
  final SupplementIntakeScheduleInput? intakeSchedule;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      if (analysisId.isNotEmpty) 'analysis_id': analysisId,
      'display_name': displayName,
      if (manufacturer != null && manufacturer!.isNotEmpty)
        'manufacturer': manufacturer,
      'ingredients': ingredients
          .map(
            (SupplementConfirmedIngredientInput ingredient) =>
                ingredient.toJson(),
          )
          .toList(growable: false),
      'serving': serving.toJson(),
      if (intakeSchedule != null) 'intake_schedule': intakeSchedule!.toJson(),
      'user_confirmed': true,
    };
  }

  Map<String, dynamic> toAgentSupplementJson() {
    return <String, dynamic>{
      'product_name': displayName,
      'ingredients': ingredients
          .where(
            (SupplementConfirmedIngredientInput ingredient) =>
                ingredient.amount != null &&
                ingredient.unit != null &&
                ingredient.unit!.isNotEmpty,
          )
          .map(
            (SupplementConfirmedIngredientInput ingredient) =>
                ingredient.toAgentNutrientJson(),
          )
          .toList(growable: false),
      'times_per_day': _positiveTimesPerDay(serving.dailyServings),
      'user_confirmed': true,
    };
  }
}

class SupplementConfirmedIngredientInput {
  SupplementConfirmedIngredientInput({
    required this.displayName,
    required this.nutrientCode,
    required this.amount,
    required this.unit,
  });

  final String displayName;
  final String? nutrientCode;
  final double? amount;
  final String? unit;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'display_name': displayName,
      if (nutrientCode != null && nutrientCode!.isNotEmpty)
        'nutrient_code': nutrientCode,
      if (amount != null) 'amount': amount,
      if (unit != null && unit!.isNotEmpty) 'unit': unit,
      'confidence': 1.0,
      'source': 'user_confirmed',
    };
  }

  Map<String, dynamic> toAgentNutrientJson() {
    return <String, dynamic>{
      'name': displayName,
      'amount': amount,
      'unit': unit,
    };
  }
}

class SupplementServingInput {
  SupplementServingInput({
    required this.amount,
    required this.unit,
    required this.dailyServings,
  });

  final double? amount;
  final String? unit;
  final double dailyServings;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      if (amount != null) 'amount': amount,
      if (unit != null && unit!.isNotEmpty) 'unit': unit,
      'daily_servings': dailyServings,
    };
  }
}

class SupplementIntakeScheduleInput {
  SupplementIntakeScheduleInput({
    required this.frequency,
    required this.timeOfDay,
  });

  final String frequency;
  final List<String> timeOfDay;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'frequency': frequency,
      'time_of_day': timeOfDay,
    };
  }
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<dynamic, dynamic>) {
    return Map<String, dynamic>.from(value);
  }
  return <String, dynamic>{};
}

List<Map<String, dynamic>> _mapList(Object? value) {
  if (value is! List<dynamic>) {
    return <Map<String, dynamic>>[];
  }
  return value
      .whereType<Map<dynamic, dynamic>>()
      .map((Map<dynamic, dynamic> item) => Map<String, dynamic>.from(item))
      .toList(growable: false);
}

List<String> _stringList(Object? value) {
  if (value is! List<dynamic>) {
    return <String>[];
  }
  return value.whereType<String>().toList(growable: false);
}

double? _doubleOrNull(Object? value) {
  if (value is num) {
    return value.toDouble();
  }
  if (value is String) {
    return double.tryParse(value);
  }
  return null;
}

int _positiveTimesPerDay(double dailyServings) {
  final int rounded = dailyServings.round();
  return rounded < 1 ? 1 : rounded;
}
