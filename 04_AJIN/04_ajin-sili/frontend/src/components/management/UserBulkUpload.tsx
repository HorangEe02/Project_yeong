// UserBulkUpload.tsx — v4.8 F-Users. CSV 일괄 사용자 업로드.
// dry-run 토글 + 결과 요약 표 (rows_total / inserted / updated / skipped / errors).

import { useState } from 'react';
import { bulkUploadUsers, type BulkIngestResult } from '@api/management';

interface UserBulkUploadProps {
  onComplete?: (result: BulkIngestResult) => void;
}

export function UserBulkUpload({ onComplete }: UserBulkUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BulkIngestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!file) {
      setError('CSV 파일을 선택하세요.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await bulkUploadUsers(file, dryRun);
      setResult(r);
      onComplete?.(r);
    } catch (e) {
      const msg = (e as Error)?.message || '업로드 실패';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="lg-card" style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <strong>CSV 일괄 업로드</strong>
        <span style={{ fontSize: 11, opacity: 0.6 }}>
          columns: username, email, name, department, position, role_level, phone
        </span>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
          />
          Dry-run (검증만)
        </label>
        <button
          type="button"
          className="lg-btn"
          disabled={loading || !file}
          onClick={handleSubmit}
        >
          {loading ? '처리 중…' : dryRun ? '검증 실행' : '실제 업로드'}
        </button>
      </div>

      {error && (
        <div className="lg-state-pill crit" style={{ marginBottom: 8 }}>
          {error}
        </div>
      )}

      {result && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 12, marginBottom: 6 }}>
            <strong>결과:</strong> {result.dry_run ? '(dry-run)' : '(적용 완료)'} ·{' '}
            {result.started_at.slice(0, 19)} → {result.finished_at.slice(0, 19)}
          </div>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={th}>total</th>
                <th style={th}>inserted</th>
                <th style={th}>updated</th>
                <th style={th}>skipped</th>
                <th style={th}>errors</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={td}>{result.rows_total}</td>
                <td style={td}>{result.rows_inserted}</td>
                <td style={td}>{result.rows_updated}</td>
                <td style={td}>{result.rows_skipped}</td>
                <td style={{ ...td, color: result.rows_error > 0 ? 'var(--lg-danger, #d33)' : 'inherit' }}>
                  {result.rows_error}
                </td>
              </tr>
            </tbody>
          </table>

          {result.error_payload.length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ fontSize: 12, cursor: 'pointer' }}>
                에러 행 {result.error_payload.length} 개
              </summary>
              <table style={{ width: '100%', fontSize: 11, marginTop: 6, borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={th}>#</th>
                    <th style={th}>code</th>
                    <th style={th}>message</th>
                  </tr>
                </thead>
                <tbody>
                  {result.error_payload.map((r) => (
                    <tr key={`${r.row_index}-${r.error_code}`}>
                      <td style={td}>{r.row_index}</td>
                      <td style={td}>{r.error_code}</td>
                      <td style={td}>{r.error_msg}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

const th: React.CSSProperties = {
  textAlign: 'left',
  padding: '4px 8px',
  borderBottom: '1px solid var(--lg-border, rgba(0,0,0,0.1))',
  fontWeight: 600,
};

const td: React.CSSProperties = {
  textAlign: 'left',
  padding: '4px 8px',
  borderBottom: '1px solid var(--lg-border-soft, rgba(0,0,0,0.05))',
};

export default UserBulkUpload;
