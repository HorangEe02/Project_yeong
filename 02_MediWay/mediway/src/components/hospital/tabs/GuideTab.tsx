import { PatientPage } from '@/pages/PatientPage';

/**
 * 안내 탭 — 기존 PatientPage (지도·QR·방문 계획)를 대시보드 탭으로 흡수.
 *
 * 전략 (v2 §Phase 2 "기존 가치 보존"):
 * - Wrapper 접근 — PatientPage를 그대로 렌더. 코드 복제 없음, 레거시
 *   /patient · /h/:slug/patient 라우트도 동일 컴포넌트로 동작 유지.
 * - PatientPage 내부는 `?mode=browse|guide` 서브 탭을 자체 관리.
 *   외부 상위 `?tab=guide`와 query param 공존 가능 (useSearchParams 병합).
 * - sessionId param (`:sessionId`)가 없는 /home 경로에서는 PatientPage가
 *   기본 "guide" 모드로 진입 — QR 스캔을 안내 탭 진입 시 기본 화면으로.
 *
 * 세션 유지: 상위 HospitalHomePage가 Mount-all + hidden 전략을 사용하므로
 *   탭 전환 시에도 DOM·훅 상태 유지. 다만 `hidden` 속성이 `display:none`
 *   효과를 내면서 `<video>` stream을 중단시킬 수 있음 — 이 위험은 C9에서
 *   E2E로 검증하고, 필요 시 `visibility:hidden + position:absolute` 패턴
 *   으로 전환 예정.
 */
export function GuideTab() {
  return <PatientPage />;
}
