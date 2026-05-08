// Day 5 Phase 3 — 응답 다운로드 4 버튼 (DOCX/XLSX/CSV/TXT)
// MessageBubble 의 assistant 풍선 푸터에 부착.

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Tooltip } from '@components/ui/Tooltip';
import { downloadResponse, type DownloadFormat } from '@api/download';

interface Props {
  /** 다운로드할 응답 본문 (마크다운). */
  content: string;
  /** 파일명 베이스 — 확장자 X. */
  filenameBase?: string;
}

const FORMATS: Array<{ key: DownloadFormat; labelKey: string; tipKey: string }> = [
  { key: 'docx', labelKey: 'chat.download.docx', tipKey: 'chat.download.tooltip_docx' },
  { key: 'xlsx', labelKey: 'chat.download.xlsx', tipKey: 'chat.download.tooltip_xlsx' },
  { key: 'csv', labelKey: 'chat.download.csv', tipKey: 'chat.download.tooltip_csv' },
  { key: 'txt', labelKey: 'chat.download.txt', tipKey: 'chat.download.tooltip_txt' },
];

export function DownloadActions({ content, filenameBase }: Props) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState<DownloadFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handle = async (fmt: DownloadFormat) => {
    if (!content?.trim()) return;
    setBusy(fmt);
    setError(null);
    try {
      await downloadResponse(content, fmt, filenameBase || 'ajin-ai-response');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  if (!content?.trim()) return null;

  return (
    <div className="download-actions" role="group" aria-label={t('chat.download.title')}>
      <span className="download-actions-eyebrow">{t('chat.download.title')}</span>
      <div className="download-actions-row">
        {FORMATS.map((f) => (
          <Tooltip key={f.key} content={t(f.tipKey)} position="top">
            <button
              type="button"
              className="download-btn"
              onClick={() => handle(f.key)}
              disabled={busy !== null}
              aria-busy={busy === f.key || undefined}
            >
              {busy === f.key ? '…' : t(f.labelKey)}
            </button>
          </Tooltip>
        ))}
      </div>
      {error && (
        <span className="download-error" role="alert">
          {t('chat.download.failed', { msg: error })}
        </span>
      )}
    </div>
  );
}
