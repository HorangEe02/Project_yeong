// W4 (P2) — 현장 모드 PWA 라우트 `/equipment/field`.
// 라인 작업자가 태블릿/스마트폰에서 사용. 큰 버튼, 폰트 1.2x, 데일리 헤드라인 + 활성 알람만 노출.
// PWA: public/manifest.webmanifest 와 index.html 의 link rel="manifest" 로 install 가능.

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ChevronRight, RefreshCcw, Send, Upload } from 'lucide-react';
import {
  fetchHeadline,
  fetchOverview,
  submitInspection,
  type InspectionSubmitPayload,
} from '@api/equipment';
import type { HeadlineResponse, OverviewResponse, ProcessHealthCard } from '@/types/equipment';
import { enqueueInspection, flushQueue, pendingCount } from '@/utils/inspectionOfflineQueue';

export function EquipmentField() {
  const navigate = useNavigate();
  const [headline, setHeadline] = useState<HeadlineResponse | null>(null);
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // v4.3 A12 — offline queue 상태
  const [pendingN, setPendingN] = useState(0);
  const [flushing, setFlushing] = useState(false);
  const [queueMessage, setQueueMessage] = useState<string | null>(null);
  const [equipmentId, setEquipmentId] = useState('PR-101');
  const [templateId, setTemplateId] = useState('1');
  const [overallStatus, setOverallStatus] = useState<InspectionSubmitPayload['overall_status']>('PASS');
  const [note, setNote] = useState('');
  const [submittingInspection, setSubmittingInspection] = useState(false);

  const refreshPending = useCallback(async () => {
    try {
      setPendingN(await pendingCount());
    } catch {
      /* IndexedDB 미지원 환경 */
    }
  }, []);

  useEffect(() => {
    void refreshPending();
    const id = window.setInterval(() => { void refreshPending(); }, 30_000);
    const onOnline = () => { void handleFlush(); };
    window.addEventListener('online', onOnline);
    return () => {
      window.clearInterval(id);
      window.removeEventListener('online', onOnline);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFlush = useCallback(async () => {
    if (flushing) return;
    setFlushing(true);
    try {
      const result = await flushQueue();
      await refreshPending();
      setQueueMessage(
        `전송 ${result.attempted}건 · 성공 ${result.succeeded}건 · 실패 ${result.failed}건 · 보류 ${result.skipped}건 · 확인필요 ${result.dead_letter}건 · 대기 ${result.remaining}건`,
      );
      console.info('[inspection-queue] flush', result);
    } finally {
      setFlushing(false);
    }
  }, [flushing, refreshPending]);

  const handleQuickInspectionSubmit = useCallback(async () => {
    if (submittingInspection) return;
    const cleanEquipmentId = equipmentId.trim();
    const parsedTemplateId = Number(templateId);
    if (!cleanEquipmentId) {
      setQueueMessage('설비 ID를 입력하세요.');
      return;
    }
    if (!Number.isInteger(parsedTemplateId) || parsedTemplateId < 1) {
      setQueueMessage('템플릿 ID는 1 이상의 숫자여야 합니다.');
      return;
    }

    const payload: InspectionSubmitPayload = {
      equipment_id: cleanEquipmentId,
      template_id: parsedTemplateId,
      inspection_date: new Date().toISOString().slice(0, 10),
      results: [],
      overall_status: overallStatus,
      note: note.trim() || undefined,
    };

    setSubmittingInspection(true);
    try {
      if (!navigator.onLine) {
        await enqueueInspection(payload);
        await refreshPending();
        setQueueMessage('오프라인 상태라 점검 제출을 대기 큐에 저장했습니다.');
        return;
      }

      try {
        await submitInspection(payload);
        setNote('');
        await refreshPending();
        setQueueMessage('점검 제출이 완료되었습니다.');
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status) {
          setQueueMessage(`점검 제출 실패: HTTP ${status}`);
          return;
        }
        await enqueueInspection(payload);
        await refreshPending();
        setQueueMessage('네트워크 오류로 점검 제출을 대기 큐에 저장했습니다.');
      }
    } finally {
      setSubmittingInspection(false);
    }
  }, [equipmentId, note, overallStatus, refreshPending, submittingInspection, templateId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([fetchHeadline(), fetchOverview()])
      .then(([h, o]) => {
        if (!active) return;
        setHeadline(h);
        setOverview(o);
      })
      .catch((e: unknown) => active && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [reloadKey]);

  // 5초 간격 자동 새로고침 (현장은 끊김 없는 알람 확인 필요)
  useEffect(() => {
    const t = window.setInterval(() => setReloadKey((k) => k + 1), 5000);
    return () => window.clearInterval(t);
  }, []);

  // 위반 vibration (브라우저 허용 시)
  useEffect(() => {
    if (!headline) return;
    const crit = headline.items.some((i) => i.severity === 'critical');
    if (crit && typeof navigator.vibrate === 'function') {
      try {
        navigator.vibrate([100, 60, 100]);
      } catch {
        /* noop */
      }
    }
  }, [headline]);

  const summarySeverity =
    headline?.items?.find((i) => i.severity === 'critical')
      ? 'critical'
      : headline?.items?.find((i) => i.severity === 'warning')
        ? 'warning'
        : 'normal';
  const summaryColor =
    summarySeverity === 'critical' ? '#dc2626' : summarySeverity === 'warning' ? '#d97706' : '#16a34a';

  return (
    <div
      data-field-mode="true"
      style={{
        minHeight: '100vh',
        background: 'var(--hud-bg, #0b0d10)',
        color: 'var(--hud-text, #e6e9ee)',
        padding: '20px 18px 28px',
        fontSize: 16, // base 1.2x of normal 14
      }}
    >
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 14,
        }}
      >
        <button
          type="button"
          onClick={() => navigate('/equipment')}
          style={largeIconBtn}
          aria-label="전체 화면으로"
        >
          <ArrowLeft size={20} />
        </button>
        <div style={{ flex: 1, textAlign: 'center' }}>
          <div style={{ fontSize: 11, opacity: 0.65, letterSpacing: '0.08em' }}>
            FIELD MODE · 현장 모드
          </div>
          <div style={{ fontSize: 18, fontWeight: 700, marginTop: 2 }}>
            설비 AI 라인 모니터
          </div>
        </div>
        <button
          type="button"
          onClick={() => setReloadKey((k) => k + 1)}
          style={largeIconBtn}
          aria-label="새로고침"
          disabled={loading}
        >
          <RefreshCcw size={20} style={loading ? { animation: 'spin 1s linear infinite' } : {}} />
        </button>
      </header>

      {/* 헤드라인 */}
      <section
        style={{
          borderRadius: 16,
          padding: 18,
          background: `color-mix(in oklab, ${summaryColor} 10%, transparent)`,
          border: `2px solid color-mix(in oklab, ${summaryColor} 50%, transparent)`,
          marginBottom: 16,
        }}
      >
        <div style={{ fontSize: 11, opacity: 0.7, letterSpacing: '0.06em' }}>
          DAILY HEADLINE
        </div>
        <div
          style={{
            marginTop: 6,
            fontSize: 19,
            fontWeight: 700,
            lineHeight: 1.4,
            color: summaryColor,
          }}
        >
          {loading && !headline ? '집계 중…' : error ? '집계 실패' : (headline?.summary ?? '신호 없음')}
        </div>
        {error && (
          <div style={{ marginTop: 6, fontSize: 13, color: '#fecaca' }}>{error}</div>
        )}
        {headline && (
          <div style={{ marginTop: 10, fontSize: 13, opacity: 0.8 }}>
            활성 알람 <b>{headline.active_alarm_count}</b>건 · 갱신 {headline.generated_at.slice(11, 19)}
          </div>
        )}
      </section>

      {/* 5공정 큰 카드 */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ fontSize: 11, opacity: 0.7, letterSpacing: '0.06em', padding: '0 2px' }}>
          5공정 상태
        </div>
        {(overview?.processes ?? []).map((p) => (
          <ProcessRow key={p.process_id} p={p} />
        ))}
        {!overview && loading && <SkeletonRow />}
      </section>

      <section
        style={{
          marginTop: 18,
          padding: '14px',
          borderRadius: 10,
          border: '1px solid color-mix(in oklab, var(--hud-text, #fff) 14%, transparent)',
          background: 'color-mix(in oklab, var(--hud-surface, #1a1c20) 82%, transparent)',
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>
          빠른 점검 제출
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1.2fr) minmax(80px, 0.6fr) minmax(110px, 0.8fr)',
            gap: 8,
          }}
        >
          <label style={fieldLabel}>
            <span style={labelText}>설비 ID</span>
            <input
              value={equipmentId}
              onChange={(e) => setEquipmentId(e.target.value)}
              style={fieldInput}
              autoComplete="off"
            />
          </label>
          <label style={fieldLabel}>
            <span style={labelText}>템플릿</span>
            <input
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
              inputMode="numeric"
              style={fieldInput}
            />
          </label>
          <label style={fieldLabel}>
            <span style={labelText}>결과</span>
            <select
              value={overallStatus}
              onChange={(e) => setOverallStatus(e.target.value as InspectionSubmitPayload['overall_status'])}
              style={fieldInput}
            >
              <option value="PASS">PASS</option>
              <option value="WARN">WARN</option>
              <option value="FAIL">FAIL</option>
            </select>
          </label>
        </div>
        <label style={{ ...fieldLabel, marginTop: 8 }}>
          <span style={labelText}>메모</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            style={{ ...fieldInput, resize: 'vertical', minHeight: 72 }}
          />
        </label>
        <button
          type="button"
          onClick={() => void handleQuickInspectionSubmit()}
          disabled={submittingInspection}
          style={{
            ...primaryActionBtn,
            cursor: submittingInspection ? 'wait' : 'pointer',
            opacity: submittingInspection ? 0.75 : 1,
          }}
        >
          <Send size={16} aria-hidden />
          {submittingInspection ? '저장 중…' : '점검 제출'}
        </button>
        {queueMessage && (
          <div style={{ marginTop: 8, fontSize: 12, color: '#cbd5e1' }}>{queueMessage}</div>
        )}
      </section>

      {pendingN > 0 && (
        <section
          style={{
            marginTop: 18,
            padding: '12px 14px',
            borderRadius: 8,
            border: '1px solid #d97706',
            background: 'color-mix(in oklab, #d97706 12%, transparent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#d97706' }}>
              점검 제출 대기 {pendingN}건
            </div>
            <div style={{ fontSize: 11, opacity: 0.7, marginTop: 2 }}>
              네트워크 복귀 시 자동 업로드. 즉시 시도하려면 옆 버튼 사용.
            </div>
          </div>
          <button
            type="button"
            onClick={() => void handleFlush()}
            disabled={flushing}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '10px 14px',
              borderRadius: 8,
              border: '1px solid #d97706',
              background: 'transparent',
              color: '#d97706',
              fontWeight: 700,
              cursor: flushing ? 'wait' : 'pointer',
            }}
            aria-label="대기 큐 업로드"
          >
            <Upload size={16} aria-hidden />
            {flushing ? '전송 중…' : '지금 전송'}
          </button>
        </section>
      )}

      <div style={{ marginTop: 22, textAlign: 'center', fontSize: 11, opacity: 0.5 }}>
        화면을 홈에 추가하면 PWA로 사용 가능 — Chrome/Safari 메뉴에서 “홈 화면에 추가”
      </div>
    </div>
  );
}

