/**
 * 사용자 환경설정.
 * RTDB path: `/users/{uid}/preferences`
 *
 * 필드는 모두 optional — 미설정 시 기본값 (대부분 false / '기본' 모드).
 * 확장 여지: 알림 수신 toggles, 언어, 테마 등.
 */
export interface UserPreferences {
  /**
   * 고령자 모드 — root `<body>` 에 `.ui-senior` 클래스 부착.
   * CSS 가 폰트 크기 · 버튼 최소 높이 · 줄 간격을 확대.
   */
  uiSenior?: boolean;
}
