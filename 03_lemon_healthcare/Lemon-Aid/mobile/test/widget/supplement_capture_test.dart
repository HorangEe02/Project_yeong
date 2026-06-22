import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_flow_screen.dart';

void main() {
  testWidgets('label preview preserves the full selected image', (
    WidgetTester tester,
  ) async {
    final File image = _writeTinyPng();
    addTearDown(() {
      if (image.existsSync()) {
        image.deleteSync();
      }
    });

    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 393,
          height: 852,
          child: SupplementLabelPreviewFrame(imagePath: image.path),
        ),
      ),
    );

    final Image previewImage = tester.widget<Image>(find.byType(Image));

    expect(previewImage.fit, BoxFit.contain);
    expect(find.byType(InteractiveViewer), findsOneWidget);
  });
}

File _writeTinyPng() {
  final Directory directory = Directory.systemTemp.createTempSync(
    'lemon-aid-preview-test-',
  );
  final File file = File('${directory.path}/label.png');
  addTearDown(() {
    if (directory.existsSync()) {
      directory.deleteSync(recursive: true);
    }
  });
  file.writeAsBytesSync(
    base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
    ),
  );
  return file;
}
