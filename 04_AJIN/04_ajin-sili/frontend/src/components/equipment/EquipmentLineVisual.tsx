// EquipmentLineVisual — Drawer 안 하단 영역에 표시되는 라인 시각화 + 설비별 정교한 SVG 애니메이션.
// PR #2-2: 각 설비의 핵심 동작 메커니즘을 시각적으로 구분되도록 재작성.
// 디자인 토큰: var(--hud-text) / var(--hud-text-dim) / var(--hud-primary, #FBBF24).
// 모든 애니메이션은 transform/opacity 만 사용 (GPU compositing).
// off-screen 시 IntersectionObserver 로 pause.

import { useEffect, useMemo, useRef, useState, type ReactElement } from 'react';
import type { EquipRow } from './types';

// ─────────────────────────────────────────────────────────────
// Global keyframes — 모든 설비 애니가 공유. 한 번만 inject.
// ─────────────────────────────────────────────────────────────
const ANIM_KEYFRAMES = `
/* Press — 슬라이드 stroke (TDC→BDC→TDC) sine 형태 */
@keyframes ela-press-slide { 0%,100% { transform: translateY(0); } 45% { transform: translateY(20px); } 50% { transform: translateY(22px); } 55% { transform: translateY(20px); } }
@keyframes ela-press-feed  { 0% { transform: translateX(0); } 30% { transform: translateX(0); } 70% { transform: translateX(-10px); } 100% { transform: translateX(-10px); } }
@keyframes ela-press-load  { 0%,40%,60%,100% { opacity: 0.3; } 48%,55% { opacity: 1; } }

/* Welder — 전극 가압 + arc flash + 비드 진행 */
@keyframes ela-weld-elec-top { 0%,100% { transform: translateY(0); } 20%,55% { transform: translateY(7px); } }
@keyframes ela-weld-elec-bot { 0%,100% { transform: translateY(0); } 20%,55% { transform: translateY(-7px); } }
@keyframes ela-weld-arc      { 0%,18%,58%,100% { opacity: 0; transform: scale(0.5); } 25%,52% { opacity: 1; transform: scale(1); } }
@keyframes ela-weld-spark    { 0% { opacity: 0; transform: scale(0.4) translate(0,0); } 30% { opacity: 1; } 100% { opacity: 0; transform: scale(1.2) translate(var(--dx,0), var(--dy,0)); } }
@keyframes ela-weld-bead     { 0%,20% { stroke-dashoffset: 30; } 60%,100% { stroke-dashoffset: 0; } }

/* Robot — 베이스 + 6축 pick & place */
@keyframes ela-robot-base { 0%,100% { transform: rotate(-20deg); } 50% { transform: rotate(20deg); } }
@keyframes ela-robot-j2   { 0%,100% { transform: rotate(28deg); }  50% { transform: rotate(-12deg); } }
@keyframes ela-robot-j3   { 0%,100% { transform: rotate(-22deg); } 50% { transform: rotate(34deg); } }
@keyframes ela-robot-grip { 0%,42% { opacity: 0; }                 48%,90% { opacity: 1; } 100% { opacity: 0; } }
@keyframes ela-robot-path { from { stroke-dashoffset: 80; } to { stroke-dashoffset: 0; } }

/* Injection — 5-phase: close → inject → hold → cool → open+eject */
@keyframes ela-inj-mold-l   { 0%,8%   { transform: translateX(8px); }   16%,80% { transform: translateX(0); }   88%,100% { transform: translateX(8px); } }
@keyframes ela-inj-mold-r   { 0%,8%   { transform: translateX(-8px); }  16%,80% { transform: translateX(0); }   88%,100% { transform: translateX(-8px); } }
@keyframes ela-inj-screw    { 0%,16%  { transform: translateX(0); }     30%,40% { transform: translateX(10px); } 88%,100% { transform: translateX(0); } }
@keyframes ela-inj-melt     { 0%,18%  { opacity: 0; }                   30%,45% { opacity: 1; }                   60%,100% { opacity: 0; } }
@keyframes ela-inj-cool     { 0%,45%  { fill-opacity: 0; }              55%,75% { fill-opacity: 0.55; }           88%,100% { fill-opacity: 0; } }
@keyframes ela-inj-eject    { 0%,82%  { opacity: 0; transform: translateY(0); }  90%,98% { opacity: 1; transform: translateY(10px); } }

/* CNC — spindle 고속 회전 + 워크피스 XY 이동 + 칩 비산 */
@keyframes ela-spin-fast  { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes ela-cnc-work-x { 0%,100% { transform: translateX(0); }   33% { transform: translateX(8px); }    66% { transform: translateX(-8px); } }
@keyframes ela-cnc-work-y { 0%,100% { transform: translateY(0); }   33% { transform: translateY(-3px); }   66% { transform: translateY(3px); } }
@keyframes ela-cnc-chip   { 0% { opacity: 0.9; transform: translate(0,0) scale(1); } 100% { opacity: 0; transform: translate(var(--dx,10px), var(--dy,-8px)) scale(0.4); } }
@keyframes ela-cnc-tool   { 0%,100% { transform: translateY(0); } 40%,60% { transform: translateY(3px); } }

/* Laser — 갈바노 미러 회전 + 빔 + 절단 경로 + assist gas */
@keyframes ela-laser-mir-x  { 0%,100% { transform: rotate(-15deg); } 50% { transform: rotate(15deg); } }
@keyframes ela-laser-mir-y  { 0%,100% { transform: rotate(20deg); }  50% { transform: rotate(-20deg); } }
@keyframes ela-laser-head   { 0% { transform: translate(0,0); } 50% { transform: translate(60px, 20px); } 100% { transform: translate(0,0); } }
@keyframes ela-laser-beam   { 0%,100% { opacity: 0.55; } 50% { opacity: 1; } }
@keyframes ela-laser-dash   { from { stroke-dashoffset: 150; } to { stroke-dashoffset: 0; } }
@keyframes ela-laser-gas    { 0% { opacity: 0; transform: scale(0.5); } 50% { opacity: 0.5; } 100% { opacity: 0; transform: scale(1.6); } }

/* Utility — 컴프레서 piston + 탱크 + 게이지 바늘 + 파이프 air flow */
@keyframes ela-util-piston  { 0%,100% { transform: translateY(0); } 50% { transform: translateY(8px); } }
@keyframes ela-util-needle  { 0%,100% { transform: rotate(-40deg); } 25% { transform: rotate(20deg); } 50% { transform: rotate(40deg); } 75% { transform: rotate(-10deg); } }
@keyframes ela-util-bubble  { 0% { opacity: 0; transform: translateX(0); } 30% { opacity: 1; } 100% { opacity: 0; transform: translateX(40px); } }
@keyframes ela-util-fan     { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* Conveyor belt — item flow */
@keyframes ela-item-flow    { 0% { transform: translateX(0); } 100% { transform: translateX(360px); } }
`;

