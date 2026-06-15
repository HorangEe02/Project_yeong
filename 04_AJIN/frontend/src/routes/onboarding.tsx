// onboarding.tsx — Feature C (신입 가이드) 독립 라우트.
// search.tsx 의 OnboardingSidePanel 을 임베드하고, 미사용 백엔드 API 6 종을 활성화한다.
// 섹션: 1) 사수·체크리스트·FAQ  2) SOP 학습 그리드  3) 부서별 빠른 질문
//       4) 협업 시나리오 매칭     5) 도면/이미지 Vision Q&A

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  BookOpen,
  MessagesSquare,
  Image as ImageIcon,
  Workflow,
  ChevronRight,
} from 'lucide-react';

import { useAuthStore } from '@store/auth';
import { OnboardingSidePanel } from '@components/search/OnboardingSidePanel';
import {
  fetchSopList,
  fetchSopQuiz,
  type SopSummary,
  type SopQuizQuestion,
} from '@api/sop';
import { matchScenario, type ScenarioCard } from '@api/scenarios';
import {
  prepareVisionAttachment,
  buildVisionUrl,
} from '@api/vision';
import { authHeaders, ONBOARDING_BASE } from '@api/onboarding';
import { addDrawingCaption } from '@api/drawings';
import { isVisionVisible, getDeptCardKeys } from '@lib/deptGroups';
import { useFeatureCFlags } from '@lib/featureFlags';
import { useIsMobile } from '@hooks/useBreakpoint';
import { AJINMobileOnboarding } from '@components/uikit/AJINMobileOnboarding';
// Feature C Sprint 1 P0 (plan §28): 9 mock UI 카드 폐기.
// 'sales' | 'hr' | 'finance' | 'it' | 'procurement' | 'legal' | 'rnd' | 'shopfloor' | 'safety'
// 카드는 endpoint 0건 + hardcoded mock data 만 보유했으므로 폐기.
// 15 vision/document 컴포넌트는 그대로 유지 (모두 /vision/* + /document/* endpoint 동작).
// 부록 K Phase 1 — 부서별 Vision 카드 5개
import { BusinessCardOCR } from '@components/onboarding/BusinessCardOCR';
import { RFQScanner } from '@components/onboarding/RFQScanner';
import { DefectPhotoAnalyzer } from '@components/onboarding/DefectPhotoAnalyzer';
import { MSDSLabelOCR } from '@components/onboarding/MSDSLabelOCR';
import { ReceiptOCR } from '@components/onboarding/ReceiptOCR';
// 부록 K Phase 2 (5)
import { ContractAnalyzer } from '@components/onboarding/ContractAnalyzer';
import { ResumeAnalyzer } from '@components/onboarding/ResumeAnalyzer';
import { POScanner } from '@components/onboarding/POScanner';
import { FinancialStatementAnalyzer } from '@components/onboarding/FinancialStatementAnalyzer';
import { IncidentSceneAnalyzer } from '@components/onboarding/IncidentSceneAnalyzer';
// 부록 K Phase 3 (6)
import { CADStandardVerifier } from '@components/onboarding/CADStandardVerifier';
import { FiveSScorer } from '@components/onboarding/FiveSScorer';
import { ErrorLogAnalyzer } from '@components/onboarding/ErrorLogAnalyzer';
import { ESGReportAnalyzer } from '@components/onboarding/ESGReportAnalyzer';
import { InventoryReceiveScanner } from '@components/onboarding/InventoryReceiveScanner';
import { CertificateOCR } from '@components/onboarding/CertificateOCR';

