// G1-F5: 법령 단일 문서 상세 페이지.
// URL: /compliance/reg/:id
//   - 검색 결과의 regulations hit 클릭 시 진입
//   - Design System v2 정합 (--hud-* 토큰, bilingual eyebrow, 2px radius)

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  fetchRegulationById,
  type RegulationDoc,
} from '@api/compliance';
import { GlossaryAutoText } from '@components/compliance/GlossaryProvider';

export function ComplianceRegulationDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [doc, setDoc] = useState<RegulationDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchRegulationById(id)
      .then((d) => {
        if (!cancelled) setDoc(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : '로드 실패');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="page lg-page">
        <div className="lg-empty">로드 중…</div>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="page lg-page">
        <section className="lg-hero">
          <div className="lg-hero-eyebrow">REGULATION DETAIL · 404</div>
          <h1 className="lg-display">법령을 찾을 수 없습니다</h1>
          <p className="lg-sub">
            ID: <code>{id}</code> {error && `— ${error}`}
          </p>
          <button className="lg-btn" onClick={() => nav(-1)}>
            ← 뒤로
          </button>
        </section>
      </div>
    );
  }

  return (
    <div className="page lg-page" data-screen-label="D · Regulation Detail">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">
          REGULATION DETAIL · MODULE D · {doc.doc_type || '—'}
        </div>
        <h1 className="lg-display">{doc.title}</h1>
        {doc.title_ko && doc.title_ko !== doc.title && (
          <p className="lg-sub">{doc.title_ko}</p>
        )}
        <div className="lg-crumb">
          <Link to="/compliance">← 법규 모니터</Link>
          {' · '}
          <Link to="/compliance/search">검색</Link>
        </div>
      </section>

      <section className="lg-card lg-reg-meta">
        <h3>METADATA · 메타데이터</h3>
        <dl className="lg-kv">
          <Field label="문서 유형" en="DOC TYPE" value={doc.doc_type} />
          <Field label="조항" en="ARTICLE" value={doc.article_no} />
          <Field label="발행 기관" en="AUTHORITY" value={doc.authority} />
          <Field label="국가" en="COUNTRY" value={doc.country} />
          <Field label="카테고리" en="CATEGORY" value={doc.category} />
          <Field
            label="이행 상태"
            en="STATUS"
            value={doc.compliance_status}
          />
          <Field
            label="시행일"
            en="EFFECTIVE"
            value={doc.effective_date}
            mono
          />
          <Field
            label="최종 개정"
            en="AMENDED"
            value={doc.last_amended}
            mono
          />
          <Field
            label="원본 ID"
            en="NATURAL ID"
            value={doc.natural_id}
            mono
          />
        </dl>

        {Array.isArray(doc.tags) && doc.tags.length > 0 && (
          <div className="lg-tags">
            {doc.tags.map((t) => (
              <span key={t} className="lg-chip">
                {t}
              </span>
            ))}
          </div>
        )}
      </section>

      <section className="lg-card lg-reg-body">
        <h3>BODY · 조문 본문</h3>
        {doc.body ? (
          <pre className="lg-pre">
            <GlossaryAutoText text={doc.body} />
          </pre>
        ) : (
          <p className="dim">본문이 비어 있습니다 (도메인 메타 데이터만 보유).</p>
        )}
      </section>
    </div>
  );
}

function Field({
  label,
  en,
  value,
  mono,
}: {
  label: string;
  en: string;
  value?: string | null;
  mono?: boolean;
}) {
  if (!value) return null;
  return (
    <>
      <dt>
        <span className="label-en">{en}</span>
        <span className="label-ko"> · {label}</span>
      </dt>
      <dd className={mono ? 'mono' : undefined}>{value}</dd>
    </>
  );
}

export default ComplianceRegulationDetail;