function ProcessRow({ p }: { p: ProcessHealthCard }) {
  const cpk = p.current_cpk ?? 0;
  const color = cpk < 1.0 ? '#dc2626' : cpk < 1.33 ? '#d97706' : '#16a34a';
  const status = cpk < 1.0 ? '즉시 정지 검토' : cpk < 1.33 ? '점검 필요' : '정상';

  return (
    <div
      style={{
        padding: '16px 18px',
        borderRadius: 14,
        background: 'color-mix(in oklab, var(--hud-surface, #1a1c20) 70%, transparent)',
        border: `1px solid color-mix(in oklab, ${color} 30%, transparent)`,
        borderLeft: `6px solid ${color}`,
        display: 'flex',
        alignItems: 'center',
        gap: 14,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 17, fontWeight: 700, lineHeight: 1.2 }}>{p.process_name}</div>
        <div style={{ marginTop: 4, fontSize: 13, opacity: 0.75 }}>
          {status} · 위반 {p.violation_count}건
          {p.violated_rules?.length ? ` (Rule ${p.violated_rules.slice(0, 3).join(',')})` : ''}
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div style={{ fontFamily: 'ui-monospace, monospace', fontSize: 22, fontWeight: 700, color }}>
          {cpk.toFixed(2)}
        </div>
        <div style={{ fontSize: 10, opacity: 0.6 }}>Cpk</div>
      </div>
      <ChevronRight size={18} style={{ opacity: 0.45, flexShrink: 0 }} />
    </div>
  );
}

