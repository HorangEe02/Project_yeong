import { useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { Download, FileUp, Upload, X, CheckCircle2, AlertCircle } from 'lucide-react';
import { bulkCreateInvitations } from '@/services/staffInvitation';
import { parseCsv, isValidEmail, type CsvRow } from '@/utils/parseCsv';
import { downloadCsv, toCsv } from '@/utils/csv';

interface BulkInviteDialogProps {
  open: boolean;
  onClose: () => void;
  onIssued: () => void;
}

interface Candidate {
  email: string;
  displayName: string;
  department: string;
  hospitalId: string;
  include: boolean;
  validation: 'ok' | 'email_invalid' | 'duplicate' | 'missing_required';
}

const TEMPLATE_CSV = 'email,displayName,department,hospitalId\nnurse1@hospital.org,김간호,내과,MediWay-Demo\ndoctor1@hospital.org,이의사,영상의학과,MediWay-Demo\n';
const MAX_ROWS = 500;

export function BulkInviteDialog({ open, onClose, onIssued }: BulkInviteDialogProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [report, setReport] = useState<
    | {
        successes: Candidate[];
        failures: Array<{ candidate: Candidate; error: string }>;
      }
    | null
  >(null);

  if (!open) return null;

  const reset = () => {
    setCandidates([]);
    setError(null);
    setProgress(null);
    setReport(null);
  };

  const handleText = (text: string) => {
    setError(null);
    const { headers, rows } = parseCsv(text);
    if (rows.length === 0) {
      setError('비어있거나 파싱할 수 없는 CSV입니다');
      return;
    }
    const need = ['email', 'department'];
    for (const h of need) {
      if (!headers.includes(h)) {
        setError(`필수 헤더 누락: ${h}`);
        return;
      }
    }
    if (rows.length > MAX_ROWS) {
      setError(`최대 ${MAX_ROWS}행까지 가능합니다 (현재 ${rows.length}행)`);
      return;
    }
    const seen = new Set<string>();
    const candList: Candidate[] = rows.map((row: CsvRow) => {
      const email = (row.email ?? '').toLowerCase();
      const department = (row.department ?? '').trim();
      const displayName = (row.displayName ?? '').trim();
      const hospitalId = (row.hospitalId ?? 'MediWay-Demo').trim();
      let validation: Candidate['validation'] = 'ok';
      if (!email || !department) validation = 'missing_required';
      else if (!isValidEmail(email)) validation = 'email_invalid';
      else if (seen.has(email)) validation = 'duplicate';
      if (email) seen.add(email);
      return {
        email,
        displayName,
        department,
        hospitalId,
        include: validation === 'ok',
        validation,
      };
    });
    setCandidates(candList);
  };

  const onFile = (file: File | null) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => handleText(String(reader.result ?? ''));
    reader.readAsText(file, 'utf-8');
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    onFile(e.dataTransfer.files?.[0] ?? null);
  };

  const onChange = (i: number, patch: Partial<Candidate>) => {
    setCandidates((list) => list.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  };

  const toggleAll = (include: boolean) => {
    setCandidates((list) =>
      list.map((c) => ({ ...c, include: include && c.validation === 'ok' })),
    );
  };

  const run = async () => {
    const selected = candidates.filter((c) => c.include && c.validation === 'ok');
    if (selected.length === 0) {
      setError('초대할 유효한 행이 없습니다');
      return;
    }
    setError(null);
    setRunning(true);
    setProgress({ done: 0, total: selected.length });
    const { successes, failures } = await bulkCreateInvitations(
      selected.map((c) => ({
        email: c.email,
        displayName: c.displayName,
        department: c.department,
        hospitalId: c.hospitalId,
      })),
      (done, total) => setProgress({ done, total }),
    );

    // candidate 매핑
    const successByEmail = new Map(successes.map((s) => [s.email, s]));
    const failureByEmail = new Map(
      failures.map((f) => [f.input.email.toLowerCase(), f.error]),
    );
    const successCandidates = selected.filter((c) => successByEmail.has(c.email));
    const failureCandidates = selected
      .filter((c) => failureByEmail.has(c.email))
      .map((c) => ({ candidate: c, error: failureByEmail.get(c.email) ?? '' }));

    setReport({ successes: successCandidates, failures: failureCandidates });
    setRunning(false);
    onIssued();
  };

  const downloadTemplate = () => {
    downloadCsv('invite-template.csv', TEMPLATE_CSV);
  };

  const downloadFailures = () => {
    if (!report) return;
    const rows = report.failures.map((f) => ({
      email: f.candidate.email,
      displayName: f.candidate.displayName,
      department: f.candidate.department,
      hospitalId: f.candidate.hospitalId,
      error: f.error,
    }));
    const csv = toCsv(rows, [
      { key: 'email', label: 'email' },
      { key: 'displayName', label: 'displayName' },
      { key: 'department', label: 'department' },
      { key: 'hospitalId', label: 'hospitalId' },
      { key: 'error', label: 'error' },
    ]);
    downloadCsv(`invite-failures-${Date.now()}.csv`, csv);
  };

  const validCount = candidates.filter((c) => c.include && c.validation === 'ok').length;
  const invalidCount = candidates.filter((c) => c.validation !== 'ok').length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 py-6">
      <div className="flex max-h-full w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-surface-container-lowest shadow-ambient-lg">
        <div className="flex items-start justify-between border-b border-surface-container-high p-5">
          <div>
            <h3 className="flex items-center gap-2 text-base font-semibold text-on-surface">
              <FileUp className="h-4 w-4 text-primary" />
              CSV 일괄 초대
            </h3>
            <p className="mt-0.5 text-xs text-on-surface-variant">
              한 번에 최대 {MAX_ROWS}명까지 의료진을 초대할 수 있습니다
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              reset();
              onClose();
            }}
            className="rounded-lg p-1 text-on-surface-variant hover:bg-surface-container-low"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {report ? (
            <div className="flex flex-col gap-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl bg-green-50 p-4">
                  <div className="flex items-center gap-2 text-green-800">
                    <CheckCircle2 className="h-4 w-4" />
                    <p className="text-sm font-semibold">성공 {report.successes.length}건</p>
                  </div>
                  <p className="mt-1 text-xs text-green-800/80">
                    초대 링크가 생성되었습니다. 상태는 "대기"로 표시됩니다.
                  </p>
                </div>
                <div className="rounded-xl bg-red-50 p-4">
                  <div className="flex items-center gap-2 text-red-700">
                    <AlertCircle className="h-4 w-4" />
                    <p className="text-sm font-semibold">실패 {report.failures.length}건</p>
                  </div>
                  {report.failures.length > 0 && (
                    <button
                      type="button"
                      onClick={downloadFailures}
                      className="mt-2 flex items-center gap-1 rounded-lg border border-red-300 bg-white px-2 py-1 text-[11px] text-red-600"
                    >
                      <Download className="h-3 w-3" />
                      실패 목록 CSV 다운로드
                    </button>
                  )}
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={reset}
                  className="rounded-lg border border-surface-container-high px-3 py-2 text-xs"
                >
                  다시 업로드
                </button>
                <button
                  type="button"
                  onClick={() => {
                    reset();
                    onClose();
                  }}
                  className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-on-primary"
                >
                  완료
                </button>
              </div>
            </div>
          ) : candidates.length === 0 ? (
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              className="flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-surface-container-high p-8 text-center"
            >
              <Upload className="h-8 w-8 text-on-surface-variant" />
              <div>
                <p className="text-sm font-medium text-on-surface">
                  CSV 파일을 여기에 끌어다 놓거나
                </p>
                <p className="mt-0.5 text-xs text-on-surface-variant">
                  필수 헤더: email, department · 선택: displayName, hospitalId
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  onFile(e.target.files?.[0] ?? null);
                  e.target.value = '';
                }}
                className="hidden"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-lg bg-primary px-4 py-2 text-xs font-medium text-on-primary"
                >
                  파일 선택
                </button>
                <button
                  type="button"
                  onClick={downloadTemplate}
                  className="flex items-center gap-1 rounded-lg border border-surface-container-high px-3 py-2 text-xs"
                >
                  <Download className="h-3 w-3" />
                  템플릿
                </button>
              </div>
              {error && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
                  {error}
                </p>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded-full bg-green-50 px-2 py-0.5 text-green-700">
                  유효 {validCount}건
                </span>
                {invalidCount > 0 && (
                  <span className="rounded-full bg-red-50 px-2 py-0.5 text-red-600">
                    오류 {invalidCount}건
                  </span>
                )}
                <span className="ml-auto flex items-center gap-2 text-on-surface-variant">
                  <button
                    type="button"
                    onClick={() => toggleAll(true)}
                    className="rounded border border-surface-container-high px-2 py-1"
                  >
                    모두 선택
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleAll(false)}
                    className="rounded border border-surface-container-high px-2 py-1"
                  >
                    모두 해제
                  </button>
                </span>
              </div>

              <div className="max-h-80 overflow-auto rounded-xl border border-surface-container-high">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-surface-container-low">
                    <tr>
                      <th className="w-8 px-2 py-1.5"></th>
                      <th className="px-2 py-1.5">email</th>
                      <th className="px-2 py-1.5">department</th>
                      <th className="px-2 py-1.5">name</th>
                      <th className="px-2 py-1.5">hospitalId</th>
                      <th className="px-2 py-1.5">상태</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((c, i) => (
                      <tr
                        key={i}
                        className={`border-t border-surface-container-high/50 ${
                          c.validation !== 'ok'
                            ? 'bg-red-50/30'
                            : 'hover:bg-surface-container-low/50'
                        }`}
                      >
                        <td className="px-2 py-1.5">
                          <input
                            type="checkbox"
                            disabled={c.validation !== 'ok'}
                            checked={c.include}
                            onChange={(e) => onChange(i, { include: e.target.checked })}
                          />
                        </td>
                        <td className="px-2 py-1.5 font-mono">{c.email}</td>
                        <td className="px-2 py-1.5">{c.department}</td>
                        <td className="px-2 py-1.5">{c.displayName || '-'}</td>
                        <td className="px-2 py-1.5 text-on-surface-variant">{c.hospitalId}</td>
                        <td className="px-2 py-1.5">
                          <StatusTag status={c.validation} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {progress && (
                <div className="flex flex-col gap-1">
                  <p className="text-xs text-on-surface-variant">
                    처리 중 · {progress.done} / {progress.total}
                  </p>
                  <div className="h-1.5 w-full rounded-full bg-surface-container-high">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{
                        width: `${Math.round((progress.done / progress.total) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              {error && (
                <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
                  {error}
                </p>
              )}

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={reset}
                  disabled={running}
                  className="rounded-lg border border-surface-container-high px-3 py-2 text-xs disabled:opacity-50"
                >
                  취소
                </button>
                <button
                  type="button"
                  onClick={run}
                  disabled={running || validCount === 0}
                  className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-on-primary disabled:opacity-50"
                >
                  {running ? '처리 중...' : `${validCount}건 초대`}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusTag({ status }: { status: Candidate['validation'] }) {
  if (status === 'ok') {
    return (
      <span className="rounded-full bg-green-50 px-2 py-0.5 text-[10px] text-green-700">
        유효
      </span>
    );
  }
  const label =
    status === 'email_invalid'
      ? '이메일 오류'
      : status === 'duplicate'
        ? '중복'
        : '필수 누락';
  return (
    <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] text-red-600">
      {label}
    </span>
  );
}
