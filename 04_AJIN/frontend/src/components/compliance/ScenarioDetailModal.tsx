// ScenarioDetailModal — Module D Phase 3 (Item 1).
// 시나리오 원문 상세 (법규명·조항·시행일·변경 전/후·체크리스트·근거).
// 시뮬레이션 Modal 과 분리: 분석 vs 레퍼런스 자료.
// 디자인 시스템 v3.5 (HUD): 2px radius, 골드 강조, 영문 eyebrow + 한글 본문.

import { useEffect, useState } from 'react';
import {
  ExternalLink,
  AlertTriangle,
  Calendar,
  FileText,
  Clock,
  Building2,
  AlertCircle,
} from 'lucide-react';
import { Modal } from '@components/ui/Modal';
import { Badge } from '@components/ui/Badge';
import { Button } from '@components/ui/Button';
import {
  fetchScenarioDetail,
  type ScenarioDetailResponse,
} from '@api/compliance';
import type { SimFallbackScenario } from './ScenarioSimulationModal';

/** v12: HTTP status 별 사용자 안내 정보 */
interface ErrorInfo {
  reason: string;
  status?: number;
}

function classifyApiError(e: unknown): ErrorInfo {
  const status = (e as { response?: { status?: number } } | null)?.response?.status;
  if (status === 404) {
    return { reason: '이 시나리오의 상세 데이터가 준비되지 않았습니다. 캐시 메타로 일부 정보를 표시합니다.', status };
  }
  if (status === 401) {
    return { reason: '인증이 만료되었습니다. 다시 로그인해주세요.', status };
  }
  if (status === 503) {
    return { reason: '검색/분석 서버를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.', status };
  }
  if (status && status >= 500) {
    return { reason: '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.', status };
  }
  return { reason: '네트워크 연결을 확인하거나 잠시 후 다시 시도해주세요.' };
}

interface Props {
  scenarioId: string | null;
  fallbackTitle?: string;
  /** v12: 메인 페이지 캐시의 ScenarioCard — 백엔드 404 시 헤더/메타에 활용 */
  fallbackScenario?: SimFallbackScenario;
  isOpen: boolean;
  onClose: () => void;
  /** "시뮬레이션 보기" 클릭 시 호출 */
  onShowSimulation?: (scenarioId: string) => void;
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#C0392B',
  high: '#E8A317',
  medium: '#6FB1FC',
  low: '#7FD89E',
};

