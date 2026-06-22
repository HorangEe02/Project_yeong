/// Reads a required string from a JSON map.
String readString(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value is String) {
    return value;
  }
  throw FormatException('Expected string field "$key".');
}

/// Reads an optional string from a JSON map.
String? readOptionalString(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value == null || value is String) {
    return value as String?;
  }
  throw FormatException('Expected nullable string field "$key".');
}

/// Reads a required integer from a JSON map.
int readInt(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value is int) {
    return value;
  }
  throw FormatException('Expected integer field "$key".');
}

/// Reads an optional integer from a JSON map.
int? readOptionalInt(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value == null || value is int) {
    return value as int?;
  }
  throw FormatException('Expected nullable integer field "$key".');
}

/// Reads a required double-compatible number from a JSON map.
double readDouble(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value is num) {
    return value.toDouble();
  }
  throw FormatException('Expected number field "$key".');
}

/// Reads an optional double-compatible number from a JSON map.
double? readOptionalDouble(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value == null) {
    return null;
  }
  if (value is num) {
    return value.toDouble();
  }
  throw FormatException('Expected nullable number field "$key".');
}

/// Reads a required JSON object from a JSON map.
Map<String, dynamic> readObject(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value is Map<String, dynamic>) {
    return value;
  }
  if (value is Map<Object?, Object?>) {
    return Map<String, dynamic>.from(value);
  }
  throw FormatException('Expected object field "$key".');
}

/// Reads a nullable JSON object from a JSON map.
Map<String, dynamic>? readOptionalObject(
  Map<String, dynamic> json,
  String key,
) {
  final Object? value = json[key];
  if (value == null) {
    return null;
  }
  if (value is Map<String, dynamic>) {
    return value;
  }
  if (value is Map<Object?, Object?>) {
    return Map<String, dynamic>.from(value);
  }
  throw FormatException('Expected nullable object field "$key".');
}

/// Reads a required list from a JSON map.
List<Object?> readList(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value is List) {
    return List<Object?>.from(value);
  }
  throw FormatException('Expected list field "$key".');
}

/// Reads an optional list from a JSON map.
List<Object?> readOptionalList(Map<String, dynamic> json, String key) {
  final Object? value = json[key];
  if (value == null) {
    return const <Object?>[];
  }
  if (value is List) {
    return List<Object?>.from(value);
  }
  throw FormatException('Expected optional list field "$key".');
}

/// Reads a required string list from a JSON map.
List<String> readStringList(Map<String, dynamic> json, String key) {
  return readList(json, key).whereType<String>().toList(growable: false);
}

/// Reads an optional string list from a JSON map.
List<String> readOptionalStringList(Map<String, dynamic> json, String key) {
  return readOptionalList(
    json,
    key,
  ).whereType<String>().toList(growable: false);
}
