// MailSendModal — Module B · 메일 발송 모달.
// B6 v4.0: 수신자/CC/BCC 입력 + 첨부 체크리스트 (doc_type별 자동 추천) + Mock 발송.
// 디자인 시스템 v3.5: glass 모달 + 16/12 라운드 + lg-state-pill.

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { Mail, Paperclip, AlertTriangle, Check, X as XIcon, Send } from 'lucide-react';
import {
  fetchAttachmentRecommendations,
  sendDraftMail,
  type AttachmentSuggestion,
} from '@api/draft';
import { useToast } from '@store/toast';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** 본문 (마크다운 그대로 전송). */
  body: string;
  /** 기본 제목 (사용자가 수정 가능). */
  defaultSubject?: string;
  /** 추천 메타. */
  docType?: string;
  /** 사전 채워질 to/cc/bcc (있을 시). */
  prefillTo?: string;
  prefillCc?: string;
  /**
   * Feature B Sprint 1 P0 (plan §14.2) — mail send guard.
   * versionId: 승인된 draft version row id. 미전달 시 백엔드 412 block_no_version.
   * internalDomains: 사내 도메인 (default ['ajin.co.kr']). 이 외 도메인은 외부로 분류.
   * watermarkId: export 단계에서 부여된 SHA1 8자. 감사 추적용.
   */
  versionId?: number;
  internalDomains?: string[];
  watermarkId?: string;
}

const DEFAULT_INTERNAL_DOMAINS = ['ajin.co.kr'];

function extractExternalDomains(
  recipients: { email: string }[],
  internalDomains: string[],
): string[] {
  const internal = new Set(internalDomains.map((d) => d.toLowerCase()));
  const ext = new Set<string>();
  for (const r of recipients) {
    if (!r.email || !r.email.includes('@')) continue;
    const dom = r.email.split('@').pop()!.toLowerCase().trim();
    if (!internal.has(dom)) ext.add(dom);
  }
  return Array.from(ext).sort();
}

function parseRecipients(raw: string): { email: string; name?: string }[] {
  // "이름 <email>" 또는 "email" 콤마/세미콜론 분리
  return raw
    .split(/[,;]/)
    .map((t) => t.trim())
    .filter(Boolean)
    .map((token) => {
      const m = token.match(/^(.+?)\s*<(.+@.+)>$/);
      if (m) return { name: m[1].trim(), email: m[2].trim() };
      return { email: token };
    });
}

