flutter run \
  --dart-define=KAKAO_NATIVE_APP_KEY=받은_카카오_키 \
  --dart-define=GOOGLE_SERVER_CLIENT_ID=받은_구글_키.apps.googleusercontent.com \
  --dart-define=API_BASE_URL=http://localhost:8000

빌드 실패시에는 flutter clean
flutter pub get
flutter run