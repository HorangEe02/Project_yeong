// W1 (P1) — 설비 AI 첫 진입 가이드 모달.
// 신입사원이 5공정 · 7 ML 엔진 · Nelson 8 의미를 1분 안에 이해할 수 있도록.
// localStorage 로 once-shown 처리 (꺼두면 재등장하지 않음).

import { useEffect, useState } from 'react';
import { Sparkles, X } from 'lucide-react';

const STORAGE_KEY = 'ajin-equipment-guide-shown';

interface Section {
  title: string;
  body: string;
}

const SECTIONS: Section[] = [
  {
    title: '5공정 동시 모니터링',
    body: 'EWP 보링 / CCH 두께 / OBC 평탄도 / 범퍼 너겟 / 시트 레일 — 5개 공정의 Cpk·위반 건수가 실시간 색상 카드로 표시됩니다.',
  },
  {
    title: 'Nelson 8 Rules',
    body: '관리도 데이터의 8가지 비정상 패턴(±3σ 이탈, 9점 연속 편향 등). IATF 16949 표준이며 위반 발생 시 한국어 권장 조치문을 함께 노출합니다.',
  },
  {
    title: 'Cpk 의미',
    body: '공정 능력 지수. 1.33 이상이면 양호, 1.67 이상이면 우수. 1.0 미만은 즉시 라인 정지 검토. 자동차 부품 PPAP 제출 기준입니다.',
  },
  {
    title: '7 ML 엔진',
    body: 'TF-IDF (에러 검색) · XGBoost (금형 수명) · Isolation Forest (이상 탐지) · Markov (연쇄 고장) · 문서 품질 · Risk · Intent. ML 엔진 탭의 ⓘ 아이콘으로 각각의 역할을 확인할 수 있습니다.',
  },
  {
    title: '알람 워크플로우',
    body: '긴급 조치 탭의 알람 카드에서 "8D Report 작성" / "관련 SOP / AI 도우미" 버튼으로 B / C 기능과 한 흐름으로 이어집니다.',
  },
];

export function OverviewGuideModal() {
  const [open, setOpen] = useState(false);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const shown = localStorage.getItem(STORAGE_KEY);
    if (!shown) setOpen(true);
  }, []);

  const close = () => {
    setOpen(false);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, '1');
    }
  };

  if (!open) return null;

  const sec = SECTIONS[idx];
  const last = idx === SECTIONS.length - 1;

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={close}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 999,
        background: 'color-mix(in oklab, var(--hud-bg) 65%, black)',
        display: 'grid',
        placeItems: 'center',
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="lg-card"
        style={{
          padding: 22,
          maxWidth: 520,
          width: '100%',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div>
            <div style={{ fontSize: 10, opacity: 0.6, letterSpacing: '0.06em' }}>
              <Sparkles size={10} style={{ verticalAlign: 'middle', marginRight: 4 }} />
              EQUIPMENT AI · 1분 가이드
            </div>
            <h2 style={{ margin: '4px 0 0', fontSize: 17, fontWeight: 700 }}>
              {sec.title}
            </h2>
          </div>
          <button
            onClick={close}
            title="닫기"
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--hud-text-dim)',
              padding: 4,
            }}
          >
            <X size={18} />
          </button>
        </div>

        <p style={{ fontSize: 13, lineHeight: 1.65, marginTop: 12 }}>
          {sec.body}
        </p>

        <div style={{ marginTop: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 4 }}>
            {SECTIONS.map((_, i) => (
              <span
                key={i}
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 999,
                  background:
                    i === idx
                      ? 'var(--hud-primary)'
                      : 'color-mix(in oklab, var(--hud-text) 20%, transparent)',
                }}
              />
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="lg-btn"
              onClick={close}
              style={{ padding: '6px 12px', fontSize: 12 }}
            >
              건너뛰기
            </button>
            <button
              className="lg-btn primary"
              onClick={() => (last ? close() : setIdx((i) => i + 1))}
              style={{ padding: '6px 16px', fontSize: 12 }}
            >
              {last ? '완료' : '다음 →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
