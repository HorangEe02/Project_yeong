import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/utils/mascot_poses.dart';

void main() {
  test('timedRandom keeps one pose inside the same time bucket', () {
    final DateTime first = DateTime(2026, 5, 26, 9, 0);
    final DateTime second = DateTime(2026, 5, 26, 9, 4, 59);

    expect(MascotFor.timedRandom(first), MascotFor.timedRandom(second));
  });

  test('timedRandom rotates across later time buckets', () {
    final Set<MascotPose> poses = <MascotPose>{
      for (int index = 0; index < 30; index += 1)
        MascotFor.timedRandom(DateTime(2026, 5, 26, 9, index * 5)),
    };

    expect(poses.length, greaterThan(1));
    expect(poses.difference(MascotPose.values.toSet()), isEmpty);
  });

  test('timedRandom rejects non-positive intervals', () {
    expect(
      () =>
          MascotFor.timedRandom(DateTime(2026, 5, 26), interval: Duration.zero),
      throwsArgumentError,
    );
  });
}
