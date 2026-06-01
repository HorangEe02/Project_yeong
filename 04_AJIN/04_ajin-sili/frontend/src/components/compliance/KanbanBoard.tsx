// D5 — Compliance Kanban Board (4 columns: backlog/in_progress/review/done).
// HTML5 native DnD. status 매핑:
//   created      → backlog
//   in_progress  → in_progress
//   acknowledged → review
//   resolved     → done

import { useEffect, useState } from 'react';
import {
  fetchCollabTickets,
  patchTicket,
  transitionTicket,
  type CollabTicket,
  type TicketStatus,
} from '@api/compliance';

const COLUMNS: { key: TicketStatus; label: string; en: string }[] = [
  { key: 'created', label: '대기', en: 'BACKLOG' },
  { key: 'in_progress', label: '진행', en: 'IN PROGRESS' },
  { key: 'acknowledged', label: '검토', en: 'REVIEW' },
  { key: 'resolved', label: '완료', en: 'DONE' },
];

interface Props {
  refreshTrigger?: number;
}

export function KanbanBoard({ refreshTrigger }: Props) {
  const [tickets, setTickets] = useState<CollabTicket[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetchCollabTickets({ limit: 100 });
      setTickets(r.tickets);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [refreshTrigger]);

  const onDrop = async (status: TicketStatus, ticketId: number) => {
    setDraggingId(null);
    const t = tickets.find((x) => x.id === ticketId);
    if (!t || t.status === status) return;
    setTickets((prev) =>
      prev.map((x) => (x.id === ticketId ? { ...x, status } : x)),
    );
    try {
      await transitionTicket(ticketId, status);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      void load();
    }
  };

  const handleProgressChange = async (ticketId: number, pct: number) => {
    setTickets((prev) =>
      prev.map((x) => (x.id === ticketId ? { ...x, progress_pct: pct } : x)),
    );
    try {
      await patchTicket(ticketId, { progress_pct: pct });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="lg-kanban">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">TICKETS · 협업 칸반</div>
          <h2 className="lg-h2">담당자 / 마감 / 진행률</h2>
        </div>
        <div className="lg-actions">
          <button className="lg-btn sm ghost" onClick={() => void load()}>
            새로고침
          </button>
        </div>
      </div>

      {error && (
        <div className="lg-error" style={{ padding: 8, marginBottom: 8 }}>
          {error}
        </div>
      )}

      {loading && tickets.length === 0 && (
        <div className="lg-sub" style={{ padding: 12 }}>
          불러오는 중…
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: 12,
          marginTop: 12,
        }}
      >
        {COLUMNS.map((col) => {
          const colTickets = tickets.filter((t) => t.status === col.key);
          return (
            <div
              key={col.key}
              onDragOver={(e) => {
                e.preventDefault();
              }}
              onDrop={() => {
                if (draggingId !== null) void onDrop(col.key, draggingId);
              }}
              style={{
                background: 'color-mix(in oklab, var(--hud-text) 3%, transparent)',
                border: '1px solid var(--hud-border)',
                borderRadius: 2,
                padding: 8,
                minHeight: 200,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 8,
                }}
              >
                <span
                  className="lg-eyebrow"
                  style={{ fontSize: 10, letterSpacing: '0.1em' }}
                >
                  {col.en}
                </span>
                <span className="lg-pill" style={{ fontSize: 10 }}>
                  {colTickets.length}
                </span>
              </div>

              {colTickets.length === 0 && (
                <div
                  className="lg-sub"
                  style={{ fontSize: 11, padding: 8, textAlign: 'center' }}
                >
                  비어있음
                </div>
              )}

              {colTickets.map((t) => (
                <div
                  key={t.id}
                  draggable
                  onDragStart={() => setDraggingId(t.id)}
                  onDragEnd={() => setDraggingId(null)}
                  style={{
                    background: 'var(--hud-surface)',
                    border: '1px solid var(--hud-border)',
                    borderRadius: 2,
                    padding: 8,
                    marginBottom: 6,
                    cursor: 'grab',
                    fontSize: 12,
                  }}
                >
                  <div
                    style={{
                      fontWeight: 600,
                      marginBottom: 4,
                      wordBreak: 'keep-all',
                    }}
                  >
                    {t.title}
                  </div>
                  <div className="dim" style={{ fontSize: 10 }}>
                    #{t.id} · 담당 {t.assignee || '미지정'}
                    {t.deadline && ` · D-day ${t.deadline}`}
                  </div>
                  <div style={{ marginTop: 6 }}>
                    <div style={{ fontSize: 10, marginBottom: 2 }}>
                      진행 {t.progress_pct}%
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={5}
                      value={t.progress_pct}
                      onChange={(e) =>
                        void handleProgressChange(t.id, Number(e.target.value))
                      }
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
