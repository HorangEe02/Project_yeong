/// SourceSelector 위젯 테스트 — 카메라/갤러리 탭 콜백.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/features/supplement/presentation/widgets/source_selector.dart';

void main() {
  testWidgets('카메라 카드 탭 → onCamera 호출', (WidgetTester tester) async {
    bool cameraTapped = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SourceSelector(
            onCamera: () => cameraTapped = true,
            onGallery: () {},
          ),
        ),
      ),
    );

    await tester.tap(find.text('카메라로 촬영'));
    await tester.pump();
    expect(cameraTapped, isTrue);
  });

  testWidgets('갤러리 카드 탭 → onGallery 호출', (WidgetTester tester) async {
    bool galleryTapped = false;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SourceSelector(
            onCamera: () {},
            onGallery: () => galleryTapped = true,
          ),
        ),
      ),
    );

    await tester.tap(find.text('갤러리에서 선택'));
    await tester.pump();
    expect(galleryTapped, isTrue);
  });

  testWidgets('안내 문구 표시', (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SourceSelector(onCamera: () {}, onGallery: () {}),
        ),
      ),
    );

    expect(find.text('영양제 라벨 사진을 등록해주세요'), findsOneWidget);
    expect(
      find.text('제품명, 성분, 함량이 잘 보이는 사진을 선택해주세요.'),
      findsOneWidget,
    );
  });
}
