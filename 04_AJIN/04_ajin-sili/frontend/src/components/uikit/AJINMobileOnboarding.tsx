// AJINMobileOnboarding — iPhone 모바일 신입 가이드 / Onboarding 화면.
//
// routes/onboarding.tsx 의 데스크탑 화면을 모바일(단일 컬럼, phone-width)로
// 재구성한다. props 없음 — routes/onboarding.tsx 가 `if (isMobile)` 분기에서
// 직접 렌더하므로 self-contained 여야 한다.
//
// 섹션 순서 (위→아래, 단일 컬럼):
//   1) 헤더 (FEATURE C · ONBOARDING / 신입 가이드 / 서브타이틀)
//   2) 첫 주 체크리스트 — OnboardingSidePanel 과 동일한 CHECKLIST_TEMPLATE +
//      동일한 localStorage 키 (`ajin-onboarding-checklist:${employee_id}`) 라
//      데스크탑/모바일 진행률이 동기화된다. 진행 progress bar + 토글 가능 항목.
//   3) SOP 학습 그리드 — fetchSopList → 카드(<button>) 탭 시 fetchSopQuiz 로
//      4지선다 퀴즈를 bottom-sheet 로 띄운다.
//   4) 부서별 빠른 질문 — GET ONBOARDING_BASE/quick-questions?department= →
//      chip(<button>) 탭 시 navigate('/chat', { state: { prefill } }) (데스크탑과 동일).
//   5) 협업 시나리오 매칭 — input → matchScenario → 결과 카드.
//
// 디자인: lg-*/hud CSS 변수 시스템 (var(--hud-text) 등) + 모바일 shell 은
// AJINMobileCompliance/Chat 과 동일 (aj-mobile > aj-screen dark > aj-bg-grad
// + aj-scroll). BottomTabBar 가림 방지를 위해 하단 safe-area + tab-bar 높이만큼
// paddingBottom 확보.
//
// 다크모드 fix (필수):
//   - SOP 카드 / 빠른질문 chip 은 <button> 이므로 color 상속 안 됨 →
//     color: var(--hud-text) 명시.
//   - SOP 카드 border 는 amber 가시화:
//     1px solid color-mix(in oklab, var(--hud-primary) 30%, transparent).

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  GraduationCap,
  CheckCircle2,
  Circle,
  ChevronRight,
  Sparkles,
  X,
} from 'lucide-react';

import { useAuthStore } from '@store/auth';
import {
  fetchSopList,
  fetchSopQuiz,
  type SopSummary,
  type SopQuizQuestion,
} from '@api/sop';
import { matchScenario, type ScenarioCard } from '@api/scenarios';
import { authHeaders, ONBOARDING_BASE } from '@api/onboarding';

// ──────────────────────────────────────────────────────────────
// 첫 주 체크리스트 — OnboardingSidePanel.tsx 와 동일 정의/키 (진행률 동기화).
// ──────────────────────────────────────────────────────────────
const STORAGE_PREFIX = 'ajin-onboarding-checklist:';

interface ChecklistItem {
  id: string;
  label: string;
  hint: string;
  to?: string;
}

const CHECKLIST_TEMPLATE: ChecklistItem[] = [
  { id: 'sop-read', label: 'SOP 8종 읽음', hint: '챗봇 → SOP 가이드 8종 모두 한 번씩 열어보기', to: '/chat' },
  { id: 'org-explore', label: '본부/팀 조직도 확인', hint: '본부 → 팀 → 팀장 동선 익히기', to: '/search?tab=people' },
  { id: 'msds', label: 'MSDS / 화학물질 안전 숙지', hint: '안전팀 SOP 절차 + 비상 연락 체계', to: '/compliance' },
  { id: 'glossary', label: '핵심 용어 30개 익힘', hint: '8D · ECN · APQP · CP/CPK · IATF', to: '/chat' },
  { id: 'first-draft', label: '첫 회의록 / 메일 초안 작성', hint: '문서 초안 템플릿으로 한 번 시도', to: '/draft' },
];

