import 'dart:io' show Platform;

import 'package:device_info_plus/device_info_plus.dart';

/// Cached device classification used by camera smoke flows.
final class DeviceEnv {
  DeviceEnv._();

  static bool? _isEmulatorCache;

  /// Whether the current Android/iOS runtime is an emulator or simulator.
  ///
  /// Returns:
  ///   `true` for Android emulators and iOS simulators, otherwise `false`.
  static Future<bool> get isEmulator async {
    final bool? cached = _isEmulatorCache;
    if (cached != null) {
      return cached;
    }
    final DeviceInfoPlugin plugin = DeviceInfoPlugin();
    try {
      if (Platform.isAndroid) {
        final AndroidDeviceInfo info = await plugin.androidInfo;
        _isEmulatorCache = !info.isPhysicalDevice;
      } else if (Platform.isIOS) {
        final IosDeviceInfo info = await plugin.iosInfo;
        _isEmulatorCache = !info.isPhysicalDevice;
      } else {
        _isEmulatorCache = false;
      }
    } catch (_) {
      _isEmulatorCache = false;
    }
    return _isEmulatorCache!;
  }

  /// Synchronous cached value for widget initialization.
  static bool get isEmulatorSync => _isEmulatorCache ?? false;

  /// Populates the cache during app startup or screen initialization.
  static Future<void> warmUp() async {
    await isEmulator;
  }
}
