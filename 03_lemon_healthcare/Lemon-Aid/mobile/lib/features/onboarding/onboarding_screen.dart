import 'package:flutter/material.dart';

import '../../core/storage/local_prefs.dart';
import '../../utils/design_tokens_v2.dart' as ds2;
import '../../widgets/common/medical_disclaimer.dart';

/// 온보딩 슬라이드 정의.
class _Slide {
  const _Slide({
    required this.assetPath,
    required this.title,
    required this.description,
    this.showDisclaimer = false,
  });

  /// 슬라이드 상단 마스코트 일러스트 경로.
  final String assetPath;

  /// 슬라이드 제목.
  final String title;

  /// 슬라이드 설명(해요체).
  final String description;

  /// 의료 면책 고지 노출 여부(분석 슬라이드).
  final bool showDisclaimer;
}

const List<_Slide> _slides = <_Slide>[
  _Slide(
    assetPath: 'assets/mascot/poses/hello.png',
    title: '레몬에이드에 오신 걸\n환영해요',
    description: '음식과 영양제를 한 번에 관리하는\n똑똑한 건강 도우미예요.',
  ),
  _Slide(
    assetPath: 'assets/mascot/poses/find.png',
    title: '사진 한 장으로\n분석해요',
    description: '영양제 라벨이나 식단을 찍으면\n부족하거나 넘치는 영양을 알려드려요.',
    showDisclaimer: true,
  ),
  _Slide(
    assetPath: 'assets/mascot/poses/celebrate.png',
    title: '매일의 루틴을\n챙겨드려요',
    description: '복용 체크와 변화 추이로\n건강 습관을 이어가요.',
  ),
];

/// 온보딩 3-slide — 첫 실행 1회 노출(가이드 01 2단계).
///
/// 슬라이드를 넘기거나 건너뛰면 [LocalPrefs.setOnboardingSeen]으로 표시한 뒤
/// [onDone]을 호출해 다음 화면(로그인/홈)으로 보낸다. 스플래시가 첫 실행에만
/// 이 화면으로 라우팅한다.
class OnboardingScreen extends StatefulWidget {
  /// 온보딩 화면을 만든다.
  const OnboardingScreen({
    required this.prefs,
    required this.onDone,
    super.key,
  });

  /// 온보딩 노출 여부를 영속하는 로컬 저장소.
  final LocalPrefs prefs;

  /// 온보딩 완료/건너뛰기 후 호출되는 콜백(다음 화면 이동).
  final VoidCallback onDone;

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _controller = PageController();
  int _page = 0;
  bool _finishing = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool get _isLast => _page == _slides.length - 1;

  void _onNext() {
    if (_isLast) {
      _finish();
      return;
    }
    _controller.nextPage(
      duration: const Duration(milliseconds: 240),
      curve: Curves.easeOut,
    );
  }

  Future<void> _finish() async {
    if (_finishing) return;
    setState(() => _finishing = true);
    await widget.prefs.setOnboardingSeen();
    if (!mounted) return;
    widget.onDone();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ds2.AppColor.bg,
      body: SafeArea(
        child: Column(
          children: <Widget>[
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.only(
                  top: ds2.AppSpace.sm,
                  right: ds2.AppSpace.md,
                ),
                child: TextButton(
                  onPressed: _finishing ? null : _finish,
                  child: Text(
                    '건너뛰기',
                    style: ds2.AppText.body.copyWith(
                      color: ds2.AppColor.inkTertiary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _controller,
                itemCount: _slides.length,
                onPageChanged: (int index) => setState(() => _page = index),
                itemBuilder: (BuildContext context, int index) =>
                    _SlideView(slide: _slides[index]),
              ),
            ),
            _Dots(count: _slides.length, active: _page),
            const SizedBox(height: ds2.AppSpace.lg),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                ds2.AppSpace.page,
                0,
                ds2.AppSpace.page,
                ds2.AppSpace.pageBottom,
              ),
              child: ds2.AppPrimaryButton(
                label: _isLast ? '시작하기' : '다음',
                accent: true,
                enabled: !_finishing,
                onPressed: _onNext,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SlideView extends StatelessWidget {
  const _SlideView({required this.slide});

  final _Slide slide;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: ds2.AppSpace.page),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: <Widget>[
          Container(
            width: 200,
            height: 200,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: ds2.AppColor.brandSoft,
              shape: BoxShape.circle,
            ),
            child: Image.asset(
              slide.assetPath,
              height: 160,
              fit: BoxFit.contain,
            ),
          ),
          const SizedBox(height: ds2.AppSpace.xxl),
          Text(
            slide.title,
            textAlign: TextAlign.center,
            style: ds2.AppText.display.copyWith(fontSize: 26),
          ),
          const SizedBox(height: ds2.AppSpace.lg),
          Text(
            slide.description,
            textAlign: TextAlign.center,
            style: ds2.AppText.bodyLg.copyWith(
              color: ds2.AppColor.inkSecondary,
            ),
          ),
          if (slide.showDisclaimer) ...<Widget>[
            const SizedBox(height: ds2.AppSpace.xl),
            const MedicalDisclaimer(variant: DisclaimerVariant.compact),
          ],
        ],
      ),
    );
  }
}

class _Dots extends StatelessWidget {
  const _Dots({required this.count, required this.active});

  final int count;
  final int active;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        for (int i = 0; i < count; i++)
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            margin: const EdgeInsets.symmetric(horizontal: ds2.AppSpace.xs),
            width: i == active ? 22 : 8,
            height: 8,
            decoration: BoxDecoration(
              color: i == active ? ds2.AppColor.brand : ds2.AppColor.border,
              borderRadius: BorderRadius.circular(ds2.AppRadius.full),
            ),
          ),
      ],
    );
  }
}
