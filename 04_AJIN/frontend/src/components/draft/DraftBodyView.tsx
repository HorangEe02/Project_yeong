// DraftBodyView — Module B · 결과 본문 + 섹션별 [다시 쓰기] 액션.
// B3 v4.0: 명시적 마커로 분리된 섹션마다 호버 시 액션 노출, 클릭 시 명령 입력 모달.
// 디자인 시스템 v3.5: lg-card-tight + lg-btn ghost sm + 16/12 라운드.

import { useEffect, useState, useCallback } from 'react';
import { Edit3, Loader2, Check } from 'lucide-react';
import {
  scanSections,
  partialEdit,
  type PartialEditSection,
} from '@api/draft';
import { useToast } from '@store/toast';

interface Props {
  body: string;
  /** 타겟 섹션이 LLM 으로 재생성된 후 새 본문을 부모에 알림. */
  onBodyChange: (newBody: string) => void;
  docType?: string;
  tone?: string;
}

interface QuickInstruction {
  id: string;
  label: string;
}

const QUICK_INSTRUCTIONS: QuickInstruction[] = [
  { id: 'polite',   label: '조금 더 정중하게' },
  { id: 'concise',  label: '간결하게 줄여줘' },
  { id: 'detailed', label: '근거를 더 자세히' },
  { id: 'formal',   label: '격식 있게 다시' },
  { id: 'data',     label: '숫자/데이터 강조' },
];

