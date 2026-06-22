// screens/settings/withdraw_screen.dart — 회원 탈퇴 (figma 957:143)
//
// 가이드 08 (f) step 29. dangerSoft 경고 카드(삭제 항목 불릿) → 사유 라디오
// (로컬 수집만 — 서버 필드 없음) → 확인 체크 → [탈퇴하기] → 최종 확인 다이얼로그
// → POST /me/data-deletion-requests(202) → 로컬 세션 정리 → 완료 화면.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app_providers.dart';
import '../../core/api/api_error.dart';
import '../../features/auth/token_session.dart';
import '../../utils/design_tokens_v2.dart';
import '../../widgets/common/app_modals.dart';

/// 삭제되는 항목 불릿.
const List<String> _kDeletionItems = <String>[
  '신체 정보·건강 프로필',
  '영양제·식단 기록',
  '복약 알림 설정',
  '분석 결과와 대화 내역',
];

/// 탈퇴 사유 (로컬 수집만 — 서버 필드 없음).
const List<String> _kReasons = <String>[
  '앱을 잘 쓰지 않아요',
  '원하는 기능이 없어요',
  '개인정보가 걱정돼요',
  '다른 앱을 써요',
  '기타',
];

/// 회원 탈퇴 화면.
class WithdrawScreen extends ConsumerStatefulWidget {
  /// 화면을 생성한다.
  const WithdrawScreen({super.key});

  @override
  ConsumerState<WithdrawScreen> createState() => _WithdrawScreenState();
}

class _WithdrawScreenState extends ConsumerState<WithdrawScreen> {
  String? _reason;
  bool _confirmed = false;
  bool _submitting = false;
  bool _done = false;

  Future<void> _withdraw() async {
    final bool confirmed = await showDeleteConfirmDialog(
      context,
      targetLabel: '계정과 모든 데이터를',
    );
    if (!confirmed || !mounted) return;

    setState(() => _submitting = true);
    try {
      await ref.read(privacyRepositoryProvider).requestDeletion();
      // 사유는 로컬 수집만 — 서버 전송 안 함(백엔드 공백). 세션을 정리한다.
      final TokenSessionController session = ref.read(tokenSessionProvider);
      await session.clearBearerToken();
      if (!mounted) return;
      setState(() {
        _submitting = false;
        _done = true;
      });
    } on ApiError catch (error) {
      if (!mounted) return;
      setState(() => _submitting = false);
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(content: Text(error.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColor.section,
      appBar: AppBar(
        backgroundColor: AppColor.section,
        elevation: 0,
        title: const Text(
          '회원 탈퇴',
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontWeight: FontWeight.w800,
            color: AppColor.ink,
          ),
        ),
      ),
      body: SafeArea(child: _done ? _buildDone() : _buildForm()),
    );
  }

  Widget _buildDone() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpace.page),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(
              Icons.check_circle_outline_rounded,
              size: 56,
              color: AppColor.success,
            ),
            const SizedBox(height: AppSpace.lg),
            Text(
              '요청을 접수했어요',
              style: AppText.subtitle.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: AppSpace.sm),
            Text(
              '그동안 함께해 주셔서 감사해요',
              textAlign: TextAlign.center,
              style: AppText.body.copyWith(color: AppColor.inkSecondary),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildForm() {
    return Column(
      children: <Widget>[
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(AppSpace.page),
            children: <Widget>[
              _WarningCard(),
              const SizedBox(height: AppSpace.lg),
              Text(
                '탈퇴 사유를 알려주세요 (선택)',
                style: AppText.subtitle.copyWith(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: AppSpace.sm),
              RadioGroup<String>(
                groupValue: _reason,
                onChanged: (String? v) => setState(() => _reason = v),
                child: Column(
                  children: <Widget>[
                    for (final String reason in _kReasons)
                      RadioListTile<String>(
                        value: reason,
                        title: Text(reason, style: AppText.body),
                        activeColor: AppColor.brand,
                        contentPadding: EdgeInsets.zero,
                      ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpace.md),
              CheckboxListTile(
                value: _confirmed,
                onChanged: (bool? v) => setState(() => _confirmed = v ?? false),
                title: Text('안내 사항을 확인했고, 탈퇴에 동의해요', style: AppText.body),
                activeColor: AppColor.brand,
                contentPadding: EdgeInsets.zero,
                controlAffinity: ListTileControlAffinity.leading,
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.page,
            AppSpace.page,
            AppSpace.page,
            AppSpace.sm,
          ),
          child: SizedBox(
            height: 52,
            child: AppPrimaryButton(
              label: '탈퇴하기',
              color: AppColor.danger,
              loading: _submitting,
              enabled: _confirmed,
              onPressed: (_confirmed && !_submitting) ? _withdraw : null,
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.page,
            0,
            AppSpace.page,
            AppSpace.lg,
          ),
          child: TextButton(
            onPressed: _submitting
                ? null
                : () => Navigator.of(context).maybePop(),
            child: Text(
              '계속 사용할게요',
              style: AppText.subtitle.copyWith(
                fontWeight: FontWeight.w700,
                color: AppColor.inkSecondary,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _WarningCard extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.lg),
      decoration: BoxDecoration(
        color: AppColor.dangerSoft,
        borderRadius: BorderRadius.circular(AppRadius.lg),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Icon(
                Icons.warning_amber_rounded,
                color: AppColor.danger,
                size: 22,
              ),
              const SizedBox(width: AppSpace.sm),
              Text(
                '탈퇴하면 아래 데이터가 삭제돼요',
                style: AppText.body.copyWith(
                  fontWeight: FontWeight.w800,
                  color: AppColor.danger,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.md),
          for (final String item in _kDeletionItems)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const Text('• ', style: TextStyle(color: AppColor.danger)),
                  Expanded(
                    child: Text(
                      item,
                      style: AppText.caption.copyWith(color: AppColor.ink),
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 4),
          Text(
            '삭제된 데이터는 되돌릴 수 없어요',
            style: AppText.micro.copyWith(color: AppColor.danger),
          ),
        ],
      ),
    );
  }
}
