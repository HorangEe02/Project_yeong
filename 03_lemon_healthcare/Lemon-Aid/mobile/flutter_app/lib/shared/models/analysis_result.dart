class AnalysisResult {
  const AnalysisResult({
    required this.analysisId,
    required this.analysisType,
    required this.status,
    required this.confidence,
    required this.resultSnapshot,
    required this.raw,
  });

  factory AnalysisResult.fromJson(Map<String, dynamic> json) {
    return AnalysisResult(
      analysisId: _stringValue(json['analysis_id'] ?? json['id']),
      analysisType: _stringValue(json['analysis_type'] ?? json['type']),
      status: _stringValue(json['status'] ?? json['analysis_status']),
      confidence: _doubleValue(json['confidence']),
      resultSnapshot: _mapValue(json['result_snapshot'] ?? json['snapshot']),
      raw: Map<String, dynamic>.from(json),
    );
  }

  final String analysisId;
  final String analysisType;
  final String status;
  final double? confidence;
  final Map<String, dynamic> resultSnapshot;
  final Map<String, dynamic> raw;

  bool get isConfirmed {
    return status == 'confirmed' || raw['user_confirmed'] == true;
  }
}

String _stringValue(Object? value) {
  return value is String ? value : '';
}

double? _doubleValue(Object? value) {
  if (value is num) {
    return value.toDouble();
  }
  if (value is String) {
    return double.tryParse(value);
  }
  return null;
}

Map<String, dynamic> _mapValue(Object? value) {
  if (value is Map<dynamic, dynamic>) {
    return Map<String, dynamic>.from(value);
  }
  return <String, dynamic>{};
}
