// HistoryFavoritesPanel — Module A · 검색 이력 / 즐겨찾기 / 최근 본 사람·문서 4분할.
// 디자인 시스템 v3.5: lg-card / lg-eyebrow / lg-h2 / lg-btn ghost sm + 16px 라운드 widget.

import { useEffect, useState } from 'react';
import { Clock, Star, User2, FileText, RotateCcw, X } from 'lucide-react';
import {
  getRecentQueries,
  getFavoritePeople,
  getViewedPeople,
  getViewedDocs,
  clearRecentQueries,
  toggleFavoritePerson,
  subscribeHistoryChanges,
  type RecentQuery,
  type FavoritePerson,
  type ViewedPerson,
  type ViewedDoc,
} from '@lib/searchHistory';

interface Props {
  onPickQuery?: (query: string) => void;
  onPickPerson?: (id: string, name: string) => void;
  onPickDoc?: (docId: string) => void;
}

function formatTime(ts: number): string {
  const diff = Date.now() - ts;
  const min = Math.floor(diff / 60_000);
  if (min < 1) return '방금';
  if (min < 60) return `${min}분 전`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}시간 전`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}일 전`;
  return new Date(ts).toISOString().slice(0, 10);
}

const WIDGET_BOX: React.CSSProperties = {
  border: '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
  borderRadius: 16,
  padding: 14,
  background: 'color-mix(in oklab, var(--hud-surface) 40%, transparent)',
};

const ROW_BTN: React.CSSProperties = {
  display: 'flex',
  width: '100%',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
  textAlign: 'left',
};

