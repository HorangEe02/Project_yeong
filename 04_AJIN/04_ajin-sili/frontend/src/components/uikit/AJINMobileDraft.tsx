// AJINMobileDraft — iPhone 모바일 문서 작성 (Module B / Draft) 화면.
//
// 데스크탑 routes/draft.tsx 의 핵심 플로우만 단일 컬럼으로 압축:
//   (1) 헤더  (2) 카테고리(내부/외부) + 문서 유형 선택  (3) 주제/어조 입력
//   (4) "생성" → POST /api/draft/stream-v2 (SSE, useSSE 훅 — 데스크탑과 동일 메커니즘)
//   (5) 토큰 스트리밍 출력  (6) 복사 + 실 다운로드(DOCX/PDF/TXT via POST /draft/export)
//   + 완료 시 자동 품질 평가 (POST /draft/quality/score) 컴팩트 표시.
//
// 데스크탑에서 의도적으로 생략한 것 (모바일 집중):
//   · CC 자동추천 / Few-shot RAG 사이드 카드 / Diff 비교 모달 / 버전 타임라인
//   · 사용자 양식 업로드(upload-reference) / 구조화 변수 폼(VariableForm)
//   · 메일 발송 모달 (이 앱에서 메일 발송은 Mock — 모바일에서는 제외)
//   · 진단 배너 / LLM 모델 셀렉터 (백엔드 default 라우팅에 위임)
//   · Firestore 이력 / 부서·개인 추천 정렬
//
// 실제 엔드포인트만 호출 — mock 생성 본문 없음. 백엔드 미응답 시 명확한 오류 표시.

import { useCallback, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Check,
  ChevronLeft,
  Copy,
  Download,
  FileText,
  Sparkles,
  Square,
} from 'lucide-react';

import { useSSE } from '@hooks/useSSE';
import { apiUrl } from '@api/baseUrl';
import {
  exportAndDownload,
  scoreQuality,
} from '@api/draft';
import type {
  DocCategory,
  DocTypeMeta,
  ExportFormat,
  QualityResponse,
} from '@/types/draft';

// ──────────────────────────────────────────────────────────────────
// 문서 유형 — 데스크탑 draft.tsx 의 MOCK_DOC_TYPES 와 동일한 실 doc_type 목록.
// (GET /draft/doc-types 가 동일 메타를 내려주지만, 모바일은 1-탭 즉시 픽을 위해
//  정적 목록으로 시작. 생성 payload 의 doc_type 은 name_ko 를 전달 — 데스크탑 onGenerate 와 동일.)
// ──────────────────────────────────────────────────────────────────
const DOC_TYPES: DocTypeMeta[] = [
  // 외부용
  { id: '8d_report', category: 'external', name_ko: '8D Report', name_en: '8D Report', required_fields: [] },
  { id: 'ecn', category: 'external', name_ko: 'ECN', name_en: 'ECN', required_fields: [] },
  { id: 'ppap', category: 'external', name_ko: 'PPAP', name_en: 'PPAP', required_fields: [] },
  { id: 'fmea', category: 'external', name_ko: 'FMEA', name_en: 'FMEA', required_fields: [] },
  { id: 'msa', category: 'external', name_ko: 'MSA', name_en: 'MSA', required_fields: [] },
  { id: 'oem_email', category: 'external', name_ko: 'OEM 영문 이메일', name_en: 'OEM Email', required_fields: [] },
  // 내부용
  { id: 'internal_email', category: 'internal', name_ko: '사내 이메일', name_en: 'Internal Email', required_fields: [] },
  { id: 'meeting_min', category: 'internal', name_ko: '회의록', name_en: 'Meeting Minutes', required_fields: [] },
  { id: 'weekly_report', category: 'internal', name_ko: '주간 보고', name_en: 'Weekly Report', required_fields: [] },
  { id: 'leave_request', category: 'internal', name_ko: '휴가 신청서', name_en: 'Leave Request', required_fields: [] },
  { id: 'business_trip_request', category: 'internal', name_ko: '출장 신청서', name_en: 'Business Trip Request', required_fields: [] },
  { id: 'travel_report', category: 'internal', name_ko: '출장 보고서', name_en: 'Travel Report', required_fields: [] },
  { id: 'quote', category: 'internal', name_ko: '견적서', name_en: 'Quote', required_fields: [] },
  { id: 'spc_report', category: 'internal', name_ko: 'SPC Report', name_en: 'SPC Report', required_fields: [] },
];

