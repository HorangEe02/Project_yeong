// NotificationBell — TopBar 글로벌 알림 벨 (Part 12 Stage 2).
// HR 알림(휴가 승인/반려/이중 결재/위임 등록)을 어느 페이지에서든 즉시 확인.
//
// 디자인 시스템 v2 준수:
// - 종 SVG 아이콘 (lucide-react Bell)
// - 미읽 카운트 = gold 원형 배지 (9+ 표기)
// - 드롭다운 = Liquid Glass (top-bar 내 자연스러운 통합)
// - outside-click + 30초 polling + window 'storage' event 동기화

import { useEffect, useRef, useState, useCallback } from 'react';
import { Bell } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// v4.8 — @api/hr 의존 제거. localStorage 기반 알림 로직 inline 통합.
type NotificationType =
  | 'request_submitted'
  | 'request_approved'
  | 'request_rejected'
  | 'second_stage_required'
  | 'delegation_set';

interface UserNotification {
  id: string;
  type: NotificationType;
  title: string;
  detail: string;
  timestamp: string;
  read: boolean;
}

const POLL_MS = 30_000;
const STORAGE_KEY = 'hr_notifications';   // 기존 사용자 데이터 호환 — key 유지

const TYPE_COLOR: Record<NotificationType, string> = {
  request_submitted:     '#2980B9',
  request_approved:      'var(--hud-primary)',
  request_rejected:      '#C0392B',
  second_stage_required: '#9B59B6',
  delegation_set:        '#2D8A4E',
};

function loadNotifications(): UserNotification[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as UserNotification[]) : [];
  } catch {
    return [];
  }
}

function saveNotifications(arr: UserNotification[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(arr.slice(0, 30)));
  } catch {
    /* ignore */
  }
}

function getNotifications(): UserNotification[] {
  return loadNotifications();
}

function markNotificationRead(id: string) {
  const arr = loadNotifications();
  const n = arr.find((x) => x.id === id);
  if (n) {
    n.read = true;
    saveNotifications(arr);
  }
}

function markAllNotificationsRead() {
  const arr = loadNotifications().map((n) => ({ ...n, read: true }));
  saveNotifications(arr);
}

