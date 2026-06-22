import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/app.dart';

void main() {
  setUpAll(() async {
    final ByteData koreanFontData = _fontData(r'C:\Windows\Fonts\malgun.ttf');
    final ByteData iconFontData = _fontData(
      r'C:\src\flutter\bin\cache\artifacts\material_fonts\MaterialIcons-Regular.otf',
    );

    await (FontLoader('Roboto')
          ..addFont(Future<ByteData>.value(koreanFontData)))
        .load();
    await (FontLoader('MaterialIcons')
          ..addFont(Future<ByteData>.value(iconFontData)))
        .load();
  });

  testWidgets('home visual snapshot', (WidgetTester tester) async {
    _setPhoneViewport(tester);

    appRouter.go('/');
    await tester.pumpWidget(const ProviderScope(child: LemonAidApp()));
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(MaterialApp).first,
      matchesGoldenFile('goldens/current-home.png'),
    );
  });

  testWidgets('routine visual snapshot', (WidgetTester tester) async {
    _setPhoneViewport(tester);

    appRouter.go('/supplement-capture');
    await tester.pumpWidget(const ProviderScope(child: LemonAidApp()));
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(MaterialApp).first,
      matchesGoldenFile('goldens/current-routine.png'),
    );
  });

  testWidgets('analysis visual snapshot', (WidgetTester tester) async {
    _setPhoneViewport(tester);

    appRouter.go(
      '/entry-result'
      '?type=supplement'
      '&title=${Uri.encodeComponent('식단 + 영양제 통합 분석')}'
      '&subtitle=${Uri.encodeComponent('식단의 당과 탄수화물 조절을 먼저 잡고, 영양제는 식사 직후 복용 흐름으로 연결하면 오늘 루틴이 안정적입니다.')}'
      '&detail1=${Uri.encodeComponent('식단 주의: 탄수화물 양 조절')}'
      '&detail2=${Uri.encodeComponent('복용 연결: 식후 루틴 유지')}',
    );
    await tester.pumpWidget(const ProviderScope(child: LemonAidApp()));
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(MaterialApp).first,
      matchesGoldenFile('goldens/current-analysis.png'),
    );
  });
}

ByteData _fontData(String path) {
  final Uint8List bytes = File(path).readAsBytesSync();
  return ByteData.sublistView(bytes);
}

void _setPhoneViewport(WidgetTester tester) {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = const Size(430, 932);
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.view.resetPhysicalSize);
}