// 부서별 빠른 질문 응답 shape (onboarding.tsx 와 동일)
interface QuickQuestionItem {
  question: string;
  category?: string;
}
interface QuickQuestionsResponse {
  questions: QuickQuestionItem[];
  department?: string;
}

// ──────────────────────────────────────────────────────────────
// Page (self-contained, no props)
// ──────────────────────────────────────────────────────────────
export function AJINMobileOnboarding() {
  const user = useAuthStore((s) => s.user);

  return (
    <div className="aj-mobile" style={{ minHeight: '100vh' }}>
      <div className="aj-screen dark" style={{ position: 'relative', minHeight: '100vh' }}>
        <div className="aj-bg-grad dark" />

        <div
          className="aj-scroll"
          style={{
            paddingTop: 12,
            // BottomTabBar 가림 방지 — safe-area + tab-bar 높이 + 여유
            paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 140px)',
            position: 'relative',
            zIndex: 3,
            minHeight: '100vh',
          }}
        >
          {/* (1) Header */}
          <div style={{ padding: '12px 20px 4px' }}>
            <div
              className="aj-mono"
              style={{
                color: 'var(--hud-primary, #FCB132)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <GraduationCap size={12} aria-hidden />
              FEATURE C · ONBOARDING
            </div>
            <h1 style={{ margin: '6px 0 4px', fontSize: 28, fontWeight: 700, letterSpacing: '-0.018em' }}>
              신입 가이드
            </h1>
            <div style={{ fontSize: 13, color: 'var(--hud-text-dim)' }}>
              첫 주 체크리스트 · SOP 학습 · 부서 빠른 질문 · 협업 시나리오
            </div>
          </div>

          {/* (2) 첫 주 체크리스트 */}
          <ChecklistSection employeeId={user?.employee_id} />

          {/* (3) SOP 학습 그리드 */}
          <SopLearningSection />

          {/* (4) 부서별 빠른 질문 */}
          <QuickQuestionsSection department={user?.department} />

          {/* (5) 협업 시나리오 매칭 */}
          <ScenarioMatchSection />
        </div>
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// (2) 첫 주 체크리스트
// ──────────────────────────────────────────────────────────────
function ChecklistSection({ employeeId }: { employeeId?: string }) {
  const navigate = useNavigate();
  const checklistKey = `${STORAGE_PREFIX}${employeeId ?? 'guest'}`;

  const [checks, setChecks] = useState<Record<string, boolean>>(() => {
    if (typeof window === 'undefined') return {};
    try {
      const raw = localStorage.getItem(checklistKey);
      return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
    } catch {
      return {};
    }
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(checklistKey, JSON.stringify(checks));
      } catch {
        // ignore quota / serialization errors
      }
    }
  }, [checks, checklistKey]);

  const completed = useMemo(
    () => CHECKLIST_TEMPLATE.filter((it) => checks[it.id]).length,
    [checks],
  );
  const total = CHECKLIST_TEMPLATE.length;
  const pct = Math.round((completed / total) * 100);

  return (
    <>
      <SectionHeader title="첫 주 체크리스트" hint={`${completed}/${total} 완료`} />

      <div style={{ padding: '0 12px' }}>
        {/* 진행률 ribbon */}
        <div
          className="aj-glass"
          style={{ padding: 14, borderRadius: 16, marginBottom: 10 }}
        >
          <div className="aj-q-bar">
            <span className="lbl">진행률</span>
            <span className="track" aria-hidden>
              <i style={{ width: `${pct}%`, transition: 'width 320ms ease' }} />
            </span>
            <span className="v">{pct}%</span>
          </div>
        </div>

        {/* 체크 항목 */}
        <ul
          style={{
            listStyle: 'none',
            margin: 0,
            padding: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          {CHECKLIST_TEMPLATE.map((it) => {
            const done = !!checks[it.id];
            return (
              <li
                key={it.id}
                className="aj-glass"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '12px 14px',
                  borderRadius: 14,
                  background: done
                    ? 'color-mix(in oklab, var(--hud-green, #2D8A4E) 12%, transparent)'
                    : undefined,
                }}
              >
                <button
                  type="button"
                  onClick={() => setChecks((p) => ({ ...p, [it.id]: !done }))}
                  title={done ? '완료 취소' : '완료 표시'}
                  aria-pressed={done}
                  style={{
                    background: 'transparent',
                    border: 0,
                    padding: 0,
                    cursor: 'pointer',
                    flexShrink: 0,
                    display: 'inline-flex',
                    color: done ? 'var(--hud-green, #2D8A4E)' : 'var(--hud-text-dim)',
                  }}
                >
                  {done ? <CheckCircle2 size={22} strokeWidth={2} /> : <Circle size={22} strokeWidth={2} />}
                </button>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 600,
                      color: 'var(--hud-text)',
                      textDecoration: done ? 'line-through' : undefined,
                      opacity: done ? 0.6 : 1,
                    }}
                  >
                    {it.label}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--hud-text-dim)', marginTop: 2 }}>
                    {it.hint}
                  </div>
                </div>
                {it.to && (
                  <button
                    type="button"
                    onClick={() => navigate(it.to as string)}
                    aria-label="해당 페이지로 이동"
                    title="해당 페이지로 이동"
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 999,
                      flexShrink: 0,
                      background: 'var(--hud-surface-2)',
                      border: '1px solid var(--hud-border)',
                      color: 'var(--hud-text)',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <ChevronRight size={15} aria-hidden />
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </>
  );
}

// ──────────────────────────────────────────────────────────────
// (3) SOP 학습 그리드 + bottom-sheet 퀴즈
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
        if (active) setItems(res.items ?? []);
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <>
      <SectionHeader title="SOP 학습 그리드" hint="탭 → 자동 퀴즈" />

      <div style={{ padding: '0 12px' }}>
        {loading && <LoadingHint text="SOP 목록 불러오는 중…" />}
        {error && <ErrorBanner message={error} />}
        {!loading && !error && items.length === 0 && (
          <EmptyHint text="등록된 SOP 가 없습니다." />
        )}

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 10,
          }}
        >
          {items.map((it) => (
            <button
              key={it.sop_id}
              type="button"
              onClick={() => setQuizOpen(it)}
              style={{
                padding: 14,
                textAlign: 'left',
                borderRadius: 14,
                background: 'var(--hud-surface-2)',
                // 다크모드 fix — amber 가시 border
                border: '1px solid color-mix(in oklab, var(--hud-primary) 30%, transparent)',
                // 다크모드 fix — <button> 은 color 상속 안 됨
                color: 'var(--hud-text)',
                fontFamily: 'inherit',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                minHeight: 108,
              }}
            >
              <div
                className="aj-mono"
                style={{ fontSize: 9, opacity: 0.6, letterSpacing: '0.08em' }}
              >
                {(it.category || '').toUpperCase()}
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.3, flex: 1 }}>
                {it.title}
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 6,
                }}
              >
                <span style={{ fontSize: 10, opacity: 0.55 }}>{it.steps_count} steps</span>
                <span
                  className="aj-status gold"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}
                >
                  퀴즈 <ChevronRight size={10} aria-hidden />
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {quizOpen && <QuizSheet sop={quizOpen} onClose={() => setQuizOpen(null)} />}
    </>
  );
}

