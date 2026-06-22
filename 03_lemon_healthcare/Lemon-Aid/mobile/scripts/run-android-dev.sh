#!/usr/bin/env bash
set -euo pipefail

# This Mac can have Docker occupying the default emulator adb port pair
# 5554/5555, so the local Android Studio smoke path uses emulator-5560.
DEVICE_ID="${DEVICE_ID:-${1:-emulator-5560}}"
API_BASE_URL="${LEMON_API_BASE_URL:-http://10.0.2.2:8000/api/v1}"

# Pair the `dev` product flavor with the matching Dart environment so the
# native app id (.dev) and the backend URL selection stay in lock-step.
flutter run -d "${DEVICE_ID}" --flavor dev \
  --dart-define="LEMON_APP_ENV=dev" \
  --dart-define="LEMON_API_BASE_URL=${API_BASE_URL}"