export function HistoryFavoritesPanel({ onPickQuery, onPickPerson, onPickDoc }: Props) {
  const [queries, setQueries] = useState<RecentQuery[]>([]);
  const [favorites, setFavorites] = useState<FavoritePerson[]>([]);
  const [viewedPeople, setViewedPeople] = useState<ViewedPerson[]>([]);
  const [viewedDocs, setViewedDocs] = useState<ViewedDoc[]>([]);

  const refresh = () => {
    setQueries(getRecentQueries());
    setFavorites(getFavoritePeople());
    setViewedPeople(getViewedPeople());
    setViewedDocs(getViewedDocs());
  };

  useEffect(() => {
    refresh();
    return subscribeHistoryChanges(refresh);
  }, []);

  const empty =
    queries.length === 0 &&
    favorites.length === 0 &&
    viewedPeople.length === 0 &&
    viewedDocs.length === 0;

  if (empty) {
    return (
      <section className="lg-card">
        <div className="lg-card-h">
          <div>
            <div className="lg-eyebrow">RECENT &amp; FAVORITES · 최근 / 즐겨찾기</div>
            <h2 className="lg-h2">아직 흔적이 없어요</h2>
          </div>
        </div>
        <div
          style={{
            padding: 16,
            fontSize: 14,
            lineHeight: 1.7,
            color: 'var(--hud-text-dim)',
          }}
        >
          검색하거나 사원 카드 / 문서 카드를 열면 이 영역에 자동으로 누적됩니다.
          <br />
          자주 찾는 사람은 <Star
            size={12}
            strokeWidth={2}
            style={{ verticalAlign: 'middle', color: 'var(--hud-primary)' }}
          />{' '}
          버튼으로 즐겨찾기에 등록할 수 있습니다.
        </div>
      </section>
    );
  }

  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">RECENT &amp; FAVORITES · 최근 / 즐겨찾기</div>
          <h2 className="lg-h2">매일 쓰는 동선</h2>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 14,
        }}
      >
        {/* RECENT QUERIES */}
        <div style={WIDGET_BOX}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 10,
            }}
          >
            <span
              className="lg-eyebrow"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 0 }}
            >
              <Clock size={12} strokeWidth={2} /> 최근 검색
            </span>
            {queries.length > 0 && (
              <button
                type="button"
                className="lg-btn ghost sm"
                onClick={clearRecentQueries}
                title="이력 비우기"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
              >
                <RotateCcw size={11} strokeWidth={2} /> 비우기
              </button>
            )}
          </div>
          {queries.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
              아직 검색 이력이 없습니다.
            </div>
          ) : (
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              {queries.slice(0, 8).map((q) => (
                <li key={`${q.query}-${q.timestamp}`}>
                  <button
                    type="button"
                    onClick={() => onPickQuery?.(q.query)}
                    className="lg-btn ghost sm"
                    style={ROW_BTN}
                    title={`${q.query} · ${formatTime(q.timestamp)}`}
                  >
                    <span
                      style={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        flex: 1,
                      }}
                    >
                      {q.query}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--hud-font-mono)',
                        fontSize: 10,
                        letterSpacing: '0.08em',
                        color: 'var(--hud-text-dim)',
                      }}
                    >
                      {formatTime(q.timestamp)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* FAVORITES */}
        <div style={WIDGET_BOX}>
          <div
            className="lg-eyebrow"
            style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}
          >
            <Star size={12} strokeWidth={2} /> 즐겨찾기 ({favorites.length})
          </div>
          {favorites.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
              아직 등록된 즐겨찾기가 없습니다.
            </div>
          ) : (
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              {favorites.slice(0, 8).map((f) => (
                <li
                  key={f.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: 8,
                    borderRadius: 12,
                    border:
                      '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => onPickPerson?.(f.id, f.name)}
                    className="lg-btn ghost sm"
                    style={{ flex: 1, textAlign: 'left', padding: '6px 8px' }}
                    title={`${f.name} (${f.position} · ${f.team})`}
                  >
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{f.name}</div>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--hud-text-dim)',
                        marginTop: 2,
                      }}
                    >
                      {f.position} · {f.team}
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      toggleFavoritePerson({
                        id: f.id,
                        name: f.name,
                        team: f.team,
                        position: f.position,
                        email: f.email,
                      })
                    }
                    className="lg-btn ghost sm"
                    title="즐겨찾기 해제"
                    aria-label="즐겨찾기 해제"
                  >
                    <X size={11} strokeWidth={2} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* RECENT VIEWED PEOPLE */}
        <div style={WIDGET_BOX}>
          <div
            className="lg-eyebrow"
            style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}
          >
            <User2 size={12} strokeWidth={2} /> 최근 본 사람
          </div>
          {viewedPeople.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
              사원 카드를 열면 누적됩니다.
            </div>
          ) : (
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              {viewedPeople.slice(0, 6).map((p) => (
                <li key={`${p.id}-${p.timestamp}`}>
                  <button
                    type="button"
                    onClick={() => onPickPerson?.(p.id, p.name)}
                    className="lg-btn ghost sm"
                    style={ROW_BTN}
                  >
                    <span style={{ fontSize: 12 }}>
                      <b>{p.name}</b>{' '}
                      <span style={{ color: 'var(--hud-text-dim)' }}>· {p.position}</span>
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--hud-font-mono)',
                        fontSize: 10,
                        letterSpacing: '0.08em',
                        color: 'var(--hud-text-dim)',
                      }}
                    >
                      {formatTime(p.timestamp)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* RECENT VIEWED DOCS */}
        <div style={WIDGET_BOX}>
          <div
            className="lg-eyebrow"
            style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}
          >
            <FileText size={12} strokeWidth={2} /> 최근 본 문서
          </div>
          {viewedDocs.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--hud-text-dim)' }}>
              문서 카드를 열면 누적됩니다.
            </div>
          ) : (
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              {viewedDocs.slice(0, 6).map((d) => (
                <li key={`${d.doc_id}-${d.timestamp}`}>
                  <button
                    type="button"
                    onClick={() => onPickDoc?.(d.doc_id)}
                    className="lg-btn ghost sm"
                    style={ROW_BTN}
                    title={`${d.title} (${d.doc_type})`}
                  >
                    <span
                      style={{
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontSize: 12,
                      }}
                    >
                      {d.title}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--hud-font-mono)',
                        fontSize: 10,
                        letterSpacing: '0.08em',
                        color: 'var(--hud-text-dim)',
                      }}
                    >
                      {formatTime(d.timestamp)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
