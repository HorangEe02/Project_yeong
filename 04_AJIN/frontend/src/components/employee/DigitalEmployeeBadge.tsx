// DigitalEmployeeBadge — 디지털 사원증 (AJIN 브랜드 톤, 앞·뒷면 CSS 3D flip).
// 첨부 AMAKERS 사원증 레이아웃 차용 + AJIN 색·폰트 적용.
// 사용처: /profile BASIC 탭 (variant=large) + /search EmployeeDetailDrawer (variant=compact).
//
// PR #1 범위: photo_url 있으면 <img>, 없으면 initials placeholder. flip 동작.
// PR #2 에서 photo upload modal 추가.

import { useState, type MouseEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera, RotateCw } from 'lucide-react';

export interface BadgeEmployee {
  /** 한글 이름 — 사원증 정면 중앙 큰 글씨. */
  name: string;
  /** 영문 이름 — 한글 아래 작은 mono 표기. 미지정 시 자동 변환 안 함. */
  nameEn?: string;
  /** 사번 (admin · 기술영업팀-021 등). */
  employeeId: string;
  /** 팀 / 부서 — 사원증 하단 부서 표시. */
  team?: string;
  /** 직급 (상무·부장·과장 등). */
  position?: string;
  /** 본부. */
  hq?: string;
  /** 증명사진 URL — 없으면 initials placeholder. */
  photoUrl?: string | null;
}

export type BadgeVariant = 'large' | 'compact';

interface Props {
  employee: BadgeEmployee;
  variant?: BadgeVariant;
  /** profile 페이지에서 사진 변경 트리거. compact 에서는 사용 안 함. */
  onPhotoClick?: () => void;
  /** 대표전화 — 뒷면 표시. */
  contactPhone?: string;
}

// AJIN 사원증 색 토큰
const NAVY = '#1f2c44';
const NAVY_LIGHT = '#2a3a58';
const ACCENT = '#FBBF24'; // AJIN primary yellow
const TEXT_LIGHT = '#f8fafc';
const TEXT_DIM = '#cbd5e1';
const BORDER = 'rgba(255,255,255,0.14)';

// 사이즈 토큰 (variant 별)
const SIZE: Record<BadgeVariant, { width: number; height: number; photoSize: number; nameFs: number; logoFs: number }> = {
  large:   { width: 260, height: 400, photoSize: 150, nameFs: 22, logoFs: 14 },
  compact: { width: 200, height: 310, photoSize: 110, nameFs: 17, logoFs: 11 },
};

// ─────────────────────────────────────────────────────────────
// QR placeholder — 간단한 SVG 격자 패턴 (qrcode.react 미설치 시 fallback)
// employeeId 의 문자별 charCode 합산을 seed 로 7x7 패턴 생성.
// 실제 QR 스캐너 호환 X — 시각 효과 전용.
// ─────────────────────────────────────────────────────────────
function QrSvg({ data, size = 48 }: { data: string; size?: number }) {
  // deterministic pseudo-random
  let seed = data.split('').reduce((a, c) => a + c.charCodeAt(0), 0) || 1;
  const rng = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
  const grid = 7;
  const cells: boolean[] = [];
  for (let i = 0; i < grid * grid; i++) cells.push(rng() > 0.5);
  // 좌상·우상·좌하 코너 anchor (3-cell L 패턴) 강제로 QR 다워 보이게
  const anchors = [
    [0, 0], [0, 1], [1, 0],
    [grid - 1, 0], [grid - 2, 0], [grid - 1, 1],
    [0, grid - 1], [1, grid - 1], [0, grid - 2],
  ];
  anchors.forEach(([x, y]) => { cells[y * grid + x] = true; });

  const cellSize = size / grid;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
      <rect width={size} height={size} fill="#fff" rx="2" />
      {cells.map((on, i) =>
        on ? (
          <rect
            key={i}
            x={(i % grid) * cellSize + 1}
            y={Math.floor(i / grid) * cellSize + 1}
            width={cellSize - 1.5}
            height={cellSize - 1.5}
            fill={NAVY}
            rx="0.5"
          />
        ) : null,
      )}
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// initials placeholder (사진 없을 때) — 한글 마지막 2자
// ─────────────────────────────────────────────────────────────
function InitialsPlaceholder({ name, size }: { name: string; size: number }) {
  const initials = name.slice(-2) || '?';
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: 4,
        background: `linear-gradient(135deg, ${NAVY_LIGHT} 0%, ${NAVY} 100%)`,
        color: ACCENT,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: size * 0.28,
        fontWeight: 800,
        letterSpacing: '0.04em',
        border: `1px solid ${BORDER}`,
      }}
      aria-label={`${name} 사진 미설정`}
    >
      {initials}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// 메인 컴포넌트
