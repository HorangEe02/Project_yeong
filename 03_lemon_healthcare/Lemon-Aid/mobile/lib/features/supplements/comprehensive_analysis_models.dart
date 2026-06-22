// features/supplements/comprehensive_analysis_models.dart
//
// 식단 종합 분석(C 하이브리드) 응답 모델.
// POST /supplements/analyze/comprehensive 의 결과를 파싱한다.
// 모든 산출식은 백엔드 책임 — 모바일은 표시·매핑만 담당 (mobile/CLAUDE.md).

import '../../shared/models/json_readers.dart';

/// 식단 종합 분석에 전달하는 성분 한 줄.
///
/// meal nutrition_summary totals 를 백엔드 계약 형태로 변환할 때 사용한다.
class ComprehensiveIngredientInput {
  /// 성분 입력 한 줄을 만든다.
  const ComprehensiveIngredientInput({
    required this.displayName,
    required this.nutrientCode,
    required this.amount,
    required this.unit,
  });

  /// 표시용 성분명.
  final String displayName;

  /// 내부 영양소 코드 (예: carbohydrate_g, protein_g, fat_g, sodium_mg).
  final String nutrientCode;

  /// 함량 값.
  final double amount;

  /// 함량 단위.
  final String unit;

  /// 백엔드 계약 형태로 직렬화한다.
  Map<String, Object?> toJson() {
    return <String, Object?>{
      'display_name': displayName,
      'nutrient_code': nutrientCode,
      'amount': amount,
      'unit': unit,
    };
  }
}

/// 부족 영양소 한 줄.
class ComprehensiveDeficientNutrient {
  /// 부족 영양소를 만든다.
  const ComprehensiveDeficientNutrient({
    required this.nutrientCode,
    this.nutrientName,
    this.currentIntake,
    this.recommendedIntake,
    this.deficitRatio,
    this.unit,
    this.confidence,
    this.message,
  });

  /// 내부 영양소 코드.
  final String nutrientCode;

  /// 표시용 영양소명.
  final String? nutrientName;

  /// 현재 섭취량.
  final double? currentIntake;

  /// 권장 섭취량.
  final double? recommendedIntake;

  /// 부족 비율 (0~1).
  final double? deficitRatio;

  /// 표시 단위.
  final String? unit;

  /// 신뢰도 (0~1).
  final double? confidence;

  /// 안전한 권고 한 줄.
  final String? message;

  /// 백엔드 부족 영양소를 파싱한다.
  factory ComprehensiveDeficientNutrient.fromJson(Map<String, dynamic> json) {
    return ComprehensiveDeficientNutrient(
      nutrientCode: readString(json, 'nutrient_code'),
      nutrientName: readOptionalString(json, 'nutrient_name'),
      currentIntake: readOptionalDouble(json, 'current_intake'),
      recommendedIntake: readOptionalDouble(json, 'recommended_intake'),
      deficitRatio: readOptionalDouble(json, 'deficit_ratio'),
      unit: readOptionalString(json, 'unit'),
      confidence: readOptionalDouble(json, 'confidence'),
      message: readOptionalString(json, 'message'),
    );
  }
}

/// 과다 섭취 영양소 한 줄.
class ComprehensiveExcessiveNutrient {
  /// 과다 섭취 영양소를 만든다.
  const ComprehensiveExcessiveNutrient({
    required this.nutrientCode,
    this.nutrientName,
    this.currentIntake,
    this.upperLimit,
    this.excessRatio,
    this.unit,
    this.confidence,
    this.message,
  });

  /// 내부 영양소 코드.
  final String nutrientCode;

  /// 표시용 영양소명.
  final String? nutrientName;

  /// 현재 섭취량.
  final double? currentIntake;

  /// 상한 섭취량.
  final double? upperLimit;

  /// 초과 비율 (0~1+).
  final double? excessRatio;

  /// 표시 단위.
  final String? unit;

  /// 신뢰도 (0~1).
  final double? confidence;

  /// 안전한 권고 한 줄.
  final String? message;

  /// 백엔드 과다 섭취 영양소를 파싱한다.
  factory ComprehensiveExcessiveNutrient.fromJson(Map<String, dynamic> json) {
    return ComprehensiveExcessiveNutrient(
      nutrientCode: readString(json, 'nutrient_code'),
      nutrientName: readOptionalString(json, 'nutrient_name'),
      currentIntake: readOptionalDouble(json, 'current_intake'),
      upperLimit: readOptionalDouble(json, 'upper_limit'),
      excessRatio: readOptionalDouble(json, 'excess_ratio'),
      unit: readOptionalString(json, 'unit'),
      confidence: readOptionalDouble(json, 'confidence'),
      message: readOptionalString(json, 'message'),
    );
  }
}

/// 주의 성분 한 줄.
class ComprehensiveCautionaryComponent {
  /// 주의 성분을 만든다.
  const ComprehensiveCautionaryComponent({
    required this.component,
    this.reason,
    this.severity,
    this.message,
    this.sourceCitation,
  });

  /// 성분명.
  final String component;

  /// 주의 사유.
  final String? reason;

  /// 심각도 (low/medium/high 등).
  final String? severity;

  /// 안전한 안내 메시지.
  final String? message;

  /// 출처 표기 (응답에 있을 때만 — 날조 금지).
  final String? sourceCitation;

