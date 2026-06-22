// features/nutrition/kdri_models.dart
//
// KDRIs(한국인 영양소 섭취기준) 룩업 응답 모델.
// GET /nutrition/kdris 의 결과를 파싱한다 (공개 라우트 — 동의 불필요).
// 백엔드 src/models/schemas/nutrition.py 의 KDRIReference / KDRILookupResponse
// 필드만 사용한다(없는 필드 날조 금지). 모든 산출은 백엔드 책임이며 모바일은
// 표시·매핑만 담당한다 (mobile/CLAUDE.md).

import '../../shared/models/json_readers.dart';

/// KDRIs 기준값 한 줄.
///
/// 성분 상세 화면의 권장량/상한 게이지 카드에 사용한다.
class KdriReference {
  /// KDRIs 기준값을 만든다.
  const KdriReference({
    required this.nutrientCode,
    required this.referenceType,
    required this.referenceUnit,
    this.nutrientNameKo,
    this.referenceAmount,
    this.ulAmount,
    this.ulUnit,
    this.reviewStatus,
  });

  /// 내부 영양소 코드 (예: vitamin_c_mg).
  final String nutrientCode;

  /// 한국어 영양소명.
  final String? nutrientNameKo;

  /// 기준 유형 (RDA, AI, EER 등).
  final String referenceType;

  /// 단일 기준 섭취량. 범위 기준만 있는 행은 null 일 수 있다.
  final double? referenceAmount;

  /// 기준 단위.
  final String referenceUnit;

  /// 상한 섭취량 (UL). 없으면 null — 마커 생략.
  final double? ulAmount;

  /// 상한 단위.
  final String? ulUnit;

  /// 행 단위 검수 상태. 미검수면 참고용 캡션을 병기한다.
  final String? reviewStatus;

  /// 백엔드 KDRIs 기준값 한 줄을 파싱한다.
  factory KdriReference.fromJson(Map<String, dynamic> json) {
    return KdriReference(
      nutrientCode: readString(json, 'nutrient_code'),
      nutrientNameKo: readOptionalString(json, 'nutrient_name_ko'),
      referenceType: readString(json, 'reference_type'),
      referenceAmount: readOptionalDouble(json, 'reference_amount'),
      referenceUnit: readString(json, 'reference_unit'),
      ulAmount: readOptionalDouble(json, 'ul_amount'),
      ulUnit: readOptionalString(json, 'ul_unit'),
      reviewStatus: readOptionalString(json, 'review_status'),
    );
  }
}

/// KDRIs 룩업 응답.
///
/// 조회 실패/빈 응답 시 화면은 권장량 카드를 생략하고 함량만 표시한다.
class KdriLookupResult {
  /// KDRIs 룩업 응답을 만든다.
  const KdriLookupResult({
    required this.references,
    required this.datasetStatus,
    required this.datasetVersion,
    this.note,
  });

  /// 매칭된 기준값 목록.
  final List<KdriReference> references;

  /// 샘플/공식 데이터 상태.
  final String datasetStatus;

  /// 데이터셋 버전.
  final String datasetVersion;

  /// 사용자 노출용 안전 문구.
  final String? note;

  /// 공식 데이터셋인지 여부 (참고용 캡션 게이팅).
  bool get isOfficialDataset => datasetStatus.toLowerCase() == 'official';

  /// 빈(표시 없음) 결과.
  static const KdriLookupResult empty = KdriLookupResult(
    references: <KdriReference>[],
    datasetStatus: 'unknown',
    datasetVersion: 'unknown',
  );

  /// 내부 영양소 코드로 기준값을 찾는다(없으면 null).
  KdriReference? referenceFor(String? nutrientCode) {
    final String? code = nutrientCode?.trim();
    if (code == null || code.isEmpty) return null;
    for (final KdriReference reference in references) {
      if (reference.nutrientCode == code) return reference;
    }
    return null;
  }

  /// 백엔드 KDRIs 룩업 응답을 파싱한다.
  factory KdriLookupResult.fromJson(Map<String, dynamic> json) {
    return KdriLookupResult(
      references: readOptionalList(json, 'references')
          .whereType<Map<String, dynamic>>()
          .map(KdriReference.fromJson)
          .toList(growable: false),
      datasetStatus: readOptionalString(json, 'dataset_status') ?? 'unknown',
      datasetVersion: readOptionalString(json, 'dataset_version') ?? 'unknown',
      note: readOptionalString(json, 'note'),
    );
  }
}
