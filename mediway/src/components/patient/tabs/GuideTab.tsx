/**
 * 안내 탭 — placeholder.
 *
 * 후속 step 범위: 병원 내부 지도 + POI + zoom/pan 상태 보존 (mount-all pattern 검증 대상).
 * e2e-tab-session.html 시나리오 B 대응.
 */
export function GuideTab() {
  return (
    <section className="space-y-4 p-4">
      <h2 className="text-xl font-semibold text-on-surface">안내</h2>
      <p className="text-sm text-on-surface-variant">병원 내부 지도와 주요 위치가 이곳에 표시될 예정입니다.</p>
    </section>
  );
}
