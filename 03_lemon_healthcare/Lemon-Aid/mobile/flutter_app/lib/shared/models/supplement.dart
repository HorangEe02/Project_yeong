class Supplement {
  const Supplement({
    required this.supplementId,
    required this.name,
    required this.status,
    required this.ingredients,
    required this.candidates,
    required this.raw,
  });

  factory Supplement.fromJson(Map<String, dynamic> json) {
    return Supplement(
      supplementId: _stringValue(json['supplement_id'] ?? json['id']),
      name: _stringValue(json['name'] ?? json['product_name']),
      status: _stringValue(json['analysis_status'] ?? json['status']),
      ingredients: _mapList(json['ingredients']),
      candidates: _mapList(json['candidates']),
      raw: Map<String, dynamic>.from(json),
    );
  }

  final String supplementId;
  final String name;
  final String status;
  final List<Map<String, dynamic>> ingredients;
  final List<Map<String, dynamic>> candidates;
  final Map<String, dynamic> raw;

  bool get hasPreviewCandidates => candidates.isNotEmpty;
}

String _stringValue(Object? value) {
  return value is String ? value : '';
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
