// G1-F5: 법령 단일 문서 상세 페이지.
// URL: /compliance/reg/:id
//   - 검색 결과의 regulations hit 클릭 시 진입
//   - Design System v2 정합 (--hud-* 토큰, bilingual eyebrow, 2px radius)

import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  fetchChanges,
  fetchRegulationById,
  type ChangeItem,
  type RegulationDoc,
  type RegulationImpact,
} from '@api/compliance';
import { GlossaryAutoText } from '@components/compliance/GlossaryProvider';

export function ComplianceRegulationDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [doc, setDoc] = useState<RegulationDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [changes, setChanges] = useState<ChangeItem[]>([]);

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

  // Issue 3 — 규제별 변경 이력 + 사내 영향 (regulation_changes 테이블 조회)
  useEffect(() => {
    if (!doc) return;
    const regType = (doc.doc_type || '').toLowerCase();
    if (!regType) return;
    let cancelled = false;
    fetchChanges(5, false, regType, id)
      .then((r) => {
        if (!cancelled) setChanges(r.changes ?? []);
      })
      .catch(() => {
        if (!cancelled) setChanges([]);
      });
    return () => {
      cancelled = true;
    };
  }, [doc, id]);

  const latestImpact = useMemo<RegulationImpact | null>(() => {
    const c = changes.find((x) => x.impact_json && x.impact_json !== '{}');
    if (!c?.impact_json) return null;
    try {
      return JSON.parse(c.impact_json) as RegulationImpact;
    } catch {
      return null;
    }
  }, [changes]);

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

      {/* Issue 3 — 규제 변경 이력 (과거 vs 현재) */}
      {changes.length > 0 && (
        <section className="lg-card lg-reg-changes">
          <h3>CHANGE HISTORY · 규제 변경 이력</h3>
          <ul className="lg-change-list">
            {changes.map((c) => (
              <li key={c.id} className="lg-change-item">
                <header>
                  <span className="lg-chip">{changeTypeLabel(c.change_type)}</span>
                  <time className="mono dim">{c.detected_at.slice(0, 10)}</time>
                </header>
                {c.before_text || c.after_text ? (
                  <div className="lg-diff">
                    {c.before_text && (
                      <div className="lg-diff-before">
                        <span className="label-en">BEFORE · 이전</span>
                        <pre>{truncate(c.before_text, 800)}</pre>
                      </div>
                    )}
                    {c.after_text && (
                      <div className="lg-diff-after">
                        <span className="label-en">AFTER · 현재</span>
                        <pre>{truncate(c.after_text, 800)}</pre>
                      </div>
                    )}
                  </div>
                ) : (
                  c.summary && <p className="dim">{c.summary}</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Issue 3 — 아진산업 영향 분석 */}
      {latestImpact && (
        <section className="lg-card lg-reg-impact">
          <h3>IMPACT · 아진산업 영향 분석</h3>
          <dl className="lg-kv">
            {latestImpact.affected_plants && latestImpact.affected_plants.length > 0 && (
              <Field
                label="영향 사업장"
                en="AFFECTED PLANTS"
                value={`${latestImpact.affected_plants.join(', ')} (${latestImpact.affected_plants.length}곳)`}
              />
            )}
            {latestImpact.affected_processes && latestImpact.affected_processes.length > 0 && (
              <Field
                label="영향 공정"
                en="AFFECTED PROCESSES"
                value={`${latestImpact.affected_processes.join(', ')} (${latestImpact.affected_processes.length}개)`}
              />
            )}
            {typeof latestImpact.affected_workers === 'number' && (
              <Field
                label="영향 작업자"
                en="AFFECTED WORKERS"
                value={`${latestImpact.affected_workers}명`}
              />
            )}
            {latestImpact.affected_chemicals && latestImpact.affected_chemicals.length > 0 && (
              <Field
                label="관련 화학물질"
                en="CHEMICALS"
                value={latestImpact.affected_chemicals.join(', ')}
              />
            )}
            {latestImpact.affected_standards && latestImpact.affected_standards.length > 0 && (
              <Field
                label="관련 안전기준"
                en="STANDARDS"
                value={latestImpact.affected_standards.join(', ')}
              />
            )}
            {typeof latestImpact.risk_score === 'number' && (
              <Field
                label="위험 점수"
                en="RISK SCORE"
                value={`${latestImpact.risk_score.toFixed(0)} / 100 · ${riskGrade(latestImpact.risk_score)}`}
                mono
              />
            )}
            {latestImpact.deadline && (
              <Field label="대응 마감" en="DEADLINE" value={latestImpact.deadline} mono />
            )}
            {latestImpact.estimated_cost && (
              <Field label="예상 비용" en="EST. COST" value={latestImpact.estimated_cost} />
            )}
          </dl>

          {latestImpact.required_actions && latestImpact.required_actions.length > 0 && (
            <>
              <h4 className="lg-section-h4">RECOMMENDED ACTIONS · 권장 조치</h4>
              <ol className="lg-action-list">
                {latestImpact.required_actions.slice(0, 5).map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ol>
            </>
          )}
        </section>
      )}
    </div>
  );
}

function changeTypeLabel(t: string): string {
  return (
    { added: '신규 추가', removed: '삭제', modified: '변경' } as Record<string, string>
  )[t] ?? t;
}

function riskGrade(score: number): string {
  if (score >= 80) return 'CRITICAL';
  if (score >= 60) return 'HIGH';
  if (score >= 40) return 'MEDIUM';
  return 'LOW';
}

function truncate(text: string, max: number): string {
  if (!text) return '';
  if (text.length <= max) return text;
  return text.slice(0, max - 1) + '…';
}

function Field({
  label,
  en,
  value,
  mono }: {
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
