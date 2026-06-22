// shared/widgets/status_state_view.dart — 전역 상태 템플릿
//
// SoT §8 상태 변형(enum)을 중앙 관리.
// 마스코트 + 볼드 타이틀 + 회색 설명 + 풀폭 CTA 구조.
//
// 사용:
//   StatusStateView(variant: StatusStateVariant.emptyNew, onPrimary: () { ... })
//   StatusStateView(
//     variant: StatusStateVariant.searchEmpty,
//     query: '비타민',
//     onPrimary: () { ... },
//   )

import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';
import '../../utils/mascot_poses.dart';

// ────────────────────────────────────────────────
// 상태 변형 enum
// ────────────────────────────────────────────────

/// 전역 상태 화면 변형.
///
/// 각 변형은 고유한 타이틀·설명·CTA 텍스트와 마스코트 포즈를 가진다.
/// CTA 콜백은 생성자 [onPrimary] / [onSecondary] 로 전달.
enum StatusStateVariant {
  /// 첫 기록 없는 빈 화면.
  emptyNew,

  /// 네트워크/서버 동기화 실패.
  syncFailed,

  /// 권한 미허용.
  permissionDenied,

  /// OCR·AI 분석 실패.
  analysisFailed,

  /// 알림 없음.
  notificationsEmpty,

  /// 검색 결과 없음 — [query] 파라미터 필요.
  searchEmpty,
}

// ────────────────────────────────────────────────
// 위젯
// ────────────────────────────────────────────────

/// SoT §8 전역 상태 템플릿 위젯.
///
/// 중앙 정렬 — 연노랑(brandSoft) 원형 배경 속 마스코트 이미지 + 볼드 타이틀
/// + 회색 2줄 설명 + 하단 풀폭 primary CTA (일부 변형은 secondary 추가).
///
/// Parameters:
///   variant  — 상태 변형.
///   query    — [StatusStateVariant.searchEmpty] 일 때 검색어. 다른 변형에서는 무시.
///   onPrimary  — primary CTA 콜백. null 이면 버튼 비활성.
///   onSecondary — secondary 텍스트 링크 콜백 (analysisFailed 변형 전용).
class StatusStateView extends StatelessWidget {
  const StatusStateView({
    super.key,
    required this.variant,
    this.query,
    this.onPrimary,
    this.onSecondary,
  });

  final StatusStateVariant variant;

  /// 검색어 — [StatusStateVariant.searchEmpty] 에서만 사용.
  final String? query;

  /// Primary CTA 콜백. null 이면 버튼 미표시.
  final VoidCallback? onPrimary;

  /// Secondary 텍스트 링크 콜백. null 이면 링크 미표시.
  final VoidCallback? onSecondary;

  // ── 데이터 매핑 ──────────────────────────────

  String _title() {
    switch (variant) {
      case StatusStateVariant.emptyNew:
        return '아직 기록이 없어요';
      case StatusStateVariant.syncFailed:
        return '불러오지 못했어요';
      case StatusStateVariant.permissionDenied:
        return '권한이 필요해요';
      case StatusStateVariant.analysisFailed:
        return '분석하지 못했어요';
      case StatusStateVariant.notificationsEmpty:
        return '알림이 없어요';
      case StatusStateVariant.searchEmpty:
        final String q = query ?? '';
        return q.isNotEmpty ? "'$q' 검색 결과가 없어요" : '검색 결과가 없어요';
    }
  }

  String _description() {
    switch (variant) {
      case StatusStateVariant.emptyNew:
        return '오늘 첫 끼니나 영양제를 사진으로 남겨볼까요?';
      case StatusStateVariant.syncFailed:
        return '네트워크가 불안정해요. 잠시 후 다시 시도해 주세요';
      case StatusStateVariant.permissionDenied:
        return '기록을 보려면 설정에서 권한을 켜주세요';
      case StatusStateVariant.analysisFailed:
        return '사진이 흐릿하거나 인식이 어려웠어요. 다시 찍어볼까요?';
      case StatusStateVariant.notificationsEmpty:
        return '새로운 소식이 오면 여기에서 알려드릴게요';
      case StatusStateVariant.searchEmpty:
        return '이름을 바꿔 검색하거나 직접 추가할 수 있어요';
    }
  }

  /// Primary CTA 레이블. null 이면 버튼 미노출.
  String? _primaryLabel() {
    switch (variant) {
      case StatusStateVariant.emptyNew:
        return '촬영하기';
      case StatusStateVariant.syncFailed:
        return '다시 시도';
      case StatusStateVariant.permissionDenied:
        return '설정 열기';
      case StatusStateVariant.analysisFailed:
        return '다시 촬영';
      case StatusStateVariant.notificationsEmpty:
        return null;
      case StatusStateVariant.searchEmpty:
        return '직접 추가하기';
    }
  }

  /// Secondary CTA 레이블 (analysisFailed 전용). null 이면 미노출.
  String? _secondaryLabel() {
    switch (variant) {
      case StatusStateVariant.analysisFailed:
        return '직접 입력하기';
      default:
        return null;
    }
  }

  MascotPose _pose() {
    switch (variant) {
      case StatusStateVariant.emptyNew:
        return MascotPose.resting; // 휴식 — 빈 상태
      case StatusStateVariant.syncFailed:
        return MascotPose.thinking; // 생각 — 로딩 실패·재시도
      case StatusStateVariant.permissionDenied:
        return MascotPose.help; // 도움 — 안내·가이드
      case StatusStateVariant.analysisFailed:
        return MascotPose.curious; // 호기심 — 질문·재시도 유도
      case StatusStateVariant.notificationsEmpty:
        return MascotPose.resting; // 휴식 — 여유·기다림
      case StatusStateVariant.searchEmpty:
        return MascotPose.find; // 돋보기 — 검색·탐색
    }
  }

  // ── 빌드 ─────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final String? primaryLabel = _primaryLabel();
    final String? secondaryLabel = _secondaryLabel();

    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.page,
          vertical: AppSpace.xl,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            // 연노랑 원형 배경 + 마스코트 이미지
            Container(
              width: 112,
              height: 112,
              decoration: BoxDecoration(
                color: AppColor.brandSoft,
                shape: BoxShape.circle,
              ),
              child: Padding(
                padding: const EdgeInsets.all(AppSpace.lg),
                child: Image.asset(
                  _pose().asset,
                  fit: BoxFit.contain,
                  errorBuilder: (_, _, _) => Icon(
                    Icons.sentiment_satisfied_rounded,
                    size: 48,
                    color: AppColor.brand,
                  ),
                ),
              ),
            ),
            const SizedBox(height: AppSpace.lg),

            // 볼드 타이틀
            Text(
              _title(),
              style: AppText.subtitle,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpace.sm),

            // 회색 설명
            Text(
              _description(),
              style: AppText.body.copyWith(color: AppColor.inkSecondary),
              textAlign: TextAlign.center,
            ),

            // Primary CTA
            if (primaryLabel != null) ...<Widget>[
              const SizedBox(height: AppSpace.xl),
              SizedBox(
                width: double.infinity,
                child: AppPrimaryButton(
                  label: primaryLabel,
                  onPressed: onPrimary,
                ),
              ),
            ],

            // Secondary 텍스트 링크 (analysisFailed 전용)
            if (secondaryLabel != null) ...<Widget>[
              const SizedBox(height: AppSpace.md),
              GestureDetector(
                onTap: onSecondary,
                child: Text(
                  secondaryLabel,
                  style: AppText.body.copyWith(
                    color: AppColor.inkTertiary,
                    decoration: TextDecoration.underline,
                    decorationColor: AppColor.inkTertiary,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
