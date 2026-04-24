/**
 * 외래 탭 — 예약 + 접수.
 *
 * 현 step(B-1 / step 3): placeholder.
 * 후속 step에서 채울 항목:
 * - `/hospitals/{hid}/appointments_by_patient/{uid}` 구독
 * - 예약 카드 리스트 + 접수 버튼
 * - `+ 새 예약` 폼
 */
export function AppointmentsTab() {
  return (
    <section className="space-y-4 p-4">
      <h2 className="text-xl font-semibold text-on-surface">외래</h2>
      <p className="text-sm text-on-surface-variant">
        예약 목록과 새 예약 양식이 이곳에 표시될 예정입니다.
      </p>
    </section>
  );
}
