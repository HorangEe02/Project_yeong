// ScenarioSimulationModal — Module D Phase 2.
// 시나리오 통합 시뮬레이션 결과 표시 (위험도 + 영향 시설/부서 + 비용 + 권장 액션 + 근거).
// 디자인 시스템 v3.5 (HUD): 2px radius, 골드 강조, 영문 eyebrow + 한글 본문.
//
// v12 강화:
//   - HTTP status 별 안내 메시지 분기 (404 / 401 / 5xx / 네트워크)
//   - fallbackScenario prop — 백엔드 404 시 시나리오 메타에서 mock simulation 구성
//   - 메시지: "백엔드 미가용" → 정확한 사유로 변경

import { useEffect, useMemo, useState } from 'react';
import { ExternalLink, AlertTriangle, CheckCircle2, Building2, Users, Clock } from 'lucide-react';
import { Modal } from '@components/ui/Modal';
import { Badge } from '@components/ui/Badge';
import { Button } from '@components/ui/Button';
import { simulateScenario, type ScenarioSimulateResponse } from '@api/compliance';

/** v12: compliance.tsx 의 ScenarioCard 와 호환되는 최소 fallback 타입 */
export interface SimFallbackScenario {
  id: string;
  title: string;
  en?: string;
  score: number;
  cat: string;
  dday: number;
  desc: string;
  risk: { fin: number; pos: number; urg: number };
  sites: string[];
  depts: string[];
}

interface Props {
  /** 클릭한 시나리오 ID. null 이면 닫힘. */
  scenarioId: string | null;
  /** 시나리오 메타 (백엔드 fetch 실패 시 폴백 표시용) */
  fallbackTitle?: string;
  fallbackCategory?: string;
  /** v12: 메인 페이지 캐시의 ScenarioCard — 404 시 client-side mock simulation 으로 표시 */
  fallbackScenario?: SimFallbackScenario;
  /** 사용자 사업장명 (영향 시설 리스트 골드 강조용) */
  userPlant?: string;
  isOpen: boolean;
  onClose: () => void;
  /** "영향 분석으로 →" 클릭 시 호출 (MONITOR 탭 전환 + selectedScenarioId 세팅) */
  onShowImpact?: (scenarioId: string) => void;
}

const CATEGORY_COLOR: Record<string, string> = {
  CRITICAL: '#C0392B',
  HIGH: '#E8A317',
  MEDIUM: '#6FB1FC',
  LOW: '#7FD89E',
};

interface ErrorInfo {
  reason: string;
  status?: number;
  isFallbackUsable: boolean;
}

function classifyError(e: unknown): ErrorInfo {
  const r = (e as { response?: { status?: number } } | null)?.response;
  const status = r?.status;
  if (status === 404) {
    return {
      reason: '이 시나리오의 즉시 시뮬레이션 데이터가 준비되지 않았습니다. 메타 데이터로 추정값을 표시합니다.',
      status,
      isFallbackUsable: true,
    };
  }
  if (status === 401) {
    return { reason: '인증이 만료되었습니다. 다시 로그인해주세요.', status, isFallbackUsable: false };
  }
  if (status === 503) {
    return { reason: '검색/분석 서버를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.', status, isFallbackUsable: true };
  }
  if (status && status >= 500) {
    return { reason: '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.', status, isFallbackUsable: true };
  }
  return {
    reason: '네트워크 연결을 확인하거나 잠시 후 다시 시도해주세요.',
    isFallbackUsable: true,
  };
}