// ─────────────────────────────────────────────────────────────
// 1. Press — 다단 슬라이드 (TDC→BDC) + 가이드 포스트 + 판재 송재 + 하중 표시
// ─────────────────────────────────────────────────────────────
function PressAnim() {
  return (
    <svg viewBox="0 0 130 110" style={{ width: '100%', height: 'auto', display: 'block' }}>
      {/* 프레임 (C-frame) */}
      <rect x="10" y="6"   width="110" height="6" fill="var(--hud-text-dim)" opacity="0.55" />
      <rect x="10" y="92"  width="110" height="6" fill="var(--hud-text-dim)" opacity="0.55" />
      <rect x="10" y="6"   width="6"   height="92" fill="var(--hud-text-dim)" opacity="0.55" />
      <rect x="114" y="6"  width="6"   height="92" fill="var(--hud-text-dim)" opacity="0.55" />

      {/* 4개 가이드 포스트 */}
      {[26, 46, 84, 104].map((x) => (
        <line key={x} x1={x} y1="14" x2={x} y2="90" stroke="var(--hud-text-dim)" strokeWidth="0.8" strokeDasharray="2 3" opacity="0.5" />
      ))}

      {/* 하부 다이 (고정) */}
      <rect x="24" y="80" width="82" height="10" rx="1.5" fill="var(--hud-text-dim)" />
      <rect x="32" y="72" width="66" height="8" rx="1" fill="var(--hud-text-dim)" opacity="0.7" />

      {/* 판재 (코일에서 송재) */}
      <g style={{ animation: 'ela-press-feed 1.4s ease-in-out infinite' }}>
        <rect x="20" y="68" width="80" height="4" rx="0.5" fill="var(--hud-primary, #FBBF24)" opacity="0.75" />
      </g>

      {/* 송재 롤러 (좌) */}
      <circle cx="20" cy="70" r="4" fill="none" stroke="var(--hud-text-dim)" strokeWidth="1" />
      <circle cx="20" cy="70" r="1.5" fill="var(--hud-text-dim)" />

      {/* 상부 다이 + 슬라이드 (왕복) */}
      <g style={{ animation: 'ela-press-slide 1.4s ease-in-out infinite' }}>
        <rect x="22" y="40" width="86" height="8" rx="1.5" fill="var(--hud-primary, #FBBF24)" />
        <rect x="36" y="48" width="58" height="20" fill="var(--hud-primary, #FBBF24)" opacity="0.88" />
        <rect x="42" y="68" width="46" height="4" fill="var(--hud-primary, #FBBF24)" opacity="0.6" />
      </g>

      {/* 위치 라벨 */}
      <line x1="6" y1="40" x2="10" y2="40" stroke="var(--hud-text-dim)" strokeWidth="0.5" />
      <line x1="6" y1="72" x2="10" y2="72" stroke="var(--hud-text-dim)" strokeWidth="0.5" />
      <text x="0" y="42" fontSize="6" fill="var(--hud-text-dim)">TDC</text>
      <text x="0" y="74" fontSize="6" fill="var(--hud-text-dim)">BDC</text>

      {/* 하중 인디케이터 (BDC 시 깜빡) */}
      <g style={{ animation: 'ela-press-load 1.4s ease-in-out infinite' }}>
        <circle cx="60" cy="100" r="2" fill="var(--hud-primary, #FBBF24)" />
        <circle cx="65" cy="100" r="2" fill="var(--hud-primary, #FBBF24)" />
        <circle cx="70" cy="100" r="2" fill="var(--hud-primary, #FBBF24)" />
      </g>
      <text x="76" y="103" fontSize="6" fill="var(--hud-primary, #FBBF24)">800 ton</text>
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// 2. Welder — 스폿 용접: 전극 상하 가압 + arc flash + 비드 진행 + 다방향 spark
// ─────────────────────────────────────────────────────────────
function WelderAnim() {
  return (
    <svg viewBox="0 0 130 110" style={{ width: '100%', height: 'auto', display: 'block' }}>
      <defs>
        <filter id="weld-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" />
        </filter>
        <radialGradient id="arc-grad" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="60%" stopColor="var(--hud-primary, #FBBF24)" stopOpacity="0.9" />
          <stop offset="100%" stopColor="var(--hud-primary, #FBBF24)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* 두 부품 (포개진 시트) */}
      <rect x="14" y="48" width="50" height="6" rx="1" fill="var(--hud-text-dim)" opacity="0.6" />
      <rect x="14" y="54" width="50" height="6" rx="1" fill="var(--hud-text-dim)" opacity="0.75" />
      <rect x="66" y="48" width="50" height="6" rx="1" fill="var(--hud-text-dim)" opacity="0.6" />
      <rect x="66" y="54" width="50" height="6" rx="1" fill="var(--hud-text-dim)" opacity="0.75" />

      {/* 비드 (용접점들) — dashoffset 으로 진행 표시 */}
      <line
        x1="20" y1="54" x2="110" y2="54"
        stroke="var(--hud-primary, #FBBF24)" strokeWidth="3.5"
        strokeLinecap="round" strokeDasharray="5 7"
        style={{ animation: 'ela-weld-bead 2.4s ease-in-out infinite' }}
      />

      {/* 상부 전극 (가압 하강) */}
      <g style={{ animation: 'ela-weld-elec-top 2.4s ease-in-out infinite' }}>
        <rect x="62" y="6" width="6" height="28" fill="var(--hud-text)" />
        <polygon points="60,34 70,34 65,46" fill="var(--hud-text)" />
      </g>

      {/* 하부 전극 (가압 상승) */}
      <g style={{ animation: 'ela-weld-elec-bot 2.4s ease-in-out infinite' }}>
        <polygon points="60,76 70,76 65,64" fill="var(--hud-text)" />
        <rect x="62" y="76" width="6" height="28" fill="var(--hud-text)" />
      </g>

      {/* 아크 flash (가운데) */}
      <g style={{ animation: 'ela-weld-arc 2.4s ease-in-out infinite' }}>
        <circle cx="65" cy="54" r="10" fill="url(#arc-grad)" filter="url(#weld-glow)" />
        <circle cx="65" cy="54" r="4" fill="#ffffff" opacity="0.85" />
      </g>

      {/* 스파크 (8방향) */}
      {[
        { dx: -14, dy: -10, d: '0.1s' }, { dx: 14, dy: -10, d: '0.2s' },
        { dx: -16, dy: 0, d: '0.0s' },   { dx: 16, dy: 0, d: '0.15s' },
        { dx: -10, dy: 12, d: '0.05s' }, { dx: 10, dy: 12, d: '0.25s' },
        { dx: 0, dy: -16, d: '0.1s' },   { dx: 0, dy: 16, d: '0.3s' },
      ].map((p, i) => (
        <circle
          key={i} cx="65" cy="54" r="1.8" fill="var(--hud-primary, #FBBF24)" filter="url(#weld-glow)"
          style={{ animation: 'ela-weld-spark 1.2s ease-out infinite', animationDelay: p.d, ['--dx' as any]: `${p.dx}px`, ['--dy' as any]: `${p.dy}px` }}
        />
      ))}

      {/* 라벨 */}
      <text x="4" y="14" fontSize="6" fill="var(--hud-text-dim)" fontFamily="monospace">I = 8.5kA</text>
      <text x="4" y="104" fontSize="6" fill="var(--hud-text-dim)" fontFamily="monospace">t = 200ms</text>
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// 3. Robot — 6축 산업로봇 pick & place + toolpath 점선
// ─────────────────────────────────────────────────────────────
function RobotArmAnim() {
  return (
    <svg viewBox="0 0 130 110" style={{ width: '100%', height: 'auto', display: 'block' }}>
      {/* 워크테이블 */}
      <rect x="8" y="92" width="114" height="6" rx="1" fill="var(--hud-text-dim)" opacity="0.4" />

      {/* pick / place 부품 */}
      <rect x="16" y="84" width="14" height="8" rx="1" fill="var(--hud-text-dim)" opacity="0.7" />
      <rect x="100" y="84" width="14" height="8" rx="1" fill="var(--hud-primary, #FBBF24)" opacity="0.55" />

      {/* toolpath 점선 (그리퍼가 따라가는 경로) */}
      <path d="M 23 84 Q 65 16 107 84" fill="none" stroke="var(--hud-primary, #FBBF24)" strokeWidth="0.8" strokeDasharray="3 4" opacity="0.5"
        style={{ animation: 'ela-robot-path 2.4s linear infinite' }} />

      {/* 베이스 */}
      <rect x="56" y="78" width="18" height="12" rx="1.5" fill="var(--hud-text-dim)" />
      <rect x="58" y="74" width="14" height="6" rx="0.5" fill="var(--hud-text-dim)" opacity="0.8" />

      {/* 축 1: 베이스 회전 */}
      <g style={{ transformOrigin: '65px 78px', animation: 'ela-robot-base 4s ease-in-out infinite' }}>
        {/* 축 2: 어깨 */}
        <rect x="62" y="38" width="6" height="38" rx="1" fill="var(--hud-text)" opacity="0.85" />
        <circle cx="65" cy="38" r="5" fill="var(--hud-primary, #FBBF24)" />

        <g style={{ transformOrigin: '65px 38px', animation: 'ela-robot-j2 4s ease-in-out infinite' }}>
          {/* 축 3: 팔꿈치 (전완) */}
          <rect x="65" y="20" width="30" height="4" rx="1" fill="var(--hud-text)" opacity="0.85" />
          <circle cx="95" cy="22" r="4" fill="var(--hud-primary, #FBBF24)" />

          <g style={{ transformOrigin: '95px 22px', animation: 'ela-robot-j3 4s ease-in-out infinite' }}>
            {/* 축 4-5-6: 손목 + 그리퍼 */}
            <rect x="95" y="20" width="14" height="6" rx="1" fill="var(--hud-text)" />
            <rect x="103" y="26" width="4" height="6" fill="var(--hud-primary, #FBBF24)" />
            {/* 그리퍼 jaws */}
            <line x1="101" y1="32" x2="98" y2="38" stroke="var(--hud-primary, #FBBF24)" strokeWidth="1.5" strokeLinecap="round" />
            <line x1="107" y1="32" x2="110" y2="38" stroke="var(--hud-primary, #FBBF24)" strokeWidth="1.5" strokeLinecap="round" />
            {/* 잡은 부품 (cycle 후반에만 표시) */}
            <rect x="100" y="38" width="8" height="6" rx="0.5" fill="var(--hud-primary, #FBBF24)"
              style={{ animation: 'ela-robot-grip 4s ease-in-out infinite' }} />
          </g>
        </g>
      </g>

      <text x="4" y="14" fontSize="6" fill="var(--hud-text-dim)" fontFamily="monospace">6-Axis · ±0.05mm</text>
      <text x="4" y="106" fontSize="6" fill="var(--hud-text-dim)" fontFamily="monospace">Pick &amp; Place</text>
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// 4. Injection — 5-phase: close → inject → hold → cool → open+eject
//    호퍼 + 스크류 + barrel + 노즐 + 캐비티
// ─────────────────────────────────────────────────────────────
function InjectionAnim() {
  return (
    <svg viewBox="0 0 130 110" style={{ width: '100%', height: 'auto', display: 'block' }}>
      {/* 호퍼 (수지 펠릿 투입) */}
      <polygon points="14,8 36,8 32,22 18,22" fill="var(--hud-text-dim)" opacity="0.55" />
      {[1, 2, 3, 4, 5].map((i) => (
        <circle key={i} cx={18 + ((i * 7) % 14)} cy={14 + (i % 2) * 4} r="1" fill="var(--hud-text-dim)" opacity="0.7" />
      ))}

      {/* Barrel (가열·스크류 회전) */}
      <rect x="14" y="22" width="60" height="14" rx="2" fill="var(--hud-text-dim)" opacity="0.7" />
      {/* 가열 밴드 */}
      {[20, 30, 40, 50, 60].map((x) => (
        <rect key={x} x={x} y="20" width="6" height="2" fill="var(--hud-primary, #FBBF24)" opacity="0.7" />
      ))}
      {/* 스크류 (전진) */}
      <g style={{ animation: 'ela-inj-screw 3.2s ease-in-out infinite' }}>
        <rect x="16" y="26" width="36" height="6" rx="1" fill="var(--hud-text)" opacity="0.85" />
        <line x1="20" y1="26" x2="20" y2="32" stroke="var(--hud-primary, #FBBF24)" strokeWidth="0.8" />
        <line x1="28" y1="26" x2="28" y2="32" stroke="var(--hud-primary, #FBBF24)" strokeWidth="0.8" />
        <line x1="36" y1="26" x2="36" y2="32" stroke="var(--hud-primary, #FBBF24)" strokeWidth="0.8" />
        <line x1="44" y1="26" x2="44" y2="32" stroke="var(--hud-primary, #FBBF24)" strokeWidth="0.8" />
      </g>
      {/* 노즐 */}
      <polygon points="74,24 84,24 80,34 78,34" fill="var(--hud-text)" />

      {/* 좌 mold (이동) */}
      <g style={{ animation: 'ela-inj-mold-l 3.2s ease-in-out infinite' }}>
        <rect x="34" y="44" width="44" height="46" rx="2" fill="var(--hud-text-dim)" opacity="0.5" />
        <path d="M 70 60 L 78 60 L 78 78 L 70 78 Z" fill="var(--hud-text)" fillOpacity="0.2" stroke="var(--hud-primary, #FBBF24)" strokeWidth="0.5" />
        {/* 냉각 (시간차 색) */}
        <rect x="70" y="60" width="8" height="18" fill="#7dd3fc"
          style={{ animation: 'ela-inj-cool 3.2s ease-in-out infinite' }} />
      </g>
      {/* 우 mold (이동) */}
      <g style={{ animation: 'ela-inj-mold-r 3.2s ease-in-out infinite' }}>
        <rect x="80" y="44" width="38" height="46" rx="2" fill="var(--hud-text-dim)" opacity="0.5" />
        <path d="M 80 60 L 88 60 L 88 78 L 80 78 Z" fill="var(--hud-text)" fillOpacity="0.2" />
      </g>

      {/* 수지 흐름 (inject phase 만 표시) */}
      <g style={{ animation: 'ela-inj-melt 3.2s linear infinite' }}>
        <rect x="79" y="34" width="2" height="32" fill="var(--hud-primary, #FBBF24)" />
        <ellipse cx="74" cy="69" rx="6" ry="3" fill="var(--hud-primary, #FBBF24)" opacity="0.9" />
      </g>

      {/* 취출 부품 (eject phase) */}
      <rect x="68" y="92" width="12" height="6" rx="1" fill="var(--hud-primary, #FBBF24)" opacity="0.85"
        style={{ animation: 'ela-inj-eject 3.2s ease-in-out infinite' }} />

      {/* 라벨 */}
      <text x="4" y="106" fontSize="6" fill="var(--hud-text-dim)" fontFamily="monospace">P = 1400 bar</text>
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// 5. CNC — spindle 고속 회전 + 워크피스 XY 이동 + 절삭칩 비산 + tool 접근
// ─────────────────────────────────────────────────────────────
function CNCAnim() {
  return (
    <svg viewBox="0 0 130 110" style={{ width: '100%', height: 'auto', display: 'block' }}>
      {/* 가공기 베드 + X-Y rail */}
      <rect x="8" y="84" width="114" height="14" rx="2" fill="var(--hud-text-dim)" opacity="0.4" />
      <line x1="10" y1="78" x2="120" y2="78" stroke="var(--hud-text-dim)" strokeWidth="0.5" opacity="0.4" strokeDasharray="3 2" />

      {/* 워크피스 + 척 (XY 이동) */}
      <g style={{ animation: 'ela-cnc-work-x 4s ease-in-out infinite' }}>
        <g style={{ animation: 'ela-cnc-work-y 4s ease-in-out infinite' }}>
          {/* 척 */}
          <rect x="42" y="74" width="46" height="10" rx="1.5" fill="var(--hud-text-dim)" />
          {/* 워크피스 */}
          <rect x="50" y="64" width="30" height="12" rx="0.5" fill="var(--hud-primary, #FBBF24)" opacity="0.7" />
          {/* 절삭 자국 (점선) */}
          <line x1="52" y1="64" x2="78" y2="64" stroke="var(--hud-text)" strokeWidth="0.5" strokeDasharray="2 1" opacity="0.7" />
        </g>
      </g>

      {/* 스핀들 헤드 */}
      <rect x="55" y="10" width="20" height="22" rx="2" fill="var(--hud-text-dim)" />
      <rect x="58" y="32" width="14" height="4" fill="var(--hud-text)" />

      {/* spindle + tool (회전 + 약한 상하) */}
      <g style={{ animation: 'ela-cnc-tool 1s ease-in-out infinite' }}>
        <g style={{ transformOrigin: '65px 45px', animation: 'ela-spin-fast 0.18s linear infinite' }}>
          <rect x="62" y="36" width="6" height="20" rx="0.5" fill="var(--hud-text)" />
          {/* 4-flute 절삭날 */}
          <line x1="62" y1="40" x2="60" y2="42" stroke="var(--hud-text-dim)" strokeWidth="1.5" />
          <line x1="68" y1="40" x2="70" y2="42" stroke="var(--hud-text-dim)" strokeWidth="1.5" />
          <line x1="62" y1="50" x2="60" y2="52" stroke="var(--hud-text-dim)" strokeWidth="1.5" />
          <line x1="68" y1="50" x2="70" y2="52" stroke="var(--hud-text-dim)" strokeWidth="1.5" />
          {/* tip */}
          <polygon points="62,56 68,56 65,62" fill="var(--hud-primary, #FBBF24)" />
        </g>
      </g>

      {/* 절삭칩 (가공점에서 비산) */}
      {[
        { dx: -22, dy: -16, d: '0s' }, { dx: 20, dy: -14, d: '0.1s' },
        { dx: -16, dy: -22, d: '0.2s' }, { dx: 14, dy: -20, d: '0.3s' },
        { dx: -10, dy: -8, d: '0.15s' }, { dx: 12, dy: -8, d: '0.25s' },
      ].map((p, i) => (
        <rect
          key={i} x="63" y="62" width="2" height="2" rx="0.3" fill="var(--hud-text-dim)"
          style={{ animation: 'ela-cnc-chip 0.6s ease-out infinite', animationDelay: p.d, ['--dx' as any]: `${p.dx}px`, ['--dy' as any]: `${p.dy}px`, transformOrigin: 'center' }}
        />
      ))}

      <text x="4" y="14" fontSize="6" fill="var(--hud-text-dim)" fontFamily="monospace">12,000 RPM</text>
      <text x="4" y="106" fontSize="6" fill="var(--hud-text-dim)" fontFamily="monospace">F = 850 mm/min</text>
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// 6. Laser — 갈바노 미러 (2축 회전) + 집속 빔 + 절단 경로 + assist gas
// ─────────────────────────────────────────────────────────────
function LaserAnim() {
  return (
    <svg viewBox="0 0 130 110" style={{ width: '100%', height: 'auto', display: 'block' }}>
      <defs>
        <filter id="laser-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="1.4" />
        </filter>
      </defs>

      {/* 워크피스 */}
      <rect x="14" y="56" width="100" height="44" rx="1" fill="var(--hud-text-dim)" opacity="0.4" />
      <rect x="14" y="56" width="100" height="2" fill="var(--hud-text-dim)" opacity="0.6" />

      {/* 절단 경로 (사각형) */}
      <path
        d="M 32 66 L 96 66 L 96 90 L 32 90 Z"
        fill="none" stroke="var(--hud-primary, #FBBF24)" strokeWidth="1.2" strokeDasharray="5 3" opacity="0.85"
        style={{ animation: 'ela-laser-dash 3s linear infinite' }}
      />

      {/* 레이저 발진기 (좌상) */}
      <rect x="6" y="6" width="22" height="14" rx="1.5" fill="var(--hud-text-dim)" />
      <text x="8" y="16" fontSize="6" fill="var(--hud-primary, #FBBF24)" fontFamily="monospace">CO₂</text>

      {/* 빔 가이드 (수평) */}
      <line x1="28" y1="13" x2="58" y2="13" stroke="var(--hud-primary, #FBBF24)" strokeWidth="1" opacity="0.8"
        style={{ animation: 'ela-laser-beam 0.5s ease-in-out infinite' }} />

      {/* 갈바노 미러 1 (X) */}
      <g style={{ transformOrigin: '58px 13px', animation: 'ela-laser-mir-x 3s ease-in-out infinite' }}>
        <rect x="54" y="10" width="8" height="6" rx="0.5" fill="var(--hud-text)" opacity="0.85" />
      </g>

      {/* 미러 1 → 미러 2 빔 */}
      <line x1="58" y1="13" x2="68" y2="28" stroke="var(--hud-primary, #FBBF24)" strokeWidth="1" opacity="0.8"
        style={{ animation: 'ela-laser-beam 0.5s ease-in-out infinite' }} />

      {/* 갈바노 미러 2 (Y) */}
      <g style={{ transformOrigin: '68px 28px', animation: 'ela-laser-mir-y 3s ease-in-out infinite' }}>
        <rect x="64" y="25" width="8" height="6" rx="0.5" fill="var(--hud-text)" opacity="0.85" />
      </g>

      {/* 헤드 + 집속 렌즈 + 빔 (이동) */}
      <g style={{ animation: 'ela-laser-head 3.4s ease-in-out infinite' }}>
        {/* 렌즈 housing */}
        <rect x="62" y="32" width="12" height="10" rx="1" fill="var(--hud-text-dim)" />
        <ellipse cx="68" cy="42" rx="4" ry="1.5" fill="var(--hud-primary, #FBBF24)" opacity="0.7" />
        {/* assist gas (원형 퍼짐) */}
        <circle cx="68" cy="56" r="6" fill="none" stroke="#7dd3fc" strokeWidth="0.5" opacity="0.6"
          style={{ animation: 'ela-laser-gas 1.4s ease-out infinite' }} />
        {/* 빔 (집속 → 절단점) */}
        <line x1="68" y1="42" x2="68" y2="56" stroke="var(--hud-primary, #FBBF24)" strokeWidth="1.5"
          filter="url(#laser-glow)"
          style={{ animation: 'ela-laser-beam 0.4s ease-in-out infinite' }} />
        {/* 절단점 (밝은 점) */}
        <circle cx="68" cy="56" r="2.2" fill="#ffffff" opacity="0.95" filter="url(#laser-glow)" />
      </g>

      <text x="4" y="106" fontSize="6" fill="var(--hud-text-dim)" fontFamily="monospace">3.0 kW · N₂ assist</text>
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────
// 7. Utility — 컴프레서 piston 왕복 + 공압 탱크 + 게이지 + 파이프 air flow + 냉각 fan
// ─────────────────────────────────────────────────────────────
function UtilityAnim() {
  return (
    <svg viewBox="0 0 130 110" style={{ width: '100%', height: 'auto', display: 'block' }}>
      {/* 베이스 */}
      <rect x="6" y="92" width="118" height="6" rx="1" fill="var(--hud-text-dim)" opacity="0.5" />

      {/* 컴프레서 본체 (좌) — piston */}
      <rect x="10" y="34" width="26" height="58" rx="2" fill="var(--hud-text-dim)" opacity="0.6" />
      <rect x="14" y="38" width="18" height="42" fill="var(--hud-text)" opacity="0.2" />
      {/* 실린더 head */}
      <rect x="14" y="22" width="18" height="14" rx="1" fill="var(--hud-text)" />
      {/* piston rod */}
      <line x1="23" y1="36" x2="23" y2="78" stroke="var(--hud-text)" strokeWidth="1" opacity="0.6" />
      {/* piston (왕복) */}
      <g style={{ animation: 'ela-util-piston 1.2s ease-in-out infinite' }}>
        <rect x="14" y="50" width="18" height="8" rx="0.5" fill="var(--hud-primary, #FBBF24)" />
        <line x1="14" y1="52" x2="32" y2="52" stroke="var(--hud-text)" strokeWidth="0.5" />
        <line x1="14" y1="56" x2="32" y2="56" stroke="var(--hud-text)" strokeWidth="0.5" />
      </g>

      {/* 송출 파이프 (좌→우 air flow) */}
      <line x1="36" y1="56" x2="76" y2="56" stroke="var(--hud-text-dim)" strokeWidth="3" opacity="0.65" />
      {/* air bubble */}
      {[0, 0.3, 0.6, 0.9].map((d, i) => (
        <circle key={i} cx="38" cy="56" r="1.5" fill="var(--hud-primary, #FBBF24)" opacity="0.85"
          style={{ animation: 'ela-util-bubble 1.6s linear infinite', animationDelay: `${d}s` }} />
      ))}

      {/* 공압 탱크 (중-우) */}
      <ellipse cx="92" cy="56" rx="24" ry="20" fill="var(--hud-text-dim)" opacity="0.55" />
      <ellipse cx="92" cy="56" rx="20" ry="16" fill="var(--hud-text)" opacity="0.18" />
      {/* 탱크 게이지 (위) */}
      <circle cx="92" cy="32" r="9" fill="var(--hud-text)" opacity="0.85" />
      <circle cx="92" cy="32" r="7" fill="var(--hud-surface, #fff)" opacity="0.9" />
      {/* 게이지 눈금 */}
      <path d="M 86 36 A 7 7 0 0 1 98 36" fill="none" stroke="var(--hud-text-dim)" strokeWidth="0.6" />
      {/* 바늘 (회전) */}
      <g style={{ transformOrigin: '92px 32px', animation: 'ela-util-needle 3s ease-in-out infinite' }}>
        <line x1="92" y1="32" x2="92" y2="26" stroke="var(--hud-primary, #FBBF24)" strokeWidth="1.2" strokeLinecap="round" />
        <circle cx="92" cy="32" r="1.2" fill="var(--hud-text)" />
      </g>

      {/* 냉각 fan (탱크 우측) */}
      <circle cx="118" cy="56" r="9" fill="none" stroke="var(--hud-text-dim)" strokeWidth="0.8" opacity="0.5" />
      <g style={{ transformOrigin: '118px 56px', animation: 'ela-util-fan 1.4s linear infinite' }}>
        {[0, 90, 180, 270].map((deg) => (
          <ellipse key={deg} cx="118" cy="56" rx="1.6" ry="7" fill="var(--hud-primary, #FBBF24)" opacity="0.8" transform={`rotate(${deg} 118 56)`} />
        ))}
        <circle cx="118" cy="56" r="2" fill="var(--hud-text)" />
      </g>

      {/* 라벨 */}
      <text x="4" y="14" fontSize="6" fill="var(--hud-text-dim)" fontFamily="monospace">7.5 bar · 230 L/min</text>
    </svg>
  );
}

const ANIM_MAP: Record<string, () => ReactElement> = {
  '프레스': PressAnim,
  '용접기': WelderAnim,
  '로봇': RobotArmAnim,
  '사출기': InjectionAnim,
  'CNC': CNCAnim,
  '레이저': LaserAnim,
  '공통설비': UtilityAnim,
};

// ─────────────────────────────────────────────────────────────
// ConveyorLine — 가로 컨베이어 + 4공정 dot + 확률 기반 OK/BAD 시뮬레이션
// ─────────────────────────────────────────────────────────────

interface ConveyorProps {
  row: EquipRow;
}

const PROC_NAMES = ['공정 1', '공정 2', '공정 3', '공정 4'];
const PROC_POSITIONS = [0.22, 0.40, 0.58, 0.76];

interface FlyingItem {
  id: number;
  status: 'pending' | 'ok' | 'bad';
}

function defectProb(alarm: number, idx: number): number {
  const base = Math.min(0.5, alarm / 100);
  const variation = 0.04 * (idx + 1);
  return Math.max(0.02, Math.min(0.7, base + variation));
}

function ConveyorLine({ row }: ConveyorProps) {
  const [items, setItems] = useState<FlyingItem[]>([]);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isVisible, setIsVisible] = useState(true);
  const idRef = useRef(0);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new IntersectionObserver(
      (entries) => setIsVisible(entries[0].isIntersecting),
      { threshold: 0.1 },
    );
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (!isVisible) return;
    const interval = window.setInterval(() => {
      setItems((prev) => {
        idRef.current += 1;
        const newItem: FlyingItem = { id: idRef.current, status: 'pending' };
        const sliced = prev.length > 7 ? prev.slice(-7) : prev;
        return [...sliced, newItem];
      });
    }, 1300);
    return () => window.clearInterval(interval);
  }, [isVisible]);

  useEffect(() => {
    items.forEach((item) => {
      if (item.status !== 'pending') return;
      const tid = window.setTimeout(() => {
        let isBad = false;
        for (let i = 0; i < 4; i++) {
          if (Math.random() < defectProb(row.alarm, i)) {
            isBad = true;
            break;
          }
        }
        setItems((prev) =>
          prev.map((it) => (it.id === item.id ? { ...it, status: isBad ? 'bad' : 'ok' } : it)),
        );
      }, 2500);
      return () => window.clearTimeout(tid);
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length, row.alarm]);

  const procDefectPct = useMemo(
    () => PROC_NAMES.map((_, i) => Math.round(defectProb(row.alarm, i) * 100)),
    [row.alarm],
  );

  return (
    <div
      ref={containerRef}
      style={{
        background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
        borderRadius: 10,
        padding: 14,
        fontFamily: 'var(--hud-font-sans)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', fontFamily: 'var(--hud-font-mono)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
          PROCESS LINE · 실시간 공정 시뮬레이션
        </div>
        <div style={{ fontSize: 10, color: 'var(--hud-text-muted, var(--hud-text-dim))' }}>
          알람 {row.alarm}건 기반 확률 모델 · 시연용 mock
        </div>
      </div>

      <div style={{ position: 'relative', height: 90, marginBottom: 14 }}>
        <div
          style={{
            position: 'absolute', left: 0, right: 0, top: 30, height: 30, borderRadius: 4,
            background: 'repeating-linear-gradient(90deg, rgba(120,120,120,0.25) 0px, rgba(120,120,120,0.25) 10px, rgba(120,120,120,0.4) 10px, rgba(120,120,120,0.4) 20px)',
            opacity: 0.45,
          }}
        />
        <div style={{ position: 'absolute', left: 0, right: 0, top: 28, height: 2, background: 'color-mix(in oklab, var(--hud-text) 22%, transparent)' }} />
        <div style={{ position: 'absolute', left: 0, right: 0, top: 60, height: 2, background: 'color-mix(in oklab, var(--hud-text) 22%, transparent)' }} />

        {PROC_POSITIONS.map((pct, i) => {
          const dpct = procDefectPct[i];
          const risk =
            dpct < 10 ? '#639922'
            : dpct < 20 ? '#97c459'
            : dpct < 30 ? '#ef9f27'
            : dpct < 45 ? '#d85a30'
            : '#e24b4a';
          return (
            <div key={i} style={{ position: 'absolute', left: `${pct * 100}%`, top: 0, transform: 'translateX(-50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, zIndex: 5 }}>
              <div style={{ fontSize: 9, color: 'var(--hud-text-dim)', whiteSpace: 'nowrap' }}>{PROC_NAMES[i]}</div>
              <div style={{ width: 14, height: 14, borderRadius: '50%', background: risk, boxShadow: `0 0 8px ${risk}44` }} />
              <div style={{ fontSize: 10, fontWeight: 600, color: risk, marginTop: 26 }}>{dpct}%</div>
            </div>
          );
        })}

        {items.map((item, idx) => (
          <div
            key={item.id}
            style={{
              position: 'absolute', top: 36, left: 0, width: 18, height: 18, borderRadius: 4,
              background:
                item.status === 'ok' ? '#c0dd97'
                : item.status === 'bad' ? '#f09595'
                : 'color-mix(in oklab, var(--hud-text) 25%, transparent)',
              border:
                item.status === 'ok' ? '1.5px solid #639922'
                : item.status === 'bad' ? '1.5px solid #a32d2d'
                : '1.5px solid color-mix(in oklab, var(--hud-text) 45%, transparent)',
              animation: `ela-item-flow 5s linear forwards`,
              animationDelay: `${idx * -0.4}s`,
              zIndex: 3, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11,
              color: item.status === 'ok' ? '#3b6d11' : item.status === 'bad' ? '#791f1f' : 'var(--hud-text)',
              fontWeight: 700,
            }}
            aria-hidden
          >
            {item.status === 'ok' ? '✓' : item.status === 'bad' ? '✕' : ''}
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
        {[
          { k: 'OK', v: items.filter((i) => i.status === 'ok').length, c: '#639922' },
          { k: 'BAD', v: items.filter((i) => i.status === 'bad').length, c: '#e24b4a' },
          { k: '진행 중', v: items.filter((i) => i.status === 'pending').length, c: 'var(--hud-text-dim)' },
        ].map((s) => (
          <div key={s.k} style={{ padding: '6px 8px', background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)', borderRadius: 6, textAlign: 'center' }}>
            <div style={{ fontSize: 9, color: 'var(--hud-text-dim)', letterSpacing: '0.1em', textTransform: 'uppercase', fontWeight: 600 }}>{s.k}</div>
            <div style={{ fontSize: 16, fontWeight: 700, color: s.c, marginTop: 2 }}>{s.v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// 통합 컴포넌트
// ─────────────────────────────────────────────────────────────

interface Props {
  row: EquipRow;
}

export function EquipmentLineVisual({ row }: Props) {
  const Anim = ANIM_MAP[row.type] ?? UtilityAnim;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, alignItems: 'stretch' }}>
      <style>{ANIM_KEYFRAMES}</style>

      <div
        style={{
          background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
          borderRadius: 10,
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', fontFamily: 'var(--hud-font-mono)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>
          MOTION · {row.type} 동작 메커니즘
        </div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: '100%', maxWidth: 300 }}>
            <Anim />
          </div>
        </div>
        <div style={{ fontSize: 10, color: 'var(--hud-text-muted, var(--hud-text-dim))', textAlign: 'center', marginTop: 4 }}>
          시연용 — 실 운전 데이터 아님
        </div>
      </div>

      <ConveyorLine row={row} />
    </div>
  );
}
