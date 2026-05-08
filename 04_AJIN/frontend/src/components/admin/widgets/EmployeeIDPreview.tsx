// EmployeeIDPreview — 부서 선택 시 자동 사번 미리보기.
// 디바운스 후 POST /admin/employee-id/preview 호출.

import { useEffect, useState } from 'react';
import { previewEmployeeId, type EmployeeIDPreviewResponse } from '@api/admin';

interface Props {
  department: string;
  onResolved?: (preview: EmployeeIDPreviewResponse) => void;
}

export function EmployeeIDPreview({ department, onResolved }: Props) {
  const [preview, setPreview] = useState<EmployeeIDPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    if (!department) {
      setPreview(null);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      previewEmployeeId(department)
        .then((p) => {
          setPreview(p);
          onResolved?.(p);
        })
        .catch((e) => setError(`미리보기 실패: ${(e as Error).message}`))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [department, onResolved]);

  if (!department) {
    return (
      <div className="lg-stat-row">
        <span>사번 미리보기</span>
        <b style={{ color: 'var(--hud-text-dim)' }}>부서를 먼저 선택하세요.</b>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="lg-stat-row">
        <span>사번 미리보기</span>
        <b>불러오는 중…</b>
      </div>
    );
  }

  if (error) {
    return (
      <div className="lg-stat-row">
        <span>사번 미리보기</span>
        <b style={{ color: '#C0392B' }}>{error}</b>
      </div>
    );
  }

  if (!preview) return null;

  return (
    <div className="lg-card lg-card-tight" style={{ padding: '12px 16px', margin: 0 }}>
      <div className="lg-pill">자동 생성</div>
      <div className="lg-stat-list" style={{ marginTop: 10 }}>
        <div className="lg-stat-row">
          <span>다음 사번</span>
          <b style={{ fontFamily: 'var(--hud-font-mono)', color: 'var(--hud-primary)', fontSize: 16 }}>
            {preview.next_id}
          </b>
        </div>
        <div className="lg-stat-row">
          <span>접두어 / 시퀀스</span>
          <b className="mono">{preview.prefix} / #{preview.sequence}</b>
        </div>
        <div className="lg-stat-row">
          <span>제안 이메일</span>
          <b className="mono" style={{ fontSize: 12 }}>{preview.suggested_email}</b>
        </div>
        <div className="lg-stat-row">
          <span>초기 비밀번호</span>
          <b className="mono">{preview.suggested_initial_password}</b>
        </div>
      </div>
    </div>
  );
}