// ─────────────────────────────────────────────────────────────

export function DigitalEmployeeBadge({
  employee,
  variant = 'large',
  onPhotoClick,
  contactPhone = '1600-AJIN',
}: Props) {
  const [flipped, setFlipped] = useState(false);
  const navigate = useNavigate();
  const dim = SIZE[variant];

  const handlePhotoClick = (e: MouseEvent) => {
    if (!onPhotoClick) return;
    e.stopPropagation(); // flip 방지
    onPhotoClick();
  };

  // QR 클릭 → /search?empId={id} 로 navigate (인원 검색에서 자동 선택)
  const handleQrClick = (e: MouseEvent) => {
    e.stopPropagation(); // flip 방지
    if (!employee.employeeId || employee.employeeId === '—') return;
    navigate(`/search?tab=people&empId=${encodeURIComponent(employee.employeeId)}`);
  };

  return (
    <div
      style={{
        width: dim.width,
        height: dim.height,
        perspective: 1200,
        cursor: 'pointer',
        userSelect: 'none',
      }}
      role="button"
      tabIndex={0}
      aria-label={`${employee.name} 디지털 사원증 (클릭 시 앞·뒤 전환)`}
      onClick={() => setFlipped((v) => !v)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          setFlipped((v) => !v);
        }
      }}
    >
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: '100%',
          transformStyle: 'preserve-3d',
          transition: 'transform 0.6s cubic-bezier(0.2, 0.8, 0.2, 1)',
          transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
        }}
      >
        {/* ─── FRONT ─── */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backfaceVisibility: 'hidden',
            WebkitBackfaceVisibility: 'hidden',
            borderRadius: 16,
            background: `linear-gradient(180deg, ${NAVY} 0%, ${NAVY_LIGHT} 100%)`,
            boxShadow: '0 14px 36px rgba(0,0,0,0.28)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            border: `1px solid ${BORDER}`,
            fontFamily: 'var(--hud-font-sans, "Pretendard", system-ui)',
            color: TEXT_LIGHT,
          }}
        >
          {/* 상단 로고 영역 — AJIN INDUSTRY SVG (다크 배경용 화이트 텍스트) */}
          <div
            style={{
              padding: variant === 'large' ? '14px 18px 10px' : '10px 14px 8px',
              borderBottom: `1px solid ${BORDER}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-start',
            }}
          >
            <img
              src="/logos/ajin_logo_dark.svg"
              alt="AJIN INDUSTRY"
              style={{
                height: variant === 'large' ? 22 : 16,
                width: 'auto',
                display: 'block',
                userSelect: 'none',
                pointerEvents: 'none',
              }}
            />
          </div>

          {/* 중앙 사진 영역 */}
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: variant === 'large' ? '18px' : '12px',
              position: 'relative',
            }}
          >
            {employee.photoUrl ? (
              <img
                src={employee.photoUrl}
                alt={`${employee.name} 증명사진`}
                style={{
                  width: dim.photoSize,
                  height: dim.photoSize,
                  borderRadius: 4,
                  objectFit: 'cover',
                  border: `1px solid ${BORDER}`,
                }}
                onClick={handlePhotoClick}
              />
            ) : (
              <div onClick={handlePhotoClick} style={{ cursor: onPhotoClick ? 'pointer' : 'default' }}>
                <InitialsPlaceholder name={employee.name} size={dim.photoSize} />
              </div>
            )}

            {/* 카메라 아이콘 — onPhotoClick 있을 때만 (profile) */}
            {onPhotoClick && (
              <button
                type="button"
                onClick={handlePhotoClick}
                aria-label="사진 변경"
                title="사진 변경"
                style={{
                  position: 'absolute',
                  bottom: variant === 'large' ? 22 : 16,
                  right: variant === 'large' ? 38 : 28,
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  border: `1px solid ${BORDER}`,
                  background: ACCENT,
                  color: NAVY,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.35)',
                  padding: 0,
                }}
              >
                <Camera size={14} strokeWidth={2.2} />
              </button>
            )}
          </div>

          {/* 하단 이름·사번 영역 */}
          <div
            style={{
              padding: variant === 'large' ? '14px 18px 18px' : '10px 14px 14px',
              background: NAVY,
              borderTop: `2px solid ${ACCENT}`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 10 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: dim.nameFs,
                    fontWeight: 700,
                    color: TEXT_LIGHT,
                    lineHeight: 1.15,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {employee.name}
                </div>
                {employee.nameEn && (
                  <div
                    style={{
                      fontSize: dim.logoFs - 2,
                      color: TEXT_DIM,
                      fontFamily: 'var(--hud-font-mono, ui-monospace, monospace)',
                      letterSpacing: '0.04em',
                      marginTop: 2,
                    }}
                  >
                    {employee.nameEn}
                  </div>
                )}
                <div
                  style={{
                    fontSize: dim.logoFs - 3,
                    color: ACCENT,
                    fontFamily: 'var(--hud-font-mono, ui-monospace, monospace)',
                    marginTop: 4,
                    letterSpacing: '0.08em',
                  }}
                >
                  ID · {employee.employeeId}
                </div>
                {(employee.team || employee.position) && (
                  <div
                    style={{
                      fontSize: dim.logoFs - 3,
                      color: TEXT_DIM,
                      marginTop: 2,
                    }}
                  >
                    {employee.position && `${employee.position} · `}{employee.team}
                  </div>
                )}
              </div>
              {/* QR — 클릭 시 인원 검색에서 해당 사원 자동 표시 */}
              <button
                type="button"
                onClick={handleQrClick}
                aria-label={`${employee.name} 인원 검색에서 보기`}
                title="QR 클릭 — 인원 검색 페이지로 이동"
                style={{
                  border: '1px solid rgba(255,255,255,0.3)',
                  borderRadius: 4,
                  padding: 2,
                  background: '#fff',
                  cursor: 'pointer',
                  lineHeight: 0,
                  flexShrink: 0,
                }}
              >
                <QrSvg data={employee.employeeId} size={variant === 'large' ? 48 : 38} />
              </button>
            </div>

            {/* flip 안내 */}
            <div
              style={{
                marginTop: 8,
                fontSize: 9,
                color: TEXT_DIM,
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                opacity: 0.7,
              }}
            >
              <RotateCw size={9} strokeWidth={1.5} />
              <span>탭하여 뒷면 보기</span>
            </div>
          </div>
        </div>

        {/* ─── BACK ─── */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backfaceVisibility: 'hidden',
            WebkitBackfaceVisibility: 'hidden',
            transform: 'rotateY(180deg)',
            borderRadius: 16,
            background: `linear-gradient(180deg, ${NAVY} 0%, ${NAVY_LIGHT} 100%)`,
            boxShadow: '0 14px 36px rgba(0,0,0,0.28)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            border: `1px solid ${BORDER}`,
            fontFamily: 'var(--hud-font-sans, "Pretendard", system-ui)',
            color: TEXT_LIGHT,
            padding: variant === 'large' ? '24px 22px' : '16px 16px',
          }}
        >
          <div
            style={{
              fontSize: dim.logoFs,
              fontWeight: 700,
              letterSpacing: '0.2em',
              color: TEXT_LIGHT,
              marginBottom: variant === 'large' ? 18 : 12,
              paddingBottom: 10,
              borderBottom: `1px solid ${BORDER}`,
            }}
          >
            AJIN AI ASSISTANT
          </div>

          <ol
            style={{
              flex: 1,
              listStyle: 'none',
              padding: 0,
              margin: 0,
              fontSize: variant === 'large' ? 12 : 10.5,
              lineHeight: 1.55,
              color: TEXT_DIM,
              display: 'flex',
              flexDirection: 'column',
              gap: variant === 'large' ? 10 : 7,
            }}
          >
            {[
              '본 증은 근무시에 항상 소지해야 합니다.',
              '본 증은 본인 이외의 타인에게 양도할 수 없습니다.',
              '본 증을 습득하신 분은 아래 연락처로 연락해주시거나, 우체통에 넣어주시기 바랍니다.',
            ].map((s, i) => (
              <li key={i} style={{ display: 'flex', gap: 6, alignItems: 'baseline' }}>
                <span style={{ color: ACCENT, fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>
                <span>{s}</span>
              </li>
            ))}
          </ol>

          {/* 대표전화 chip */}
          <div
            style={{
              marginTop: variant === 'large' ? 16 : 10,
              padding: variant === 'large' ? '10px 12px' : '8px 10px',
              borderRadius: 8,
              border: `1px solid ${ACCENT}`,
              background: 'rgba(251, 191, 36, 0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
            }}
          >
            <span
              style={{
                fontSize: variant === 'large' ? 11 : 9,
                color: TEXT_DIM,
                letterSpacing: '0.12em',
                fontFamily: 'var(--hud-font-mono, ui-monospace, monospace)',
              }}
            >
              대표전화
            </span>
            <span
              style={{
                fontSize: variant === 'large' ? 16 : 13,
                fontWeight: 700,
                color: ACCENT,
                fontFamily: 'var(--hud-font-mono, ui-monospace, monospace)',
                letterSpacing: '0.06em',
              }}
            >
              {contactPhone}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
