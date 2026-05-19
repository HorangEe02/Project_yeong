/// 인증 / 프로필 / 동의 모델 — backend `models/schemas/auth.py` 와 1:1 매핑.
///
/// `fieldRename: FieldRename.snake` 으로 snake_case JSON ↔ camelCase Dart.
library;

// freezed factory 인자의 @JsonKey 는 freezed 매크로가 getter 로 옮겨주지만,
// 분석기는 일시 invalid_annotation_target 으로 경고함 (freezed README 권장 무시).
// ignore_for_file: invalid_annotation_target

import 'package:freezed_annotation/freezed_annotation.dart';

part 'auth_models.freezed.dart';
part 'auth_models.g.dart';

/// 복약 정보 1건 — backend 가 free-form JSON 으로 받음.
///
/// freezed `@Default` 의 nested generic (`<Map<String, dynamic>>[]`) 가
/// 파서 버그 (`>>` malformed) 를 일으키므로 typedef 로 분리.
typedef MedicationMap = Map<String, Object?>;

/// 사용자 성별 — backend `Sex` (Literal["male", "female"]) 매핑.
enum Sex {
  @JsonValue('male')
  male,
  @JsonValue('female')
  female,
}

/// 회원가입/프로필 입력.
///
/// `chronic_diseases` 와 `medications` 가 비어있지 않으면 ConsentMatrix 에
/// `chronic_disease` / `medications` 동의 토글이 추가로 표시된다.
@freezed
class ProfileInput with _$ProfileInput {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory ProfileInput({
    required int age,
    required Sex sex,
    @JsonKey(name: 'height_cm') required double heightCm,
    @JsonKey(name: 'weight_kg') required double weightKg,
    @JsonKey(name: 'is_pregnant') @Default(false) bool isPregnant,
    @JsonKey(name: 'is_lactating') @Default(false) bool isLactating,
    @JsonKey(name: 'is_smoker') @Default(false) bool isSmoker,
    @JsonKey(name: 'chronic_diseases')
    @Default(<String>[])
    List<String> chronicDiseases,
    @Default(<MedicationMap>[]) List<MedicationMap> medications,
  }) = _ProfileInput;

  factory ProfileInput.fromJson(Map<String, dynamic> json) =>
      _$ProfileInputFromJson(json);
}

/// 회원가입 시 사용자가 토글한 개별 동의 항목.
@freezed
class ConsentAccept with _$ConsentAccept {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory ConsentAccept({
    @JsonKey(name: 'consent_type') required String consentType,
    required bool accepted,
  }) = _ConsentAccept;

  factory ConsentAccept.fromJson(Map<String, dynamic> json) =>
      _$ConsentAcceptFromJson(json);
}

/// 회원가입 요청 body.
@freezed
class RegisterRequest with _$RegisterRequest {
  const factory RegisterRequest({
    required String email,
    required String password,
    required ProfileInput profile,
    required List<ConsentAccept> consents,
  }) = _RegisterRequest;

  factory RegisterRequest.fromJson(Map<String, dynamic> json) =>
      _$RegisterRequestFromJson(json);
}

/// 로그인 요청 body.
@freezed
class LoginRequest with _$LoginRequest {
  const factory LoginRequest({
    required String email,
    required String password,
  }) = _LoginRequest;

  factory LoginRequest.fromJson(Map<String, dynamic> json) =>
      _$LoginRequestFromJson(json);
}

/// 토큰 갱신 요청.
@freezed
class RefreshRequest with _$RefreshRequest {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory RefreshRequest({
    @JsonKey(name: 'refresh_token') required String refreshToken,
  }) = _RefreshRequest;

  factory RefreshRequest.fromJson(Map<String, dynamic> json) =>
      _$RefreshRequestFromJson(json);
}

/// 인증 응답 — backend `TokenResponse`.
@freezed
class TokenResponse with _$TokenResponse {
  @JsonSerializable(fieldRename: FieldRename.snake)
  const factory TokenResponse({
    @JsonKey(name: 'access_token') required String accessToken,
    @JsonKey(name: 'refresh_token') required String refreshToken,
    @JsonKey(name: 'token_type') @Default('bearer') String tokenType,
    @JsonKey(name: 'expires_in_seconds') @Default(900) int expiresInSeconds,
  }) = _TokenResponse;

  factory TokenResponse.fromJson(Map<String, dynamic> json) =>
      _$TokenResponseFromJson(json);
}

/// 인증된 사용자 — 토큰 + 프로필 일부.
///
/// M-2 시점은 백엔드가 `/auth/me` 같은 엔드포인트를 노출하지 않으므로
/// register 응답의 profile 또는 토큰 payload 의 sub 만 보관. 후속 트랙에서
/// 프로필 fetch 추가.
@freezed
class User with _$User {
  const factory User({
    required String email,
    ProfileInput? profile,
  }) = _User;

  factory User.fromJson(Map<String, dynamic> json) => _$UserFromJson(json);
}
