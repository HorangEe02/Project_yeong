// DownloadActions.tsx — Phase 2: 공통 다운로드 액션 (모든 모듈 재사용).
// lg-export-row + lg-chip 마크업만 사용 — 신규 CSS 클래스 0개.
//
// 사용처:
//   - Module B (Draft):    /draft 작성 결과 (프리셋: 'draft', 9포맷)
//   - Module D (Compliance): 시나리오 결과, 변경 감지 (프리셋: 'compliance')
//   - Module F (Equipment): 점검 체크리스트, MTBF 보고서 (프리셋: 'equipment')
//   - Module E (Admin):     명단, 로그인 이력 (프리셋: 'admin')
//   - Module A (Search):    검색 결과 (프리셋: 'search')
//
// 분기:
//   - clipboard → navigator.clipboard.writeText
//   - hwp / hwpx → frontend WASM (lib/hwp.ts)
//   - docx / pdf / xlsx / csv / txt / odt → 백엔드 (props.onBackendExport 또는 기본 /api/draft/export)

import { useCallback, useState } from 'react';
import { downloadHwp, downloadBlob } from '@lib/hwp';
import { exportDraft } from '@api/draft';
import {
  EXPORT_FORMAT_META,
  FORMAT_PRESETS,
  type ExportFormat,
} from '@/types/export';

type ContentSource = string | (() => string) | (() => Promise<string>);

export type DownloadSource = 'draft' | 'compliance' | 'equipment' | 'admin' | 'search' | 'default';

export interface DownloadActionsProps {
  /** 마크다운/평문 콘텐츠 — 함수면 클릭 시 lazy 평가 (테이블 직렬화 등). */
  content: ContentSource;
  /** 파일명(확장자 제외). 기본 'download' */
  basename?: string;
  /** 노출할 포맷 — 미지정 시 source 프리셋 사용. */
  formats?: ExportFormat[];
  /** 모듈별 프리셋 — formats 가 없을 때만 사용. */
  source?: DownloadSource;
  /** 백엔드 export 오버라이드 (모듈별 다른 endpoint 필요 시). */
  onBackendExport?: (fmt: ExportFormat, content: string) => Promise<Blob>;
  /** 메타 (HWP 문서 제목/저자). */
  metadata?: { title?: string; doc_type?: string; author?: string };
  /** 부가 클래스 (lg-export-row 외부 wrapper 등). */
  className?: string;
  /** 추가 chip 슬롯 (예: '재평가' 등) — chip 앞에 prepend. */
  prepend?: React.ReactNode;
}

async function resolveContent(src: ContentSource): Promise<string> {
  if (typeof src === 'function') {
    const result = src();
    return result instanceof Promise ? await result : result;
  }
  return src;
}

export function DownloadActions({
  content,
  basename = 'download',
  formats,
  source = 'default',
  onBackendExport,
  metadata,
  className,
  prepend,
}: DownloadActionsProps) {
  const [busy, setBusy] = useState<ExportFormat | null>(null);
  const [errorFmt, setErrorFmt] = useState<ExportFormat | null>(null);

  const visibleFormats = formats ?? FORMAT_PRESETS[source] ?? FORMAT_PRESETS.default;

  const handleExport = useCallback(
    async (fmt: ExportFormat) => {
      if (busy) return;
      setBusy(fmt);
      setErrorFmt(null);

      try {
        const text = await resolveContent(content);
        if (!text || text.trim().length === 0) {
          throw new Error('빈 콘텐츠');
        }

        // ── 클립보드 ─────────────────────────────────────
        if (fmt === 'clipboard') {
          await navigator.clipboard.writeText(text);
          // 시각적 피드백: 잠깐 busy 유지 후 해제
          setTimeout(() => setBusy(null), 600);
          return;
        }

        // ── HWP / HWPX (Frontend WASM) ───────────────────
        if (fmt === 'hwp' || fmt === 'hwpx') {
          await downloadHwp(text, `${basename}.${fmt}`, fmt, {
            title: metadata?.title,
            author: metadata?.author,
          });
          return;
        }

        // ── 백엔드 (DOCX/PDF/XLSX/CSV/TXT/ODT) ───────────
        let blob: Blob;
        if (onBackendExport) {
          blob = await onBackendExport(fmt, text);
        } else {
          // 기본: /api/draft/export 활용 (모든 모듈 공용 가능)
          blob = await exportDraft({
            content: text,
            format: fmt as 'docx' | 'pdf' | 'xlsx' | 'csv' | 'txt' | 'odt',
            doc_type: metadata?.doc_type ?? 'general',
          });
        }
        const ext = EXPORT_FORMAT_META[fmt].ext;
        downloadBlob(blob, `${basename}.${ext}`);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.warn(`[DownloadActions] ${fmt} 실패:`, msg);
        setErrorFmt(fmt);
        // 사용자에게 toast 알림이 있다면 활용 가능
        alert(`${fmt.toUpperCase()} 다운로드 실패: ${msg}`);
        setTimeout(() => setErrorFmt(null), 3000);
      } finally {
        // 클로저가 capture한 옛 busy 값과 비교하면 안 됨 — 항상 reset.
        setBusy(null);
      }
    },
    [content, basename, metadata, onBackendExport],
  );

  return (
    <div className={'lg-export-row' + (className ? ' ' + className : '')}>
      {prepend}
      {visibleFormats.map((fmt) => {
        const meta = EXPORT_FORMAT_META[fmt];
        const isBusy = busy === fmt;
        const hasError = errorFmt === fmt;
        return (
          <button
            key={fmt}
            type="button"
            className="lg-chip"
            onClick={() => void handleExport(fmt)}
            disabled={isBusy || (busy !== null && busy !== fmt)}
            title={`${meta.label} (${meta.channel === 'frontend' ? 'WASM 변환' : meta.channel === 'browser' ? '브라우저' : '서버 변환'})`}
            style={hasError ? { borderColor: 'var(--hud-red)', color: 'var(--hud-red)' } : undefined}
          >
            {isBusy ? '...' : fmt === 'clipboard' ? '⧉ 복사' : `↓ ${meta.label}`}
          </button>
        );
      })}
    </div>
  );
}
