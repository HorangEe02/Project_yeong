import { useAuthStore } from '@/stores/authStore';
import { usePreferencesStore } from '@/stores/preferencesStore';

/**
 * 더보기 탭 — 환경설정 및 부가 기능 진입점.
 *
 * 현 step (B-2 / step 8b): 고령자 모드 토글 + 미리보기 샘플.
 * 후속 step 에서 추가 예정: 알림 설정, 문의/피드백, 이용약관 등.
 *
 * UX 원칙 (사용자 편의 중심):
 *  - 토글은 큰 hit box + 명확한 ON/OFF — 노인층 탭 실수 최소화
 *  - 토글 옆 샘플 미리보기 — ON 결과를 시각적으로 확인 가능
 *  - 변경 즉시 반영 — root body.ui-senior class 갱신 (App.tsx effect)
 *  - 로그인 필요 없음 — localStorage fallback 으로 익명도 동작
 */
export function MoreTab() {
  const user = useAuthStore((s) => s.user);
  const uiSenior = usePreferencesStore((s) => s.uiSenior);
  const setUiSenior = usePreferencesStore((s) => s.setUiSenior);

  const uid = user && !user.isAnonymous ? user.uid : null;

  const toggle = () => {
    void setUiSenior(uid, !uiSenior);
  };

  return (
    <section className="space-y-4 p-4">
      <h2 className="text-xl font-semibold text-on-surface">더보기</h2>

      <article className="space-y-3 rounded-xl bg-surface-container-lowest p-5">
        <header className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-on-surface">고령자 모드</h3>
            <p className="mt-1 text-xs text-on-surface-variant">
              글자와 버튼 크기를 확대하고 줄 간격을 넓힙니다.
            </p>
          </div>
          <ToggleSwitch checked={uiSenior} onChange={toggle} label="고령자 모드" />
        </header>

        <SamplePreview senior={uiSenior} />

        {!uid && (
          <p className="text-[11px] text-on-surface-variant">
            로그인 없이도 이 기기에서 설정이 유지됩니다. 로그인 후에는 계정 전체에 적용됩니다.
          </p>
        )}
      </article>
    </section>
  );
}

function ToggleSwitch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={onChange}
      className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
        checked ? 'bg-primary' : 'bg-surface-container-high'
      }`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-ambient-sm transition-transform ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

/**
 * 토글이 ON 일 때 body.ui-senior 가 붙어 자동 확대되므로
 * 여기는 별도 inline style 없이 고유 샘플 텍스트만 표시.
 * 미리보기는 실제 UI 변화를 그대로 보여준다 (WYSIWYG).
 */
function SamplePreview({ senior }: { senior: boolean }) {
  return (
    <div className="rounded-lg bg-surface-container-low p-4">
      <p className="text-xs font-medium uppercase tracking-wider text-on-surface-variant">
        미리보기
      </p>
      <p className="mt-1 text-sm text-on-surface">
        좋은 오후입니다, 박준영님. 내과 순번 1번, 대기 중입니다.
      </p>
      <button
        type="button"
        className="mt-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-on-primary"
        onClick={(e) => e.preventDefault()}
      >
        진료 시작
      </button>
      {!senior && (
        <p className="mt-2 text-[11px] text-on-surface-variant">
          스위치를 켜면 글자가 커지고 버튼이 더 눌리기 쉬워집니다.
        </p>
      )}
    </div>
  );
}