// Bottom-sheet 퀴즈 — 모바일 제스처(하단에서 슬라이드 업) 친화 모달.
function QuizSheet({ sop, onClose }: { sop: SopSummary; onClose: () => void }) {
  const [questions, setQuestions] = useState<SopQuizQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    let active = true;
    fetchSopQuiz(sop.sop_id, 3)
      .then((r) => {
        if (active) setQuestions(r.questions ?? []);
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
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

  const allAnswered =
    questions.length > 0 && questions.every((_, idx) => answers[idx] !== undefined);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${sop.title} 퀴즈`}
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 999,
        background: 'color-mix(in oklab, var(--hud-bg) 55%, black)',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="aj-glass"
        style={{
          width: '100%',
          maxWidth: 480,
          maxHeight: '88vh',
          overflowY: 'auto',
          borderTopLeftRadius: 22,
          borderTopRightRadius: 22,
          padding: '14px 18px calc(env(safe-area-inset-bottom, 0px) + 22px)',
          animation: 'aj-sheet-up 260ms cubic-bezier(0.22, 1, 0.36, 1)',
        }}
      >
        {/* grabber */}
        <div
          aria-hidden
          style={{
            width: 38,
            height: 4,
            borderRadius: 999,
            background: 'var(--hud-border)',
            margin: '0 auto 12px',
          }}
        />

        {/* sheet header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="aj-mono" style={{ fontSize: 10, opacity: 0.55 }}>
              SOP QUIZ · {sop.sop_id}
            </div>
            <h2 style={{ margin: '4px 0 0', fontSize: 17, fontWeight: 700, lineHeight: 1.3 }}>
              {sop.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            style={{
              width: 34,
              height: 34,
              borderRadius: 999,
              flexShrink: 0,
              background: 'var(--hud-surface-2)',
              border: '1px solid var(--hud-border)',
              color: 'var(--hud-text)',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={16} aria-hidden />
          </button>
        </div>

        {loading && <LoadingHint text="퀴즈 생성 중…" />}
        {error && <ErrorBanner message={error} />}
        {!loading && !error && questions.length === 0 && (
          <EmptyHint text="이 SOP에서 출제 가능한 퀴즈가 없습니다." />
        )}

        <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 18 }}>
          {questions.map((q, idx) => {
            const selected = answers[idx];
            return (
              <div key={idx}>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--hud-text)', lineHeight: 1.4 }}>
                  Q{idx + 1}. {q.question}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 10 }}>
                  {q.options.map((opt, oi) => {
                    const isCorrect = submitted && oi === q.correct_index;
                    const isWrong = submitted && selected === oi && oi !== q.correct_index;
                    const isSel = selected === oi;
                    return (
                      <label
                        key={oi}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          padding: '11px 12px',
                          borderRadius: 12,
                          cursor: submitted ? 'default' : 'pointer',
                          color: 'var(--hud-text)',
                          border: `1px solid ${
                            isCorrect
                              ? 'color-mix(in oklab, #16a34a 55%, transparent)'
                              : isWrong
                                ? 'color-mix(in oklab, #dc2626 55%, transparent)'
                                : isSel
                                  ? 'color-mix(in oklab, var(--hud-primary) 55%, transparent)'
                                  : 'var(--hud-border)'
                          }`,
                          background: isCorrect
                            ? 'color-mix(in oklab, #16a34a 18%, transparent)'
                            : isWrong
                              ? 'color-mix(in oklab, #dc2626 14%, transparent)'
                              : isSel
                                ? 'color-mix(in oklab, var(--hud-primary) 10%, transparent)'
                                : 'var(--hud-surface-2)',
                        }}
                      >
                        <input
                          type="radio"
                          name={`mq-${idx}`}
                          checked={isSel}
                          disabled={submitted}
                          onChange={() => setAnswers((p) => ({ ...p, [idx]: oi }))}
                          style={{ accentColor: 'var(--hud-primary, #FCB132)', flexShrink: 0 }}
                        />
                        <span style={{ fontSize: 13, lineHeight: 1.4 }}>{opt}</span>
                      </label>
                    );
                  })}
                </div>
                {submitted && (
                  <div
                    style={{
                      fontSize: 12,
                      color: 'var(--hud-text-dim)',
                      marginTop: 8,
                      paddingLeft: 2,
                      lineHeight: 1.5,
                    }}
                  >
                    💡 {q.explanation}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {questions.length > 0 && (
          <div
            style={{
              marginTop: 20,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
            }}
          >
            {score ? (
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--hud-text)' }}>
                결과: {score.correct} / {score.total} 정답
              </div>
            ) : (
              <div style={{ fontSize: 11, color: 'var(--hud-text-dim)' }}>
                모든 문항에 답한 후 제출하세요.
              </div>
            )}
            <button
              type="button"
              disabled={submitted || !allAnswered}
              onClick={() => setSubmitted(true)}
              style={{
                padding: '10px 22px',
                borderRadius: 12,
                border: '1px solid color-mix(in oklab, var(--hud-primary) 45%, transparent)',
                background:
                  submitted || !allAnswered
                    ? 'var(--hud-surface-2)'
                    : 'var(--hud-primary, #FCB132)',
                color: submitted || !allAnswered ? 'var(--hud-text-dim)' : '#1A1004',
                fontFamily: 'inherit',
                fontSize: 14,
                fontWeight: 700,
                cursor: submitted || !allAnswered ? 'not-allowed' : 'pointer',
                flexShrink: 0,
              }}
            >
              {submitted ? '제출 완료' : '제출'}
            </button>
          </div>
        )}
      </div>

      {/* bottom-sheet slide-up keyframes (scoped, 1회 주입) */}
      <style>{`@keyframes aj-sheet-up { from { transform: translateY(100%); } to { transform: translateY(0); } }`}</style>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// (4) 부서별 빠른 질문 — chip → navigate('/chat', { state:{ prefill } })
// ──────────────────────────────────────────────────────────────
function QuickQuestionsSection({ department }: { department?: string }) {
  const navigate = useNavigate();
  const [data, setData] = useState<QuickQuestionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const dept = department ? `?department=${encodeURIComponent(department)}` : '';
    fetch(`${ONBOARDING_BASE}/quick-questions${dept}`, { headers: authHeaders() })
      .then(async (r) => {
        if (!r.ok) throw new Error(`status ${r.status}`);
        return (await r.json()) as QuickQuestionsResponse;
      })
      .then((j) => {
        if (active) setData(j);
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [department]);

  return (
    <>
      <SectionHeader title={`${department ?? '부서'} 빠른 질문`} hint="탭 → 챗봇" />

      <div style={{ padding: '0 12px' }}>
        {loading && <LoadingHint text="질문 목록 불러오는 중…" />}
        {error && <ErrorBanner message={error} />}
        {!loading && !error && !data?.questions?.length && (
          <EmptyHint text="질문 목록을 불러올 수 없습니다." />
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {data?.questions?.map((q, i) => (
            <button
              key={i}
              type="button"
              // 데스크탑과 동일 — chat.tsx 가 location.state.prefill 을 읽음
              onClick={() => navigate('/chat', { state: { prefill: q.question } })}
              style={{
                padding: '9px 14px',
                borderRadius: 999,
                background: 'var(--hud-surface-2)',
                border: '1px solid var(--hud-border)',
                // 다크모드 fix — <button> color 상속 안 됨
                color: 'var(--hud-text)',
                fontFamily: 'inherit',
                fontSize: 12.5,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                textAlign: 'left',
              }}
            >
              {q.question}
              <ChevronRight size={12} aria-hidden style={{ opacity: 0.6, flexShrink: 0 }} />
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

// ──────────────────────────────────────────────────────────────
// (5) 협업 시나리오 매칭
// ──────────────────────────────────────────────────────────────
function ScenarioMatchSection() {
  const [query, setQuery] = useState('');
  const [card, setCard] = useState<ScenarioCard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tried, setTried] = useState(false);

  const onMatch = async () => {
    if (!query.trim() || loading) return;
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
    <>
      <SectionHeader title="협업 시나리오 매칭" hint="상황 입력 → 절차 카드" />

      <div style={{ padding: '0 12px' }}>
        <div className="aj-glass" style={{ padding: 12, borderRadius: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', marginBottom: 8, lineHeight: 1.5 }}>
            “PPAP 제출 요청 받았어요” 같이 상황을 입력하면 절차 카드를 즉시 응답합니다.
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onMatch();
              }}
              placeholder="예: 고객사가 8D 보고서를 요청했어요"
              style={{
                flex: 1,
                minWidth: 0,
                padding: '11px 14px',
                borderRadius: 12,
                border: '1px solid var(--hud-border)',
                background: 'var(--hud-surface-2)',
                color: 'var(--hud-text)',
                fontFamily: 'inherit',
                fontSize: 14,
                outline: 'none',
              }}
            />
            <button
              type="button"
              disabled={loading || !query.trim()}
              onClick={onMatch}
              style={{
                padding: '0 18px',
                borderRadius: 12,
                border: '1px solid color-mix(in oklab, var(--hud-primary) 45%, transparent)',
                background:
                  loading || !query.trim()
                    ? 'var(--hud-surface-2)'
                    : 'var(--hud-primary, #FCB132)',
                color: loading || !query.trim() ? 'var(--hud-text-dim)' : '#1A1004',
                fontFamily: 'inherit',
                fontSize: 14,
                fontWeight: 700,
                cursor: loading || !query.trim() ? 'not-allowed' : 'pointer',
                flexShrink: 0,
                whiteSpace: 'nowrap',
              }}
            >
              {loading ? '매칭 중…' : '매칭'}
            </button>
          </div>
        </div>

        {error && <ErrorBanner message={error} />}

        {tried && !loading && !card && !error && (
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--hud-text-dim)', lineHeight: 1.5 }}>
            매칭된 시나리오가 없습니다. 다른 키워드(예: PPAP, ECN, 클레임)로 시도해 보세요.
          </div>
        )}

        {card && (
          <div
            style={{
              marginTop: 12,
              padding: 16,
              borderRadius: 16,
              border: '1px solid color-mix(in oklab, var(--hud-primary) 35%, transparent)',
              background: 'color-mix(in oklab, var(--hud-primary) 7%, transparent)',
            }}
          >
            <div className="aj-mono" style={{ fontSize: 10, opacity: 0.6 }}>
              SCENARIO · {card.scenario_id} · 요청 부서: {card.requesting_dept || '—'}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--hud-text)', marginTop: 4, lineHeight: 1.35 }}>
              {card.situation}
            </div>

            {card.my_actions?.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <div
                  className="aj-mono"
                  style={{ fontSize: 10, opacity: 0.6, marginBottom: 6, letterSpacing: '0.1em' }}
                >
                  내가 할 일
                </div>
                <ol
                  style={{
                    margin: 0,
                    paddingLeft: 18,
                    fontSize: 13,
                    lineHeight: 1.7,
                    color: 'var(--hud-text)',
                  }}
                >
                  {card.my_actions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ol>
              </div>
            )}

            {(card.hand_off_to || card.hand_off_items?.length > 0) && (
              <div style={{ marginTop: 14 }}>
                <div
                  className="aj-mono"
                  style={{ fontSize: 10, opacity: 0.6, marginBottom: 6, letterSpacing: '0.1em' }}
                >
                  이관 — {card.hand_off_to || '—'}
                </div>
                <ul
                  style={{
                    margin: 0,
                    paddingLeft: 18,
                    fontSize: 13,
                    lineHeight: 1.7,
                    color: 'var(--hud-text)',
                  }}
                >
                  {card.hand_off_items?.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </div>
            )}

            {card.tips?.length > 0 && (
              <div style={{ marginTop: 12, fontSize: 12, color: 'var(--hud-text-dim)', lineHeight: 1.5 }}>
                💡 {card.tips.join(' · ')}
              </div>
            )}

            {card.deadline_info && (
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--hud-text)' }}>
                ⏰ {card.deadline_info}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ──────────────────────────────────────────────────────────────
// Shared UI bits (모바일 톤)
// ──────────────────────────────────────────────────────────────
function SectionHeader({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="aj-sect-h">
      <h3 style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <Sparkles size={11} aria-hidden style={{ opacity: 0.7 }} />
        {title}
      </h3>
      {hint && <span className="more">{hint}</span>}
    </div>
  );
}

function LoadingHint({ text }: { text: string }) {
  return (
    <div style={{ padding: '14px 2px', fontSize: 13, color: 'var(--hud-text-dim)' }}>
      {text}
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div style={{ padding: '14px 2px', fontSize: 13, color: 'var(--hud-text-dim)' }}>
      {text}
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      style={{
        marginTop: 12,
        padding: '10px 12px',
        borderRadius: 12,
        border: '1px solid color-mix(in oklab, #dc2626 35%, transparent)',
        background: 'color-mix(in oklab, #dc2626 8%, transparent)',
        fontSize: 12.5,
        color: 'var(--hud-text)',
        lineHeight: 1.5,
      }}
    >
      ⚠️ {message}
    </div>
  );
}

export default AJINMobileOnboarding;