export function ScenarioDetailModal({
  scenarioId,
  fallbackTitle,
  fallbackScenario,
  isOpen,
  onClose,
  onShowSimulation,
}: Props) {
  const [data, setData] = useState<ScenarioDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorInfo, setErrorInfo] = useState<ErrorInfo | null>(null);

  useEffect(() => {
    if (!scenarioId || !isOpen) {
      setData(null);
      setErrorInfo(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setErrorInfo(null);
    fetchScenarioDetail(scenarioId)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) {
          setErrorInfo(classifyApiError(e));
          setData(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scenarioId, isOpen]);

  /** 백엔드 미가용 시 fallbackScenario 로 헤더/메타 일부 표시. */
  const showFallbackMeta = !data && !!fallbackScenario && !!errorInfo;

  const sevColor =
    SEVERITY_COLOR[(data?.severity ?? 'medium').toLowerCase()] ?? SEVERITY_COLOR.medium;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl" title="규제 상세">
      <div style={{ padding: '4px 4px 12px', minHeight: 320 }}>
        {/* 로딩/에러 */}
        {loading && (
          <div
            style={{
              padding: 24,
              textAlign: 'center',
              color: 'var(--hud-text-muted)',
            }}
          >
            ⏳ 규제 원문 로딩 중...
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
        {showFallbackMeta && fallbackScenario && (
          <div
            style={{
              padding: 10,
              marginBottom: 14,
              borderRadius: 2,
              border: '1px dashed var(--hud-border)',
              background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
              fontSize: 12,
              color: 'var(--hud-text-dim)',
            }}
          >
            <span
              className="mono"
              style={{
                fontSize: 10,
                padding: '2px 6px',
                borderRadius: 999,
                border: '1px solid var(--hud-orange)',
                color: 'var(--hud-orange)',
                marginRight: 8,
                letterSpacing: '0.06em',
              }}
            >
              FALLBACK
            </span>
            상세 데이터 미가용. 시나리오 카드 메타 정보로 일부 필드만 표시합니다.
          </div>
        )}

        {/* 헤더 */}
        <div style={{ marginBottom: 16 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginBottom: 8,
            }}
          >
            {(() => {
              const sev = (data?.severity ?? fallbackScenario?.cat?.toLowerCase() ?? '').toString();
              if (!sev) return null;
              return (
                <Badge
                  status={
                    sev === 'critical' || sev === 'high'
                      ? 'fail'
                      : sev === 'medium'
                        ? 'warn'
                        : 'info'
                  }
                >
                  {sev.toUpperCase()}
                </Badge>
              );
            })()}
            {(() => {
              const dday = data?.days_remaining ?? fallbackScenario?.dday ?? 0;
              if (dday <= 0) return null;
              return (
                <span
                  className="mono"
                  style={{ fontSize: 13, fontWeight: 600, color: sevColor }}
                >
                  <Clock
                    size={12}
                    strokeWidth={1.5}
                    style={{ verticalAlign: -2, marginRight: 4 }}
                  />
                  D-{dday}
                </span>
              );
            })()}
          </div>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, lineHeight: 1.3 }}>
            {data?.title ?? fallbackScenario?.title ?? fallbackTitle ?? '규제 상세'}
          </h2>
          {data?.description && (
            <p
              style={{
                margin: '8px 0 0 0',
                fontSize: 13,
                color: 'var(--hud-text-dim)',
                lineHeight: 1.55,
              }}
            >
              {data.description}
            </p>
          )}
        </div>

        {data && (
          <>
            {/* 법규 메타 */}
            <section
              style={{
                padding: 14,
                marginBottom: 16,
                borderRadius: 2,
                border: '1px solid var(--hud-border, #2A2520)',
                background: 'var(--hud-surface, #111820)',
              }}
            >
              <div
                className="label-en"
                style={{
                  fontSize: 10,
                  letterSpacing: '0.1em',
                  color: 'var(--hud-text-muted)',
                  marginBottom: 6,
                }}
              >
                <FileText
                  size={11}
                  strokeWidth={1.5}
                  style={{ verticalAlign: -1, marginRight: 4 }}
                />
                REGULATION · 법규 정보
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '90px 1fr',
                  gap: '6px 12px',
                  fontSize: 13,
                }}
              >
                <span style={{ color: 'var(--hud-text-muted)' }}>법규명</span>
                <strong>{data.regulation.name || '—'}</strong>
                {data.regulation.article && (
                  <>
                    <span style={{ color: 'var(--hud-text-muted)' }}>조항</span>
                    <span>{data.regulation.article}</span>
                  </>
                )}
                {data.regulation.authority && (
                  <>
                    <span style={{ color: 'var(--hud-text-muted)' }}>소관 기관</span>
                    <span>{data.regulation.authority}</span>
                  </>
                )}
                {data.deadline && (
                  <>
                    <span style={{ color: 'var(--hud-text-muted)' }}>시행일</span>
                    <span style={{ color: sevColor, fontWeight: 600 }}>
                      <Calendar
                        size={11}
                        strokeWidth={1.5}
                        style={{ verticalAlign: -1, marginRight: 4 }}
                      />
                      {data.deadline}
                    </span>
                  </>
                )}
              </div>
            </section>

            {/* 변경 전/후 비교 */}
            {(data.change_before || data.change_after) && (
              <section style={{ marginBottom: 16 }}>
                <div
                  className="label-en"
                  style={{
                    fontSize: 10,
                    letterSpacing: '0.1em',
                    color: 'var(--hud-text-muted)',
                    marginBottom: 6,
                  }}
                >
                  CHANGE COMPARISON · 변경 전/후 원문
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: 8,
                  }}
                >
                  {data.change_before && (
                    <ChangeBox
                      label="변경 전"
                      version={data.change_before.version}
                      effective={data.change_before.effective_date}
                      text={data.change_before.text}
                      tone="dim"
                    />
                  )}
                  {data.change_after && (
                    <ChangeBox
                      label="변경 후"
                      version={data.change_after.version}
                      effective={data.change_after.effective_date}
                      text={data.change_after.text}
                      tone="primary"
                    />
                  )}
                </div>
              </section>
            )}

            {/* 영향 영역 + 적용 사업장 */}
            <section
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: 12,
                marginBottom: 16,
              }}
            >
              {data.impact_areas.length > 0 && (
                <div>
                  <div
                    className="label-en"
                    style={{
                      fontSize: 10,
                      letterSpacing: '0.1em',
                      color: 'var(--hud-text-muted)',
                      marginBottom: 6,
                    }}
                  >
                    <AlertCircle
                      size={11}
                      strokeWidth={1.5}
                      style={{ verticalAlign: -1, marginRight: 4 }}
                    />
                    IMPACT AREAS · 영향 영역
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {data.impact_areas.map((a) => (
                      <span
                        key={a}
                        style={{
                          fontSize: 11,
                          padding: '3px 9px',
                          borderRadius: 999,
                          background:
                            'color-mix(in oklab, var(--hud-orange) 14%, transparent)',
                          color: 'var(--hud-orange)',
                          border:
                            '1px solid color-mix(in oklab, var(--hud-orange) 30%, transparent)',
                        }}
                      >
                        {a}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {data.applicable_plants.length > 0 && (
                <div>
                  <div
                    className="label-en"
                    style={{
                      fontSize: 10,
                      letterSpacing: '0.1em',
                      color: 'var(--hud-text-muted)',
                      marginBottom: 6,
                    }}
                  >
                    <Building2
                      size={11}
                      strokeWidth={1.5}
                      style={{ verticalAlign: -1, marginRight: 4 }}
                    />
                    APPLICABLE PLANTS · 적용 사업장 (
                    {data.applicable_plants.length}개)
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {data.applicable_plants.map((p) => (
                      <span
                        key={p}
                        style={{
                          fontSize: 10,
                          padding: '2px 7px',
                          borderRadius: 999,
                          background:
                            'color-mix(in oklab, var(--hud-text) 8%, transparent)',
                          color: 'var(--hud-text-dim)',
                          fontFamily: 'var(--hud-font-mono)',
                        }}
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </section>

            {/* 권장 조치 */}
            {data.required_actions.length > 0 && (
              <section style={{ marginBottom: 16 }}>
                <div
                  className="label-en"
                  style={{
                    fontSize: 10,
                    letterSpacing: '0.1em',
                    color: 'var(--hud-text-muted)',
                    marginBottom: 8,
                  }}
                >
                  REQUIRED ACTIONS · 컴플라이언스 체크리스트
                </div>
                <ol
                  style={{
                    margin: 0,
                    paddingLeft: 18,
                    fontSize: 13,
                    lineHeight: 1.7,
                  }}
                >
                  {data.required_actions.map((act, i) => (
                    <li key={i} style={{ marginBottom: 4 }}>
                      {act}
                    </li>
                  ))}
                </ol>
                {data.estimated_cost && (
                  <div
                    style={{
                      marginTop: 8,
                      padding: '6px 10px',
                      fontSize: 12,
                      borderRadius: 2,
                      background: 'rgba(232,163,23,0.10)',
                      border: '1px dashed var(--hud-orange)',
                      color: 'var(--hud-orange)',
                    }}
                  >
                    💰 예상 비용: <strong>{data.estimated_cost}</strong>
                  </div>
                )}
              </section>
            )}

            {/* 근거/출처 링크 */}
            {data.references.length > 0 && (
              <section style={{ marginBottom: 14 }}>
                <div
                  className="label-en"
                  style={{
                    fontSize: 10,
                    letterSpacing: '0.1em',
                    color: 'var(--hud-text-muted)',
                    marginBottom: 6,
                  }}
                >
                  REFERENCES · 근거 자료
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {data.references.map((r, i) => (
                    <a
                      key={i}
                      href={r.url || '#'}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: 12,
                        color: r.url ? 'var(--hud-primary)' : 'var(--hud-text-muted)',
                        textDecoration: 'none',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      {r.url && <ExternalLink size={11} strokeWidth={1.5} />}
                      {r.title}
                    </a>
                  ))}
                </div>
              </section>
            )}

            {/* 액션 버튼 */}
            <div
              style={{
                display: 'flex',
                gap: 8,
                marginTop: 18,
                justifyContent: 'flex-end',
              }}
            >
              {onShowSimulation && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    onShowSimulation(data.scenario_id);
                    onClose();
                  }}
                >
                  시뮬레이션 보기 →
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

function ChangeBox({
  label,
  version,
  effective,
  text,
  tone,
}: {
  label: string;
  version: string;
  effective: string;
  text: string;
  tone: 'dim' | 'primary';
}) {
  const isPrimary = tone === 'primary';
  return (
    <div
      style={{
        padding: 10,
        borderRadius: 2,
        background: isPrimary
          ? 'color-mix(in oklab, var(--hud-primary) 8%, transparent)'
          : 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
        border: `1px solid ${
          isPrimary
            ? 'color-mix(in oklab, var(--hud-primary) 35%, transparent)'
            : 'color-mix(in oklab, var(--hud-text) 12%, transparent)'
        }`,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          marginBottom: 6,
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: isPrimary ? 'var(--hud-primary)' : 'var(--hud-text-muted)',
            letterSpacing: '0.05em',
          }}
        >
          {label}
        </span>
        <span
          className="mono"
          style={{ fontSize: 10, color: 'var(--hud-text-muted)' }}
        >
          {version} {effective && `· ${effective}`}
        </span>
      </div>
      <pre
        style={{
          margin: 0,
          fontSize: 11,
          lineHeight: 1.55,
          color: 'var(--hud-text)',
          fontFamily: 'inherit',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          maxHeight: 220,
          overflow: 'auto',
        }}
      >
        {text || '—'}
      </pre>
    </div>
  );
}