const TONES = [
  { id: 'standard', ko: '표준' },
  { id: 'formal_internal', ko: '격식 (사내)' },
  { id: 'formal_external', ko: '격식 (외부)' },
  { id: 'friendly', ko: '친근' },
  { id: 'concise', ko: '간결' },
] as const;

const CATEGORIES: { k: DocCategory; en: string; ko: string }[] = [
  { k: 'internal', en: 'INTERNAL', ko: '내부' },
  { k: 'external', en: 'EXTERNAL', ko: '외부' },
];

// 모바일 다운로드 — 데스크탑 9포맷 중 가장 보편적인 3종만 노출 (POST /draft/export 동일 호출).
const DOWNLOAD_FORMATS: { fmt: ExportFormat; label: string }[] = [
  { fmt: 'docx', label: 'DOCX' },
  { fmt: 'pdf', label: 'PDF' },
  { fmt: 'txt', label: 'TXT' },
];

const GOLD = 'var(--aj-gold, #FCB132)';

export function AJINMobileDraft() {
  const navigate = useNavigate();

  // ── 입력 상태 ───────────────────────────────────────────
  const [category, setCategory] = useState<DocCategory>('internal');
  const [docTypeId, setDocTypeId] = useState<string>('internal_email');
  const [toneId, setToneId] = useState<string>('standard');
  const [userRequest, setUserRequest] = useState('');

  // ── 생성 결과 ───────────────────────────────────────────
  const [output, setOutput] = useState('');
  const [err, setErr] = useState<string | null>(null);

  // ── 부가 상태 ───────────────────────────────────────────
  const [quality, setQuality] = useState<QualityResponse | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [downloadingFmt, setDownloadingFmt] = useState<ExportFormat | null>(null);
  const [downloadErr, setDownloadErr] = useState<string | null>(null);

  const outputRef = useRef<HTMLDivElement | null>(null);
  const ranAutoRef = useRef(false);

  const filteredDocTypes = useMemo(
    () => DOC_TYPES.filter((d) => d.category === category),
    [category],
  );

  const docTypeKo = useMemo(
    () => DOC_TYPES.find((d) => d.id === docTypeId)?.name_ko ?? docTypeId,
    [docTypeId],
  );

  // ── 완료 시 자동 품질 평가 (POST /draft/quality/score) ──
  const scoreNow = useCallback(
    async (text: string) => {
      if (!text || text.trim().length < 50) return;
      setQualityLoading(true);
      try {
        const res = await scoreQuality({ text, doc_type: docTypeId });
        setQuality(res);
      } catch {
        // 품질 평가는 부가 기능 — 실패 시 조용히 생략 (생성 본문은 유효).
        setQuality(null);
      } finally {
        setQualityLoading(false);
      }
    },
    [docTypeId],
  );

  // ── SSE 스트리밍 (데스크탑과 동일: useSSE + stream-v2) ──
  const sse = useSSE({
    onToken: (chunk) => setOutput((prev) => prev + chunk),
    onDone: () => {
      if (ranAutoRef.current) return;
      ranAutoRef.current = true;
      // onDone 시점의 최신 output 을 scrollRef 가 아닌 state 로 읽기 위해 setOutput 콜백 사용.
      setOutput((finalText) => {
        void scoreNow(finalText);
        return finalText;
      });
    },
    onError: (msg) => {
      setOutput((prev) => {
        if (!prev) {
          setErr(`생성 실패: ${msg} — 모델/네트워크를 확인하고 다시 시도해 주세요.`);
        }
        return prev;
      });
    },
  });

  const isStreaming = sse.isStreaming;

  const onGenerate = useCallback(() => {
    if (isStreaming) return;
    setErr(null);
    setQuality(null);
    setOutput('');
    ranAutoRef.current = false;

    const tone = TONES.find((t) => t.id === toneId)?.ko ?? toneId;

    // 데스크탑 buildStreamV2Request 와 동일 페이로드. URL 은 apiUrl() 로 정규화
    // (AJINMobileChat 의 buildChatUrl 패턴과 일치 — VITE_API_BASE_URL 환경에서도 안전).
    const url = apiUrl('/api/draft/stream-v2');
    const body = {
      doc_type: docTypeKo || 'general',
      tone,
      meta: {},
      user_request: userRequest,
      language: 'ko' as const,
      context: category,
      // provider/model 미지정 → 백엔드 LLMRouter 가 default 선택 (모바일은 셀렉터 생략).
      render_template: true,
    };

    void sse.start({ url, body }).catch((e) => {
      setErr(
        `생성 시작 실패: ${e instanceof Error ? e.message : String(e)} — 백엔드 상태를 확인해 주세요.`,
      );
    });

    // 결과 영역으로 스크롤
    setTimeout(() => outputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60);
  }, [isStreaming, toneId, docTypeKo, userRequest, category, sse]);

  const onCancel = useCallback(() => {
    sse.stop();
  }, [sse]);

  // ── 복사 ────────────────────────────────────────────────
  const onCopy = useCallback(async () => {
    if (!output) return;
    try {
      await navigator.clipboard.writeText(output);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setDownloadErr('클립보드 복사 실패 — 브라우저 권한을 확인해 주세요.');
    }
  }, [output]);

  // ── 다운로드 (POST /draft/export → blob → 브라우저 다운로드) ──
  const onDownload = useCallback(
    async (fmt: ExportFormat) => {
      if (!output || downloadingFmt) return;
      setDownloadErr(null);
      setDownloadingFmt(fmt);
      try {
        const basename = `draft_${docTypeId || 'general'}_${new Date()
          .toISOString()
          .slice(0, 10)}`;
        const ext = fmt === 'hwpx' ? 'hwpx' : fmt;
        await exportAndDownload(output, fmt, docTypeId || 'general', `${basename}.${ext}`);
      } catch (e) {
        setDownloadErr(
          `다운로드 실패 (${fmt.toUpperCase()}): ${e instanceof Error ? e.message : String(e)}`,
        );
      } finally {
        setDownloadingFmt(null);
      }
    },
    [output, downloadingFmt, docTypeId],
  );

  const canGenerate = userRequest.trim().length > 0 && !isStreaming;
  const status = isStreaming ? '스트리밍 중' : output ? '완료' : '대기';

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div
          className="aj-scroll"
          style={{
            position: 'relative',
            zIndex: 3,
            minHeight: '100vh',
            paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 120px)',
          }}
        >
          {/* ── Top bar ── */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '14px 16px 4px',
            }}
          >
            <button
              type="button"
              onClick={() => navigate(-1)}
              aria-label="뒤로"
              style={{
                width: 36,
                height: 36,
                borderRadius: 999,
                background: 'transparent',
                border: '1px solid rgba(127,127,127,0.25)',
                color: 'var(--hud-text)',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <ChevronLeft size={18} aria-hidden />
            </button>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                className="aj-mono"
                style={{ fontSize: 10, opacity: 0.6, letterSpacing: '0.12em' }}
              >
                DOCUMENT DRAFT · MODULE B
              </div>
              <div style={{ fontSize: 15, fontWeight: 700, marginTop: 2 }}>문서 작성</div>
            </div>
            <span
              className="aj-chip"
              style={{
                fontSize: 10,
                padding: '4px 9px',
                background: isStreaming ? 'rgba(252,177,50,0.18)' : 'rgba(79,183,116,0.18)',
                border: `1px solid ${isStreaming ? 'rgba(252,177,50,0.4)' : 'rgba(79,183,116,0.4)'}`,
                color: 'inherit',
              }}
            >
              {isStreaming ? 'STREAMING' : 'READY'}
            </span>
          </div>

          {/* ── Hero ── */}
          <div style={{ padding: '10px 16px 4px' }}>
            <h1
              style={{
                margin: '4px 0',
                fontSize: 26,
                fontWeight: 700,
                letterSpacing: '-0.018em',
                lineHeight: 1.15,
              }}
            >
              무엇을 <span style={{ color: GOLD }}>작성</span>할까요?
            </h1>
            <div style={{ fontSize: 13, opacity: 0.65, lineHeight: 1.45 }}>
              이메일·보고서·8D·PPAP·신청서 등 14종 사내 문서를 AI가 초안 작성합니다.
            </div>
          </div>

          {/* ── 1. 카테고리 토글 ── */}
          <div style={{ padding: '14px 16px 0' }}>
            <div
              className="aj-mono"
              style={{ fontSize: 10, opacity: 0.55, marginBottom: 8, letterSpacing: '0.1em' }}
            >
              CATEGORY · 문서 분류
            </div>
            <div
              style={{
                display: 'flex',
                gap: 6,
                padding: 4,
                borderRadius: 999,
                background: 'var(--hud-surface-2)',
                border: '1px solid var(--hud-border-light)',
              }}
            >
              {CATEGORIES.map((c) => {
                const on = category === c.k;
                return (
                  <button
                    key={c.k}
                    type="button"
                    onClick={() => {
                      setCategory(c.k);
                      // 카테고리 전환 시 해당 분류 첫 문서로 docType 재설정
                      const first = DOC_TYPES.find((d) => d.category === c.k);
                      if (first) setDocTypeId(first.id);
                    }}
                    aria-pressed={on}
                    style={{
                      flex: 1,
                      padding: '8px 0',
                      borderRadius: 999,
                      border: 0,
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      fontSize: 13,
                      fontWeight: 700,
                      background: on ? GOLD : 'transparent',
                      color: on ? '#1A1004' : 'var(--hud-text)',
                      transition: 'background 180ms ease, color 180ms ease',
                    }}
                  >
                    {c.ko}
                    <span
                      style={{
                        fontSize: 9,
                        opacity: 0.6,
                        marginLeft: 6,
                        fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                      }}
                    >
                      {c.en}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── 2. 문서 유형 칩 그리드 ── */}
          <div style={{ padding: '16px 16px 0' }}>
            <div
              className="aj-mono"
              style={{ fontSize: 10, opacity: 0.55, marginBottom: 8, letterSpacing: '0.1em' }}
            >
              TEMPLATE · 문서 유형 ({filteredDocTypes.length}종)
            </div>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: 8,
              }}
            >
              {filteredDocTypes.map((d) => {
                const on = d.id === docTypeId;
                return (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => setDocTypeId(d.id)}
                    aria-pressed={on}
                    className="aj-glass"
                    style={{
                      padding: '12px 12px',
                      borderRadius: 14,
                      textAlign: 'left',
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      color: 'var(--hud-text)',
                      border: on
                        ? `1px solid ${GOLD}`
                        : '1px solid var(--hud-border-light)',
                      boxShadow: on
                        ? '0 8px 22px -12px rgba(252,177,50,0.6)'
                        : 'none',
                      transition: 'border-color 180ms ease, box-shadow 180ms ease',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: 999,
                          flexShrink: 0,
                          background: on ? GOLD : 'rgba(127,127,127,0.4)',
                        }}
                      />
                      <span style={{ fontSize: 14, fontWeight: 600 }}>{d.name_ko}</span>
                    </div>
                    <div
                      className="aj-mono"
                      style={{ fontSize: 9, opacity: 0.45, marginTop: 4, paddingLeft: 12 }}
                    >
                      {d.name_en}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── 3. 어조 + 4. 주제 입력 ── */}
          <div style={{ padding: '18px 16px 0' }}>
            <div
              className="aj-mono"
              style={{ fontSize: 10, opacity: 0.55, marginBottom: 8, letterSpacing: '0.1em' }}
            >
              REQUEST · 작성 요청
            </div>

            {/* 어조 — 가로 스크롤 칩 */}
            <div
              style={{
                display: 'flex',
                gap: 6,
                overflowX: 'auto',
                paddingBottom: 4,
                marginBottom: 10,
                WebkitOverflowScrolling: 'touch',
              }}
            >
              {TONES.map((t) => {
                const on = t.id === toneId;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setToneId(t.id)}
                    aria-pressed={on}
                    style={{
                      flexShrink: 0,
                      padding: '6px 14px',
                      borderRadius: 999,
                      cursor: 'pointer',
                      fontFamily: 'inherit',
                      fontSize: 12,
                      fontWeight: 600,
                      whiteSpace: 'nowrap',
                      background: on ? 'var(--hud-primary-dim)' : 'var(--hud-surface-2)',
                      border: `1px solid ${on ? 'rgba(252,177,50,0.5)' : 'var(--hud-border-light)'}`,
                      color: on ? GOLD : 'var(--hud-text)',
                    }}
                  >
                    {t.ko}
                  </button>
                );
              })}
            </div>

            {/* 주제 textarea */}
            <div
              className="aj-glass"
              style={{ padding: '4px 4px', borderRadius: 16, marginBottom: 10 }}
            >
              <textarea
                value={userRequest}
                onChange={(e) => setUserRequest(e.target.value)}
                rows={3}
                placeholder="예: 현대차 SQ팀에 PPAP Level 3 제출 안내 / 이번 주 진행 현황 요약"
                style={{
                  width: '100%',
                  background: 'transparent',
                  border: 0,
                  outline: 0,
                  resize: 'vertical',
                  minHeight: 64,
                  maxHeight: 200,
                  padding: '10px 12px',
                  color: 'var(--hud-text)',
                  fontFamily: 'inherit',
                  fontSize: 15,
                  lineHeight: 1.55,
                }}
              />
            </div>

            {/* 생성 / 중단 버튼 */}
            {isStreaming ? (
              <button
                type="button"
                onClick={onCancel}
                style={{
                  width: '100%',
                  minHeight: 50,
                  borderRadius: 14,
                  border: '1px solid rgba(127,127,127,0.3)',
                  background: 'var(--hud-surface-2)',
                  color: 'var(--hud-text)',
                  fontFamily: 'inherit',
                  fontSize: 15,
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                }}
              >
                <Square size={15} aria-hidden /> 생성 중단
              </button>
            ) : (
              <button
                type="button"
                onClick={onGenerate}
                disabled={!canGenerate}
                style={{
                  width: '100%',
                  minHeight: 50,
                  borderRadius: 14,
                  border: `1px solid ${canGenerate ? 'rgba(252,177,50,0.5)' : 'var(--hud-border-light)'}`,
                  background: canGenerate ? GOLD : 'var(--hud-surface-2)',
                  color: canGenerate ? '#1A1004' : 'var(--hud-text-dim)',
                  fontFamily: 'inherit',
                  fontSize: 15,
                  fontWeight: 700,
                  letterSpacing: '0.01em',
                  cursor: canGenerate ? 'pointer' : 'not-allowed',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  boxShadow: canGenerate ? '0 10px 26px -10px rgba(252,177,50,0.6)' : 'none',
                  transition: 'background 180ms ease, box-shadow 180ms ease',
                }}
              >
                <Sparkles size={16} aria-hidden />
                {docTypeKo} 초안 생성
              </button>
            )}

            {/* 생성 오류 */}
            {err && (
              <div
                className="aj-glass"
                style={{
                  marginTop: 12,
                  padding: '10px 12px',
                  borderRadius: 12,
                  fontSize: 12,
                  lineHeight: 1.5,
                  color: '#FF7565',
                  border: '1px solid rgba(255,117,101,0.35)',
                }}
              >
                {err}
              </div>
            )}
          </div>

          {/* ── 5. 출력 ── */}
          <div ref={outputRef} style={{ padding: '20px 16px 0', scrollMarginTop: 12 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 8,
              }}
            >
              <div
                className="aj-mono"
                style={{ fontSize: 10, opacity: 0.55, letterSpacing: '0.1em' }}
              >
                OUTPUT · 생성 결과
              </div>
              <span
                className="aj-mono"
                style={{
                  fontSize: 10,
                  opacity: 0.6,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                }}
              >
                {isStreaming && (
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: 999,
                      background: GOLD,
                      animation: 'aj-draft-pulse 1s ease-in-out infinite',
                    }}
                  />
                )}
                {status}
              </span>
            </div>

            <div
              className="aj-glass"
              style={{
                borderRadius: 16,
                padding: '14px 14px',
                minHeight: 140,
              }}
            >
              {output ? (
                <div
                  style={{
                    fontSize: 14,
                    lineHeight: 1.65,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: 'var(--hud-text)',
                  }}
                >
                  {output}
                  {isStreaming && (
                    <span
                      aria-hidden
                      style={{
                        display: 'inline-block',
                        width: 8,
                        height: '1.05em',
                        marginLeft: 2,
                        verticalAlign: 'text-bottom',
                        background: GOLD,
                        animation: 'aj-draft-blink 1s steps(2, start) infinite',
                      }}
                    />
                  )}
                </div>
              ) : isStreaming ? (
                <div style={{ fontSize: 13, opacity: 0.6, color: 'var(--hud-text)' }}>
                  AI가 사내 SOP·용어집·과거 이력을 참고해 초안을 작성하고 있습니다…
                </div>
              ) : (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    minHeight: 110,
                    textAlign: 'center',
                    opacity: 0.55,
                  }}
                >
                  <FileText size={26} aria-hidden style={{ opacity: 0.7 }} />
                  <div style={{ fontSize: 13, color: 'var(--hud-text)' }}>
                    문서 유형을 고르고 주제를 입력한 뒤<br />
                    초안 생성을 눌러주세요.
                  </div>
                </div>
              )}
            </div>

            {/* ── 6. 액션: 복사 + 다운로드 (output 완료 시) ── */}
            {output && !isStreaming && (
              <>
                <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => void onCopy()}
                    style={{
                      flex: '1 1 100%',
                      minHeight: 44,
                      borderRadius: 12,
                      border: '1px solid var(--hud-border-light)',
                      background: 'var(--hud-surface-2)',
                      color: 'var(--hud-text)',
                      fontFamily: 'inherit',
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                    }}
                  >
                    {copied ? (
                      <>
                        <Check size={15} aria-hidden style={{ color: '#4FB774' }} /> 복사됨
                      </>
                    ) : (
                      <>
                        <Copy size={15} aria-hidden /> 본문 복사
                      </>
                    )}
                  </button>
                  {DOWNLOAD_FORMATS.map(({ fmt, label }) => {
                    const busy = downloadingFmt === fmt;
                    return (
                      <button
                        key={fmt}
                        type="button"
                        onClick={() => void onDownload(fmt)}
                        disabled={!!downloadingFmt}
                        style={{
                          flex: '1 1 0',
                          minWidth: 0,
                          minHeight: 44,
                          borderRadius: 12,
                          border: '1px solid rgba(252,177,50,0.4)',
                          background: 'var(--hud-primary-dim)',
                          color: GOLD,
                          fontFamily: 'inherit',
                          fontSize: 12,
                          fontWeight: 700,
                          cursor: downloadingFmt ? 'wait' : 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: 5,
                          opacity: downloadingFmt && !busy ? 0.5 : 1,
                        }}
                      >
                        <Download size={14} aria-hidden />
                        {busy ? '…' : label}
                      </button>
                    );
                  })}
                </div>

                {downloadErr && (
                  <div
                    style={{
                      marginTop: 8,
                      fontSize: 11,
                      lineHeight: 1.5,
                      color: '#FF7565',
                      fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                    }}
                  >
                    {downloadErr}
                  </div>
                )}
              </>
            )}
          </div>

          {/* ── 품질 평가 (완료 후 자동) — 컴팩트 ── */}
          {output && !isStreaming && (qualityLoading || quality) && (
            <div style={{ padding: '16px 16px 0' }}>
              <div
                className="aj-mono"
                style={{ fontSize: 10, opacity: 0.55, marginBottom: 8, letterSpacing: '0.1em' }}
              >
                QUALITY · 품질 평가
              </div>
              <div className="aj-glass" style={{ borderRadius: 16, padding: '14px 16px' }}>
                {qualityLoading && !quality ? (
                  <div style={{ fontSize: 13, opacity: 0.6, color: 'var(--hud-text)' }}>
                    품질 평가 중…
                  </div>
                ) : quality ? (
                  <>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'baseline',
                        gap: 10,
                        marginBottom: 12,
                      }}
                    >
                      <div
                        style={{
                          fontSize: 32,
                          fontWeight: 700,
                          lineHeight: 1,
                          color: 'var(--hud-text)',
                          animation: 'aj-draft-rise 320ms ease-out',
                        }}
                      >
                        {Math.round(quality.total_score)}
                        <span style={{ fontSize: 14, opacity: 0.5, fontWeight: 500 }}>/100</span>
                      </div>
                      <span
                        className="aj-chip"
                        style={{
                          fontSize: 13,
                          fontWeight: 700,
                          padding: '3px 12px',
                          background: 'rgba(252,177,50,0.18)',
                          border: '1px solid rgba(252,177,50,0.4)',
                          color: GOLD,
                          animation: 'aj-draft-rise 320ms ease-out',
                        }}
                      >
                        {quality.grade}
                      </span>
                    </div>

                    {/* 5기준 바 — 데스크탑 QUALITY_CRITERIA 와 동일 매핑 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {(
                        [
                          { ko: '구조', key: 'structure', maxKey: 'structure_max' },
                          { ko: '분량', key: 'length', maxKey: 'length_max' },
                          { ko: '전문성', key: 'terminology', maxKey: 'terminology_max' },
                          { ko: '완성도', key: 'completeness', maxKey: 'completeness_max' },
                          { ko: '톤', key: 'tone', maxKey: 'tone_max' },
                        ] as const
                      ).map((c) => {
                        const sc = Math.round(
                          (quality.scores[c.key] as number) ?? 0,
                        );
                        const mx = (quality.scores[c.maxKey] as number) || 1;
                        const pct = Math.max(0, Math.min(100, (sc / mx) * 100));
                        return (
                          <div
                            key={c.key}
                            style={{ display: 'flex', alignItems: 'center', gap: 10 }}
                          >
                            <span
                              style={{
                                fontSize: 12,
                                width: 44,
                                flexShrink: 0,
                                color: 'var(--hud-text)',
                              }}
                            >
                              {c.ko}
                            </span>
                            <div
                              style={{
                                flex: 1,
                                height: 6,
                                borderRadius: 999,
                                background: 'var(--hud-surface-2)',
                                overflow: 'hidden',
                              }}
                            >
                              <span
                                style={{
                                  display: 'block',
                                  height: '100%',
                                  width: `${pct}%`,
                                  borderRadius: 999,
                                  background: GOLD,
                                  transition: 'width 420ms cubic-bezier(0.22,1,0.36,1)',
                                }}
                              />
                            </div>
                            <span
                              className="aj-mono"
                              style={{
                                fontSize: 11,
                                opacity: 0.7,
                                width: 40,
                                textAlign: 'right',
                                flexShrink: 0,
                                color: 'var(--hud-text)',
                              }}
                            >
                              {sc}/{mx}
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    {quality.improvements?.length > 0 && (
                      <div
                        style={{
                          marginTop: 12,
                          fontSize: 12,
                          lineHeight: 1.5,
                          opacity: 0.75,
                          color: 'var(--hud-text)',
                        }}
                      >
                        개선: {quality.improvements.slice(0, 2).join(' · ')}
                      </div>
                    )}
                  </>
                ) : null}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 컴포넌트 로컬 키프레임 (단일 파일 self-contained) */}
      <style>{`
        @keyframes aj-draft-blink { 0%, 50% { opacity: 1; } 50.01%, 100% { opacity: 0; } }
        @keyframes aj-draft-pulse { 0%, 100% { opacity: 0.4; transform: scale(0.85); } 50% { opacity: 1; transform: scale(1); } }
        @keyframes aj-draft-rise { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}

export default AJINMobileDraft;