export function ScenarioSimulationModal({
  scenarioId,
  fallbackTitle,
  fallbackCategory,
  fallbackScenario,
  userPlant,
  isOpen,
  onClose,
  onShowImpact,
}: Props) {
  const [result, setResult] = useState<ScenarioSimulateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorInfo, setErrorInfo] = useState<ErrorInfo | null>(null);

  // 시나리오 변경 시 시뮬레이션 fetch
  useEffect(() => {
    if (!scenarioId || !isOpen) {
      setResult(null);
      setErrorInfo(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErrorInfo(null);
    simulateScenario(scenarioId)
      .then((res) => {
        if (!cancelled) setResult(res);
      })
      .catch((e) => {
        if (!cancelled) {
          setErrorInfo(classifyError(e));
          setResult(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scenarioId, isOpen]);

  /** v12: 백엔드 호출 실패 시 메인 페이지 캐시로 mock simulation 구성. */
  const fallbackResult = useMemo<ScenarioSimulateResponse | null>(() => {
    if (!fallbackScenario || !errorInfo?.isFallbackUsable) return null;
    return {
      scenario_id: fallbackScenario.id,
      title: fallbackScenario.title,
      category: fallbackScenario.cat,
      deadline_days: fallbackScenario.dday,
      description: fallbackScenario.desc,
      risk_score: {
        total: fallbackScenario.score,
        fin: fallbackScenario.risk.fin,
        pos: fallbackScenario.risk.pos,
        urg: fallbackScenario.risk.urg,
      },
      impact: {
        plants: fallbackScenario.sites.filter((s) => s && s !== '—'),
        departments: fallbackScenario.depts,
        cost_estimate_krw_bn: 0,
        cost_breakdown: [],
      },
      recommended_actions: [],
      evidence_links: [],
    };
  }, [fallbackScenario, errorInfo]);

  const displayResult = result ?? fallbackResult;
  const isFallback = !result && !!fallbackResult;

  const title = displayResult?.title ?? fallbackTitle ?? '시나리오 시뮬레이션';
  const category = displayResult?.category ?? fallbackCategory ?? 'MEDIUM';
  const catColor = CATEGORY_COLOR[category] ?? CATEGORY_COLOR.MEDIUM;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg" title="시나리오 시뮬레이션">
      <div style={{ padding: '4px 4px 12px', minHeight: 320 }}>
        {/* ── 헤더: 카테고리 뱃지 + D-day + 제목 ───────────── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
          <Badge status={category === 'CRITICAL' ? 'fail' : category === 'HIGH' ? 'warn' : 'info'}>
            {category}
          </Badge>
          {displayResult && displayResult.deadline_days > 0 && (
            <span
              className="mono"
              style={{ fontSize: 13, fontWeight: 600, color: catColor }}
            >
              <Clock size={12} strokeWidth={1.5} style={{ verticalAlign: -2, marginRight: 4 }} />
              D-{displayResult.deadline_days}
            </span>
          )}
          {isFallback && (
            <span
              className="mono"
              style={{
                fontSize: 10,
                padding: '2px 8px',
                borderRadius: 999,
                border: '1px solid var(--hud-orange)',
                color: 'var(--hud-orange)',
                letterSpacing: '0.06em',
              }}
              title="백엔드 응답을 받지 못해 메타 데이터 기반 추정값을 표시합니다"
            >
              FALLBACK · 추정값
            </span>
          )}
        </div>
        <h2 style={{ margin: '0 0 6px 0', fontSize: 22, fontWeight: 700 }}>
          {title}
        </h2>
        {displayResult?.description && (
          <p style={{ margin: '0 0 18px 0', fontSize: 13, color: 'var(--hud-text-dim)', lineHeight: 1.55 }}>
            {displayResult.description}
          </p>
        )}

        {/* ── 로딩/에러 ────────────────────────────────────── */}
        {loading && (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--hud-text-muted)' }}>
            ⏳ 시뮬레이션 분석 중...
          </div>
        )}
        {errorInfo && (
          <div
            style={{
              padding: 12,
              marginBottom: 14,
              borderRadius: 2,
              border: '1px solid var(--hud-orange)',
              background: 'rgba(232,163,23,0.10)',
              color: 'var(--hud-orange)',
              fontSize: 12,
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
            }}
          >
            <AlertTriangle size={14} style={{ marginTop: 2, flexShrink: 0 }} />
            <span>
              {errorInfo.reason}
              {errorInfo.status && (
                <span className="mono" style={{ marginLeft: 6, opacity: 0.7 }}>
                  (HTTP {errorInfo.status})
                </span>
              )}
            </span>
          </div>
        )}

        {displayResult && (
          <>
            {/* ── 위험도 점수 ─────────────────────────────────── */}
            <section
              style={{
                padding: 16,
                marginBottom: 18,
                borderRadius: 2,
                border: `1px solid ${catColor}55`,
                background: `${catColor}0D`,
              }}
            >
              <div className="label-en" style={{ fontSize: 10, letterSpacing: '0.1em', color: catColor }}>
                RISK SCORE · 위험도 점수{isFallback ? ' (추정)' : ''}
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 4 }}>
                <span style={{ fontSize: 42, fontWeight: 800, color: catColor, lineHeight: 1 }}>
                  {displayResult.risk_score.total}
                </span>
                <span style={{ fontSize: 14, color: 'var(--hud-text-dim)' }}>/100</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginTop: 10 }}>
                <ScoreCell label="재무" value={displayResult.risk_score.fin} max={40} />
                <ScoreCell label="가능성" value={displayResult.risk_score.pos} max={30} />
                <ScoreCell label="긴급" value={displayResult.risk_score.urg} max={30} />
              </div>
            </section>

            {/* ── 영향 시설 / 부서 ─────────────────────────── */}
            <section style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 18 }}>
              <div>
                <div
                  className="label-en"
                  style={{ fontSize: 10, letterSpacing: '0.1em', color: 'var(--hud-text-muted)', marginBottom: 6 }}
                >
                  <Building2 size={11} strokeWidth={1.5} style={{ verticalAlign: -1, marginRight: 4 }} />
                  AFFECTED PLANTS · 영향 시설
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {displayResult.impact.plants.length === 0 ? (
                    <span style={{ fontSize: 12, color: 'var(--hud-text-muted)' }}>—</span>
                  ) : (
                    displayResult.impact.plants.map((p) => {
                      const isMine = userPlant && p.includes(userPlant);
                      return (
                        <span
                          key={p}
                          style={{
                            fontSize: 11,
                            padding: '3px 9px',
                            borderRadius: 999,
                            background: isMine
                              ? 'var(--hud-primary)'
                              : 'color-mix(in oklab, var(--hud-text) 8%, transparent)',
                            color: isMine ? 'var(--hud-bg)' : 'var(--hud-text-dim)',
                            fontWeight: isMine ? 700 : 400,
                            border: isMine ? '1px solid var(--hud-primary)' : '1px solid transparent',
                          }}
                          title={isMine ? '본인 사업장' : ''}
                        >
                          {p}{isMine ? ' ★' : ''}
                        </span>
                      );
                    })
                  )}
                </div>
              </div>
              <div>
                <div
                  className="label-en"
                  style={{ fontSize: 10, letterSpacing: '0.1em', color: 'var(--hud-text-muted)', marginBottom: 6 }}
                >
                  <Users size={11} strokeWidth={1.5} style={{ verticalAlign: -1, marginRight: 4 }} />
                  AFFECTED DEPARTMENTS · 영향 부서
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {displayResult.impact.departments.length === 0 ? (
                    <span style={{ fontSize: 12, color: 'var(--hud-text-muted)' }}>—</span>
                  ) : (
                    displayResult.impact.departments.map((d) => (
                      <span
                        key={d}
                        style={{
                          fontSize: 11,
                          padding: '3px 9px',
                          borderRadius: 999,
                          background: 'color-mix(in oklab, var(--hud-primary) 14%, transparent)',
                          color: 'var(--hud-primary)',
                          border: '1px solid color-mix(in oklab, var(--hud-primary) 30%, transparent)',
                        }}
                      >
                        {d}
                      </span>
                    ))
                  )}
                </div>
              </div>
            </section>

            {/* ── 비용 추정 (관세 시나리오) ─────────────────── */}
            {displayResult.impact.cost_estimate_krw_bn > 0 && (
              <section
                style={{
                  padding: 12,
                  marginBottom: 18,
                  borderRadius: 2,
                  border: '1px dashed var(--hud-border, #2A2520)',
                  background: 'var(--hud-surface, #111820)',
                }}
              >
                <div
                  className="label-en"
                  style={{ fontSize: 10, letterSpacing: '0.1em', color: 'var(--hud-text-muted)', marginBottom: 4 }}
                >
                  COST ESTIMATE · 비용 추정 (연간)
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ fontSize: 24, fontWeight: 700, color: 'var(--hud-orange, #E8A317)' }}>
                    {displayResult.impact.cost_estimate_krw_bn.toFixed(2)}
                  </span>
                  <span style={{ fontSize: 13, color: 'var(--hud-text-dim)' }}>억 원 / 년</span>
                </div>
                {displayResult.impact.cost_breakdown.length > 0 && (
                  <div style={{ fontSize: 11, color: 'var(--hud-text-muted)', marginTop: 4 }}>
                    {displayResult.impact.cost_breakdown.length}개 품목 분석 — 상세는 관세 시뮬레이터 탭 참조
                  </div>
                )}
              </section>
            )}

            {/* ── 권장 액션 ───────────────────────────────────── */}
            {displayResult.recommended_actions.length > 0 && (
              <section style={{ marginBottom: 18 }}>
                <div
                  className="label-en"
                  style={{ fontSize: 10, letterSpacing: '0.1em', color: 'var(--hud-text-muted)', marginBottom: 8 }}
                >
                  RECOMMENDED ACTIONS · 권장 대응 액션
                </div>
                <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {displayResult.recommended_actions.map((act, i) => (
                    <li
                      key={i}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: 10,
                        padding: '8px 12px',
                        borderRadius: 2,
                        background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
                        border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
                        fontSize: 13,
                        lineHeight: 1.55,
                      }}
                    >
                      <CheckCircle2
                        size={14}
                        strokeWidth={1.5}
                        style={{ color: 'var(--hud-primary)', flexShrink: 0, marginTop: 2 }}
                      />
                      <span>{act}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* ── 근거 링크 ───────────────────────────────────── */}
            {displayResult.evidence_links.length > 0 && (
              <section style={{ marginBottom: 14 }}>
                <div
                  className="label-en"
                  style={{ fontSize: 10, letterSpacing: '0.1em', color: 'var(--hud-text-muted)', marginBottom: 6 }}
                >
                  EVIDENCE · 근거 자료
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {displayResult.evidence_links.map((ev, i) => (
                    <a
                      key={i}
                      href={ev.url || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: 12,
                        color: ev.url ? 'var(--hud-primary)' : 'var(--hud-text-muted)',
                        textDecoration: 'none',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      {ev.url && <ExternalLink size={11} strokeWidth={1.5} />}
                      {ev.title}
                    </a>
                  ))}
                </div>
              </section>
            )}

            {/* ── 액션 버튼 ───────────────────────────────────── */}
            <div style={{ display: 'flex', gap: 8, marginTop: 18, justifyContent: 'flex-end' }}>
              {onShowImpact && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    onShowImpact(displayResult.scenario_id);
                    onClose();
                  }}
                >
                  영향 분석으로 →
                </Button>
              )}
              <Button variant="primary" size="sm" onClick={onClose}>
                닫기
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

function ScoreCell({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div>
      <div style={{ fontSize: 10, color: 'var(--hud-text-muted)', marginBottom: 3, fontFamily: 'var(--hud-font-mono)' }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--hud-text)' }}>
        {value}
        <span style={{ fontSize: 11, color: 'var(--hud-text-muted)', marginLeft: 3 }}>/{max}</span>
      </div>
      <div
        style={{
          height: 3,
          background: 'color-mix(in oklab, var(--hud-text) 8%, transparent)',
          borderRadius: 999,
          marginTop: 4,
          overflow: 'hidden',
        }}
      >
        <span
          style={{
            display: 'block',
            height: '100%',
            width: `${pct}%`,
            background: 'var(--hud-primary)',
          }}
        />
      </div>
    </div>
  );
}
