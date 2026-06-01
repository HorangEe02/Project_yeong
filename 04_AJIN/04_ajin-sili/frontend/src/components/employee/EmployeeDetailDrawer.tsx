// EmployeeDetailDrawer — Module A 인원 상세 패널.
// 디자인 시스템 v3.5 (HUD): 2px radius, 골드 강조, 영문 eyebrow + 한글 본문, 이모지 미사용.

import { useEffect, useState } from 'react';
import { Mail, Phone, Building2, IdCard, MapPin, Briefcase, Hash, Users, AtSign, MessageSquare, Star } from 'lucide-react';
import { Drawer } from '@components/ui/Drawer';
import { Button } from '@components/ui/Button';
import { Badge } from '@components/ui/Badge';
import { EmployeeExtrasSection } from '@components/employee/EmployeeExtrasSection';
import { DigitalEmployeeBadge } from '@components/employee/DigitalEmployeeBadge';
import type { FilteredEmployee } from '@lib/visibility';
import {
  isFavoritePerson,
  toggleFavoritePerson,
  subscribeHistoryChanges,
} from '@lib/searchHistory';

interface Props {
  employee: FilteredEmployee | null;
  isOpen: boolean;
  onClose: () => void;
  /** 메일/문서작성 등 액션. employee 가 null 이면 미호출. */
  onMail?: (emp: FilteredEmployee) => void;
  onDraft?: (emp: FilteredEmployee) => void;
  onCall?: (emp: FilteredEmployee) => void;
  /** W3 — 멘션 복사(클립보드) / 챗봇 문의(/chat 진입) */
  onMention?: (emp: FilteredEmployee) => void;
  onAskChat?: (emp: FilteredEmployee) => void;
  /** 키보드 네비게이션용 인접 인원 핸들러. */
  onPrev?: () => void;
  onNext?: () => void;
}

/**
 * 단일 정보 행 — eyebrow(영문) + label(한글) + value 좌우 배치.
 * 디자인 시스템 패턴 그대로.
 */
function InfoRow({
  icon: Icon,
  eyebrow,
  label,
  value,
  mono = false,
  href,
}: {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  eyebrow: string;
  label: string;
  value: string;
  mono?: boolean;
  href?: string;
}) {
  const valueEl = href ? (
    <a href={href} style={{ color: 'var(--hud-primary)', textDecoration: 'none' }}>
      {value}
    </a>
  ) : (
    <span>{value}</span>
  );
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '24px 1fr',
        gap: 12,
        padding: '12px 0',
        borderBottom: '1px solid var(--hud-border-light, #20262E)',
      }}
    >
      <div style={{ color: 'var(--hud-primary)', paddingTop: 2 }}>
        <Icon size={16} strokeWidth={1.5} />
      </div>
      <div>
        <div
          className="label-en"
          style={{
            fontSize: 10,
            letterSpacing: '0.1em',
            color: 'var(--hud-text-muted)',
            marginBottom: 2,
          }}
        >
          {eyebrow}
        </div>
        <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>
          {label}
        </div>
        <div
          style={{
            fontSize: 14,
            fontWeight: 600,
            fontFamily: mono ? 'var(--hud-font-mono, monospace)' : undefined,
          }}
        >
          {valueEl}
        </div>
      </div>
    </div>
  );
}

