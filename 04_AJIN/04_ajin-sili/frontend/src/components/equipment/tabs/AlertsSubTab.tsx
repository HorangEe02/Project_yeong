// AlertsSubTab — F-alerts 서브탭 (긴급 조치 큐).
// W2 (P0) — 액션 3개 라우팅: Acknowledge / 8D Report 시작 / 관련 SOP 보기.

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, FileText, BookOpen } from 'lucide-react';

interface Alert {
  id: string;
  severity: 'crit' | 'warn';
  title: string;
  detail: string;
  ago: string;
  sopHint?: string;        // /chat prefill 시 SOP 키워드
  draftPrefill: string;    // /draft prefill 본문
}

const ALERTS: Alert[] = [
  {
    id: 'alert-paint-1',
    severity: 'crit',
    title: '도장 #1',
    detail: 'Cpk 0.89 · Nelson Rule 1·2·5 위반',
    ago: '14분 전',
    sopHint: '도장 라인 Cpk 0.89, Nelson Rule 1·2·5 발생 시 절차를 알려주세요.',
    draftPrefill:
      '[도장 #1] SPC 위반\n- 공정: 도장 #1\n- 현재 Cpk: 0.89 (목표 1.33)\n- 위반 Nelson Rule: 1, 2, 5\n- 발생: 14분 전\n\n위 위반에 대한 8D Report 초안을 작성해 주세요.',
  },
  {
    id: 'alert-weld-2',
    severity: 'warn',
    title: '용접 #2',
    detail: 'Cpk 1.18 · 평균 이동 감지 (Rule 2)',
    ago: '32분 전',
    sopHint: '용접 너겟 평균 이동이 감지된 경우 즉시 점검 절차?',
    draftPrefill:
      '[용접 #2] 평균 이동 감지\n- 공정: 용접 #2\n- 현재 Cpk: 1.18\n- 위반 Nelson Rule: 2 (9점 연속 편향)\n- 발생: 32분 전\n\n원인 분석 및 컨테인먼트 액션 8D Report 초안을 작성해 주세요.',
  },
  {
    id: 'alert-mold-md007',
    severity: 'warn',
    title: 'MD-007 (OBC-RR)',
    detail: '잔여 사이클 15,000 (XGBoost 예측 D-3)',
    ago: '1시간 전',
    sopHint: 'OBC 금형 잔여수명 임박 시 정비 예약 절차?',
    draftPrefill:
      '[금형 MD-007 / OBC-RR] 잔여수명 임박\n- 잔여 사이클: 15,000 shots\n- 예측 교체일: D-3 (XGBoost 95% CI)\n- 현재 가동: 정상\n\n정비 예약 / 대체 금형 준비 안내문 초안을 작성해 주세요.',
  },
];

const ACK_KEY = 'ajin-equipment-acked-alerts';

function loadAcked(): Set<string> {
  if (typeof window === 'undefined') return new Set();
  try {
    const raw = localStorage.getItem(ACK_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}
function saveAcked(set: Set<string>) {
  localStorage.setItem(ACK_KEY, JSON.stringify(Array.from(set)));
}

interface Props {
  alertCount: number;
}

export function AlertsSubTab({ alertCount }: Props) {
  const navigate = useNavigate();
  const [acked, setAcked] = useState<Set<string>>(() => loadAcked());

  useEffect(() => {
    saveAcked(acked);
  }, [acked]);

  const visible = useMemo(
    () => ALERTS.filter((a) => !acked.has(a.id)),
    [acked],
  );

  const onAck = (id: string) => {
    setAcked((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  };

  const onDraft8D = (a: Alert) => {
    navigate('/draft', { state: { prefill: a.draftPrefill, doc_type: '8D' } });
  };

  const onOpenSop = (a: Alert) => {
    if (a.sopHint) {
      navigate('/chat', { state: { prefill: a.sopHint } });
    } else {
      navigate('/onboarding');
    }
  };

  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">URGENT · 긴급 조치 큐</div>
          <h2 className="lg-h2">즉시 대응 필요</h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="lg-pill">{visible.length}건</span>
          {acked.size > 0 && (
            <button
              type="button"
              onClick={() => setAcked(new Set())}
              style={{
                fontSize: 10,
                padding: '3px 8px',
                border: '1px solid var(--hud-border)',
                borderRadius: 999,
                background: 'transparent',
                color: 'var(--hud-text)',
                cursor: 'pointer',
                opacity: 0.7,
              }}
              title="확인한 알람을 다시 표시"
            >
              {acked.size} 확인 · 되돌리기
            </button>
          )}
          <span style={{ fontSize: 11, opacity: 0.5 }} title="props 로 전달된 사이드바 총합">
            {alertCount > 0 ? `total ${alertCount}` : ''}
          </span>
        </div>
      </div>

      {visible.length === 0 && (
        <div style={{ padding: 24, fontSize: 13, opacity: 0.65 }}>
          모든 알람을 확인했습니다. 신규 알람은 OVERVIEW 의 데일리 헤드라인 또는 SPC 탭에서 감지됩니다.
        </div>
      )}

      <div className="lg-urg-list">
        {visible.map((a) => (
          <article
            key={a.id}
            className={`lg-urg-row ${a.severity}`}
          >
            <div className="lg-urg-main">
              <span className="cat">{a.severity === 'crit' ? 'CRITICAL' : 'HIGH'}</span>
              <div className="body">
                <b>{a.title}</b>
                <span> · {a.detail}</span>
              </div>
              <span className="time mono">{a.ago}</span>
            </div>
            <div className="lg-urg-actions">
              <ActionBtn icon={<CheckCircle2 size={12} />} onClick={() => onAck(a.id)}>
                Acknowledge
              </ActionBtn>
              <ActionBtn icon={<FileText size={12} />} onClick={() => onDraft8D(a)} primary>
                8D Report 작성
              </ActionBtn>
              <ActionBtn icon={<BookOpen size={12} />} onClick={() => onOpenSop(a)}>
                관련 SOP / AI 도우미
              </ActionBtn>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ActionBtn({
  icon,
  children,
  onClick,
  primary,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick: () => void;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`lg-action-btn${primary ? ' primary' : ''}`}
    >
      <span aria-hidden="true">{icon}</span>
      {children}
    </button>
  );
}