function SkeletonRow() {
  return (
    <div
      style={{
        height: 70,
        borderRadius: 14,
        background: 'color-mix(in oklab, var(--hud-text, #fff) 6%, transparent)',
        animation: 'pulse 1.4s ease-in-out infinite',
      }}
    />
  );
}

const largeIconBtn: React.CSSProperties = {
  minWidth: 48,
  minHeight: 48,
  borderRadius: 12,
  border: '1px solid color-mix(in oklab, var(--hud-text, #fff) 18%, transparent)',
  background: 'transparent',
  color: 'var(--hud-text, #fff)',
  display: 'grid',
  placeItems: 'center',
  cursor: 'pointer',
};

const fieldLabel: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
};

const labelText: React.CSSProperties = {
  fontSize: 11,
  opacity: 0.68,
};

const fieldInput: React.CSSProperties = {
  width: '100%',
  borderRadius: 8,
  border: '1px solid color-mix(in oklab, var(--hud-text, #fff) 18%, transparent)',
  background: 'color-mix(in oklab, var(--hud-bg, #0b0d10) 70%, transparent)',
  color: 'var(--hud-text, #fff)',
  padding: '10px 11px',
  fontSize: 14,
  boxSizing: 'border-box',
};

const primaryActionBtn: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 8,
  width: '100%',
  marginTop: 10,
  minHeight: 44,
  borderRadius: 8,
  border: '1px solid #16a34a',
  background: '#16a34a',
  color: '#fff',
  fontWeight: 700,
};
