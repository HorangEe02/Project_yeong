// EmployeeDetailDrawer — Module A 인원 상세 패널.
// 디자인 시스템 v3.5 (HUD): 2px radius, 골드 강조, 영문 eyebrow + 한글 본문, 이모지 미사용.

import { Mail, Phone, Building2, IdCard, MapPin, Briefcase, Hash, Users } from 'lucide-react';
import { Drawer } from '@components/ui/Drawer';
import { Button } from '@components/ui/Button';
import { Badge } from '@components/ui/Badge';
import type { FilteredEmployee } from '@lib/visibility';

interface Props {
  employee: FilteredEmployee | null;
  isOpen: boolean;
  onClose: () => void;
  /** 메일/문서작성 등 액션. employee 가 null 이면 미호출. */
  onMail?: (emp: FilteredEmployee) => void;
  onDraft?: (emp: FilteredEmployee) => void;
  onCall?: (emp: FilteredEmployee) => void;
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
  onPrev,
  onNext,
}: Props) {
  if (!employee) {
    return (
      <Drawer isOpen={isOpen} onClose={onClose} side="right" width={420} title="인원 상세">
        <div style={{ padding: 24, color: 'var(--hud-text-muted)' }}>선택된 인원이 없습니다.</div>
      </Drawer>
    );
  }

  const e = employee;
  const visibilityFull = e.visibility === 'FULL';
  const phoneRaw = e.mobile || '';
  const phoneClean = phoneRaw.replace(/[^0-9]/g, '');

  return (
    <Drawer isOpen={isOpen} onClose={onClose} side="right" width={420} title="인원 상세">
      <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* ── 헤더: 아바타 + 이름/직급/마스킹 뱃지 ─────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 2,
              background:
                'linear-gradient(135deg, var(--hud-primary) 0%, var(--hud-primary-light, #FFD066) 100%)',
              color: 'var(--hud-bg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
              fontWeight: 800,
              letterSpacing: '0.04em',
            }}
            aria-hidden
          >
            {e.name.slice(-2)}
          </div>
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
            <div style={{ marginTop: 6 }}>
              {visibilityFull ? (
                <Badge status="ok">FULL ACCESS · 전체 조회</Badge>
              ) : (
                <Badge status="warn">MASKED · 일부 마스킹</Badge>
              )}
            </div>
          </div>
        </div>

        {/* ── 빠른 액션 ───────────────────────────────────────── */}
        <div style={{ display: 'flex', gap: 8 }}>
          {onMail && visibilityFull && (
            <Button variant="primary" size="sm" onClick={() => onMail(e)}>
              <Mail size={14} strokeWidth={1.5} style={{ marginRight: 6 }} />
              메일 보내기
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
            >
              <Phone size={14} strokeWidth={1.5} style={{ marginRight: 6 }} />
              전화
            </Button>
          )}
          {onDraft && (
            <Button variant="ghost" size="sm" onClick={() => onDraft(e)}>
              문서 작성 →
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
            value={visibilityFull ? e.email : e.emailMasked}
            mono
            href={visibilityFull ? `mailto:${e.email}` : undefined}
          />
          <InfoRow icon={MapPin} eyebrow="PLANT" label="사업장" value={e.plant} />
          {/* 마지막 행 — borderBottom 제거 */}
          <div style={{ height: 4 }} />
        </div>

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

        {/* ── 마스킹 안내 ─────────────────────────────────────── */}
        {!visibilityFull && (
          <div
            style={{
              padding: 12,
              border: '1px dashed var(--hud-border, #2A2520)',
              borderRadius: 2,
              fontSize: 12,
              color: 'var(--hud-text-muted)',
              lineHeight: 1.6,
            }}
          >
            <strong style={{ color: 'var(--hud-orange, #E8A317)' }}>제한 모드</strong>
            <br />
            타 본부·부서 인원은 사내 보안 정책에 따라 휴대전화·이메일이 일부 마스킹되어 표시됩니다.
            상세 조회가 필요하면 인사관리팀에 문의하세요.
          </div>
        )}
      </div>
    </Drawer>
  );
}
