// OnboardingSidePanel — Module A · 신입 온보딩 사이드 패널.
// 디자인 시스템 v3.5: lg-card / lg-eyebrow / lg-h2 / lg-btn / 16-12-2-999 radii.
// 신입(role_level <= 2)에게만 노출. 사수 / 첫 주 체크리스트 / 용어 / 부서 FAQ.

import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  GraduationCap,
  CheckCircle2,
  Circle,
  BookOpen,
  HelpCircle,
  UserCheck,
  ArrowRight,
} from 'lucide-react';
import { useAuthStore } from '@store/auth';
import { fetchByDepartment, type BackendEmployee } from '@api/employee';

const NEW_HIRE_THRESHOLD = 2;
const STORAGE_PREFIX = 'ajin-onboarding-checklist:';

interface ChecklistItem {
  id: string;
  label: string;
  hint: string;
  action: { kind: 'route'; to: string } | { kind: 'noop' };
}

const CHECKLIST_TEMPLATE: ChecklistItem[] = [
  {
    id: 'sop-read',
    label: 'SOP 8종 읽음',
    hint: '챗봇 → SOP 가이드 8종 모두 한 번씩 열어보기',
    action: { kind: 'route', to: '/chat' },
  },
  {
    id: 'org-explore',
    label: '본부/팀 조직도 확인',
    hint: '본부 → 팀 → 팀장 동선 익히기',
    action: { kind: 'route', to: '/search?tab=people' },
  },
  {
    id: 'msds',
    label: 'MSDS / 화학물질 안전 숙지',
    hint: '안전팀 SOP 절차 + 비상 연락 체계',
    action: { kind: 'route', to: '/compliance' },
  },
  {
    id: 'glossary',
    label: '핵심 용어 30개 익힘',
    hint: '8D · ECN · APQP · CP/CPK · IATF',
    action: { kind: 'route', to: '/chat' },
  },
  {
    id: 'first-draft',
    label: '첫 회의록 / 메일 초안 작성',
    hint: '문서 초안 템플릿으로 한 번 시도',
    action: { kind: 'route', to: '/draft' },
  },
];

const FAQ_BY_DEPT: Record<string, string[]> = {
  default: [
    '8D 보고서 양식 어디서 찾나요?',
    'ECN 신청은 어느 팀에 보내야 하나요?',
    '내선번호 단축 발신 규칙이 있나요?',
    'IATF 16949 사내 매뉴얼 위치?',
    '비상시 안전책임자 연락처?',
  ],
  품질보증팀: [
    'APQP 5단계는 정확히 무엇인가요?',
    'CP/CPK 기준치 1.33 / 1.67 차이?',
    '8D 작성 시 D3 격리 조치 예시?',
    'PPAP Level 3 제출 서류 체크리스트?',
    '고객 불량 클레임 응대 절차?',
  ],
  생산기술팀: [
    'SPC 차트에서 Nelson 8 Rules 활용?',
    '프레스 안전거리 현행 규정?',
    '금형 수명 예측 KPI 보는 법?',
    '5대 코어툴 이름 풀어 쓰기?',
    '불량 발생 시 라인 정지 권한?',
  ],
};

const WIDGET_BOX: React.CSSProperties = {
  border: '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
  borderRadius: 16,
  padding: 16,
  background: 'color-mix(in oklab, var(--hud-surface) 40%, transparent)',
};

interface MentorCardProps {
  busy: boolean;
  mentor: BackendEmployee | null;
  onAskChat: () => void;
  onViewProfile: () => void;
}

function MentorCard({ busy, mentor, onAskChat, onViewProfile }: MentorCardProps) {
  if (busy) {
    return (
      <div style={{ ...WIDGET_BOX, fontSize: 12, color: 'var(--hud-text-dim)' }}>
        사수 정보 불러오는 중…
      </div>
    );
  }
  if (!mentor) {
    return (
      <div
        style={{
          ...WIDGET_BOX,
          borderStyle: 'dashed',
          fontSize: 12,
          color: 'var(--hud-text-dim)',
        }}
      >
        사수가 자동 추론되지 않았습니다. 인사관리팀 또는 부서장에게 문의하세요.
      </div>
    );
  }
  return (
    <div style={WIDGET_BOX}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {/* 아바타 — 캐노니컬 lg-avatar 패턴 (999px 원형, 골드 톤) */}
        <span
          className="lg-avatar"
          aria-hidden
          style={{ width: 44, height: 44, fontSize: 14 }}
        >
          {mentor.name.slice(-2)}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="lg-eyebrow" style={{ marginBottom: 2 }}>
            MENTOR · 추정 사수
          </div>
          <div style={{ fontSize: 15, fontWeight: 600, lineHeight: 1.3 }}>
            {mentor.name}
          </div>
          <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', marginTop: 2 }}>
            {mentor.position} · {mentor.department}
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
        <button
          type="button"
          className="lg-btn ghost sm"
          onClick={onAskChat}
          style={{
            flex: 1,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
          }}
          title="챗봇으로 더 알아보기"
        >
          챗봇 문의 <ArrowRight size={11} strokeWidth={2} />
        </button>
        <button
          type="button"
          className="lg-btn ghost sm"
          onClick={onViewProfile}
          style={{ flex: 1 }}
        >
          상세 보기
        </button>
      </div>
    </div>
  );
}

interface Props {
  forceVisible?: boolean;
}

