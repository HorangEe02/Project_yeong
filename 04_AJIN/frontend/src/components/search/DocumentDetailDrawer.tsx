// DocumentDetailDrawer — Module A · 문서 상세 드로어.
// 디자인 시스템 v3.5: lg-btn / lg-pill / lg-tag + 영문 eyebrow + 한글 본문.
// EmployeeDetailDrawer 패턴 호환 (Drawer ui-modal 컨테이너 사용).

import { FileText, MessageSquare, PenLine, Copy } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Drawer } from '@components/ui/Drawer';
import { useToast } from '@store/toast';
import type { DocSearchResultItem } from '@api/search';

interface Props {
  doc: DocSearchResultItem | null;
  isOpen: boolean;
  onClose: () => void;
  tokens: string[];
}

const DOC_TYPE_LABEL: Record<string, string> = {
  '8d_report': '8D 보고서',
  ecn: 'ECN',
  email: '이메일',
  meeting_note: '회의록',
  ppap: 'PPAP',
};

function escapeReg(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function highlight(text: string, tokens: string[]): React.ReactNode {
  if (!text) return null;
  if (!tokens.length) return text;
  const pattern = new RegExp(`(${tokens.map(escapeReg).join('|')})`, 'gi');
  const parts = text.split(pattern);
  return parts.map((p, i) =>
    pattern.test(p) ? (
      <mark key={i} className="lg-hl">
        {p}
      </mark>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

export function DocumentDetailDrawer({ doc, isOpen, onClose, tokens }: Props) {
  const navigate = useNavigate();
  const { addToast } = useToast();

  if (!doc) {
    return (
      <Drawer isOpen={isOpen} onClose={onClose} title="" width={560}>
        <span />
      </Drawer>
    );
  }

  const docTypeLabel = DOC_TYPE_LABEL[doc.doc_type] ?? doc.doc_type ?? 'DOC';
  const meta = doc.metadata ?? {};
  const date =
    (meta['date'] as string) ??
    (meta['created_at'] as string) ??
    (meta['updated_at'] as string) ??
    null;
  const author = (meta['author'] as string) ?? null;
  const department = (meta['department'] as string) ?? null;

  const handleDraft = () => {
    navigate('/draft', {
      state: {
        prefillSourceDoc: {
          docId: doc.doc_id,
          title: doc.title,
          docType: doc.doc_type,
          content: doc.content,
        },
      },
    });
    onClose();
  };

  const handleAskChat = () => {
    navigate('/chat', {
      state: {
        prefillContext: {
          kind: 'document',
          docId: doc.doc_id,
          title: doc.title,
          excerpt: doc.content?.slice(0, 600) ?? '',
        },
        prefillPrompt: `다음 문서에 대해 알려줘: "${doc.title}"`,
      },
    });
    onClose();
  };

  const handleCopy = async () => {
    try {
      const text = `[${doc.title}]\n${doc.content ?? ''}`;
      await navigator.clipboard.writeText(text);
      addToast({ type: 'success', message: '문서 본문이 클립보드에 복사되었습니다.' });
    } catch {
      addToast({ type: 'error', message: '클립보드 복사에 실패했습니다.' });
    }
  };

  return (
    <Drawer isOpen={isOpen} onClose={onClose} title={doc.title || '(제목 없음)'} width={560}>
      <div
        style={{
          padding: '20px 24px',
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
        }}
      >
        {/* META BAR — pills/tags only */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 8,
            paddingBottom: 14,
            borderBottom:
              '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
          }}
        >
          <span className="lg-pill">{docTypeLabel}</span>
          {doc.part_name && <span className="lg-tag mod">{doc.part_name}</span>}
          {date && (
            <span
              className="mono"
              style={{
                fontFamily: 'var(--hud-font-mono)',
                fontSize: 11,
                color: 'var(--hud-text-dim)',
                letterSpacing: '0.08em',
              }}
            >
              {date.toString().slice(0, 10)}
            </span>
          )}
          {author && (
            <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>
              작성자 · {author}
            </span>
          )}
          {department && (
            <span style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>
              {department}
            </span>
          )}
          <span
            style={{
              marginLeft: 'auto',
              fontFamily: 'var(--hud-font-mono)',
              fontSize: 10,
              letterSpacing: '0.12em',
              color: 'var(--hud-primary)',
            }}
            title="RRF score"
          >
            RRF · {doc.score?.toFixed?.(2) ?? '—'}
          </span>
        </div>

        {/* ACTIONS — lg-btn 캐노니컬 */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 8,
          }}
        >
          <button
            type="button"
            className="lg-btn sm"
            onClick={handleDraft}
            style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
          >
            <PenLine size={13} strokeWidth={2} />
            초안 작성
          </button>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={handleAskChat}
            style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
          >
            <MessageSquare size={13} strokeWidth={2} />
            챗봇 문의
          </button>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={handleCopy}
            style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}
          >
            <Copy size={13} strokeWidth={2} />
            본문 복사
          </button>
        </div>

        {/* BODY PREVIEW — eyebrow + 12px radius */}
        <div>
          <div
            className="lg-eyebrow"
            style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}
          >
            <FileText size={12} strokeWidth={2} /> CONTENT · 본문 미리보기
          </div>
          <div
            style={{
              padding: 14,
              borderRadius: 12,
              border:
                '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
              background:
                'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
              maxHeight: 380,
              overflow: 'auto',
              fontSize: 13,
              lineHeight: 1.65,
              color: 'var(--hud-text-dim)',
              whiteSpace: 'pre-wrap',
            }}
          >
            {highlight(doc.content || '(본문 없음)', tokens)}
          </div>
        </div>

        {/* DOC ID 푸터 */}
        <div
          className="mono"
          style={{
            fontFamily: 'var(--hud-font-mono)',
            fontSize: 10,
            letterSpacing: '0.12em',
            color: 'var(--hud-text-muted)',
            paddingTop: 4,
          }}
        >
          DOC ID · {doc.doc_id || '—'}
        </div>
      </div>
    </Drawer>
  );
}