export function MailSendModal({
  isOpen,
  onClose,
  body,
  defaultSubject = '',
  docType = '',
  prefillTo = '',
  prefillCc = '',
  versionId,
  internalDomains = DEFAULT_INTERNAL_DOMAINS,
  watermarkId,
}: Props) {
  const { addToast } = useToast();

  const [subject, setSubject] = useState(defaultSubject);
  const [toRaw, setToRaw] = useState(prefillTo);
  const [ccRaw, setCcRaw] = useState(prefillCc);
  const [bccRaw, setBccRaw] = useState('');
  const [attachments, setAttachments] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  // 첨부 추천 (doc_type 기반)
  const [suggestions, setSuggestions] = useState<AttachmentSuggestion[]>([]);
  const [attachChecks, setAttachChecks] = useState<Record<string, boolean>>({});

  // 모달 열릴 때 초기화 + 첨부 추천 로드
  useEffect(() => {
    if (!isOpen) return;
    setSubject(defaultSubject);
    setToRaw(prefillTo);
    setCcRaw(prefillCc);
    setBccRaw('');
    setAttachments([]);
    setAttachChecks({});

    if (!docType) {
      setSuggestions([]);
      return;
    }
    let cancelled = false;
    fetchAttachmentRecommendations(docType)
      .then((r) => {
        if (cancelled) return;
        setSuggestions(r.items);
      })
      .catch(() => !cancelled && setSuggestions([]));
    return () => {
      cancelled = true;
    };
  }, [isOpen, docType, defaultSubject, prefillTo, prefillCc]);

  // 필수 첨부 누락 검사
  const missingRequired = useMemo(
    () => suggestions.filter((s) => s.required && !attachChecks[s.label]),
    [suggestions, attachChecks],
  );

  const handleSend = async () => {
    const to = parseRecipients(toRaw);
    if (to.length === 0) {
      addToast({ type: 'warning', message: '수신자를 입력하세요.' });
      return;
    }
    if (!subject.trim()) {
      addToast({ type: 'warning', message: '제목이 비어 있습니다.' });
      return;
    }
    if (missingRequired.length > 0) {
      const proceed = confirm(
        `필수 첨부 ${missingRequired.length}건이 체크되지 않았습니다 ` +
          `(${missingRequired.map((s) => s.label).join(', ')}). 계속 발송할까요?`,
      );
      if (!proceed) return;
    }

    // Feature B Sprint 1 P0 (plan §14.2) — 외부 도메인 확인 다이얼로그.
    // CC/BCC 도 포함 검사. 사내 도메인 외 (예: hkmc.com, gmail.com 등) 가 1개 이상이면 확인.
    const cc = parseRecipients(ccRaw);
    const bcc = parseRecipients(bccRaw);
    const externalDomains = extractExternalDomains(
      [...to, ...cc, ...bcc],
      internalDomains,
    );
    let acknowledged_external = false;
    if (externalDomains.length > 0) {
      const ok = confirm(
        `⚠ 외부 도메인 발송 확인\n\n` +
          `다음 외부 도메인으로 메일이 발송됩니다:\n` +
          `  - ${externalDomains.join('\n  - ')}\n\n` +
          `BCC 는 외부 발송 시 사용할 수 없습니다.\n` +
          `정말 발송하시겠습니까?`,
      );
      if (!ok) return;
      acknowledged_external = true;
    }

    setBusy(true);
    try {
      const r = await sendDraftMail({
        subject: subject.trim(),
        body,
        body_format: 'markdown',
        to,
        cc,
        bcc,
        attachments,
        doc_type: docType,
        // Sprint 1 P0 — 가드 필수 필드.
        version_id: versionId ?? 0,
        acknowledged_external,
        watermark_id: watermarkId ?? '',
      });
      if (r.ok) {
        addToast({
          type: 'success',
          message: `발송 완료 (${r.adapter}) · ${r.message_id}`,
        });
        onClose();
      } else {
        addToast({ type: 'error', message: `발송 실패: ${r.detail}` });
      }
    } catch (err) {
      // 가드 차단 시 axios → 4xx 응답. detail.decision 추출.
      const e = err as { response?: { status?: number; data?: { detail?: unknown } }; message?: string };
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      let msg = e?.message ?? '발송 실패';
      if (status === 412 && detail && typeof detail === 'object') {
        const d = detail as { decision?: string; message?: string };
        msg = `발송 차단 (${d.decision ?? '?'}) — ${d.message ?? ''}`;
      } else if (status === 422) {
        msg = '발송 차단 — version_id 누락 또는 형식 오류';
      }
      addToast({ type: 'error', message: msg });
    } finally {
      setBusy(false);
    }
  };

  if (!isOpen) return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label="메일 발송"
      onClick={() => !busy && onClose()}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1100,
        background: 'color-mix(in oklab, var(--hud-bg, #0A0E14) 60%, transparent)',
        backdropFilter: 'blur(4px) saturate(120%)',
        WebkitBackdropFilter: 'blur(4px) saturate(120%)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: '8vh',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 'min(640px, 92vw)',
          maxHeight: '84vh',
          overflow: 'auto',
          background: 'var(--glass-bg-strong, var(--hud-surface, #111820))',
          backdropFilter:
            'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
          WebkitBackdropFilter:
            'blur(var(--glass-blur, 24px)) saturate(var(--glass-saturate, 140%))',
          border:
            '1px solid var(--glass-border, color-mix(in oklab, var(--hud-text) 12%, transparent))',
          borderRadius: 16,
          padding: 22,
          boxShadow:
            'inset 0 1px 0 var(--glass-highlight, rgba(255,255,255,0.18)), 0 24px 60px -28px rgba(0,0,0,0.4)',
        }}
      >
        {/* 헤더 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 16,
          }}
        >
          <div className="lg-eyebrow" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 0 }}>
            <Mail size={11} strokeWidth={2} /> MAIL · 메일 발송
          </div>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={onClose}
            disabled={busy}
            aria-label="닫기"
            style={{ padding: 4 }}
          >
            <XIcon size={12} strokeWidth={2} />
          </button>
        </div>

        {/* 수신자 */}
        <div className="lg-field" style={{ marginBottom: 10 }}>
          <label>받는 사람 (To)</label>
          <input
            type="text"
            value={toRaw}
            onChange={(e) => setToRaw(e.target.value)}
            placeholder="예: 김QA <kim@ajin.co.kr>, ho@ajin.co.kr"
            disabled={busy}
            autoFocus
          />
        </div>
        <div
          className="lg-filter-grid"
          style={{ gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}
        >
          <div className="lg-field">
            <label>참조 (CC)</label>
            <input
              type="text"
              value={ccRaw}
              onChange={(e) => setCcRaw(e.target.value)}
              placeholder="cc1@ajin.co.kr, cc2@..."
              disabled={busy}
            />
          </div>
          <div className="lg-field">
            <label>숨은 참조 (BCC)</label>
            <input
              type="text"
              value={bccRaw}
              onChange={(e) => setBccRaw(e.target.value)}
              placeholder="(선택)"
              disabled={busy}
            />
          </div>
        </div>

        {/* 제목 */}
        <div className="lg-field" style={{ marginBottom: 14 }}>
          <label>제목</label>
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="예: 8D 보고서 — EWP-001 외경 부적합"
            disabled={busy}
          />
        </div>

        {/* 첨부 추천 */}
        {suggestions.length > 0 && (
          <div
            style={{
              padding: 14,
              borderRadius: 12,
              border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
              background: 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
              marginBottom: 14,
            }}
          >
            <div
              className="lg-eyebrow"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                marginBottom: 10,
                justifyContent: 'space-between',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Paperclip size={11} strokeWidth={2} /> ATTACHMENTS · 첨부 체크리스트
              </span>
              {missingRequired.length > 0 && (
                <span
                  className="lg-state-pill warn"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
                >
                  <AlertTriangle size={9} strokeWidth={2} /> 필수 {missingRequired.length}건 누락
                </span>
              )}
            </div>
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
              {suggestions.map((s) => {
                const checked = !!attachChecks[s.label];
                return (
                  <li
                    key={s.label}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '6px 8px',
                      borderRadius: 8,
                      background: checked
                        ? 'color-mix(in oklab, var(--hud-green, #2D8A4E) 8%, transparent)'
                        : 'transparent',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) =>
                        setAttachChecks({ ...attachChecks, [s.label]: e.target.checked })
                      }
                      disabled={busy}
                      style={{ accentColor: 'var(--hud-primary)' }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, color: 'var(--hud-text)' }}>
                        {s.required && (
                          <span style={{ color: 'var(--hud-primary)', marginRight: 4 }}>★</span>
                        )}
                        {s.label}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginTop: 2 }}>
                        {s.description} {s.file_hint && `· ${s.file_hint}`}
                      </div>
                    </div>
                    {checked && (
                      <Check size={11} strokeWidth={2} style={{ color: 'var(--hud-green, #2D8A4E)' }} />
                    )}
                  </li>
                );
              })}
            </ul>

            {/* 첨부 파일명 직접 입력 (Mock 단계 — 실 연동 시 파일 업로더로 교체) */}
            <div className="lg-field" style={{ marginTop: 10 }}>
              <label>실제 첨부 파일명 (콤마 구분, 선택)</label>
              <input
                type="text"
                value={attachments.join(', ')}
                onChange={(e) =>
                  setAttachments(
                    e.target.value
                      .split(',')
                      .map((s) => s.trim())
                      .filter(Boolean),
                  )
                }
                placeholder="예: 8d_evidence.xlsx, control_plan.pdf"
                disabled={busy}
              />
            </div>
          </div>
        )}

        {/* 본문 미리보기 */}
        <div className="lg-field" style={{ marginBottom: 14 }}>
          <label>본문 (편집기에서 작성한 내용 그대로 발송)</label>
          <pre
            style={{
              padding: 12,
              borderRadius: 12,
              border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
              background: 'color-mix(in oklab, var(--hud-surface) 60%, transparent)',
              maxHeight: 200,
              overflow: 'auto',
              fontFamily: 'var(--hud-font)',
              fontSize: 12,
              lineHeight: 1.55,
              color: 'var(--hud-text-dim)',
              whiteSpace: 'pre-wrap',
            }}
          >
            {body || '(본문 없음)'}
          </pre>
        </div>

        {/* 액션 */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button
            type="button"
            className="lg-btn ghost sm"
            onClick={onClose}
            disabled={busy}
          >
            취소
          </button>
          <button
            type="button"
            className="lg-btn"
            onClick={handleSend}
            disabled={busy}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <Send size={13} strokeWidth={2} />
            {busy ? '발송 중…' : '발송'}
          </button>
        </div>

        {/* Mock 안내 */}
        <div
          className="dim"
          style={{
            marginTop: 12,
            fontSize: 11,
            lineHeight: 1.55,
            color: 'var(--hud-text-muted)',
            fontStyle: 'italic',
          }}
        >
          현재 환경: Mock 어댑터 (실 송신 없음, 결과만 반환). 사내 SMTP / Microsoft Graph
          연동은 별도 PoC 트랙에서 활성화됩니다.
        </div>
      </div>
    </div>,
    document.body,
  );
}