export function OnboardingSidePanel({ forceVisible = false }: Props) {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();

  const isNewHire =
    forceVisible || (user ? user.role_level <= NEW_HIRE_THRESHOLD : false);

  const checklistKey = `${STORAGE_PREFIX}${user?.employee_id ?? 'guest'}`;
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
      localStorage.setItem(checklistKey, JSON.stringify(checks));
    }
  }, [checks, checklistKey]);

  const completed = useMemo(
    () => CHECKLIST_TEMPLATE.filter((it) => checks[it.id]).length,
    [checks],
  );

  const [mentor, setMentor] = useState<BackendEmployee | null>(null);
  const [mentorBusy, setMentorBusy] = useState(false);
  useEffect(() => {
    if (!isNewHire || !user?.department) return;
    let cancelled = false;
    setMentorBusy(true);
    fetchByDepartment(user.department)
      .then((r) => {
        if (cancelled) return;
        const seniorRanks = ['부장', '차장', '과장', '팀장', '책임'];
        const senior =
          r.employees.find((e) =>
            seniorRanks.some((s) => (e.position || '').includes(s)),
          ) ?? null;
        setMentor(senior);
      })
      .catch(() => !cancelled && setMentor(null))
      .finally(() => !cancelled && setMentorBusy(false));
    return () => {
      cancelled = true;
    };
  }, [isNewHire, user?.department]);

  if (!isNewHire) return null;

  const dept = user?.department ?? 'default';
  const faq = FAQ_BY_DEPT[dept] ?? FAQ_BY_DEPT.default;

  return (
    <section className="lg-card">
      <div className="lg-card-h">
        <div>
          <div
            className="lg-eyebrow"
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <GraduationCap size={12} strokeWidth={2} /> ONBOARDING · 신입 사이드 패널
          </div>
          <h2 className="lg-h2">
            첫 주 체크리스트{' '}
            <span className="lg-h2-sub">
              · {completed}/{CHECKLIST_TEMPLATE.length} 진행
            </span>
          </h2>
        </div>
        <span className="lg-pill">{user?.position ?? '신입'}</span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 16,
        }}
      >
        {/* MENTOR */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div
            className="lg-eyebrow"
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <UserCheck size={12} strokeWidth={2} /> 나의 사수 (자동 추정)
          </div>
          <MentorCard
            busy={mentorBusy}
            mentor={mentor}
            onAskChat={() => {
              if (!mentor) return;
              navigate('/chat', {
                state: {
                  prefillContext: {
                    kind: 'mentor',
                    name: mentor.name,
                    team: mentor.department,
                    position: mentor.position,
                  },
                  prefillPrompt: `${mentor.department} ${mentor.position} ${mentor.name}님께 OJT 시간을 잡고 싶다는 메시지를 작성해줘.`,
                },
              });
            }}
            onViewProfile={() =>
              navigate('/search?tab=people', {
                state: { initialQuery: mentor?.name },
              })
            }
          />
        </div>

        {/* CHECKLIST */}
        <div>
          <div
            className="lg-eyebrow"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 10,
            }}
          >
            <CheckCircle2 size={12} strokeWidth={2} /> 첫 주 체크리스트
          </div>
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
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '10px 12px',
                    borderRadius: 12,
                    border:
                      '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
                    background: done
                      ? 'color-mix(in oklab, var(--hud-green, #2D8A4E) 8%, transparent)'
                      : 'color-mix(in oklab, var(--hud-surface) 40%, transparent)',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setChecks((prev) => ({ ...prev, [it.id]: !done }))}
                    title={done ? '완료 취소' : '완료 표시'}
                    aria-pressed={done}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      padding: 0,
                      cursor: 'pointer',
                      color: done
                        ? 'var(--hud-green, #2D8A4E)'
                        : 'var(--hud-text-dim)',
                      display: 'inline-flex',
                    }}
                  >
                    {done ? (
                      <CheckCircle2 size={18} strokeWidth={2} />
                    ) : (
                      <Circle size={18} strokeWidth={2} />
                    )}
                  </button>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: 'var(--hud-text)',
                        textDecoration: done ? 'line-through' : undefined,
                        opacity: done ? 0.65 : 1,
                      }}
                    >
                      {it.label}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--hud-text-dim)',
                        marginTop: 2,
                      }}
                    >
                      {it.hint}
                    </div>
                  </div>
                  {it.action.kind === 'route' && (
                    <button
                      type="button"
                      className="lg-btn ghost sm"
                      onClick={() =>
                        navigate(
                          it.action.kind === 'route' ? it.action.to : '/',
                        )
                      }
                      title="해당 페이지로 이동"
                      aria-label="이동"
                    >
                      <ArrowRight size={12} strokeWidth={2} />
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>

        {/* GLOSSARY + FAQ */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <div
              className="lg-eyebrow"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                marginBottom: 10,
              }}
            >
              <BookOpen size={12} strokeWidth={2} /> 용어 사전 빠른 진입
            </div>
            <button
              type="button"
              className="lg-btn ghost sm"
              onClick={() =>
                navigate('/chat', {
                  state: {
                    prefillPrompt:
                      '8D, ECN, APQP, CP/CPK, IATF 16949, REACH SVHC 의 정의를 신입이 이해하기 쉽게 설명해줘.',
                  },
                })
              }
              style={{
                width: '100%',
                justifyContent: 'flex-start',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              핵심 용어 30개 챗봇으로 보기 <ArrowRight size={11} strokeWidth={2} />
            </button>
          </div>
          <div>
            <div
              className="lg-eyebrow"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                marginBottom: 10,
              }}
            >
              <HelpCircle size={12} strokeWidth={2} /> 부서 FAQ TOP 5 ({dept})
            </div>
            <ul
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              {faq.map((q, i) => (
                <li key={i}>
                  <button
                    type="button"
                    className="lg-btn ghost sm"
                    onClick={() =>
                      navigate('/chat', { state: { prefillPrompt: q } })
                    }
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 10px',
                      fontSize: 12,
                    }}
                    title="챗봇으로 묻기"
                  >
                    Q{i + 1}. {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