export function EmployeeDetailDrawer({
  employee,
  isOpen,
  onClose,
  onMail,
  onDraft,
  onCall,
  onMention,
  onAskChat,
  onPrev,
  onNext,
}: Props) {
  // W4 — 즐겨찾기 상태 (employee 변경 / localStorage 변경 시 갱신)
  const [isFav, setIsFav] = useState(false);
  useEffect(() => {
    if (!employee) return;
    setIsFav(isFavoritePerson(employee.id));
    return subscribeHistoryChanges(() => {
      if (employee) setIsFav(isFavoritePerson(employee.id));
    });
  }, [employee]);

  if (!employee) {
    return (
      <Drawer isOpen={isOpen} onClose={onClose} side="right" width={420} title="인원 상세">
        <div style={{ padding: 24, color: 'var(--hud-text-muted)' }}>선택된 인원이 없습니다.</div>
      </Drawer>
    );
  }

  const e = employee;
  const handleToggleFav = () => {
    const nowFav = toggleFavoritePerson({
      id: e.id,
      name: e.name,
      team: e.team,
      position: e.position,
      email: e.visibility === 'FULL' ? e.email : undefined,
    });
    setIsFav(nowFav);
  };
  const visibilityFull = e.visibility === 'FULL';
  const phoneRaw = e.mobile || '';
  const phoneClean = phoneRaw.replace(/[^0-9]/g, '');

  return (
    <Drawer isOpen={isOpen} onClose={onClose} side="right" width={420} title="인원 상세">
      <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* ── 헤더: 디지털 사원증 + 이름/직급/마스킹 뱃지 ─────────────── */}
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 4 }}>
          <DigitalEmployeeBadge
            employee={{
              name: e.name,
              employeeId: e.id ? String(e.id) : '—',
              team: e.team,
              position: e.position,
              hq: e.hq,
              photoUrl: null, // PR #2 에서 photo_url 필드 추가 시 e.photoUrl 로 교체
            }}
            variant="compact"
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              className="label-en"
              style={{ fontSize: 10, color: 'var(--hud-text-muted)', letterSpacing: '0.1em' }}
            >
              EMPLOYEE · 사원
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, lineHeight: 1.2 }}>{e.name}</div>
            <div style={{ fontSize: 13, color: 'var(--hud-text-dim)', marginTop: 2 }}>
              {e.position} · {e.hq}
            </div>
            <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
              {visibilityFull ? (
                <Badge status="ok">FULL ACCESS · 전체 조회</Badge>
              ) : (
                <Badge status="warn">MASKED · 일부 마스킹</Badge>
              )}
              {/* W4 — 즐겨찾기 토글 (lg-btn 캐노니컬 패턴) */}
              <button
                type="button"
                onClick={handleToggleFav}
                aria-pressed={isFav}
                aria-label={isFav ? '즐겨찾기 해제' : '즐겨찾기 추가'}
                title={isFav ? '즐겨찾기 해제' : '즐겨찾기에 추가'}
                className={`lg-btn ${isFav ? '' : 'ghost'} sm`}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <Star
                  size={12}
                  strokeWidth={2}
                  fill={isFav ? 'currentColor' : 'none'}
                />
                {isFav ? '즐겨찾기됨' : '즐겨찾기'}
              </button>
            </div>
          </div>
        </div>

        {/* ── W3 빠른 액션 4종 (메일 / 멘션 / 초안 / 챗봇) + 전화 (옵션) ─── */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 8,
          }}
        >
          {onMail && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => onMail(e)}
              disabled={!e.email}
              icon={<Mail size={14} strokeWidth={1.5} />}
              title={e.email ? '메일 보내기' : '이메일 정보 없음'}
            >
              메일
            </Button>
          )}
          {onMention && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onMention(e)}
              icon={<AtSign size={14} strokeWidth={1.5} />}
              title="멘션 형식으로 클립보드에 복사"
            >
              멘션 복사
            </Button>
          )}
          {onDraft && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onDraft(e)}
              disabled={!visibilityFull}
              icon={<Mail size={14} strokeWidth={1.5} />}
              title={visibilityFull ? '이 사람에게 보내는 초안 작성' : '권한이 제한된 사원입니다'}
            >
              초안 작성
            </Button>
          )}
          {onAskChat && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onAskChat(e)}
              icon={<MessageSquare size={14} strokeWidth={1.5} />}
              title="챗봇으로 더 알아보기"
            >
              챗봇 문의
            </Button>
          )}
          {onCall && visibilityFull && phoneClean && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (onCall) onCall(e);
                window.location.href = `tel:${phoneClean}`;
              }}
              icon={<Phone size={14} strokeWidth={1.5} />}
              title="휴대전화 걸기"
              style={{ gridColumn: '1 / -1' }}
            >
              전화 {phoneClean}
            </Button>
          )}
        </div>

        {/* ── 상세 정보 그리드 ────────────────────────────────── */}
        <div
          style={{
            border: '1px solid var(--hud-border, #2A2520)',
            borderRadius: 2,
            padding: '0 14px',
            background: 'var(--hud-surface, #111820)',
          }}
        >
          <InfoRow icon={IdCard} eyebrow="EMPLOYEE ID" label="사번" value={e.id} mono />
          <InfoRow icon={Building2} eyebrow="HQ / DIVISION" label="본부" value={e.hq} />
          <InfoRow icon={Users} eyebrow="TEAM" label="팀 / 부서" value={e.team} />
          <InfoRow icon={Briefcase} eyebrow="POSITION" label="직급" value={e.position} />
          <InfoRow
            icon={Hash}
            eyebrow="EXT."
            label="내선번호"
            value={e.extMasked || '—'}
            mono
          />
          <InfoRow
            icon={Phone}
            eyebrow="MOBILE"
            label="휴대전화"
            value={e.phoneMasked || '—'}
            mono
            href={visibilityFull && phoneClean ? `tel:${phoneClean}` : undefined}
          />
          <InfoRow
            icon={Mail}
            eyebrow="EMAIL"
            label="이메일"
            value={e.email || '—'}
            mono
            href={e.email ? `mailto:${e.email}` : undefined}
          />
          <InfoRow icon={MapPin} eyebrow="PLANT" label="사업장" value={e.plant} />
          {/* 마지막 행 — borderBottom 제거 */}
          <div style={{ height: 4 }} />
        </div>

        {/* ── W7 부가 정보 (출장/직속부하/결재) — 권한 분기 ─── */}
        <EmployeeExtrasSection employeeId={e.id} />

        {/* ── 인접 인원 네비게이션 (선택) ───────────────────── */}
        {(onPrev || onNext) && (
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <Button
              variant="ghost"
              size="sm"
              onClick={onPrev}
              disabled={!onPrev}
              style={{ flex: 1 }}
            >
              ← 이전
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={onNext}
              disabled={!onNext}
              style={{ flex: 1 }}
            >
              다음 →
            </Button>
          </div>
        )}

        {/* ── 마스킹 안내 (F5 — 휴대전화만 마스킹) ─────────────── */}
        {!visibilityFull && (
          <div
            style={{
              padding: 12,
              border: '1px dashed var(--hud-border, #2A2520)',
              borderRadius: 12,
              fontSize: 12,
              color: 'var(--hud-text-muted)',
              lineHeight: 1.6,
            }}
          >
            <strong style={{ color: 'var(--hud-orange, #E8A317)' }}>제한 모드</strong>
            <br />
            타 본부·부서 인원은 휴대전화만 일부 마스킹되어 표시됩니다. 내선번호와 사내
            이메일은 협업 자산으로 공개되며, 휴대전화 등 상세 개인정보는 인사관리팀이 별도
            관리합니다.
          </div>
        )}
      </div>
    </Drawer>
  );
}
