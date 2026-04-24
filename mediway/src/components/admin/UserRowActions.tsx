import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  Shield,
  Pause,
  Play,
  MoreVertical,
  ExternalLink,
  Mail,
  Trash2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { IconButton } from '@/components/admin/IconButton';
import type { AdminUserRow } from '@/types/admin';

interface UserRowActionsProps {
  row: AdminUserRow;
  isSelf: boolean;
  onChangeRole: () => void;
  onToggleStatus: () => void;
  onResetPassword: () => void;
  onSoftDelete: () => void;
}

const MENU_WIDTH_PX = 192; // w-48
const MENU_GAP_PX = 4;

interface MenuPos {
  top: number;
  left: number;
}

export function UserRowActions({
  row,
  isSelf,
  onChangeRole,
  onToggleStatus,
  onResetPassword,
  onSoftDelete,
}: UserRowActionsProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState<MenuPos | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    if (!menuOpen || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const spaceRight = window.innerWidth - rect.right;
    // 오른쪽 공간이 메뉴 폭보다 좁으면 트리거 우측에 맞춰 왼쪽으로 펼침
    const alignRight = spaceRight < MENU_WIDTH_PX;
    const left = alignRight ? rect.right - MENU_WIDTH_PX : rect.left;
    setMenuPos({
      top: rect.bottom + MENU_GAP_PX,
      left: Math.max(8, Math.min(left, window.innerWidth - MENU_WIDTH_PX - 8)),
    });
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    const onClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        menuRef.current?.contains(target) ||
        triggerRef.current?.contains(target)
      ) {
        return;
      }
      close();
    };
    document.addEventListener('mousedown', onClickOutside);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    return () => {
      document.removeEventListener('mousedown', onClickOutside);
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
    };
  }, [menuOpen]);

  if (isSelf) {
    return (
      <span className="text-[11px] text-on-surface-variant/70">(본인)</span>
    );
  }
  if (row.status === 'deleted') {
    return (
      <Link
        to={`/admin/users/${row.uid}`}
        className="flex h-7 w-7 items-center justify-center rounded-lg border border-surface-container-high text-on-surface-variant hover:bg-surface-container-low"
        aria-label="상세 보기"
      >
        <ExternalLink className="h-3.5 w-3.5" />
      </Link>
    );
  }

  const select = (fn: () => void) => {
    setMenuOpen(false);
    fn();
  };

  return (
    <>
      <IconButton
        ref={triggerRef}
        label="액션"
        onClick={() => setMenuOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
      >
        <MoreVertical className="h-3.5 w-3.5" />
      </IconButton>
      {menuOpen && menuPos &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            style={{ position: 'fixed', top: menuPos.top, left: menuPos.left, width: MENU_WIDTH_PX }}
            className="z-50 overflow-hidden rounded-xl bg-surface-container-lowest shadow-ambient-lg"
          >
            <Link
              to={`/admin/users/${row.uid}`}
              onClick={() => setMenuOpen(false)}
              className="flex items-center gap-2 px-3 py-2 text-xs text-on-surface no-underline hover:bg-surface-container-low"
            >
              <ExternalLink className="h-3 w-3" />
              상세 보기
            </Link>
            <button
              type="button"
              onClick={() => select(onChangeRole)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-on-surface hover:bg-surface-container-low"
            >
              <Shield className="h-3 w-3 text-primary" />
              역할 변경
            </button>
            <button
              type="button"
              onClick={() => select(onToggleStatus)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-on-surface hover:bg-surface-container-low"
            >
              {row.status === 'active' ? (
                <Pause className="h-3 w-3" />
              ) : (
                <Play className="h-3 w-3" />
              )}
              {row.status === 'active' ? '비활성화' : '활성화'}
            </button>
            <button
              type="button"
              onClick={() => select(onResetPassword)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-on-surface hover:bg-surface-container-low"
            >
              <Mail className="h-3 w-3" />
              비밀번호 재설정 메일
            </button>
            <button
              type="button"
              onClick={() => select(onSoftDelete)}
              className="flex w-full items-center gap-2 border-t border-surface-container-high px-3 py-2 text-left text-xs text-red-600 hover:bg-surface-container-low"
            >
              <Trash2 className="h-3 w-3" />
              계정 삭제
            </button>
          </div>,
          document.body,
        )}
    </>
  );
}