export function NotificationBell() {
  const [items, setItems] = useState<UserNotification[]>([]);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();

  const reload = useCallback(() => setItems(getNotifications()), []);

  useEffect(() => {
    reload();
    const id = window.setInterval(reload, POLL_MS);
    const onStorage = (e: StorageEvent) => { if (e.key === STORAGE_KEY) reload(); };
    window.addEventListener('storage', onStorage);
    return () => {
      window.clearInterval(id);
      window.removeEventListener('storage', onStorage);
    };
  }, [reload]);

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener('mousedown', onClick);
    return () => window.removeEventListener('mousedown', onClick);
  }, [open]);

  const unreadCount = items.filter((n) => !n.read).length;
  const recent = items.slice(0, 5);

  const handleItemClick = (n: UserNotification) => {
    markNotificationRead(n.id);
    reload();
  };

  const handleMarkAll = () => {
    markAllNotificationsRead();
    reload();
  };

  const handleViewAll = () => {
    setOpen(false);
    navigate('/');   // v4.8 — /hr 라우트 제거됨. 대시보드로 이동
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', display: 'inline-flex' }}>
      <button
        onClick={() => setOpen(!open)}
        title={`알림 ${unreadCount}건 미읽음`}
        style={{
          position: 'relative',
          padding: '4px 8px',
          background: 'transparent',
          border: 'none',
          color: 'var(--hud-text)',
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Bell size={16} strokeWidth={1.8} color={unreadCount > 0 ? 'var(--hud-primary)' : 'var(--hud-text-dim)'} />
        {unreadCount > 0 && (
          <span style={{
            position: 'absolute',
            top: 1, right: 1,
            minWidth: 14, height: 14, padding: '0 4px',
            borderRadius: 7,
            background: 'var(--hud-primary)',
            color: '#0A0E14',
            fontSize: 9, fontWeight: 700,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            lineHeight: 1,
          }}>{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 8px)',
          right: 0,
          width: 340,
          maxHeight: 480,
          background: 'var(--glass-bg-strong, var(--hud-surface))',
          backdropFilter: 'blur(20px) saturate(160%)',
          WebkitBackdropFilter: 'blur(20px) saturate(160%)',
          border: '1px solid var(--glass-border, var(--hud-border))',
          borderRadius: 2,
          boxShadow: '0 12px 32px -8px rgba(0,0,0,0.4)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          zIndex: 1000,
        }}>
          {/* Header */}
          <div style={{
            padding: '10px 14px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid var(--hud-border-light)',
          }}>
            <div>
              <div className="lg-eyebrow" style={{ fontSize: 9 }}>NOTIFICATIONS</div>
              <div style={{ fontSize: 12, color: 'var(--hud-text)', fontWeight: 600 }}>
                알림 {unreadCount > 0 ? `${unreadCount}건 미읽음` : '모두 읽음'}
              </div>
            </div>
            {unreadCount > 0 && (
              <button onClick={handleMarkAll} style={{
                padding: '4px 8px',
                background: 'transparent',
                border: '1px solid var(--hud-border)',
                color: 'var(--hud-text-dim)',
                fontSize: 10,
                cursor: 'pointer',
                borderRadius: 2,
              }}>모두 읽음</button>
            )}
          </div>

          {/* Items */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
            {recent.length === 0 && (
              <div style={{
                padding: 24,
                textAlign: 'center',
                fontSize: 11,
                color: 'var(--hud-text-muted)',
              }}>
                알림이 없습니다.<br />
                <span style={{ fontSize: 10 }}>휴가 신청 / 승인 시 여기에 표시됩니다.</span>
              </div>
            )}
            {recent.map((n) => (
              <div
                key={n.id}
                onClick={() => handleItemClick(n)}
                style={{
                  padding: '10px 14px',
                  cursor: 'pointer',
                  background: n.read ? 'transparent' : 'color-mix(in oklab, var(--hud-surface-2) 60%, transparent)',
                  borderLeft: `3px solid ${TYPE_COLOR[n.type]}`,
                  marginBottom: 2,
                }}
              >
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  gap: 8,
                }}>
                  <div style={{
                    fontSize: 12,
                    fontWeight: n.read ? 400 : 600,
                    color: 'var(--hud-text)',
                    flex: 1,
                  }}>
                    {n.title}
                    {!n.read && <span style={{
                      marginLeft: 6, color: TYPE_COLOR[n.type], fontSize: 9,
                    }}>● NEW</span>}
                  </div>
                  <span style={{ fontSize: 9, color: 'var(--hud-text-muted)', whiteSpace: 'nowrap' }}>
                    {formatRelative(n.timestamp)}
                  </span>
                </div>
                <div style={{
                  fontSize: 11,
                  color: 'var(--hud-text-dim)',
                  marginTop: 2,
                  lineHeight: 1.4,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                }}>{n.detail}</div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div style={{
            padding: '8px 14px',
            borderTop: '1px solid var(--hud-border-light)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <span style={{ fontSize: 10, color: 'var(--hud-text-muted)' }}>
              HR 이벤트 · 30초 자동 갱신
            </span>
            <button onClick={handleViewAll} style={{
              padding: '4px 10px',
              background: 'transparent',
              border: 'none',
              color: 'var(--hud-primary)',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}>HR 화면 →</button>
          </div>
        </div>
      )}
    </div>
  );
}

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60_000);
  if (min < 1) return '방금';
  if (min < 60) return `${min}분 전`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}시간 전`;
  const day = Math.floor(hr / 24);
  if (day === 1) return '어제';
  if (day < 7) return `${day}일 전`;
  return new Date(iso).toLocaleDateString('ko-KR');
}
