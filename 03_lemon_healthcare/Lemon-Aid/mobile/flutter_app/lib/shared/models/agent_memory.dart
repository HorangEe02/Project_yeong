class AgentMemory {
  const AgentMemory({
    required this.memoryId,
    required this.userId,
    required this.summary,
    required this.tags,
    required this.raw,
  });

  factory AgentMemory.fromJson(Map<String, dynamic> json) {
    return AgentMemory(
      memoryId: _stringValue(json['memory_id'] ?? json['id']),
      userId: _stringValue(json['user_id']),
      summary: _stringValue(json['summary'] ?? json['memory_summary']),
      tags: _stringList(json['tags']),
      raw: Map<String, dynamic>.from(json),
    );
  }

  final String memoryId;
  final String userId;
  final String summary;
  final List<String> tags;
  final Map<String, dynamic> raw;

  bool get isEmpty => summary.isEmpty && raw.isEmpty;
}

String _stringValue(Object? value) {
  return value is String ? value : '';
}

List<String> _stringList(Object? value) {
  if (value is! List<dynamic>) {
    return <String>[];
  }
  return value.whereType<String>().toList(growable: false);
}