// ──────────────────────────────────────────────────────────────
// Page
// ──────────────────────────────────────────────────────────────
export function Onboarding() {
  const user = useAuthStore((s) => s.user);
  const featureCFlags = useFeatureCFlags();
  const isMobile = useIsMobile();

  if (!user) {
    return (
      <div style={{ padding: 24 }}>
        <div className="lg-card">
          <div className="lg-state-pill crit">로그인 필요</div>
        </div>
      </div>
    );
  }

  if (isMobile) return <AJINMobileOnboarding />;

  return (
    <div className="page lg-page" data-screen-label="C · Onboarding">
      <div className="lg-card-h" style={{ marginBottom: 18 }}>
        <div>
          <div className="lg-pill">FEATURE C · ONBOARDING</div>
          <h1 style={{ marginTop: 6, fontSize: 24, fontWeight: 700, letterSpacing: '-0.01em' }}>
            신입 가이드
          </h1>
          <div style={{ fontSize: 13, color: 'var(--hud-text-dim)', marginTop: 4 }}>
            사수 · 체크리스트 · SOP 학습 · 협업 시나리오 · 도면 Q&amp;A — 첫 주 적응을 위한 통합 화면
          </div>
        </div>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) 360px',
          gap: 18,
          alignItems: 'start',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <SopLearningSection />
          <QuickQuestionsSection />
          <ScenarioMatchSection />

          {/* JP1~JP3 — 부서 적응형 카드 */}
          {featureCFlags.analyzers_enabled && (() => {
            const dept = user.department ?? '';
            const cards = getDeptCardKeys(dept);
            return (
              <>
                {/* Feature C Sprint 1 P0 (plan §28): 9 mock UI 카드 폐기
                    'sales'|'hr'|'finance'|'it'|'procurement'|'legal'|'rnd'|'shopfloor'|'safety'
                    카드는 endpoint 0건이라 폐기. 15 vision/document 카드는 그대로 유지. */}

                {/* 부록 K Phase 1 — Vision 카드 5개 */}
                {cards.includes('business-card') && <BusinessCardOCR department={dept} />}
                {cards.includes('rfq') && <RFQScanner department={dept} />}
                {cards.includes('defect') && <DefectPhotoAnalyzer department={dept} />}
                {cards.includes('msds-ocr') && <MSDSLabelOCR department={dept} />}
                {cards.includes('receipt') && <ReceiptOCR department={dept} />}

                {/* 부록 K Phase 2 (5) */}
                {cards.includes('contract') && <ContractAnalyzer department={dept} />}
                {cards.includes('resume') && <ResumeAnalyzer department={dept} />}
                {cards.includes('po') && <POScanner department={dept} />}
                {cards.includes('financial-statement') && <FinancialStatementAnalyzer department={dept} />}
                {cards.includes('incident') && <IncidentSceneAnalyzer department={dept} />}

                {/* 부록 K Phase 3 (6) */}
                {cards.includes('cad-verify') && <CADStandardVerifier department={dept} />}
                {cards.includes('5s') && <FiveSScorer department={dept} />}
                {cards.includes('error-log') && <ErrorLogAnalyzer department={dept} />}
                {cards.includes('esg') && <ESGReportAnalyzer department={dept} />}
                {cards.includes('inventory-receive') && <InventoryReceiveScanner department={dept} />}
                {cards.includes('certificate') && <CertificateOCR department={dept} />}
              </>
            );
          })()}

          {/* JP1 — Vision Q&A: G1/G2/G5 (품질·생산기술·R&D) 만 노출 */}
          {isVisionVisible(user.department ?? '') && (
            <VisionUploadSection department={user.department} />
          )}
        </div>

        <div style={{ position: 'sticky', top: 16 }}>
          <OnboardingSidePanel forceVisible />
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Section 1 — SOP 학습 그리드 + 자동 퀴즈 모달
// ──────────────────────────────────────────────────────────────
function SopLearningSection() {
  const [items, setItems] = useState<SopSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [quizOpen, setQuizOpen] = useState<SopSummary | null>(null);

  useEffect(() => {
    let active = true;
    fetchSopList()
      .then((res) => {
        if (!active) return;
        setItems(res.items ?? []);
      })
      .catch((e: unknown) => {
        if (!active) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <SectionHeader
        icon={<BookOpen size={16} />}
        eyebrow="SOP LIBRARY"
        title="SOP 학습 그리드"
        subtitle="8종 표준 절차 — 각 항목 클릭 시 자동 생성 4지선다 퀴즈"
      />

      {loading && <SkeletonRow />}
      {error && <ErrorBanner message={error} />}
      {!loading && !error && items.length === 0 && (
        <EmptyHint text="등록된 SOP 가 없습니다." />
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: 12,
          marginTop: 14,
        }}
      >
        {items.map((it) => (
          <button
            key={it.sop_id}
            onClick={() => setQuizOpen(it)}
            className="lg-card"
            style={{
              padding: 14,
              textAlign: 'left',
              background: 'var(--hud-surface-2)',
              border: '1px solid color-mix(in oklab, var(--hud-primary) 30%, transparent)',
              color: 'var(--hud-text)',
              cursor: 'pointer',
              transition: 'transform 120ms ease, border-color 120ms ease',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(-2px)';
              (e.currentTarget as HTMLButtonElement).style.borderColor =
                'color-mix(in oklab, var(--hud-primary) 60%, transparent)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.transform = 'translateY(0)';
              (e.currentTarget as HTMLButtonElement).style.borderColor =
                'color-mix(in oklab, var(--hud-primary) 30%, transparent)';
            }}
          >
            <div style={{ fontSize: 10, opacity: 0.6, letterSpacing: '0.04em' }}>
              {it.category.toUpperCase()} · {it.department}
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>{it.title}</div>
            <div style={{ fontSize: 11, opacity: 0.55, marginTop: 6 }}>
              {it.steps_count} steps · 클릭하여 퀴즈 풀기 →
            </div>
          </button>
        ))}
      </div>

      {quizOpen && (
        <QuizModal
          sop={quizOpen}
          onClose={() => setQuizOpen(null)}
        />
      )}
    </section>
  );
}

function QuizModal({ sop, onClose }: { sop: SopSummary; onClose: () => void }) {
  const [questions, setQuestions] = useState<SopQuizQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    let active = true;
    fetchSopQuiz(sop.sop_id, 3)
      .then((r) => active && setQuestions(r.questions ?? []))
      .catch((e: unknown) =>
        active && setError(e instanceof Error ? e.message : String(e)),
      )
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [sop.sop_id]);

  const score = useMemo(() => {
    if (!submitted) return null;
    let s = 0;
    questions.forEach((q, idx) => {
      if (answers[idx] === q.correct_index) s += 1;
    });
    return { correct: s, total: questions.length };
  }, [submitted, answers, questions]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'color-mix(in oklab, var(--hud-bg) 70%, black)',
        zIndex: 999,
        display: 'grid',
        placeItems: 'center',
        padding: 16,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="lg-card"
        style={{ padding: 24, maxWidth: 640, width: '100%', maxHeight: '85vh', overflow: 'auto' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <div style={{ fontSize: 10, opacity: 0.6 }}>SOP QUIZ · {sop.sop_id}</div>
            <h2 style={{ margin: '4px 0 0', fontSize: 18, fontWeight: 700 }}>{sop.title}</h2>
          </div>
          <button onClick={onClose} className="lg-btn" style={{ padding: '6px 12px' }}>
            닫기
          </button>
        </div>

        {loading && <SkeletonRow />}
        {error && <ErrorBanner message={error} />}

        {!loading && !error && questions.length === 0 && (
          <EmptyHint text="이 SOP에서 출제 가능한 퀴즈가 없습니다." />
        )}

        <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 18 }}>
          {questions.map((q, idx) => {
            const selected = answers[idx];
            return (
              <div key={idx}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>
                  Q{idx + 1}. {q.question}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                  {q.options.map((opt, oi) => {
                    const isCorrect = submitted && oi === q.correct_index;
                    const isWrong = submitted && selected === oi && oi !== q.correct_index;
                    return (
                      <label
                        key={oi}
                        style={{
                          display: 'flex',
                          gap: 8,
                          padding: '8px 10px',
                          border: '1px solid var(--hud-border)',
                          borderRadius: 8,
                          cursor: submitted ? 'default' : 'pointer',
                          background: isCorrect
                            ? 'color-mix(in oklab, #16a34a 18%, transparent)'
                            : isWrong
                              ? 'color-mix(in oklab, #dc2626 14%, transparent)'
                              : 'transparent',
                        }}
                      >
                        <input
                          type="radio"
                          name={`q-${idx}`}
                          checked={selected === oi}
                          disabled={submitted}
                          onChange={() => setAnswers((p) => ({ ...p, [idx]: oi }))}
                        />
                        <span style={{ fontSize: 12 }}>{opt}</span>
                      </label>
                    );
                  })}
                </div>
                {submitted && (
                  <div style={{ fontSize: 11, opacity: 0.7, marginTop: 6, paddingLeft: 10 }}>
                    💡 {q.explanation}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {questions.length > 0 && (
          <div style={{ marginTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            {score ? (
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                결과: {score.correct} / {score.total} 정답
              </div>
            ) : (
              <div style={{ fontSize: 11, opacity: 0.6 }}>모든 문항에 답한 후 제출하세요.</div>
            )}
            <button
              className="lg-btn primary"
              disabled={
                submitted ||
                questions.some((_, idx) => answers[idx] === undefined)
              }
              onClick={() => setSubmitted(true)}
              style={{ padding: '8px 18px' }}
            >
              {submitted ? '제출 완료' : '제출'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Section 2 — 부서별 빠른 질문 (backend /onboarding/quick-questions)
// ──────────────────────────────────────────────────────────────
interface QuickQuestionItem {
  question: string;
  category?: string;
}
interface QuickQuestionsResponse {
  questions: QuickQuestionItem[];
  department?: string;
}

function QuickQuestionsSection() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const [data, setData] = useState<QuickQuestionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const dept = user?.department ? `?department=${encodeURIComponent(user.department)}` : '';
    fetch(`${ONBOARDING_BASE}/quick-questions${dept}`, { headers: authHeaders() })
      .then(async (r) => {
        if (!r.ok) throw new Error(`status ${r.status}`);
        return (await r.json()) as QuickQuestionsResponse;
      })
      .then((j) => active && setData(j))
      .catch((e: unknown) =>
        active && setError(e instanceof Error ? e.message : String(e)),
      )
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [user?.department]);

  const onPick = (q: string) => {
    // /chat 라우트로 prefill 이동 (chat.tsx 가 location.state.prefill 을 읽도록)
    navigate('/chat', { state: { prefill: q } });
  };

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <SectionHeader
        icon={<MessagesSquare size={16} />}
        eyebrow="QUICK QUESTIONS"
        title={`${user?.department ?? '부서'} 빠른 질문`}
        subtitle="자주 묻는 질문 6개 — 클릭 시 AI 도우미로 prefill 이동"
      />

      {loading && <SkeletonRow />}
      {error && <ErrorBanner message={error} />}
      {!loading && !error && !data?.questions?.length && (
        <EmptyHint text="질문 목록을 불러올 수 없습니다." />
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14 }}>
        {data?.questions?.map((q, i) => (
          <button
            key={i}
            onClick={() => onPick(q.question)}
            style={{
              padding: '8px 14px',
              borderRadius: 999,
              border: '1px solid var(--hud-border)',
              background: 'var(--hud-surface-2)',
              color: 'var(--hud-text)',
              fontSize: 12,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            {q.question}
            <ChevronRight size={12} />
          </button>
        ))}
      </div>
    </section>
  );
}

// ──────────────────────────────────────────────────────────────
// Section 3 — 협업 시나리오 매칭
// ──────────────────────────────────────────────────────────────
function ScenarioMatchSection() {
  const [query, setQuery] = useState('');
  const [card, setCard] = useState<ScenarioCard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tried, setTried] = useState(false);

  const onMatch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setCard(null);
    setTried(true);
    try {
      const res = await matchScenario(query.trim());
      setCard(res.card);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <SectionHeader
        icon={<Workflow size={16} />}
        eyebrow="SCENARIO MATCH"
        title="협업 시나리오 매칭"
        subtitle="“PPAP 제출 요청 받았어요” 같이 상황을 입력 → 절차 카드 즉시 응답 (LLM 호출 0)"
      />

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onMatch()}
          placeholder="예: 고객사가 8D 보고서를 요청했어요"
          style={{
            flex: 1,
            padding: '10px 14px',
            borderRadius: 8,
            border: '1px solid var(--hud-border)',
            background: 'var(--hud-surface-2)',
            fontSize: 13,
            color: 'var(--hud-text)',
          }}
        />
        <button
          className="lg-btn primary"
          disabled={loading || !query.trim()}
          onClick={onMatch}
          style={{ padding: '0 18px' }}
        >
          {loading ? '매칭 중…' : '매칭'}
        </button>
      </div>

      {error && <div style={{ marginTop: 12 }}><ErrorBanner message={error} /></div>}

      {tried && !loading && !card && !error && (
        <div style={{ marginTop: 14, fontSize: 12, opacity: 0.65 }}>
          매칭된 시나리오가 없습니다. 다른 키워드(예: PPAP, ECN, 클레임)로 시도해 보세요.
        </div>
      )}

      {card && (
        <div
          style={{
            marginTop: 14,
            padding: 16,
            borderRadius: 12,
            border: '1px solid color-mix(in oklab, var(--hud-primary) 35%, transparent)',
            background: 'color-mix(in oklab, var(--hud-primary) 6%, transparent)',
          }}
        >
          <div style={{ fontSize: 10, opacity: 0.6 }}>
            SCENARIO · {card.scenario_id} · 요청 부서: {card.requesting_dept || '—'}
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, marginTop: 4 }}>
            {card.situation}
          </div>

          {card.my_actions?.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 600, opacity: 0.7, marginBottom: 4 }}>
                내가 할 일
              </div>
              <ol style={{ margin: 0, paddingLeft: 20, fontSize: 12, lineHeight: 1.6 }}>
                {card.my_actions.map((a, i) => <li key={i}>{a}</li>)}
              </ol>
            </div>
          )}

          {(card.hand_off_to || card.hand_off_items?.length > 0) && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 600, opacity: 0.7, marginBottom: 4 }}>
                이관 — {card.hand_off_to || '—'}
              </div>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, lineHeight: 1.6 }}>
                {card.hand_off_items?.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </div>
          )}

          {card.tips?.length > 0 && (
            <div style={{ marginTop: 12, fontSize: 11, opacity: 0.7 }}>
              💡 {card.tips.join(' · ')}
            </div>
          )}

          {card.deadline_info && (
            <div style={{ marginTop: 8, fontSize: 11 }}>
              ⏰ {card.deadline_info}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// ──────────────────────────────────────────────────────────────
// Section 4 — 도면/이미지 Vision Q&A
// ──────────────────────────────────────────────────────────────
function VisionUploadSection({ department }: { department?: string }) {
  const user = useAuthStore((s) => s.user);
  const [file, setFile] = useState<File | null>(null);
  const [query, setQuery] = useState('이 부품/도면이 뭔지 설명해 주세요.');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [indexStatus, setIndexStatus] = useState<'idle' | 'saving' | 'saved' | 'failed'>('idle');
  const [indexedId, setIndexedId] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const onFile = (f: File | null) => {
    setError(null);
    setResponse('');
    setIndexStatus('idle');
    setIndexedId(null);
    if (!f) {
      setFile(null);
      return;
    }
    try {
      // 파일 검증은 prepareVisionAttachment 가 처리 (사이즈/MIME)
      setFile(f);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onSaveCaption = async () => {
    if (!response.trim() || !file) return;
    setIndexStatus('saving');
    try {
      const r = await addDrawingCaption({
        caption: response.trim(),
        keywords: query.trim(),
        department: department ?? '',
        uploader: user?.username ?? '',
        file_name: file.name,
        image_size: file.size,
        source_model: 'gemini-vision',
      });
      setIndexedId(r.id);
      setIndexStatus('saved');
    } catch {
      setIndexStatus('failed');
    }
  };

  const onSubmit = async () => {
    if (!file || !query.trim()) return;
    setLoading(true);
    setError(null);
    setResponse('');
    try {
      // Storage 업로드는 best-effort (Firebase Auth 미통합이면 skip)
      await prepareVisionAttachment(file);

      const fd = new FormData();
      fd.append('query', query.trim());
      if (department) fd.append('department', department);
      fd.append('file', file);

      const res = await fetch(buildVisionUrl(), {
        method: 'POST',
        headers: authHeaders(),
        body: fd,
      });
      if (!res.ok || !res.body) {
        throw new Error(`vision API ${res.status}`);
      }

      // SSE 스트림 파싱 (간이) — `data: <json>` 누적
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let acc = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const event = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          for (const line of event.split('\n')) {
            if (!line.startsWith('data:')) continue;
            const payload = line.slice(5).trim();
            if (!payload || payload === '[DONE]') continue;
            try {
              const j = JSON.parse(payload) as { delta?: string; text?: string };
              acc += j.delta ?? j.text ?? '';
              setResponse(acc);
            } catch {
              acc += payload;
              setResponse(acc);
            }
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="lg-card" style={{ padding: 20 }}>
      <SectionHeader
        icon={<ImageIcon size={16} />}
        eyebrow="DRAWING / IMAGE Q&A"
        title="도면 · 부품 사진 Q&A"
        subtitle="현장 부품/도면 사진을 올리면 Vision LLM 이 식별 + 설명"
      />

      <div
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = 'copy';
        }}
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files?.[0] ?? null;
          if (f) onFile(f);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        style={{
          marginTop: 14,
          padding: 24,
          borderRadius: 10,
          border: '2px dashed var(--hud-border-light)',
          textAlign: 'center',
          cursor: 'pointer',
          background: file
            ? 'color-mix(in oklab, var(--hud-primary) 6%, transparent)'
            : 'transparent',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
        <ImageIcon size={20} style={{ opacity: 0.6 }} />
        <div style={{ marginTop: 8, fontSize: 13 }}>
          {file ? file.name : '이미지를 드래그하거나 클릭하여 선택'}
        </div>
        <div style={{ marginTop: 4, fontSize: 10, opacity: 0.55 }}>
          PNG / JPG, 최대 5 MB
        </div>
      </div>

      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        rows={2}
        style={{
          marginTop: 12,
          width: '100%',
          padding: 10,
          borderRadius: 8,
          border: '1px solid var(--hud-border)',
          background: 'var(--hud-surface-2)',
          fontSize: 13,
          color: 'var(--hud-text)',
          resize: 'vertical',
        }}
      />

      <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 11, opacity: 0.6 }}>
          {department ? `부서 컨텍스트: ${department}` : '부서 정보 없음'}
        </div>
        <button
          className="lg-btn primary"
          disabled={loading || !file || !query.trim()}
          onClick={onSubmit}
          style={{ padding: '8px 18px' }}
        >
          {loading ? '분석 중…' : '질문하기'}
        </button>
      </div>

      {error && <div style={{ marginTop: 12 }}><ErrorBanner message={error} /></div>}

      {response && (
        <>
          <div
            style={{
              marginTop: 14,
              padding: 14,
              borderRadius: 10,
              border: '1px solid var(--hud-border)',
              background: 'var(--hud-surface-2)',
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
            }}
          >
            {response}
          </div>
          <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <div style={{ fontSize: 11, opacity: 0.65 }}>
              이 캡션을 도면 인덱스에 저장하면 “/search → 도면” 탭에서 재검색할 수 있습니다.
            </div>
            <button
              className="lg-btn"
              disabled={loading || indexStatus === 'saving' || indexStatus === 'saved'}
              onClick={onSaveCaption}
              style={{ padding: '8px 14px' }}
            >
              {indexStatus === 'saving'
                ? '저장 중…'
                : indexStatus === 'saved'
                  ? `저장됨 #${indexedId ?? ''}`
                  : indexStatus === 'failed'
                    ? '재시도'
                    : '도면 인덱스에 저장'}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

// ──────────────────────────────────────────────────────────────
// Shared UI bits
// ──────────────────────────────────────────────────────────────
function SectionHeader({
  icon, eyebrow, title, subtitle,
}: { icon: React.ReactNode; eyebrow: string; title: string; subtitle: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: 'color-mix(in oklab, var(--hud-primary) 14%, transparent)',
          color: 'var(--hud-primary)',
          display: 'grid',
          placeItems: 'center',
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 10, opacity: 0.55, letterSpacing: '0.06em' }}>
          <Sparkles size={10} style={{ verticalAlign: 'middle', marginRight: 4 }} />
          {eyebrow}
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, marginTop: 2 }}>{title}</div>
        <div style={{ fontSize: 12, opacity: 0.65, marginTop: 2 }}>{subtitle}</div>
      </div>
    </div>
  );
}

function SkeletonRow() {
  return (
    <div
      style={{
        marginTop: 12,
        height: 12,
        borderRadius: 6,
        background: 'var(--hud-border)',
        animation: 'pulse 1.4s ease-in-out infinite',
      }}
    />
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      style={{
        marginTop: 12,
        padding: '8px 12px',
        borderRadius: 8,
        border: '1px solid color-mix(in oklab, #dc2626 35%, transparent)',
        background: 'color-mix(in oklab, #dc2626 8%, transparent)',
        fontSize: 12,
        color: 'var(--hud-text)',
      }}
    >
      ⚠️ {message}
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div style={{ marginTop: 12, fontSize: 12, opacity: 0.6 }}>
      {text}
    </div>
  );
}