  /// 백엔드 주의 성분을 파싱한다.
  factory ComprehensiveCautionaryComponent.fromJson(
    Map<String, dynamic> json,
  ) {
    return ComprehensiveCautionaryComponent(
      component: readString(json, 'component'),
      reason: readOptionalString(json, 'reason'),
      severity: readOptionalString(json, 'severity'),
      message: readOptionalString(json, 'message'),
      sourceCitation: readOptionalString(json, 'source_citation'),
    );
  }
}

/// 목적별(만성질환 등) 분석 한 줄.
class ComprehensivePurposeTarget {
  /// 목적별 분석 한 줄을 만든다.
  const ComprehensivePurposeTarget({
    required this.condition,
    this.relevanceScore,
    this.evidenceLevel,
    this.message,
    this.sourceCitation,
  });

  /// 대상 상태(예: 당뇨).
  final String condition;

  /// 관련도 점수 (0~1).
  final double? relevanceScore;

  /// 근거 등급.
  final String? evidenceLevel;

  /// 안전한 안내 메시지.
  final String? message;

  /// 출처 표기 (응답에 있을 때만).
  final String? sourceCitation;

  /// 백엔드 목적별 분석을 파싱한다.
  factory ComprehensivePurposeTarget.fromJson(Map<String, dynamic> json) {
    return ComprehensivePurposeTarget(
      condition: readString(json, 'condition'),
      relevanceScore: readOptionalDouble(json, 'relevance_score'),
      evidenceLevel: readOptionalString(json, 'evidence_level'),
      message: readOptionalString(json, 'message'),
      sourceCitation: readOptionalString(json, 'source_citation'),
    );
  }
}

/// 식단 종합 분석(C 하이브리드) 응답.
///
/// 호출 실패/빈 응답 시 화면은 점수 영역을 숨기고 기존 정보를 표시한다.
class ComprehensiveDietAnalysis {
  /// 식단 종합 분석 응답을 만든다.
  const ComprehensiveDietAnalysis({
    required this.deficientNutrients,
    required this.excessiveNutrients,
    required this.cautionaryComponents,
    required this.purposeTargets,
    required this.chronicDiseaseIndications,
    required this.warnings,
    this.dietScore,
    this.dietScoreLabel,
    this.dietScoreMessage,
    this.dietScoreConfidence,
  });

  /// 부족 영양소.
  final List<ComprehensiveDeficientNutrient> deficientNutrients;

  /// 과다 섭취 영양소.
  final List<ComprehensiveExcessiveNutrient> excessiveNutrients;

  /// 주의 성분.
  final List<ComprehensiveCautionaryComponent> cautionaryComponents;

  /// 목적별 분석.
  final List<ComprehensivePurposeTarget> purposeTargets;

  /// 만성질환 적응증(개인화 카드용 — 프로필 있을 때만).
  final List<String> chronicDiseaseIndications;

  /// 안전한 경고 코드/메시지.
  final List<String> warnings;

  /// 식단 점수 (0~100).
  final double? dietScore;

  /// 식단 점수 라벨(헤드라인).
  final String? dietScoreLabel;

  /// 식단 점수 메시지.
  final String? dietScoreMessage;

  /// 점수 신뢰도 (0~1).
  final double? dietScoreConfidence;

  /// 점수 영역을 표시할 수 있는지 여부.
  bool get hasScore => dietScore != null;

  /// 어떤 분석 카드라도 표시할 내용이 있는지 여부.
  bool get hasContent =>
      deficientNutrients.isNotEmpty ||
      excessiveNutrients.isNotEmpty ||
      cautionaryComponents.isNotEmpty ||
      purposeTargets.isNotEmpty;

  /// 빈(표시 없음) 분석.
  static const ComprehensiveDietAnalysis empty = ComprehensiveDietAnalysis(
    deficientNutrients: <ComprehensiveDeficientNutrient>[],
    excessiveNutrients: <ComprehensiveExcessiveNutrient>[],
    cautionaryComponents: <ComprehensiveCautionaryComponent>[],
    purposeTargets: <ComprehensivePurposeTarget>[],
    chronicDiseaseIndications: <String>[],
    warnings: <String>[],
  );

  /// 백엔드 종합 분석 응답을 파싱한다.
  factory ComprehensiveDietAnalysis.fromJson(Map<String, dynamic> json) {
    return ComprehensiveDietAnalysis(
      deficientNutrients: readOptionalList(json, 'deficient_nutrients')
          .whereType<Map<String, dynamic>>()
          .map(ComprehensiveDeficientNutrient.fromJson)
          .toList(growable: false),
      excessiveNutrients: readOptionalList(json, 'excessive_nutrients')
          .whereType<Map<String, dynamic>>()
          .map(ComprehensiveExcessiveNutrient.fromJson)
          .toList(growable: false),
      cautionaryComponents: readOptionalList(json, 'cautionary_components')
          .whereType<Map<String, dynamic>>()
          .map(ComprehensiveCautionaryComponent.fromJson)
          .toList(growable: false),
      purposeTargets: readOptionalList(json, 'purpose_targets')
          .whereType<Map<String, dynamic>>()
          .map(ComprehensivePurposeTarget.fromJson)
          .toList(growable: false),
      chronicDiseaseIndications: readOptionalStringList(
        json,
        'chronic_disease_indications',
      ),
      warnings: readOptionalStringList(json, 'warnings'),
      dietScore: readOptionalDouble(json, 'diet_score'),
      dietScoreLabel: readOptionalString(json, 'diet_score_label'),
      dietScoreMessage: readOptionalString(json, 'diet_score_message'),
      dietScoreConfidence: readOptionalDouble(json, 'diet_score_confidence'),
    );
  }
}
