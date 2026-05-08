// G2: 알림 환경설정 페이지.
// URL: /profile/notifications
//
// Design System v2 정합:
//   - bilingual eyebrow (NOTIFICATION SETTINGS · 알림 설정)
//   - 1px hairline 카드 + 2px radius
//   - 골드 액센트 (--hud-primary) + label-en/label-ko 패턴

import { useEffect, useState } from 'react';
import {
  fetchMyPrefs,
  sendTestNotification,
  updateMyPrefs,
  type NotificationPrefs,
} from '@api/notifications';

export function ProfileNotifications() {
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);
  const [email, setEmail] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMyPrefs()
      .then((p) => {
        setEmail(p.email);
        const { user_id: _uid, email: _em, ...rest } = p;
        setPrefs(rest);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : '로드 실패');
      });
  }, []);

  if (error) {
    return (
      <div className="page lg-page">
        <p className="lg-error">⚠ {error}</p>
      </div>
    );
  }
  if (!prefs) {
    return (
      <div className="page lg-page">
        <div className="lg-empty">로드 중…</div>
      </div>
    );
  }

  const update = <K extends keyof NotificationPrefs>(
    k: K,
    v: NotificationPrefs[K],
  ) => setPrefs({ ...prefs, [k]: v });

  const save = async () => {
    setSaving(true);
    setMsg('');
    try {
      const r = await updateMyPrefs(prefs);
      setEmail(r.email);
      setMsg('저장됨');
    } catch (e) {
      setMsg(`저장 실패: ${e instanceof Error ? e.message : e}`);
    } finally {
      setSaving(false);
    }
  };

  const sendTest = async () => {
    setMsg('');
    try {
      await sendTestNotification();
      setMsg('테스트 메일이 발송 큐에 적재되었습니다 (1~2분 후 도착).');
    } catch (e) {
      setMsg(`테스트 실패: ${e instanceof Error ? e.message : e}`);
    }
  };

  return (
    <div className="page lg-page" data-screen-label="Profile · Notifications">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">NOTIFICATION SETTINGS · PROFILE</div>
        <h1 className="lg-display">알림 설정</h1>
        <p className="lg-sub">
          수신 메일: <strong>{email || '—'}</strong>
        </p>
      </section>

      <section className="lg-card lg-prefs-section">
        <h3>
          <span className="label-en">CHANNELS</span>
          <span className="label-ko"> · 채널</span>
        </h3>
        <label className="lg-pref-row">
          <input
            type="checkbox"
            checked={prefs.enabled}
            onChange={(e) => update('enabled', e.target.checked)}
          />
          <span>알림 사용</span>
        </label>
        <label className="lg-pref-row">
          <input
            type="checkbox"
            checked={prefs.channel_email}
            onChange={(e) => update('channel_email', e.target.checked)}
          />
          <span>이메일</span>
        </label>
        <label className="lg-pref-row dim">
          <input type="checkbox" disabled checked={prefs.channel_slack} />
          <span>Slack (차분기 지원)</span>
        </label>
      </section>

      <section className="lg-card lg-prefs-section">
        <h3>
          <span className="label-en">SEVERITY THRESHOLD</span>
          <span className="label-ko"> · 심각도 임계값</span>
        </h3>
        <select
          className="lg-select"
          value={prefs.severity_threshold}
          onChange={(e) => update('severity_threshold', e.target.value as never)}
        >
          <option value="LOW">LOW 이상 — 모든 변경</option>
          <option value="MEDIUM">MEDIUM 이상</option>
          <option value="HIGH">HIGH 이상 (권장)</option>
          <option value="CRITICAL">CRITICAL 만</option>
        </select>
        <p className="dim small">
          선택한 심각도 미만의 변경은 일일 다이제스트로만 발송됩니다.
        </p>
      </section>

      <section className="lg-card lg-prefs-section">
        <h3>
          <span className="label-en">DAILY DIGEST</span>
          <span className="label-ko"> · 일일 다이제스트</span>
        </h3>
        <label className="lg-pref-row">
          <input
            type="checkbox"
            checked={prefs.digest_enabled}
            onChange={(e) => update('digest_enabled', e.target.checked)}
          />
          <span>매일 다이제스트 받기</span>
        </label>
        <label className="lg-pref-row">
          <span>발송 시각 (KST)</span>
          <input
            type="number"
            min={0}
            max={23}
            className="lg-input-num"
            value={prefs.digest_hour_kst}
            onChange={(e) =>
              update('digest_hour_kst', Math.max(0, Math.min(23, Number(e.target.value))))
            }
          />
          <span className="dim mono">:00</span>
        </label>
      </section>

      <section className="lg-card lg-prefs-section">
        <h3>
          <span className="label-en">FILTERS</span>
          <span className="label-ko"> · 필터</span>
        </h3>
        <label className="lg-pref-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
          <span className="label-en">PLANTS · 관심 시설 (쉼표 구분, 비우면 전체)</span>
          <input
            className="lg-search-input"
            type="text"
            value={(prefs.plant_filter || []).join(',')}
            onChange={(e) =>
              update(
                'plant_filter',
                e.target.value
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean),
              )
            }
            placeholder="KSN-1, KJ-2"
          />
        </label>
        <label className="lg-pref-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
          <span className="label-en">DEPARTMENT · 관심 부서</span>
          <select
            className="lg-select"
            value={prefs.department_filter || ''}
            onChange={(e) => update('department_filter', e.target.value || null)}
          >
            <option value="">전체</option>
            <option value="EHS">환경안전</option>
            <option value="Quality">품질</option>
            <option value="Procurement">구매</option>
            <option value="Production">생산</option>
          </select>
        </label>
      </section>

      <div className="lg-prefs-actions">
        <button className="lg-btn lg-btn-primary" onClick={save} disabled={saving}>
          {saving ? '저장 중…' : '저장'}
        </button>
        <button className="lg-btn" onClick={sendTest}>
          테스트 메일 보내기
        </button>
        {msg && <span className="dim">{msg}</span>}
      </div>
    </div>
  );
}

export default ProfileNotifications;
