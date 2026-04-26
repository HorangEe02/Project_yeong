import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { History } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { usePreferencesStore } from '@/stores/preferencesStore';
import { useNotificationPrefsStore } from '@/stores/notificationPrefsStore';
import { useHospital } from '@/contexts/HospitalContext';
import {
  CHANNEL_LABELS,
  CHANNEL_ORDER,
  SCENARIO_LABELS,
  SCENARIO_ORDER,
  type NotificationChannel,
  type NotificationEventType,
  type UserNotificationPrefs,
} from '@/types/notificationPrefs';

/**
 * 더보기 탭 — 환경설정 및 부가 기능 진입점.
 *
 * 카드 구성 (차례대로):
 *  1) 고령자 모드 — 앱 전체 글자/버튼 확대 토글
 *  2) 알림 설정 — 채널 4종 + 시나리오 7종 on/off + 전체 수신 거부
 *
 * UX 원칙:
 *  - 토글 즉시 반영 (save 버튼 없음)
 *  - 큰 hit box (고령자 친화)
 *  - revokedAt 설정 시 하위 섹션 opacity 낮춰 비활성 표시
 */
export function MoreTab() {
  const user = useAuthStore((s) => s.user);
  const uid = user && !user.isAnonymous ? user.uid : null;
  const { slug } = useHospital();

  // 고령자 모드
  const uiSenior = usePreferencesStore((s) => s.uiSenior);
  const setUiSenior = usePreferencesStore((s) => s.setUiSenior);

  // 알림 설정
  const notifInit = useNotificationPrefsStore((s) => s.init);
  const notifCleanup = useNotificationPrefsStore((s) => s.cleanup);
  useEffect(() => {
    notifInit(uid);
    return () => {
      notifCleanup();
    };
  }, [uid, notifInit, notifCleanup]);

  return (
    <section className="space-y-4 p-4">
      <h2 className="text-xl font-semibold text-on-surface">더보기</h2>

      {/* 고령자 모드 */}
      <article className="space-y-3 rounded-xl bg-surface-container-lowest p-5">
        <header className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-on-surface">고령자 모드</h3>
            <p className="mt-1 text-xs text-on-surface-variant">
              글자와 버튼 크기를 확대하고 줄 간격을 넓힙니다.
            </p>
          </div>
          <ToggleSwitch
            checked={uiSenior}
            onChange={() => void setUiSenior(uid, !uiSenior)}
            label="고령자 모드"
          />
        </header>

        <SamplePreview senior={uiSenior} />

        {!uid && (
          <p className="text-[11px] text-on-surface-variant">
            로그인 없이도 이 기기에서 설정이 유지됩니다. 로그인 후에는 계정 전체에 적용됩니다.
          </p>
        )}
      </article>

      {/* 알림 설정 */}
      <NotificationPrefsCard uid={uid} />

      {/* 방문 이력 (Phase I.4.3) */}
      <HistoryLinkCard slug={slug} />
    </section>
  );
}

/** 방문 이력 페이지 진입 카드. 인증 안 된 사용자도 링크는 보이지만 페이지가 ProtectedRoute. */
function HistoryLinkCard({ slug }: { slug: string }) {
  return (
    <article className="rounded-xl bg-surface-container-lowest p-5">
      <Link
        to={`/h/${slug}/patient/history`}
        data-testid="more-history-link"
        className="flex items-center justify-between gap-3 no-underline"
      >
        <div className="flex items-center gap-3">
          <History className="h-5 w-5 text-primary" aria-hidden="true" />
          <div>
            <h3 className="text-base font-semibold text-on-surface">방문 이력</h3>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              지난 방문 기록을 확인합니다.
            </p>
          </div>
        </div>
        <span className="text-xs text-on-surface-variant" aria-hidden="true">
          →
        </span>
      </Link>
    </article>
  );
}

function NotificationPrefsCard({ uid }: { uid: string | null }) {
  const prefs = useNotificationPrefsStore((s) => s.prefs);
  const initialized = useNotificationPrefsStore((s) => s.initialized);
  const error = useNotificationPrefsStore((s) => s.error);
  const setChannel = useNotificationPrefsStore((s) => s.setChannel);
  const setScenario = useNotificationPrefsStore((s) => s.setScenario);
  const revokeAll = useNotificationPrefsStore((s) => s.revokeAll);
  const restore = useNotificationPrefsStore((s) => s.restore);

  if (!uid) {
    return (
      <article className="space-y-3 rounded-xl bg-surface-container-lowest p-5">
        <header>
          <h3 className="text-base font-semibold text-on-surface">알림 설정</h3>
          <p className="mt-1 text-xs text-on-surface-variant">
            로그인 후 채널/시나리오별 on/off 를 설정할 수 있습니다.
          </p>
        </header>
      </article>
    );
  }

  const revoked = !!prefs.revokedAt;

  return (
    <article className="space-y-4 rounded-xl bg-surface-container-lowest p-5">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-on-surface">알림 설정</h3>
          <p className="mt-1 text-xs text-on-surface-variant">
            알림톡 · 앱 푸시 · SMS · 이메일 우선순위로 발송됩니다.
          </p>
        </div>
        <ToggleSwitch
          checked={!revoked}
          onChange={() => void (revoked ? restore(uid) : revokeAll(uid))}
          label={revoked ? '전체 알림 다시 받기' : '전체 알림 받기'}
        />
      </header>

      {!initialized && (
        <p className="text-xs text-on-surface-variant">설정 불러오는 중…</p>
      )}
      {error && (
        <p className="text-xs text-primary">{error}</p>
      )}

      <div className={revoked ? 'pointer-events-none opacity-40' : ''}>
        <section className="mt-2">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-on-surface-variant">
            채널
          </p>
          <ul className="space-y-2">
            {CHANNEL_ORDER.map((ch) => (
              <li key={ch} className="flex items-center justify-between">
                <span className="text-sm text-on-surface">{CHANNEL_LABELS[ch]}</span>
                <ToggleSwitch
                  checked={isChannelAllowed(prefs, ch)}
                  onChange={() =>
                    void setChannel(uid, ch, !isChannelAllowed(prefs, ch))
                  }
                  label={`${CHANNEL_LABELS[ch]} 수신`}
                />
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-5">
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-on-surface-variant">
            시나리오
          </p>
          <ul className="space-y-2">
            {SCENARIO_ORDER.map((sc) => (
              <li key={sc} className="flex items-center justify-between">
                <span className="text-sm text-on-surface">{SCENARIO_LABELS[sc]}</span>
                <ToggleSwitch
                  checked={isScenarioAllowed(prefs, sc)}
                  onChange={() =>
                    void setScenario(uid, sc, !isScenarioAllowed(prefs, sc))
                  }
                  label={`${SCENARIO_LABELS[sc]} 수신`}
                />
              </li>
            ))}
          </ul>
        </section>
      </div>

      {revoked && (
        <p className="rounded-lg bg-surface-container-low p-3 text-xs text-on-surface-variant">
          전체 알림이 거부된 상태입니다. 다시 받으려면 위 스위치를 켜주세요.
        </p>
      )}
    </article>
  );
}

/** 기본값: pref 에서 false 명시되지 않으면 ON. */
function isChannelAllowed(
  prefs: UserNotificationPrefs,
  channel: NotificationChannel,
): boolean {
  return prefs.channels?.[channel] !== false;
}
function isScenarioAllowed(
  prefs: UserNotificationPrefs,
  scenario: NotificationEventType,
): boolean {
  return prefs.scenarios?.[scenario] !== false;
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
      className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors ${
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
