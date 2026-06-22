import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/core/config/app_environment.dart';

void main() {
  test('resolves production aliases', () {
    expect(AppEnvironment.fromName('prod'), AppEnvironment.prod);
    expect(AppEnvironment.fromName('production'), AppEnvironment.prod);
  });

  test('resolves staging aliases', () {
    expect(AppEnvironment.fromName('staging'), AppEnvironment.staging);
    expect(AppEnvironment.fromName('stage'), AppEnvironment.staging);
  });

  test('resolves dev aliases', () {
    expect(AppEnvironment.fromName('dev'), AppEnvironment.dev);
    expect(AppEnvironment.fromName('development'), AppEnvironment.dev);
  });

  test('is case-insensitive and trims whitespace', () {
    expect(AppEnvironment.fromName('  PROD  '), AppEnvironment.prod);
    expect(AppEnvironment.fromName('Staging'), AppEnvironment.staging);
  });

  test('falls back to dev for blank or unknown values', () {
    expect(AppEnvironment.fromName(''), AppEnvironment.dev);
    expect(AppEnvironment.fromName('   '), AppEnvironment.dev);
    expect(AppEnvironment.fromName('qa'), AppEnvironment.dev);
  });

  test('marks only non-local environments as remote', () {
    expect(AppEnvironment.dev.isRemote, isFalse);
    expect(AppEnvironment.staging.isRemote, isTrue);
    expect(AppEnvironment.prod.isRemote, isTrue);
  });
}
