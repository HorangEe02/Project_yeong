// 점검 이력 CSV/XLSX 업로드 카드 (v4.3 Phase 1.6).
// docs/INSPECTION_CSV_SCHEMA.md 스키마 기반.

import { useState } from 'react';
import { Upload, CheckCircle2, AlertCircle } from 'lucide-react';

import {
  uploadInspectionCsv,
  type InspectionIngestResult,
} from '@api/equipment';
import { useToastStore } from '@store/toast';

export function InspectionUploadCard() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<InspectionIngestResult | null>(null);
  const [dryRun, setDryRun] = useState(true);

  const addToast = useToastStore.getState().addToast;

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const res = await uploadInspectionCsv(file, { dryRun });
      setResult(res);
      const mode = dryRun ? 'dry-run' : 'live';
      const lines: string[] = [
        `${mode} · total ${res.rows_total}`,
        `inserted ${res.rows_inserted} · updated ${res.rows_updated} · skipped ${res.rows_skipped} · error ${res.rows_error}`,
      ];
      addToast({
        type: res.rows_error > 0 ? 'warning' : 'success',
        title: `점검 이력 업로드 (${mode})`,
        message: lines.join(' · '),
        duration: 5000,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addToast({ type: 'error', title: '업로드 실패', message: msg, duration: 6000 });
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="lg-card" style={{ marginBottom: 12 }}>
      <div className="lg-card-h">
        <div>
          <div className="lg-eyebrow">UPLOAD · CSV/XLSX 적재</div>
          <h2 className="lg-h2">점검 이력 일괄 업로드</h2>
        </div>
        <a
          href="/docs/INSPECTION_CSV_SCHEMA.md"
          target="_blank"
          rel="noreferrer"
          style={{ fontSize: 12, color: 'var(--hud-text-dim)', textDecoration: 'underline' }}
        >
          스키마 보기 ↗
        </a>
      </div>

      <div
        style={{
          display: 'flex',
          gap: 12,
          alignItems: 'center',
          flexWrap: 'wrap',
          padding: '12px 0',
        }}
      >
        <input
          type="file"
          accept=".csv,.xlsx"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          style={{ fontSize: 12 }}
          aria-label="점검 이력 CSV/XLSX 파일 선택"
        />
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
          />
          Dry-run (검증만)
        </label>
        <button
          className="lg-btn"
          disabled={!file || uploading}
          onClick={handleUpload}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <Upload size={14} aria-hidden />
          {uploading ? '처리 중…' : dryRun ? '검증' : '적재'}
        </button>
      </div>

      {result && (
        <div
          style={{
            marginTop: 8,
            padding: 12,
            borderRadius: 6,
            border: '1px solid var(--hud-border)',
            background: 'color-mix(in oklab, var(--hud-bg) 90%, transparent)',
            fontSize: 13,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            {result.rows_error === 0 ? (
              <CheckCircle2 size={16} color="var(--hud-green)" aria-hidden />
            ) : (
              <AlertCircle size={16} color="var(--hud-orange)" aria-hidden />
            )}
            <span style={{ fontWeight: 700 }}>
              {result.dry_run ? '검증 결과' : '적재 결과'}
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8, fontFamily: 'var(--hud-font-mono)' }}>
            <Stat label="total" value={result.rows_total} />
            <Stat label="inserted" value={result.rows_inserted} color="var(--hud-green)" />
            <Stat label="updated" value={result.rows_updated} color="var(--hud-blue)" />
            <Stat label="skipped" value={result.rows_skipped} color="var(--hud-text-dim)" />
            <Stat label="error" value={result.rows_error} color={result.rows_error > 0 ? 'var(--hud-red)' : undefined} />
          </div>
          {result.error_payload.length > 0 && (
            <details style={{ marginTop: 10 }}>
              <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--hud-red)' }}>
                에러 row {result.error_payload.length}건 (최대 50건 표시)
              </summary>
              <ul style={{ marginTop: 6, paddingLeft: 18, fontSize: 12, lineHeight: 1.6 }}>
                {result.error_payload.slice(0, 50).map((e, i) => (
                  <li key={i}>
                    <code>row {e.row_index}</code> · [{e.error_code}] {e.error_msg}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: 18, color: color ?? 'var(--hud-text)', fontWeight: 700 }}>{value}</div>
    </div>
  );
}