export function DraftBodyView({ body, onBodyChange, docType, tone }: Props) {
  const { addToast } = useToast();

  const [sections, setSections] = useState<PartialEditSection[]>([]);
  const [scanBusy, setScanBusy] = useState(false);

  // 모달 상태
  const [editingSection, setEditingSection] = useState<PartialEditSection | null>(null);
  const [instruction, setInstruction] = useState('');
  const [editBusy, setEditBusy] = useState(false);
  const [lastEditedIdx, setLastEditedIdx] = useState<number | null>(null);

  // body 변경 시 섹션 재스캔 (디바운스)
  useEffect(() => {
    if (!body || body.trim().length < 10) {
      setSections([]);
      return;
    }
    let cancelled = false;
    setScanBusy(true);
    const t = setTimeout(async () => {
      try {
        const r = await scanSections(body);
        if (!cancelled) setSections(r.sections);
      } catch {
        if (!cancelled) setSections([]);
      } finally {
        if (!cancelled) setScanBusy(false);
      }
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [body]);

  const handleEdit = useCallback(async () => {
    if (!editingSection || !instruction.trim()) return;
    setEditBusy(true);
    try {
      const r = await partialEdit({
        body,
        target_section_index: editingSection.index,
        instruction: instruction.trim(),
        doc_type: docType,
        tone,
      });
      onBodyChange(r.new_body);
      setLastEditedIdx(r.target_section_index);
      setEditingSection(null);
      setInstruction('');
      addToast({
        type: 'success',
        message: `"${editingSection.title || '섹션'}" 재작성 완료 (${r.model})`,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '재작성 실패';
      addToast({ type: 'error', message: `부분 수정 실패: ${msg}` });
    } finally {
      setEditBusy(false);
    }
  }, [editingSection, instruction, body, docType, tone, onBodyChange, addToast]);

  if (sections.length === 0) {
    return null; // 섹션 마커가 없으면 안내 없음 (전체 재생성 워크플로우만)
  }

  return (
    <>
      <section
        style={{
          marginTop: 14,
          padding: 14,
          borderRadius: 16,
          border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
          background: 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 10,
            gap: 8,
          }}
        >
          <div
            className="lg-eyebrow"
            style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 0 }}
          >
            <Edit3 size={11} strokeWidth={2} />
            PARTIAL EDIT · 섹션별 다시 쓰기
          </div>
          <span
            className="mono"
            style={{
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              letterSpacing: '0.1em',
              color: scanBusy ? 'var(--hud-primary)' : 'var(--hud-text-muted)',
            }}
          >
            {scanBusy ? 'SCANNING…' : `${sections.length} SECTIONS`}
          </span>
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          {sections.map((s) => (
            <div
              key={s.index}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 12px',
                borderRadius: 12,
                border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
                background:
                  lastEditedIdx === s.index
                    ? 'color-mix(in oklab, var(--hud-green, #2D8A4E) 8%, transparent)'
                    : 'color-mix(in oklab, var(--hud-surface) 60%, transparent)',
              }}
            >
              <span
                className="mono"
                style={{
                  fontFamily: 'var(--hud-font-mono)',
                  fontSize: 10,
                  color: 'var(--hud-text-muted)',
                  letterSpacing: '0.1em',
                  minWidth: 36,
                }}
              >
                {s.marker || `#${s.index + 1}`}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: 'var(--hud-text)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={s.title || s.preview}
                >
                  {s.title || '(제목 없음)'}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--hud-text-dim)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    marginTop: 2,
                  }}
                >
                  {s.preview}
                </div>
              </div>
              {lastEditedIdx === s.index && (
                <span
                  className="lg-state-pill ok"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
                >
                  <Check size={9} strokeWidth={2} /> 수정됨
                </span>
              )}
              <button
                type="button"
                className="lg-btn ghost sm"
                onClick={() => {
                  setEditingSection(s);
                  setInstruction('');
                }}
                title={`"${s.title || s.marker}" 섹션만 다시 쓰기`}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
              >
                <Edit3 size={11} strokeWidth={2} /> 다시 쓰기
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* 모달 — 명령 입력 */}
      {editingSection && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="부분 수정"
          onClick={() => !editBusy && setEditingSection(null)}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: 'color-mix(in oklab, var(--hud-bg, #0A0E14) 60%, transparent)',
            backdropFilter: 'blur(4px) saturate(120%)',
            WebkitBackdropFilter: 'blur(4px) saturate(120%)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'center',
            paddingTop: '15vh',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              width: 'min(560px, 92vw)',
              background: 'var(--glass-bg-strong, var(--hud-surface, #111820))',
              backdropFilter: 'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
              WebkitBackdropFilter: 'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
              border: '1px solid var(--glass-border, color-mix(in oklab, var(--hud-text) 12%, transparent))',
              borderRadius: 16,
              padding: 20,
              boxShadow:
                'inset 0 1px 0 var(--glass-highlight, rgba(255,255,255,0.18)), 0 24px 60px -28px rgba(0,0,0,0.4)',
            }}
          >
            <div className="lg-eyebrow" style={{ marginBottom: 4 }}>
              PARTIAL EDIT · 섹션 수정
            </div>
            <h3
              style={{
                margin: '0 0 14px',
                fontSize: 17,
                fontWeight: 600,
                color: 'var(--hud-text)',
              }}
            >
              {editingSection.marker} {editingSection.title}
            </h3>

            {/* 빠른 명령 칩 */}
            <div className="lg-eyebrow" style={{ marginBottom: 6 }}>
              빠른 명령
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
              {QUICK_INSTRUCTIONS.map((q) => (
                <button
                  key={q.id}
                  type="button"
                  className="lg-btn ghost sm"
                  onClick={() => setInstruction(q.label)}
                  disabled={editBusy}
                >
                  {q.label}
                </button>
              ))}
            </div>

            <div className="lg-field" style={{ marginBottom: 14 }}>
              <label>명령 (자유 입력)</label>
              <textarea
                className="lg-textarea"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                rows={3}
                placeholder="예: 더 단정하게, 숫자 데이터 강조, 영문 톤 유지..."
                disabled={editBusy}
                autoFocus
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                className="lg-btn ghost sm"
                onClick={() => setEditingSection(null)}
                disabled={editBusy}
              >
                취소
              </button>
              <button
                type="button"
                className="lg-btn"
                onClick={handleEdit}
                disabled={editBusy || !instruction.trim()}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                {editBusy ? (
                  <>
                    <Loader2
                      size={13}
                      strokeWidth={2}
                      style={{ animation: 'spin 1s linear infinite' }}
                    />
                    재작성 중…
                  </>
                ) : (
                  <>
                    <Edit3 size={13} strokeWidth={2} /> 재작성
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
