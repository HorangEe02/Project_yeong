// chat.tsx — Module C · AI 업무 도우미 (lg-* canonical 양식 재구성).
// 캐노니컬 uiux/web_app/Chat.jsx 1:1 매핑 + 기존 useSSE / useChatStore 보존.
// v3.3 Phase A — LLM 멀티 프로바이더 셀렉터 + localStorage 영속 + SSE force_provider 배선.

import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSSE } from '@hooks/useSSE';
import { useUIStore } from '@store/ui';
import { useAuthStore } from '@store/auth';
import { useToastStore } from '@store/toast';
import { buildChatUrl } from '@api/onboarding';
import { ModelSelect } from '@/components/chat/ModelSelect';
import { ActionCardRouter } from '@/components/chat/cards';
import type { ActionCard } from '@/components/chat/cards/types';
import type { ForceProvider } from '@/types/chat';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';
import { buildWelcomeMessage } from '@lib/chatGreeting';
import {
  loadChatSession,
  saveChatSession,
  clearChatSession,
} from '@lib/chatSession';
import { downloadResponse, type DownloadFormat } from '@api/download';
import {
  fetchSopList,
  fetchSopDetail,
  fetchSopQuiz,
  type SopSummary,
  type SopDetail,
  type SopQuizResponse,
} from '@api/sop';
import { fetchUserScenarios, type UserScenarioItem } from '@api/scenarios';

// v3.3 Phase B — 부서 컨텍스트 RBAC 임계값 (rbac.ts / backend onboarding.py 와 정합)
const MANAGER_ROLE_LEVEL = 3;    // 같은 본부 내 부서 변경 가능 (admin 진입)
const EXECUTIVE_ROLE_LEVEL = 4;  // 전사 부서 변경 가능
const DEFAULT_DEPT = '품질보증팀';

/** 부서명 → 본부명. ALL_DEPTS / DEPTS_BY_DIVISION 역매핑. */
function divisionOf(dept: string): string | null {
  for (const [div, list] of Object.entries(DEPTS_BY_DIVISION)) {
    if (list.includes(dept)) return div;
  }
  return null;
}

// v3.3 — 사용자 마지막 모델 선택 영속 키
const FORCE_PROVIDER_LS_KEY = 'ajin-chat-force-provider';

function loadForceProvider(): ForceProvider | null {
  try {
    const raw = localStorage.getItem(FORCE_PROVIDER_LS_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as Partial<ForceProvider>;
    if (
      v &&
      typeof v.provider === 'string' &&
      typeof v.model === 'string' &&
      v.provider.length > 0 &&
      v.model.length > 0
    ) {
      return { provider: v.provider, model: v.model };
    }
  } catch {
    /* corrupted — 무시 */
  }
  return null;
}

type ChatMode = '교육' | '업무';
type SidePanel = 'sop' | 'collab' | 'quiz';
type ModelFamily = 'qwen' | 'gemma' | 'gemini' | 'exaone' | 'other';

interface ChatMessageMeta {
  src: string;     // legacy raw label (e.g., 'SOP_GUIDE', 'QWEN-3.5')
  conf: string;    // confidence (e.g., '88%', '—')
  latency: string; // human-readable latency (e.g., '124ms · 41 t/s')
  // v3.3 Phase A — 풍부한 LLM 메타 (있으면 표시, 없으면 legacy 필드 fallback)
  provider?: string;       // 'ollama' | 'gemini' | 'lm_studio'
  model?: string;          // 'qwen3.5:9b' | 'gemini-2.5-pro' ...
  ttftMs?: number;         // first token latency
  totalLatencyMs?: number; // total response latency
  tokensIn?: number;
  tokensOut?: number;
  contextUsed?: number;    // 사용된 컨텍스트 char (또는 token)
  contextTotal?: number;   // 모드별 한도 (3000/2000)
}

interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  text: string;
  t: string; // HH:MM
  meta?: ChatMessageMeta;
  streaming?: boolean;
  action?: boolean;
  /** v3.3 Phase A-5 — 비교 모드에서 어느 모델 응답인지 표기 (left | right). */
  paneSide?: 'left' | 'right';
  /** v3.3 Phase F-2 — 인-챗 액션 카드 0~N개 (백엔드 SSE action_card 이벤트에서 push). */
  actionCards?: ActionCard[];
}

// v3.3 Phase A-4 — SSE metadata 페이로드 안전 파싱 유틸
function pickString(o: Record<string, unknown> | undefined, ...keys: string[]): string | undefined {
  if (!o) return undefined;
  for (const k of keys) {
    const v = o[k];
    if (typeof v === 'string' && v.length > 0) return v;
  }
  return undefined;
}
function pickNumber(o: Record<string, unknown> | undefined, ...keys: string[]): number | undefined {
  if (!o) return undefined;
  for (const k of keys) {
    const v = o[k];
    if (typeof v === 'number' && Number.isFinite(v)) return v;
  }
  return undefined;
}

// v3.3 Phase A-4 — 모델/프로바이더 → 패밀리 분류 (UI 색상용)
function familyOf(model?: string, provider?: string): ModelFamily {
  if (provider === 'gemini') return 'gemini';
  if (!model) return 'other';
  if (model.startsWith('qwen')) return 'qwen';
  if (model.startsWith('gemma')) return 'gemma';
  if (model.startsWith('exaone')) return 'exaone';
  return 'other';
}

// v3.3 Phase A-4 — 패밀리별 시각 색상 (디자인 시스템 토큰만 사용)
function familyColor(f: ModelFamily): string {
  switch (f) {
    case 'qwen':   return 'var(--hud-blue)';
    case 'gemma':  return 'var(--hud-green)';
    case 'exaone': return 'var(--hud-red)';
    case 'gemini': return 'var(--hud-primary)';
    default:       return 'var(--hud-text-dim)';
  }
}

// v3.3 Phase A-4 — 모델 라벨 정규화 (qwen3.5:9b → QWEN-3.5-9B)
function formatModelLabel(model?: string): string {
  if (!model) return '';
  return model.replace(/:/g, '-').toUpperCase();
}

// v3.3 Phase B — 30개 전체 부서 (department_router.py DEPARTMENT_PROFILES 와 정합).
// 본부별 optgroup 으로 그룹화 — admin 시뮬레이션 시 직관적 탐색.
const DEPTS_BY_DIVISION: Record<string, string[]> = {
  생산본부: ['품질보증팀', '안전보건팀', '생산관리팀', '영업팀', '자재관리팀'],
  생산기술본부: [
    '생산기술팀',
    '자동화기술팀',
    'FA사업팀',
    '플랜트사업팀',
    '제품설계팀',
    '공법계획팀',
    '용기운영팀',
    '비전연구팀',
  ],
  개발본부: ['기술영업팀', '부품개발팀', '금형생산팀'],
  기술연구소: ['바디선행개발팀', '전장선행개발팀'],
  관리본부: ['총무인사팀', '품질경영팀', 'ESG경영팀', '기술교육원'],
  구매본부: ['구매팀', '해외지원팀', '상생협력팀'],
  재경본부: ['재무팀', '회계팀', 'IT전략팀', '원가기획팀'],
  '독립': ['내부감사팀'],
};
const ALL_DEPTS = Object.values(DEPTS_BY_DIVISION).flat();

// v3.3 Phase D-4 — 동적 Quick Questions (백엔드 GET /api/onboarding/quick-questions)
interface QuickQuestionItem {
  id: string;
  label: string;
  promptText: string;
  category: 'scenario' | 'action' | 'sop' | 'general';
  min_level: number;
  max_level: number;
  tags?: string[];
}

interface QuickQuestionsResponse {
  items: QuickQuestionItem[];
  department: string;
  role_level: number;
  total: number;
}

async function fetchQuickQuestions(department: string): Promise<QuickQuestionItem[]> {
  const apiUrl = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';
  try {
    const res = await fetch(
      `${apiUrl}/api/onboarding/quick-questions?department=${encodeURIComponent(department)}`,
      { headers: { Accept: 'application/json' } },
    );
    if (!res.ok) return [];
    const data: QuickQuestionsResponse = await res.json();
    return data.items ?? [];
  } catch {
    return [];
  }
}

const SOP_STEPS = [
  { n: 1, title: '금형 점검',     items: ['금형 표면 균열 확인', '가이드 핀 마모 측정', '냉각 라인 누수 점검'], warn: '마모 0.3mm 초과 시 즉시 교체' },
  { n: 2, title: '재료 준비',     items: ['소재 두께 측정', '코일 정렬 확인', '윤활제 도포'],                  warn: '두께 편차 ±0.05mm 이내' },
  { n: 3, title: '클램프 / 압력', items: ['클램프 압력 설정', '슬라이드 위치 조정', '안전 인터록 점검'],       warn: '안전거리 400mm 준수 (산안법 개정)' },
  { n: 4, title: '시운전 1회',    items: ['저속 1샷 진행', '치수 확인', '소음/진동 청각 점검'],               warn: '이상음 즉시 정지' },
  { n: 5, title: '치수 측정',     items: ['주요 치수 5개소 측정', 'GD&T 검증', 'SPC 기록 입력'],              warn: 'Cpk 1.33 미만 시 조정' },
  { n: 6, title: '연속 트라이 50샷', items: ['50샷 연속 가공', '전수 검사', 'Nelson Rule 모니터링'],          warn: 'Rule 2 (9점 평균이동) 발생 시 정지' },
  { n: 7, title: '승인 / 기록',   items: ['최종 보고서 작성', '품질팀 승인', '양산 이관'],                    warn: '8D 발행 대비 이력 보관' },
];

// 협업 시나리오 5종 — 정적 fallback (백엔드 미가용 시).
// 라이브에서는 fetchUserScenarios() 로 DB 의 활성 시나리오를 동적 로드하여 HR_ADMIN 편집 즉시 반영.
interface CollabCard {
  trig: string;
  dept: string;
  steps: string;
  deadline: string;
}

const COLLAB_FALLBACK: CollabCard[] = [
  { trig: '품질팀에서 8D 올려달라는데?', dept: '품질보증팀', steps: '1) 8D 양식 → 2) 5-Why → 3) 영구조치 → 4) OEM 회신', deadline: '14일' },
  { trig: '설계 변경 요청 왔어',         dept: '부품개발팀', steps: '1) ECN 발행 → 2) 영향평가 → 3) PPAP 재제출 → 4) 양산 적용일', deadline: '7일' },
  { trig: 'Cpk 1.0 떨어졌어',           dept: '품질보증팀', steps: '1) Nelson Rule 진단 → 2) 시정조치 → 3) 재측정 → 4) 보고서', deadline: '24시간' },
  { trig: '신차 PPAP 서류 우리 부서 산출물은?', dept: '부품개발팀', steps: '1) FMEA → 2) Control Plan → 3) MSA → 4) PPAP 패키지', deadline: '4주' },
  { trig: '다음 주 안전 점검 뭐 준비?',  dept: '안전보건팀', steps: '1) 5S 점검 → 2) MSDS 게시 → 3) 비상구 확보 → 4) 안전표지', deadline: '3일' },
];

/** API 응답 → 카드 표시 형태 매핑. my_actions 를 numbered steps 로 합침. */
function toCollabCard(it: UserScenarioItem): CollabCard {
  const trig = it.trigger_keywords[0] || it.situation || it.scenario_id;
  const stepsText = it.my_actions.length
    ? it.my_actions.map((a, i) => `${i + 1}) ${a}`).join(' → ')
    : (it.situation || '절차 미지정');
  // deadline_info 에서 첫 시간 단위 추출 (예: "5영업일 이내" → "5일")
  const m = it.deadline_info.match(/(\d+)\s*(영업일|일|시간|주|개월)/);
  const deadline = m ? `${m[1]}${m[2].replace('영업', '')}` : it.deadline_info.slice(0, 12);
  return { trig, dept: it.requesting_dept || '담당 부서', steps: stepsText, deadline };
}

// v3.6 — SOP_LIST_8 정적 배열 제거. 백엔드 /api/onboarding/sop/list 에서 부서별 필터링된 결과 사용.
// 이전엔 8개 모두 onClick 핸들러 없어 클릭 불가. 01번만 i===0 스타일로 활성처럼 보였을 뿐.
// 폴백 (백엔드 미가용 시 데모용) — sop_id 없이 단순 표시
const SOP_FALLBACK: SopSummary[] = [
  { sop_id: 'SOP-001', title: '금형 교체',     department: '생산기술팀', category: 'production', steps_count: 7 },
  { sop_id: 'SOP-002', title: '용접 검사',     department: '품질보증팀', category: 'quality',    steps_count: 6 },
  { sop_id: 'SOP-003', title: 'CNC 가공',      department: '생산기술팀', category: 'production', steps_count: 8 },
  { sop_id: 'SOP-8D',  title: '8D Report 작성', department: '품질보증팀', category: 'quality',    steps_count: 8 },
  { sop_id: 'SOP-ECN', title: 'ECN 발행',      department: '설계팀',     category: 'change',     steps_count: 5 },
  { sop_id: 'SOP-SPC', title: 'SPC 분석',      department: '품질보증팀', category: 'quality',    steps_count: 6 },
  { sop_id: 'SOP-PPAP', title: 'PPAP 제출',    department: '품질보증팀', category: 'quality',    steps_count: 9 },
  { sop_id: 'SOP-SAFE', title: '안전 점검',    department: '안전관리팀', category: 'safety',     steps_count: 5 },
];

const QUIZ_Q = {
  q: 'Step 3 — 산안법 개정에 따른 프레스 안전거리 기준은?',
  options: [
    { k: 'A', t: '200mm',          ok: false },
    { k: 'B', t: '300mm (기존)',   ok: false },
    { k: 'C', t: '400mm (개정)',   ok: true },
    { k: 'D', t: '500mm',          ok: false },
  ],
  related: 3,
  explain:
    '2026년 산안법 시행규칙 개정으로 프레스 안전거리는 300→400mm로 강화되었습니다. (D-30 시행)',
};

// v3.6 — 정적 welcomeMsgs 제거. 첫 진입 시 buildWelcomeMessage(user) 로 동적 인사말 생성.
// 이전 정적 대화는 신입 사용자에게 "내가 보낸 메시지인가?" 혼란을 유발했음.
function buildInitialMsgs(welcomeText: string, t: string): ChatMessage[] {
  return [
    {
      id: 'a-welcome',
      role: 'ai',
      t,
      meta: { src: 'WELCOME', conf: '—', latency: '0ms' },
      text: welcomeText,
    },
  ];
}

// v3.6 — 채팅 세션 localStorage 영속은 @lib/chatSession 으로 분리.
// (LeftSidebar 로그아웃 핸들러도 같은 키를 사용해야 하므로 공용 유틸로 추출)

/** streaming 중 라우트 이동 시 SSE 끊김 → 영속 시 streaming=false + 안내 문구 부착 */
function sanitizeForPersist(arr: ChatMessage[]): ChatMessage[] {
  return arr.map((m) =>
    m.streaming
      ? {
          ...m,
          streaming: false,
          text: m.text + (m.text ? '\n\n' : '') + '_[페이지 이동으로 응답 중단됨]_',
        }
      : m,
  );
}

function nowHM(): string {
  const d = new Date();
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}

export function Chat() {
  const setUIStreaming = useUIStore((s) => s.setStreaming);
  // v3.3 Phase F-4 — 인-챗 카드의 "Module X 로 열기" 버튼을 SPA 내비게이션으로 처리.
  const navigate = useNavigate();

  // v3.3 Phase B — 부서 컨텍스트 RBAC.
  // L=3 (MANAGER): 같은 본부 내만 / L>=4 (EXEC/SYS): 전사 / L<3: 자기 부서 고정 + 자물쇠.
  const user = useAuthStore((s) => s.user);
  const userLevel = user?.role_level ?? 0;
  const isAdmin = userLevel >= MANAGER_ROLE_LEVEL;
  const isExecutive = userLevel >= EXECUTIVE_ROLE_LEVEL;
  // `??` 가 아니라 `||` — backend 가 빈 문자열 department 를 돌려주는 경우(또는 mock
  // 정합 깨짐) 까지 폴백되도록. ?? 는 null/undefined 만 잡아 select 가 빈 옵션으로 렌더되는
  // 버그가 있었음 (구매팀 사용자 데모에서 발견).
  const myDept = user?.department || DEFAULT_DEPT;
  const myDivision = useMemo(() => divisionOf(myDept), [myDept]);

  const [mode, setMode] = useState<ChatMode>('교육');
  const [dept, setDept] = useState(myDept);

  // v3.6.1 — 사용자 전환 감지용 ref. employee_id 가 바뀌면 dept 재동기화 + 채팅 세션 리셋.
  // 이전엔 executive(L≥4) 사용자에게는 dept sync 분기가 없어 mount 시점 값으로 영구 고정됐다.
  const lastUserIdRef = useRef<string | undefined>(user?.employee_id);

  // 사용자 변경(로그인/로그아웃/부서 이동) 시 권한 위반 부서면 자기 부서로 강제 동기화
  useEffect(() => {
    // 사용자 자체가 바뀐 경우(로그아웃 → 다른 계정 로그인) 는 무조건 자기 부서로.
    if (lastUserIdRef.current !== user?.employee_id) {
      setDept(myDept);
      return;
    }
    if (!isAdmin && dept !== myDept) {
      setDept(myDept);
      return;
    }
    // L=3 — 본부 경계 위반 시 자기 부서로 복귀
    if (isAdmin && !isExecutive && myDivision) {
      const currentDiv = divisionOf(dept);
      if (currentDiv && currentDiv !== myDivision) {
        setDept(myDept);
      }
    }
  }, [user?.employee_id, isAdmin, isExecutive, myDept, myDivision]); // eslint-disable-line react-hooks/exhaustive-deps
  const [input, setInput] = useState('');
  const [view, setView] = useState<SidePanel>('sop');
  const [sopStep, setSopStep] = useState(0);
  // v3.6 — SOP 목록 (백엔드 부서별 필터링). 미가용 시 SOP_FALLBACK 사용.
  // chatGreeting 처럼 fetch 1회로 충분 — SOP 항목은 자주 바뀌지 않음.
  const [sopList, setSopList] = useState<SopSummary[]>(SOP_FALLBACK);
  useEffect(() => {
    let cancelled = false;
    fetchSopList()
      .then((res) => {
        if (cancelled) return;
        if (res.items && res.items.length > 0) {
          setSopList(res.items);
        }
      })
      .catch(() => {
        // 백엔드 실패 → 폴백 유지 (오프라인 데모 보존)
      });
    return () => {
      cancelled = true;
    };
  }, [user?.username]);

  // 협업 시나리오 5종 (Phase 1+2 — DB 동적 로드, 미가용 시 정적 fallback).
  // HR_ADMIN 이 /admin → "협업 시나리오" 탭에서 편집/추가하면 즉시 반영됨.
  const [collabList, setCollabList] = useState<CollabCard[]>(COLLAB_FALLBACK);
  useEffect(() => {
    let cancelled = false;
    fetchUserScenarios('', 'ko')
      .then((res) => {
        if (cancelled) return;
        if (res.items && res.items.length > 0) {
          setCollabList(res.items.map(toCollabCard));
        }
      })
      .catch(() => {
        // 백엔드/인증 실패 → fallback 유지 (5종 보장)
      });
    return () => {
      cancelled = true;
    };
  }, [user?.username]);

  // v3.6 — 선택된 SOP (상단 가이드 패널 + 퀴즈 탭 동기화).
  // 첫 진입 시 sopList[0] 자동 선택 → 가이드 패널이 항상 의미 있는 내용 표시.
  const [selectedSopId, setSelectedSopId] = useState<string | null>(null);
  useEffect(() => {
    if (selectedSopId == null && sopList.length > 0) {
      setSelectedSopId(sopList[0].sop_id);
    }
  }, [sopList, selectedSopId]);

  // 선택된 SOP 의 상세 (steps, prerequisites, safety_warnings 등)
  const [sopDetail, setSopDetail] = useState<SopDetail | null>(null);
  const [sopDetailErr, setSopDetailErr] = useState<string | null>(null);

  // 선택된 SOP 의 자동 생성 퀴즈 (4지선다 N문항)
  const [sopQuiz, setSopQuiz] = useState<SopQuizResponse | null>(null);
  const [sopQuizErr, setSopQuizErr] = useState<string | null>(null);

  // selectedSopId 변경 시 detail + quiz 동시 fetch + sopStep 초기화
  useEffect(() => {
    if (!selectedSopId) {
      setSopDetail(null);
      setSopQuiz(null);
      return;
    }
    let cancelled = false;
    setSopDetailErr(null);
    setSopQuizErr(null);
    setSopStep(0);

    fetchSopDetail(selectedSopId)
      .then((d) => {
        if (!cancelled) setSopDetail(d);
      })
      .catch((e) => {
        if (!cancelled) {
          setSopDetail(null);
          setSopDetailErr(e instanceof Error ? e.message : String(e));
        }
      });

    fetchSopQuiz(selectedSopId, 3)
      .then((q) => {
        if (!cancelled) setSopQuiz(q);
      })
      .catch((e) => {
        if (!cancelled) {
          setSopQuiz(null);
          setSopQuizErr(e instanceof Error ? e.message : String(e));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedSopId]);

  // 퀴즈 탭 — 사용자 답안·점수 트래킹 (탭 진입 시 초기화)
  const [quizAnswers, setQuizAnswers] = useState<Record<number, number>>({});
  useEffect(() => {
    setQuizAnswers({});
  }, [selectedSopId]);

  // v3.6 — 동적 인사말 (사용자 정보 기반). 라우트 진입 시점의 user 로 1회 계산.
  // 빈 채팅 초기화·세션 리셋 등에서도 동일 인사말 재사용.
  // v3.6.1 — 동명이인 방어 + 사용자 전환 즉시 반영 위해 employee_id 도 deps 에 포함.
  const welcomeMsgs = useMemo(
    () => buildInitialMsgs(buildWelcomeMessage(user).text, nowHM()),
    // user 가 바뀌지 않는 한 동일 인사말 유지 — 의도적으로 nowHM() 도 1회만 생성
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [user?.employee_id, user?.username, user?.position, user?.department],
  );

  // v3.6 — localStorage 영속 (라우트 이동/새로고침 시 채팅 보존)
  // 첫 진입 (저장된 세션 없음 또는 다른 사용자의 세션) 시 환영 메시지로 시작.
  const [msgs, setMsgs] = useState<ChatMessage[]>(() => {
    const saved = loadChatSession<ChatMessage>(user?.employee_id)?.msgs;
    if (saved && saved.length > 0) return saved;
    const welcome = buildWelcomeMessage(user);
    return buildInitialMsgs(welcome.text, nowHM());
  });

  // v3.3 Phase A — 사용자가 강제 선택한 (provider, model). null = 자동 (LLMRouter 폴백).
  const [forceProvider, setForceProvider] = useState<ForceProvider | null>(loadForceProvider);

  // localStorage 영속 — 변경마다 즉시 저장. 자동(null)은 키 삭제.
  useEffect(() => {
    try {
      if (forceProvider) {
        localStorage.setItem(FORCE_PROVIDER_LS_KEY, JSON.stringify(forceProvider));
      } else {
        localStorage.removeItem(FORCE_PROVIDER_LS_KEY);
      }
    } catch {
      /* private mode 등 — 무시 */
    }
  }, [forceProvider]);

  // v3.3 Phase A-5 — 비교 모드 (이중창 Gemini ↔ Ollama).
  // 활성 시 같은 질문을 두 모델로 동시 호출하고 응답을 좌·우 패널에 병렬 스트리밍.
  // 기본 비활성 — 토큰 비용 2배라 명시적 토글 필요.
  const [compareMode, setCompareMode] = useState(false);
  const [compareProvider, setCompareProvider] = useState<ForceProvider | null>({
    provider: 'gemini',
    model: 'gemini-2.5-pro',
  });
  const [compareMsgs, setCompareMsgs] = useState<ChatMessage[]>(
    () => loadChatSession<ChatMessage>(user?.employee_id)?.compareMsgs ?? welcomeMsgs,
  );

  // 변경마다 영속 저장 (debounce 없음 — useState set 빈도가 낮아 불필요).
  // userId 를 함께 저장 → 다른 사용자 로그인 시 loadChatSession() 가 자동 폐기.
  useEffect(() => {
    saveChatSession<ChatMessage>(user?.employee_id, msgs, compareMsgs, sanitizeForPersist);
  }, [user?.employee_id, msgs, compareMsgs]);

  // v3.6.1 — SPA 내에서 로그아웃 → 다른 계정 로그인으로 user 가 바뀌었는데 Chat 컴포넌트가
  // unmount 되지 않은 경우, msgs/compareMsgs 가 직전 사용자의 환영 메시지를 그대로 안고 있다.
  // 이 effect 가 employee_id 변화를 감지해 즉시 새 사용자 인사말로 교체한다.
  useEffect(() => {
    if (lastUserIdRef.current === user?.employee_id) return;
    lastUserIdRef.current = user?.employee_id;
    const fresh = buildInitialMsgs(buildWelcomeMessage(user).text, nowHM());
    setMsgs(fresh);
    setCompareMsgs(fresh);
    clearChatSession();
  }, [user?.employee_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // v3.6 — 세션 삭제 (확인 모달 + Undo 토스트). 이전: 즉시 wipe 였음 → 실수 클릭 위험.
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const undoBackupRef = useRef<{ msgs: ChatMessage[]; compareMsgs: ChatMessage[] } | null>(null);
  const addToast = useToastStore((s) => s.addToast);

  // 사용자가 작성한 실제 대화 수 (welcomeMsgs 어시스턴트 인사 제외)
  const userMsgCount = useMemo(
    () =>
      msgs.filter((m) => m.role === 'user').length +
      compareMsgs.filter((m) => m.role === 'user').length,
    [msgs, compareMsgs],
  );

  // 스트리밍 중 여부는 sse/compareSSE 선언이 아래에 있어 클로저로만 접근 (TDZ 회피).
  const isStreamingRef = useRef(false);

  // 헤더 버튼 / 단축키 → 확인 모달 오픈
  const handleResetRequest = () => {
    if (isStreamingRef.current) return;
    if (userMsgCount === 0) {
      addToast({ type: 'info', message: '삭제할 채팅 기록이 없습니다.', duration: 2200 });
      return;
    }
    setShowResetConfirm(true);
  };

  // 모달 확인 → 실제 삭제 + Undo 가능한 토스트 표시
  const handleResetConfirm = () => {
    undoBackupRef.current = { msgs: [...msgs], compareMsgs: [...compareMsgs] };
    setMsgs(welcomeMsgs);
    setCompareMsgs(welcomeMsgs);
    clearChatSession();
    setShowResetConfirm(false);
    addToast({
      type: 'success',
      title: '채팅 기록이 삭제되었습니다',
      message: `${userMsgCount}개 대화가 비워졌습니다. 5초 이내에 되돌릴 수 있습니다.`,
      duration: 5000,
      action: {
        label: '되돌리기',
        onClick: () => {
          const b = undoBackupRef.current;
          if (!b) return;
          setMsgs(b.msgs);
          setCompareMsgs(b.compareMsgs);
          undoBackupRef.current = null;
          addToast({ type: 'info', message: '채팅 기록이 복구되었습니다.', duration: 2500 });
        },
      },
    });
    // 토스트 만료 후 백업 정리 — 메모리 누수 방지
    setTimeout(() => {
      undoBackupRef.current = null;
    }, 5500);
  };

  // 단축키 ⌘/Ctrl + Shift + Backspace
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'Backspace' || e.key === 'Delete')) {
        e.preventDefault();
        handleResetRequest();
      }
      // Esc → 모달 닫기
      if (e.key === 'Escape' && showResetConfirm) {
        setShowResetConfirm(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userMsgCount, showResetConfirm]);

  // v3.3 Phase D-4 — 동적 Quick Questions (부서/직급별 6 슬롯).
  const [quickQuestions, setQuickQuestions] = useState<QuickQuestionItem[]>([]);

  // 부서 변경 / 사용자 변경 시 자동 리페치
  useEffect(() => {
    let cancelled = false;
    void fetchQuickQuestions(dept).then((items) => {
      if (!cancelled) setQuickQuestions(items);
    });
    return () => {
      cancelled = true;
    };
  }, [dept, userLevel]);

  const activeMsgIdRef = useRef<string | null>(null);
  const compareActiveMsgIdRef = useRef<string | null>(null);

  // SSE — 백엔드 /api/onboarding/chat 응답 수신
  const sse = useSSE({
    onToken: (chunk) => {
      const id = activeMsgIdRef.current;
      if (!id) return;
      setMsgs((arr) =>
        arr.map((m) => (m.id === id ? { ...m, text: m.text + chunk } : m)),
      );
    },
    onMetadata: (meta) => {
      const id = activeMsgIdRef.current;
      if (!id) return;
      setMsgs((arr) =>
        arr.map((m) =>
          m.id === id
            ? {
                ...m,
                meta: {
                  ...(m.meta ?? { src: 'AUTO', conf: '—', latency: '...' }),
                  src: pickString(meta, 'source') ?? m.meta?.src ?? 'AUTO',
                  conf: pickString(meta, 'confidence') ?? m.meta?.conf ?? '—',
                  latency: pickString(meta, 'latency') ?? m.meta?.latency ?? '...',
                  provider: pickString(meta, 'provider', 'final_provider') ?? m.meta?.provider,
                  model: pickString(meta, 'model', 'final_model') ?? m.meta?.model,
                  ttftMs: pickNumber(meta, 'ttft_ms', 'ttftMs') ?? m.meta?.ttftMs,
                  totalLatencyMs:
                    pickNumber(meta, 'latency_ms', 'total_latency_ms', 'latencyMs') ??
                    m.meta?.totalLatencyMs,
                  tokensIn:
                    pickNumber(meta, 'tokens_in', 'input_tokens', 'prompt_tokens') ??
                    m.meta?.tokensIn,
                  tokensOut:
                    pickNumber(meta, 'tokens_out', 'output_tokens', 'completion_tokens') ??
                    m.meta?.tokensOut,
                },
              }
            : m,
        ),
      );
    },
    onDone: (final) => {
      const id = activeMsgIdRef.current;
      if (!id) return;
      setMsgs((arr) =>
        arr.map((m) =>
          m.id === id
            ? {
                ...m,
                streaming: false,
                meta: {
                  ...(m.meta ?? { src: 'AUTO', conf: '—', latency: '...' }),
                  src: pickString(final, 'source') ?? m.meta?.src ?? 'AUTO',
                  conf: pickString(final, 'confidence') ?? m.meta?.conf ?? '88%',
                  latency: pickString(final, 'latency') ?? m.meta?.latency ?? '124ms',
                  provider: pickString(final, 'provider', 'final_provider') ?? m.meta?.provider,
                  model: pickString(final, 'model', 'final_model') ?? m.meta?.model,
                  ttftMs: pickNumber(final, 'ttft_ms', 'ttftMs') ?? m.meta?.ttftMs,
                  totalLatencyMs:
                    pickNumber(final, 'latency_ms', 'total_latency_ms', 'latencyMs') ??
                    m.meta?.totalLatencyMs,
                  tokensIn:
                    pickNumber(final, 'tokens_in', 'input_tokens', 'prompt_tokens') ??
                    m.meta?.tokensIn,
                  tokensOut:
                    pickNumber(final, 'tokens_out', 'output_tokens', 'completion_tokens') ??
                    m.meta?.tokensOut,
                },
              }
            : m,
        ),
      );
      activeMsgIdRef.current = null;
      setUIStreaming(false);
    },
    // v3.3 Phase F-3 — 백엔드 액션 카드 이벤트 → 활성 메시지에 push
    onActionCard: (card) => {
      const id = activeMsgIdRef.current;
      if (!id) return;
      setMsgs((arr) =>
        arr.map((m) =>
          m.id === id
            ? { ...m, actionCards: [...(m.actionCards ?? []), card] }
            : m,
        ),
      );
    },
    onError: () => {
      const id = activeMsgIdRef.current;
      if (id) {
        // SSE 실패 시 mock 응답 시뮬레이션 (시연 안전)
        simulateMockResponse(id);
      }
      setUIStreaming(false);
    },
  });

  // v3.3 Phase A-5 — 비교 모드 두 번째 SSE 핸들러.
  // 같은 콜백 형태이지만 compareMsgs / compareActiveMsgIdRef 를 갱신.
  const compareSSE = useSSE({
    onToken: (chunk) => {
      const id = compareActiveMsgIdRef.current;
      if (!id) return;
      setCompareMsgs((arr) =>
        arr.map((m) => (m.id === id ? { ...m, text: m.text + chunk } : m)),
      );
    },
    onMetadata: (meta) => {
      const id = compareActiveMsgIdRef.current;
      if (!id) return;
      setCompareMsgs((arr) =>
        arr.map((m) =>
          m.id === id
            ? {
                ...m,
                meta: {
                  ...(m.meta ?? { src: 'AUTO', conf: '—', latency: '...' }),
                  src: pickString(meta, 'source') ?? m.meta?.src ?? 'AUTO',
                  conf: pickString(meta, 'confidence') ?? m.meta?.conf ?? '—',
                  latency: pickString(meta, 'latency') ?? m.meta?.latency ?? '...',
                  provider: pickString(meta, 'provider', 'final_provider') ?? m.meta?.provider,
                  model: pickString(meta, 'model', 'final_model') ?? m.meta?.model,
                  ttftMs: pickNumber(meta, 'ttft_ms', 'ttftMs') ?? m.meta?.ttftMs,
                  totalLatencyMs:
                    pickNumber(meta, 'latency_ms', 'total_latency_ms', 'latencyMs') ??
                    m.meta?.totalLatencyMs,
                  tokensIn:
                    pickNumber(meta, 'tokens_in', 'input_tokens', 'prompt_tokens') ??
                    m.meta?.tokensIn,
                  tokensOut:
                    pickNumber(meta, 'tokens_out', 'output_tokens', 'completion_tokens') ??
                    m.meta?.tokensOut,
                },
              }
            : m,
        ),
      );
    },
    onDone: (final) => {
      const id = compareActiveMsgIdRef.current;
      if (!id) return;
      setCompareMsgs((arr) =>
        arr.map((m) =>
          m.id === id
            ? {
                ...m,
                streaming: false,
                meta: {
                  ...(m.meta ?? { src: 'AUTO', conf: '—', latency: '...' }),
                  src: pickString(final, 'source') ?? m.meta?.src ?? 'AUTO',
                  conf: pickString(final, 'confidence') ?? m.meta?.conf ?? '88%',
                  latency: pickString(final, 'latency') ?? m.meta?.latency ?? '124ms',
                  provider: pickString(final, 'provider', 'final_provider') ?? m.meta?.provider,
                  model: pickString(final, 'model', 'final_model') ?? m.meta?.model,
                  ttftMs: pickNumber(final, 'ttft_ms', 'ttftMs') ?? m.meta?.ttftMs,
                  totalLatencyMs:
                    pickNumber(final, 'latency_ms', 'total_latency_ms', 'latencyMs') ??
                    m.meta?.totalLatencyMs,
                  tokensIn:
                    pickNumber(final, 'tokens_in', 'input_tokens', 'prompt_tokens') ??
                    m.meta?.tokensIn,
                  tokensOut:
                    pickNumber(final, 'tokens_out', 'output_tokens', 'completion_tokens') ??
                    m.meta?.tokensOut,
                },
              }
            : m,
        ),
      );
      compareActiveMsgIdRef.current = null;
    },
    // v3.3 Phase F-3 — 비교 모드 두 번째 패널의 액션 카드 (compareMsgs 에 push)
    onActionCard: (card) => {
      const id = compareActiveMsgIdRef.current;
      if (!id) return;
      setCompareMsgs((arr) =>
        arr.map((m) =>
          m.id === id
            ? { ...m, actionCards: [...(m.actionCards ?? []), card] }
            : m,
        ),
      );
    },
    onError: () => {
      const id = compareActiveMsgIdRef.current;
      if (id) simulateMockCompareResponse(id);
    },
  });

  // v3.6 — 채팅 기록 삭제 차단용 streaming 상태 동기화 (TDZ 회피).
  useEffect(() => {
    isStreamingRef.current = sse.isStreaming || compareSSE.isStreaming;
  }, [sse.isStreaming, compareSSE.isStreaming]);

  const simulateMockResponse = (msgId: string) => {
    const reply =
      mode === '교육'
        ? `교육 모드(컨텍스트 3,000자)로 답변드립니다. "${dept}" 부서 컨텍스트와 사내 SOP·용어집 297항목을 결합해 단계별로 설명합니다. 학습 종료 시 4지선다 퀴즈가 자동 생성됩니다.`
        : '업무 모드(컨텍스트 2,000자)로 즉답드립니다. 핵심 절차 + 양식 위치 + 마감 기한을 간결하게 안내합니다.';
    let i = 0;
    const tick = () => {
      i += 4;
      setMsgs((arr) =>
        arr.map((m) => (m.id === msgId ? { ...m, text: reply.slice(0, i) } : m)),
      );
      if (i < reply.length) {
        setTimeout(tick, 25);
      } else {
        const mockModel = forceProvider?.model ?? 'qwen3.5:9b';
        const mockProvider = forceProvider?.provider ?? 'ollama';
        setMsgs((arr) =>
          arr.map((m) =>
            m.id === msgId
              ? {
                  ...m,
                  streaming: false,
                  meta: {
                    src: 'MOCK',
                    conf: '88%',
                    latency: '124ms · 41 t/s',
                    provider: mockProvider,
                    model: mockModel,
                    ttftMs: 124,
                    totalLatencyMs: 980,
                    tokensIn: Math.round(reply.length / 3),
                    tokensOut: 41,
                  },
                }
              : m,
          ),
        );
        activeMsgIdRef.current = null;
        setUIStreaming(false);
      }
    };
    setTimeout(tick, 200);
  };

  // v3.3 Phase A-5 — 비교 모드 mock 응답. compareMsgs 갱신.
  const simulateMockCompareResponse = (msgId: string) => {
    const reply =
      mode === '교육'
        ? `(비교) 같은 질문에 대한 두 번째 모델의 응답입니다. ${dept} 컨텍스트 + 사내 지식. 동일 입력으로 답변 스타일·정확성·지연을 비교해 보세요.`
        : '(비교) 두 번째 모델의 즉답 — 핵심 절차 요약. 모델 간 답변 차이를 확인할 수 있습니다.';
    let i = 0;
    const tick = () => {
      i += 4;
      setCompareMsgs((arr) =>
        arr.map((m) => (m.id === msgId ? { ...m, text: reply.slice(0, i) } : m)),
      );
      if (i < reply.length) {
        setTimeout(tick, 25);
      } else {
        const mockModel = compareProvider?.model ?? 'gemini-2.5-pro';
        const mockProvider = compareProvider?.provider ?? 'gemini';
        setCompareMsgs((arr) =>
          arr.map((m) =>
            m.id === msgId
              ? {
                  ...m,
                  streaming: false,
                  meta: {
                    src: 'MOCK',
                    conf: '88%',
                    latency: '186ms · 38 t/s',
                    provider: mockProvider,
                    model: mockModel,
                    ttftMs: 186,
                    totalLatencyMs: 1240,
                    tokensIn: Math.round(reply.length / 3),
                    tokensOut: 38,
                  },
                }
              : m,
          ),
        );
        compareActiveMsgIdRef.current = null;
      }
    };
    setTimeout(tick, 200);
  };

  // v3.3 Phase D-4 — Quick Questions chip 클릭 시 즉시 send 가능하도록 textOverride 인자 지원.
  const send = (textOverride?: string) => {
    const raw = textOverride !== undefined ? textOverride : input;
    if (!raw.trim() || sse.isStreaming || compareSSE.isStreaming) return;
    const q = raw.trim();
    if (textOverride === undefined) setInput('');

    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: 'user', text: q, t: nowHM() };

    // 사용자 메시지 — 비교 모드면 양쪽 패널에 동일 표시
    setMsgs((arr) => [...arr, userMsg]);
    if (compareMode) {
      setCompareMsgs((arr) => [...arr, userMsg]);
    }

    // v3.3 Phase A-5 — 비교 모드에서는 단축 mock 응답을 건너뛴다 (LLM 응답 비교가 목적).
    // 단축 mock 은 일반 모드 + 업무 모드에서만 동작 (Phase E 에서 인-챗 액션으로 대체 예정).
    const isError = /(에러|코드|E-?\d)/i.test(q);
    const isPerson = /(부장|차장|어디|담당자)/i.test(q);
    const isSpc = /(spc|cpk|관리도|nelson)/i.test(q);
    if (!compareMode && mode === '업무' && (isError || isPerson || isSpc)) {
      const aiText = isError
        ? 'E-101 베어링 마모 · HIGH · 평균 복구 35분 · 이력 24건. Markov 후속: E-205 윤활부족 (0.62) → E-310 모터과열 (0.31).'
        : isPerson
        ? '품질보증팀 담당 차장 · 본사 · 내선 1234 · contact@ajin.com'
        : '5공정 Cpk: CCH 1.51 ● / OBC 1.18 ⚠ / 범퍼빔 0.89 ⛔ Rule 1·2·5 / 도어 1.62 ● / 볼시트 1.55 ●';
      setMsgs((arr) => [
        ...arr,
        {
          id: `a-${Date.now()}`,
          role: 'ai',
          text: aiText,
          t: nowHM(),
          meta: {
            src: isError ? 'ERROR_DB' : isPerson ? 'PEOPLE_SEARCH' : 'SPC_DASHBOARD',
            conf: '99%',
            latency: isError ? '12ms' : isPerson ? '8ms' : '15ms',
          },
          action: true,
        },
      ]);
      return;
    }

    // ── PRIMARY 패널 (forceProvider) — placeholder + SSE 시작 ──
    const aiId = `a-${Date.now()}`;
    activeMsgIdRef.current = aiId;
    setMsgs((arr) => [
      ...arr,
      {
        id: aiId,
        role: 'ai',
        text: '',
        streaming: true,
        t: nowHM(),
        meta: {
          src: 'AUTO',
          conf: '—',
          latency: '...',
          provider: forceProvider?.provider,
          model: forceProvider?.model,
        },
        paneSide: compareMode ? 'left' : undefined,
      },
    ]);
    setUIStreaming(true);

    void sse
      .start({
        url: buildChatUrl(),
        body: {
          query: q,
          mode,
          department: dept,
          language: 'ko',
          force_provider: forceProvider
            ? [forceProvider.provider, forceProvider.model]
            : null,
        },
      })
      .catch(() => simulateMockResponse(aiId));

    // ── COMPARE 패널 (compareProvider) — 비교 모드에서만 두 번째 호출 ──
    if (compareMode) {
      const compareId = `ac-${Date.now()}`;
      compareActiveMsgIdRef.current = compareId;
      setCompareMsgs((arr) => [
        ...arr,
        {
          id: compareId,
          role: 'ai',
          text: '',
          streaming: true,
          t: nowHM(),
          meta: {
            src: 'AUTO',
            conf: '—',
            latency: '...',
            provider: compareProvider?.provider,
            model: compareProvider?.model,
          },
          paneSide: 'right',
        },
      ]);

      void compareSSE
        .start({
          url: buildChatUrl(),
          body: {
            query: q,
            mode,
            department: dept,
            language: 'ko',
            force_provider: compareProvider
              ? [compareProvider.provider, compareProvider.model]
              : null,
          },
        })
        .catch(() => simulateMockCompareResponse(compareId));
    }
  };

  // 입력 자동 포커스 (모드/부서 변경 시 유지)
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    inputRef.current?.focus();
  }, [mode, dept]);

  // v3.3 Phase C-3 — 키보드 단축키: ⌘/Ctrl + Shift + M 으로 교육 ↔ 업무 토글
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === 'm') {
        e.preventDefault();
        setMode((cur) => (cur === '교육' ? '업무' : '교육'));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // 토큰/컨텍스트 mock 카운트
  const tokenStats = useMemo(() => {
    const total = mode === '교육' ? 3000 : 2000;
    const used = msgs.reduce((acc, m) => acc + Math.floor(m.text.length / 3), 0);
    return { used, total };
  }, [mode, msgs]);

  // v3.3 Phase A-5 — 메시지 버블 렌더 (compare 모드에서 msgs / compareMsgs 양쪽 재사용).
  const renderBubble = (m: ChatMessage) => (
    <div
      key={m.id}
      style={{
        alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
        maxWidth: '85%',
        padding: '12px 14px',
        borderRadius:
          m.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
        background:
          m.role === 'user'
            ? 'color-mix(in oklab, var(--hud-primary) 10%, transparent)'
            : m.action
            ? 'color-mix(in oklab, var(--hud-blue) 8%, transparent)'
            : 'color-mix(in oklab, var(--hud-surface) 70%, transparent)',
        border:
          '1px solid ' +
          (m.role === 'user'
            ? 'color-mix(in oklab, var(--hud-primary) 35%, transparent)'
            : 'color-mix(in oklab, var(--hud-text) 8%, transparent)'),
      }}
    >
      {m.meta && (
        <div
          className="mono"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            fontSize: 10,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--hud-text-dim)',
            marginBottom: 8,
            flexWrap: 'wrap',
          }}
        >
          <b style={{ color: 'var(--hud-text)' }}>
            {m.role === 'user' ? 'YOU · 김아진' : 'AI'}
          </b>
          {m.role === 'ai' && (m.meta.provider || m.meta.model) ? (
            <span
              style={{
                padding: '2px 8px',
                borderRadius: 999,
                fontFamily: 'var(--hud-font-mono)',
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: '0.08em',
                color: familyColor(familyOf(m.meta.model, m.meta.provider)),
                background:
                  'color-mix(in oklab, ' +
                  familyColor(familyOf(m.meta.model, m.meta.provider)) +
                  ' 14%, transparent)',
                border:
                  '1px solid color-mix(in oklab, ' +
                  familyColor(familyOf(m.meta.model, m.meta.provider)) +
                  ' 35%, transparent)',
              }}
              title={(m.meta.provider ?? '') + (m.meta.model ? ` / ${m.meta.model}` : '')}
            >
              {(m.meta.provider ?? '').toUpperCase()}
              {m.meta.model ? ` · ${formatModelLabel(m.meta.model)}` : ''}
            </span>
          ) : (
            <span style={{ color: 'var(--hud-primary)' }}>{m.meta.src}</span>
          )}
          {typeof m.meta.ttftMs === 'number' && (
            <span>TTFT {Math.round(m.meta.ttftMs)}ms</span>
          )}
          {typeof m.meta.totalLatencyMs === 'number' ? (
            <span>· {Math.round(m.meta.totalLatencyMs)}ms</span>
          ) : (
            m.meta.latency && m.meta.latency !== '...' && <span>· {m.meta.latency}</span>
          )}
          {(typeof m.meta.tokensIn === 'number' || typeof m.meta.tokensOut === 'number') && (
            <span>
              · {m.meta.tokensIn ?? 0}→{m.meta.tokensOut ?? 0}t
            </span>
          )}
          {m.meta.conf && m.meta.conf !== '—' && <span>· {m.meta.conf}</span>}
          <span style={{ marginLeft: 'auto' }}>{m.t}</span>
        </div>
      )}
      {/* v3.3 Phase F-2 — 인-챗 액션 카드 (텍스트 답변 위에 표시) */}
      {m.role === 'ai' && m.actionCards && m.actionCards.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {m.actionCards.map((card, idx) => (
            <ActionCardRouter
              key={`${m.id}-card-${idx}`}
              card={card}
              onOpen={(url) => {
                // v3.3 Phase F-4 — 외부 URL 은 풀 페이지, 내부는 SPA 내비게이션
                if (/^https?:\/\//i.test(url)) {
                  window.open(url, '_blank', 'noopener,noreferrer');
                } else {
                  navigate(url);
                }
              }}
              onLoginClick={() => navigate('/login')}
            />
          ))}
        </div>
      )}
      {/* v3.5 — AI 응답은 마크다운 렌더링, 사용자/액션 mock 응답은 plain text */}
      {m.role === 'ai' && !m.action && m.text ? (
        <div style={{ position: 'relative', color: 'var(--hud-text)' }}>
          <MarkdownRenderer content={m.text} variant="chat" />
          {m.streaming && (
            <span
              className="streaming-cursor"
              aria-hidden
              style={{ display: 'inline-block', width: 8, height: 14, marginLeft: 2 }}
            />
          )}
        </div>
      ) : (
        <div
          className={m.streaming ? 'streaming-cursor' : ''}
          style={{
            fontSize: 14,
            lineHeight: 1.65,
            color: 'var(--hud-text)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {m.text}
        </div>
      )}
      {m.role === 'ai' && !m.streaming && !m.action && m.text && (
        <div
          style={{
            display: 'flex',
            gap: 6,
            marginTop: 10,
            paddingTop: 10,
            borderTop:
              '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)',
            flexWrap: 'wrap',
          }}
        >
          {/* v3.6 — 응답 다운로드 (DOCX/XLSX/CSV/TXT). 이전엔 onClick 미구현으로 작동 안 했음. */}
          {(['docx', 'xlsx', 'csv', 'txt'] as DownloadFormat[]).map((fmt) => (
            <button
              key={fmt}
              className="lg-btn ghost sm"
              onClick={async () => {
                try {
                  const filename = `ajin-ai-${m.id}-${new Date().toISOString().slice(0, 10)}`;
                  await downloadResponse(m.text || '', fmt, filename);
                } catch (e) {
                  console.warn(`[chat-download] ${fmt} 실패:`, e);
                  alert(`${fmt.toUpperCase()} 다운로드 실패: ${e instanceof Error ? e.message : String(e)}`);
                }
              }}
              title={`${fmt.toUpperCase()} 형식으로 다운로드`}
            >
              ↓ {fmt.toUpperCase()}
            </button>
          ))}
          <button className="lg-btn ghost sm" title="좋아요">👍</button>
          <button className="lg-btn ghost sm" title="싫어요">👎</button>
        </div>
      )}
    </div>
  );

  return (
    <div className="page lg-page lg-chat-page" data-screen-label="C · AI Chat">
      {/* HERO */}
      <section className="lg-hero lg-hero-chat">
        <div className="lg-hero-eyebrow">AI WORK ASSISTANT · MODULE C</div>
        <div
          className="lg-chat-hero-row"
          style={{ display: 'flex', alignItems: 'flex-end', gap: 24, flexWrap: 'wrap' }}
        >
          <div style={{ flex: 1, minWidth: 300 }}>
            <h1 className="lg-display">AI 업무 도우미</h1>
            <p className="lg-sub">
              처음 입사하셨거나 모르는 업무가 있을 때, 사내 절차·용어·법규를 24시간 자유롭게 질문할 수 있는 AI 도우미. 부서별 SOP 8종과 협업 시나리오 5종을 안내하고, 교육 모드와 실무 모드로 상황에 맞춰 답변합니다.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            {/* v3.3 Phase B — 부서 컨텍스트: admin 만 자유 변경, 일반 사용자는 자물쇠 */}
            <div
              className={`lg-field ${!isAdmin ? 'lg-field-locked' : ''}`}
              style={{ minWidth: 180 }}
            >
              <label>
                부서 컨텍스트{!isAdmin && (
                  <span style={{ marginLeft: 6, fontSize: 9, opacity: 0.6 }}>(고정)</span>
                )}
              </label>
              {isAdmin ? (
                <select
                  value={dept}
                  onChange={(e) => {
                    const next = e.target.value;
                    // L=3 본부 경계 — 타 본부 시도는 무시 (방어적, optgroup disabled 와 중복)
                    if (!isExecutive && myDivision) {
                      const nextDiv = divisionOf(next);
                      if (nextDiv && nextDiv !== myDivision) return;
                    }
                    setDept(next);
                  }}
                  disabled={sse.isStreaming || compareSSE.isStreaming}
                >
                  {Object.entries(DEPTS_BY_DIVISION).map(([div, list]) => {
                    const blocked = !isExecutive && myDivision !== null && div !== myDivision;
                    return (
                      <optgroup
                        key={div}
                        label={blocked ? `${div} (본부 외)` : div}
                        disabled={blocked}
                      >
                        {list.map((d) => (
                          <option key={d} value={d} disabled={blocked}>
                            {d}
                          </option>
                        ))}
                      </optgroup>
                    );
                  })}
                  {/* user.department 이 미등록 부서면 fallback 옵션 추가 */}
                  {!ALL_DEPTS.includes(dept) && (
                    <option key={dept} value={dept}>
                      {dept}
                    </option>
                  )}
                </select>
              ) : (
                <select value={dept} disabled aria-readonly>
                  <option value={dept}>{dept}</option>
                </select>
              )}
            </div>
            {/* v3.3 Phase B — admin 시뮬레이션 배지 (자기 부서 외 선택 시) */}
            {isAdmin && user?.department && dept !== user.department && (
              <span
                className="lg-pill lg-pill-warn"
                style={{ alignSelf: 'flex-end', marginBottom: 10 }}
                title={`자기 부서 ${user.department} → ${dept} 시뮬레이션 중`}
              >
                [ADMIN] {dept} 시뮬레이션
              </span>
            )}
            {/* v3.3 Phase A — LLM 멀티 프로바이더 셀렉터 (PRIMARY) */}
            <ModelSelect
              value={forceProvider}
              onChange={setForceProvider}
              feature="onboarding"
              disabled={sse.isStreaming || compareSSE.isStreaming}
            />
            {/* v3.3 Phase A-5 — 비교 모드: 두 번째 ModelSelect (compareMode 활성 시만) */}
            {compareMode && (
              <ModelSelect
                value={compareProvider}
                onChange={setCompareProvider}
                feature="onboarding"
                disabled={sse.isStreaming || compareSSE.isStreaming}
              />
            )}
            {/* v3.3 Phase A-5 — 비교 모드 토글 */}
            <button
              type="button"
              onClick={() => setCompareMode((v) => !v)}
              disabled={sse.isStreaming || compareSSE.isStreaming}
              title={compareMode ? '비교 모드 끄기' : '같은 질문을 두 모델로 비교 (토큰 비용 2배)'}
              style={{
                padding: '9px 14px',
                borderRadius: 999,
                border: '1px solid color-mix(in oklab, var(--hud-text) 12%, transparent)',
                cursor: 'pointer',
                background: compareMode
                  ? 'color-mix(in oklab, var(--hud-primary) 18%, transparent)'
                  : 'transparent',
                color: compareMode ? 'var(--hud-primary)' : 'var(--hud-text-dim)',
                fontSize: 12,
                fontWeight: 600,
                fontFamily: 'var(--hud-font-mono)',
                letterSpacing: '0.04em',
                transition: 'all .15s',
              }}
            >
              {compareMode ? '◐ 비교 ON' : '◯ 비교 OFF'}
            </button>
            {/* v3.6 — 채팅 기록 삭제 (확인 모달 + Undo 토스트). 단축키 ⌘/Ctrl+Shift+Backspace */}
            <button
              type="button"
              onClick={handleResetRequest}
              disabled={(sse.isStreaming || compareSSE.isStreaming)}
              title={
                userMsgCount > 0
                  ? `채팅 기록 삭제 (${userMsgCount}개 대화) · ⌘/Ctrl+Shift+Backspace`
                  : '삭제할 채팅 기록이 없습니다'
              }
              aria-label="채팅 기록 삭제"
              style={{
                padding: '9px 14px',
                borderRadius: 999,
                border: `1px solid color-mix(in oklab, ${
                  userMsgCount > 0 ? 'var(--hud-red)' : 'var(--hud-text)'
                } 18%, transparent)`,
                cursor: (sse.isStreaming || compareSSE.isStreaming) ? 'not-allowed' : 'pointer',
                background: 'transparent',
                color: userMsgCount > 0 ? 'var(--hud-red)' : 'var(--hud-text-dim)',
                fontSize: 12,
                fontWeight: 600,
                fontFamily: 'var(--hud-font-mono)',
                letterSpacing: '0.04em',
                transition: 'all .15s',
                opacity: (sse.isStreaming || compareSSE.isStreaming) ? 0.4 : 1,
              }}
            >
              🗑 기록 삭제{userMsgCount > 0 ? ` (${userMsgCount})` : ''}
            </button>
            <div
              role="group"
              aria-label="챗 모드 전환 (교육/업무) — 단축키 ⌘/Ctrl+Shift+M"
              style={{
                display: 'inline-flex',
                gap: 4,
                padding: 4,
                borderRadius: 999,
                background: 'color-mix(in oklab, var(--hud-surface) 60%, transparent)',
                border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
              }}
            >
              {(['교육', '업무'] as ChatMode[]).map((m) => {
                const isActive = mode === m;
                return (
                  <button
                    key={m}
                    type="button"
                    role="switch"
                    aria-pressed={isActive}
                    aria-label={
                      m === '교육'
                        ? '교육 모드 (컨텍스트 3,000자, 좌측 SOP 패널 표시)'
                        : '업무 모드 (컨텍스트 2,000자, 챗 풀화면)'
                    }
                    title={`${m} 모드 — 단축키: ⌘/Ctrl+Shift+M`}
                    onClick={() => setMode(m)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: 999,
                      border: 0,
                      cursor: 'pointer',
                      background: isActive ? 'var(--hud-primary)' : 'transparent',
                      color: isActive ? 'var(--hud-bg)' : 'var(--hud-text-dim)',
                      fontSize: 12,
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      minWidth: 70,
                    }}
                  >
                    <b style={{ fontSize: 13 }}>{m}</b>
                    <i style={{ fontSize: 9, fontStyle: 'normal', opacity: 0.85 }}>
                      {m === '교육' ? '3,000자' : '2,000자'}
                    </i>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* QUICK QUESTIONS — v3.3 Phase D-4: 부서/직급별 동적 6 슬롯, 클릭 시 즉시 send */}
      <section className="lg-card lg-card-tight">
        <div className="lg-eyebrow">
          QUICK · {dept} · L{userLevel || 1} 추천 질문
          {quickQuestions.length === 0 && (
            <span style={{ marginLeft: 8, opacity: 0.5 }}>로딩…</span>
          )}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
          {quickQuestions.map((q) => (
            <button
              key={q.id}
              className="lg-chip"
              onClick={() => send(q.promptText)}
              disabled={sse.isStreaming || compareSSE.isStreaming}
              type="button"
              title={q.promptText}
              data-category={q.category}
            >
              {q.label}
            </button>
          ))}
        </div>
      </section>

      {/* v3.3 Phase C — 모드별 그리드:
           교육: lg-grid-1-2 (좌 SOP + 우 챗)
           업무: lg-grid-full (1컬럼 챗 풀화면, 좌측 패널 슬라이드 아웃) */}
      <div className={`lg-grid ${mode === '교육' ? 'lg-grid-1-2' : 'lg-grid-full'}`}>
        {/* ─── 좌(360px): SOP/협업/퀴즈 ─── lg-side-panel 클래스로 모드 전환 시 슬라이드.
             업무 모드에서는 lg-grid-full + 자체 CSS 가 transform: translateX(-110%) + pointer-events: none 으로 차단. */}
        <section
          className="lg-card lg-card-tight lg-side-panel"
          aria-hidden={mode === '업무'}
        >
          <div
            style={{
              display: 'flex',
              gap: 4,
              padding: 4,
              marginBottom: 14,
              borderRadius: 999,
              background: 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
              border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
            }}
          >
            {([
              { k: 'sop' as const, l: 'SOP 8' },
              { k: 'collab' as const, l: '협업 5' },
              { k: 'quiz' as const, l: '퀴즈' },
            ]).map((s) => (
              <button
                key={s.k}
                onClick={() => setView(s.k)}
                style={{
                  flex: 1,
                  padding: '7px 12px',
                  borderRadius: 999,
                  border: 0,
                  cursor: 'pointer',
                  background:
                    view === s.k ? 'var(--hud-primary)' : 'transparent',
                  color: view === s.k ? 'var(--hud-bg)' : 'var(--hud-text-dim)',
                  fontSize: 12,
                  fontWeight: 500,
                }}
              >
                {s.l}
              </button>
            ))}
          </div>

          {/* SOP — v3.6 동적: selectedSopId 기반으로 백엔드에서 fetch.
              미선택/실패 시 정적 SOP_STEPS (프레스 트라이) 폴백. */}
          {view === 'sop' && (() => {
            // 활성 데이터 소스 결정 (백엔드 우선, 폴백은 정적)
            const activeTitle = sopDetail?.title ?? '프레스 트라이';
            const activeDept = sopDetail?.department ?? '품질보증팀';
            const activeSteps = sopDetail?.steps ?? null;
            const totalSteps = activeSteps?.length ?? SOP_STEPS.length;
            const safeStep = Math.min(sopStep, totalSteps - 1);

            // 현재 step 데이터 (백엔드 vs 폴백 통합 형태)
            const stepData = activeSteps
              ? {
                  number: activeSteps[safeStep].step_number,
                  title: activeSteps[safeStep].title,
                  items: activeSteps[safeStep].checklist ?? [],
                  warn: activeSteps[safeStep].caution ?? '',
                  responsible: activeSteps[safeStep].responsible ?? '',
                  estimatedTime: activeSteps[safeStep].estimated_time ?? '',
                  relatedTerms: activeSteps[safeStep].related_terms ?? [],
                }
              : {
                  number: SOP_STEPS[safeStep].n,
                  title: SOP_STEPS[safeStep].title,
                  items: SOP_STEPS[safeStep].items,
                  warn: SOP_STEPS[safeStep].warn,
                  responsible: '',
                  estimatedTime: '',
                  relatedTerms: [] as string[],
                };

            return (
              <>
                <div className="lg-eyebrow">SOP · {activeTitle}</div>
                {sopDetail && (
                  <div style={{
                    display: 'inline-block',
                    marginTop: 4,
                    padding: '2px 8px',
                    borderRadius: 999,
                    fontSize: 11,
                    color: 'var(--hud-primary)',
                    background: 'color-mix(in oklab, var(--hud-primary) 12%, transparent)',
                    border: '1px solid color-mix(in oklab, var(--hud-primary) 30%, transparent)',
                  }}>
                    {activeDept}
                  </div>
                )}
                {sopDetailErr && (
                  <div style={{
                    marginTop: 6,
                    fontSize: 11,
                    color: 'var(--hud-orange)',
                  }}>
                    ⚠ 백엔드 미가용 — 폴백 표시 ({sopDetailErr})
                  </div>
                )}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: 12,
                    color: 'var(--hud-text-dim)',
                    margin: '8px 0 14px',
                  }}
                >
                  <span>Step {safeStep + 1}/{totalSteps}</span>
                  <div
                    style={{
                      flex: 1,
                      marginLeft: 12,
                      height: 4,
                      borderRadius: 999,
                      background: 'color-mix(in oklab, var(--hud-text) 8%, transparent)',
                      overflow: 'hidden',
                    }}
                  >
                    <span
                      style={{
                        display: 'block',
                        height: '100%',
                        width: ((safeStep + 1) / totalSteps) * 100 + '%',
                        background: 'var(--hud-primary)',
                        transition: 'width .3s ease',
                      }}
                    />
                  </div>
                </div>
                <div
                  style={{
                    padding: '14px 16px',
                    borderRadius: 14,
                    background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
                    border: '1px solid color-mix(in oklab, var(--hud-text) 10%, transparent)',
                  }}
                >
                  <div
                    style={{
                      fontSize: 15,
                      fontWeight: 600,
                      color: 'var(--hud-text)',
                      marginBottom: 10,
                    }}
                  >
                    Step {stepData.number} — {stepData.title}
                  </div>
                  {/* v3.6 — 담당자·예상 소요시간 메타 (백엔드 SOP 만 제공) */}
                  {(stepData.responsible || stepData.estimatedTime) && (
                    <div style={{
                      display: 'flex',
                      gap: 12,
                      marginBottom: 10,
                      fontSize: 11,
                      color: 'var(--hud-text-muted)',
                    }}>
                      {stepData.responsible && (
                        <span>👤 담당: <strong style={{ color: 'var(--hud-text-dim)' }}>{stepData.responsible}</strong></span>
                      )}
                      {stepData.estimatedTime && (
                        <span>⏱ 예상: <strong style={{ color: 'var(--hud-text-dim)' }}>{stepData.estimatedTime}</strong></span>
                      )}
                    </div>
                  )}
                  <ul
                    style={{
                      paddingLeft: 18,
                      margin: 0,
                      fontSize: 13,
                      lineHeight: 1.7,
                      color: 'var(--hud-text)',
                    }}
                  >
                    {stepData.items.map((it: string) => (
                      <li key={it}>{it}</li>
                    ))}
                  </ul>
                  {stepData.warn && (
                    <div
                      style={{
                        marginTop: 10,
                        padding: '8px 10px',
                        borderRadius: 8,
                        background: 'color-mix(in oklab, var(--hud-orange) 12%, transparent)',
                        border: '1px dashed color-mix(in oklab, var(--hud-orange) 30%, transparent)',
                        fontSize: 12,
                        color: 'var(--hud-orange)',
                      }}
                    >
                      ⚠ {stepData.warn}
                    </div>
                  )}
                  {/* v3.6 — 관련 용어 (있으면 표시) */}
                  {stepData.relatedTerms && stepData.relatedTerms.length > 0 && (
                    <div style={{
                      marginTop: 10,
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 6,
                    }}>
                      {stepData.relatedTerms.map((term: string) => (
                        <span key={term} style={{
                          fontSize: 11,
                          padding: '2px 8px',
                          borderRadius: 999,
                          background: 'color-mix(in oklab, var(--hud-text) 6%, transparent)',
                          color: 'var(--hud-text-dim)',
                          border: '1px solid color-mix(in oklab, var(--hud-text) 12%, transparent)',
                        }}>
                          # {term}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                  <button
                    className="lg-btn ghost sm"
                    disabled={safeStep === 0}
                    onClick={() => setSopStep((s) => Math.max(0, s - 1))}
                  >
                    ◀ 이전
                  </button>
                  <button
                    className="lg-btn sm"
                    onClick={() => setSopStep((s) => Math.min(totalSteps - 1, s + 1))}
                    disabled={safeStep >= totalSteps - 1}
                  >
                    다음 ▶
                  </button>
                  <button className="lg-btn ghost sm" onClick={() => setView('quiz')}>
                    퀴즈
                  </button>
                </div>

              <div style={{ marginTop: 18 }}>
                <div className="lg-eyebrow" style={{ marginBottom: 8 }}>
                  SOP 8종
                </div>
                {/* v3.6 — 백엔드에서 부서별 필터링된 SOP 목록을 클릭 가능 버튼으로 렌더.
                    클릭 시 채팅창에 "{SOP명} 알려줘" 자동 입력 + 전송. */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {sopList.map((sop, i) => {
                    const isSelected = sop.sop_id === selectedSopId;
                    return (
                      <button
                        key={sop.sop_id}
                        onClick={() => {
                          // v3.6 — 패널 전환만 수행 (채팅 자동 질문 제거).
                          // 상단 SOP 가이드 패널을 이 SOP 로 교체 (selectedSopId 변경 → useEffect 가
                          // detail+quiz 자동 fetch). 채팅은 사용자가 직접 입력하도록 분리.
                          setSelectedSopId(sop.sop_id);
                          setSopStep(0);
                          setView('sop');
                        }}
                        title={`${sop.title} (${sop.department}, ${sop.steps_count}단계) — 클릭하면 상단 가이드와 퀴즈가 이 SOP 로 전환됩니다`}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          padding: '8px 12px',
                          borderRadius: 8,
                          fontSize: 12,
                          background: isSelected
                            ? 'color-mix(in oklab, var(--hud-primary) 14%, transparent)'
                            : 'transparent',
                          color: isSelected ? 'var(--hud-primary)' : 'var(--hud-text-dim)',
                          border: isSelected
                            ? '1px solid color-mix(in oklab, var(--hud-primary) 40%, transparent)'
                            : '1px solid transparent',
                          cursor: 'pointer',
                          textAlign: 'left',
                          transition: 'background 0.15s, color 0.15s, border 0.15s',
                          fontWeight: isSelected ? 600 : 400,
                        }}
                        onMouseEnter={(e) => {
                          if (isSelected) return;
                          e.currentTarget.style.background =
                            'color-mix(in oklab, var(--hud-primary) 8%, transparent)';
                          e.currentTarget.style.color = 'var(--hud-primary)';
                          e.currentTarget.style.borderColor =
                            'color-mix(in oklab, var(--hud-primary) 24%, transparent)';
                        }}
                        onMouseLeave={(e) => {
                          if (isSelected) return;
                          e.currentTarget.style.background = 'transparent';
                          e.currentTarget.style.color = 'var(--hud-text-dim)';
                          e.currentTarget.style.borderColor = 'transparent';
                        }}
                      >
                        <span className="mono" style={{ fontSize: 11 }}>
                          {String(i + 1).padStart(2, '0')}
                        </span>
                        <span style={{ flex: 1 }}>{sop.title}</span>
                        <span
                          style={{
                            fontSize: 10,
                            opacity: 0.7,
                            color: isSelected ? 'var(--hud-primary)' : 'var(--hud-text-muted)',
                          }}
                        >
                          {sop.steps_count}단계
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </>
            );
          })()}

          {/* COLLAB */}
          {view === 'collab' && (
            <>
              <div className="lg-eyebrow">협업 시나리오 5종</div>
              <h3
                className="lg-h2"
                style={{ fontSize: 18, marginTop: 6, marginBottom: 14 }}
              >
                트리거 → 부서 → 절차
              </h3>
              {/* v3.6 — 협업 시나리오 카드 클릭 가능. 클릭 시 트리거 문장을 자동 전송하여
                  LLM 이 collaboration_guide.match_collaboration() 으로 시나리오 매칭. */}
              {collabList.map((s) => (
                <button
                  key={s.trig}
                  onClick={() => send(`"${s.trig}" 같은 상황에서 어떻게 협업해야 해?`)}
                  title={`"${s.trig}" 시나리오 — 클릭하면 전체 절차 안내`}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 12,
                    background: 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
                    border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
                    marginBottom: 10,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                    cursor: 'pointer',
                    textAlign: 'left',
                    width: '100%',
                    transition: 'background 0.15s, border 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background =
                      'color-mix(in oklab, var(--hud-primary) 8%, transparent)';
                    e.currentTarget.style.borderColor = 'var(--hud-primary)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background =
                      'color-mix(in oklab, var(--hud-text) 4%, transparent)';
                    e.currentTarget.style.borderColor =
                      'color-mix(in oklab, var(--hud-text) 8%, transparent)';
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--hud-text)' }}>
                    "{s.trig}"
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--hud-primary)' }}>
                    → {s.dept}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--hud-text-dim)', lineHeight: 1.6 }}>
                    {s.steps}
                  </div>
                  <div
                    className="mono"
                    style={{
                      fontSize: 11,
                      color: 'var(--hud-orange)',
                      marginTop: 4,
                    }}
                  >
                    ⏱ {s.deadline}
                  </div>
                </button>
              ))}
            </>
          )}

          {/* QUIZ — v3.6 동적: selectedSopId 기반 백엔드 퀴즈 (quiz_engine.generate_sop_quiz).
              미가용/미선택 시 정적 QUIZ_Q (산안법 안전거리) 폴백. */}
          {view === 'quiz' && (() => {
            const dynQs = sopQuiz?.questions ?? [];
            const useDynamic = dynQs.length > 0;

            return (
              <>
                <div className="lg-eyebrow">
                  QUIZ · {useDynamic ? sopQuiz?.title : '자동 생성'}
                </div>
                {sopQuizErr && (
                  <div style={{
                    marginTop: 6,
                    fontSize: 11,
                    color: 'var(--hud-orange)',
                  }}>
                    ⚠ 백엔드 미가용 — 정적 폴백 표시 ({sopQuizErr})
                  </div>
                )}

                {useDynamic ? (
                  // 동적 퀴즈 — 여러 문항 표시
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 18, marginTop: 12 }}>
                    {dynQs.map((q, qi) => {
                      const userAnswer = quizAnswers[qi];
                      const answered = userAnswer !== undefined;
                      return (
                        <div key={qi}>
                          <h3 style={{
                            fontSize: 14,
                            fontWeight: 600,
                            margin: '0 0 10px 0',
                            lineHeight: 1.5,
                            color: 'var(--hud-text)',
                          }}>
                            <span style={{ color: 'var(--hud-primary)', marginRight: 6 }}>
                              Q{qi + 1}.
                            </span>
                            {q.question}
                          </h3>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            {q.options.map((opt, oi) => {
                              const isCorrect = oi === q.correct_index;
                              const isPicked = userAnswer === oi;
                              const showResult = answered;
                              return (
                                <button
                                  key={oi}
                                  onClick={() =>
                                    setQuizAnswers((prev) => ({ ...prev, [qi]: oi }))
                                  }
                                  disabled={answered}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 12,
                                    padding: '10px 14px',
                                    borderRadius: 10,
                                    cursor: answered ? 'default' : 'pointer',
                                    textAlign: 'left',
                                    background: showResult && isCorrect
                                      ? 'color-mix(in oklab, var(--hud-green) 14%, transparent)'
                                      : showResult && isPicked && !isCorrect
                                        ? 'color-mix(in oklab, var(--hud-red) 12%, transparent)'
                                        : 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
                                    border: '1px solid ' + (
                                      showResult && isCorrect
                                        ? 'color-mix(in oklab, var(--hud-green) 40%, transparent)'
                                        : showResult && isPicked && !isCorrect
                                          ? 'color-mix(in oklab, var(--hud-red) 40%, transparent)'
                                          : 'color-mix(in oklab, var(--hud-text) 10%, transparent)'
                                    ),
                                    color: showResult && isCorrect
                                      ? 'var(--hud-green)'
                                      : showResult && isPicked && !isCorrect
                                        ? 'var(--hud-red)'
                                        : 'var(--hud-text)',
                                    fontSize: 13,
                                    transition: 'background 0.15s, border 0.15s',
                                  }}
                                >
                                  <span className="mono" style={{ fontWeight: 700, fontSize: 13 }}>
                                    {String.fromCharCode(65 + oi)}
                                  </span>
                                  <span style={{ flex: 1 }}>{opt}</span>
                                  {showResult && isCorrect && (
                                    <span className="mono" style={{ fontSize: 11, fontWeight: 600 }}>
                                      정답 ✓
                                    </span>
                                  )}
                                  {showResult && isPicked && !isCorrect && (
                                    <span className="mono" style={{ fontSize: 11, fontWeight: 600 }}>
                                      오답 ✗
                                    </span>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                          {answered && (
                            <div style={{
                              marginTop: 8,
                              padding: '10px 12px',
                              borderRadius: 10,
                              background: 'color-mix(in oklab, var(--hud-primary) 8%, transparent)',
                              border: '1px dashed color-mix(in oklab, var(--hud-primary) 24%, transparent)',
                              fontSize: 12,
                              color: 'var(--hud-text-dim)',
                              lineHeight: 1.55,
                            }}>
                              💡 {q.explanation}
                            </div>
                          )}
                          {q.related_step > 0 && (
                            <button
                              className="lg-btn ghost sm"
                              style={{ marginTop: 8 }}
                              onClick={() => {
                                setSopStep(Math.max(0, q.related_step - 1));
                                setView('sop');
                              }}
                            >
                              ↩ Step {q.related_step} 다시 보기
                            </button>
                          )}
                        </div>
                      );
                    })}
                    {/* 점수 요약 */}
                    {Object.keys(quizAnswers).length === dynQs.length && (
                      <div style={{
                        marginTop: 6,
                        padding: '12px 14px',
                        borderRadius: 12,
                        background: 'color-mix(in oklab, var(--hud-primary) 14%, transparent)',
                        border: '1px solid var(--hud-primary)',
                        fontSize: 14,
                        fontWeight: 600,
                        color: 'var(--hud-primary)',
                        textAlign: 'center',
                      }}>
                        🎯 점수: {dynQs.filter((q, i) => quizAnswers[i] === q.correct_index).length} / {dynQs.length}
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        className="lg-btn ghost sm"
                        onClick={() => setQuizAnswers({})}
                      >
                        🔄 다시 풀기
                      </button>
                      <button
                        className="lg-btn ghost sm"
                        onClick={() => setView('sop')}
                      >
                        ← SOP 가이드로
                      </button>
                    </div>
                  </div>
                ) : (
                  // 폴백 — 정적 QUIZ_Q (백엔드 미가용 또는 SOP 미선택 시)
                  <>
                    <h3 className="lg-h2"
                      style={{ fontSize: 16, marginTop: 6, marginBottom: 14, lineHeight: 1.4 }}
                    >
                      {QUIZ_Q.q}
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {QUIZ_Q.options.map((o) => (
                        <button
                          key={o.k}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 12,
                            padding: '10px 14px',
                            borderRadius: 10,
                            cursor: 'pointer',
                            textAlign: 'left',
                            background: o.ok
                              ? 'color-mix(in oklab, var(--hud-green) 14%, transparent)'
                              : 'color-mix(in oklab, var(--hud-text) 4%, transparent)',
                            border: '1px solid ' + (o.ok
                              ? 'color-mix(in oklab, var(--hud-green) 40%, transparent)'
                              : 'color-mix(in oklab, var(--hud-text) 10%, transparent)'),
                            color: o.ok ? 'var(--hud-green)' : 'var(--hud-text)',
                            fontSize: 13,
                          }}
                        >
                          <span className="mono" style={{ fontWeight: 700, fontSize: 13 }}>
                            {o.k}
                          </span>
                          <span style={{ flex: 1 }}>{o.t}</span>
                          {o.ok && (
                            <span className="mono" style={{ fontSize: 11, fontWeight: 600 }}>
                              정답 ✓
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                    <div style={{
                      marginTop: 14,
                      padding: '10px 12px',
                      borderRadius: 10,
                      background: 'color-mix(in oklab, var(--hud-primary) 8%, transparent)',
                      border: '1px dashed color-mix(in oklab, var(--hud-primary) 24%, transparent)',
                      fontSize: 12,
                      color: 'var(--hud-text-dim)',
                      lineHeight: 1.55,
                    }}>
                      {QUIZ_Q.explain}
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                      <button
                        className="lg-btn ghost sm"
                        onClick={() => {
                          setSopStep(QUIZ_Q.related - 1);
                          setView('sop');
                        }}
                      >
                        ↩ Step {QUIZ_Q.related} 다시
                      </button>
                    </div>
                  </>
                )}
              </>
            );
          })()}
        </section>

        {/* ─── 우(flex): 채팅 스트림 ─── lg-chat-pane: 업무 모드(lg-grid-full)에서 max-width:1280px 중앙정렬 */}
        <section className="lg-card lg-chat-pane">
          <div className="lg-card-h">
            <div>
              <div className="lg-eyebrow">CHAT · {dept.toUpperCase()} · {mode.toUpperCase()}</div>
              <h2 className="lg-h2">세션 #A47-2026</h2>
            </div>
            <span
              className="lg-pill"
              style={{ color: sse.isStreaming ? 'var(--hud-orange)' : '#7FD89E' }}
            >
              {sse.isStreaming ? '● STREAMING' : '● LIVE'}
            </span>
          </div>

          {/* v3.3 Phase A-5 — 메시지 스트림: compareMode면 좌·우 2 컬럼, 아니면 단일 */}
          {compareMode ? (
            <div className="lg-grid lg-grid-compare">
              <div>
                <div
                  className="lg-eyebrow"
                  style={{
                    marginBottom: 8,
                    color: familyColor(
                      familyOf(forceProvider?.model, forceProvider?.provider),
                    ),
                  }}
                >
                  PRIMARY · {forceProvider ? formatModelLabel(forceProvider.model) : 'AUTO'}
                </div>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 14,
                    maxHeight: 520,
                    overflowY: 'auto',
                    padding: '4px 2px',
                  }}
                >
                  {msgs.map(renderBubble)}
                </div>
              </div>
              <div>
                <div
                  className="lg-eyebrow"
                  style={{
                    marginBottom: 8,
                    color: familyColor(
                      familyOf(compareProvider?.model, compareProvider?.provider),
                    ),
                  }}
                >
                  COMPARE · {compareProvider ? formatModelLabel(compareProvider.model) : 'AUTO'}
                </div>
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 14,
                    maxHeight: 520,
                    overflowY: 'auto',
                    padding: '4px 2px',
                  }}
                >
                  {compareMsgs.map(renderBubble)}
                </div>
              </div>
            </div>
          ) : (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
                maxHeight: 520,
                overflowY: 'auto',
                padding: '4px 2px',
              }}
            >
              {msgs.map(renderBubble)}
            </div>
          )}

          {/* 메타 바 — v3.3 Phase C-2: 업무 모드에서는 미니 칩으로 압축 */}
          <div
            className="mono"
            style={{
              display: 'flex',
              gap: mode === '교육' ? 12 : 8,
              padding: mode === '교육' ? '10px 0' : '6px 12px',
              fontSize: mode === '교육' ? 11 : 10,
              color: 'var(--hud-text-dim)',
              letterSpacing: '0.06em',
              borderTop:
                mode === '교육'
                  ? '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)'
                  : 'none',
              borderBottom:
                mode === '교육'
                  ? '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)'
                  : '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
              borderRadius: mode === '교육' ? 0 : 999,
              background:
                mode === '교육'
                  ? 'transparent'
                  : 'color-mix(in oklab, var(--hud-surface) 50%, transparent)',
              margin: mode === '교육' ? '14px 0 12px' : '10px 0 8px',
              flexWrap: mode === '교육' ? 'wrap' : 'nowrap',
              overflowX: mode === '업무' ? 'auto' : undefined,
              alignSelf: mode === '업무' ? 'flex-start' : undefined,
            }}
          >
            <span>
              토큰 <b>{tokenStats.used}</b>/{tokenStats.total.toLocaleString()}
            </span>
            <span>·</span>
            <span>
              컨텍스트 <b>{Math.min(msgs.length, 6)}턴</b>
            </span>
            <span>·</span>
            <span>
              모델 <b>{forceProvider ? formatModelLabel(forceProvider.model) : 'AUTO'}</b>
            </span>
            {mode === '교육' && (
              <>
                <span>·</span>
                <span>
                  의도 분류 <b>5ms</b>
                </span>
              </>
            )}
          </div>

          {/* COMPOSER */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              borderRadius: 16,
              background: 'color-mix(in oklab, var(--hud-surface) 70%, transparent)',
              border: '1px solid color-mix(in oklab, var(--hud-text) 8%, transparent)',
              backdropFilter: 'blur(20px)',
            }}
          >
            <button
              type="button"
              className="lg-btn ghost sm"
              style={{ borderRadius: 999, padding: '6px 10px' }}
              title="첨부 (PDF/DOCX/이미지)"
            >
              📎
            </button>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={
                sse.isStreaming
                  ? 'AI가 응답을 생성하고 있습니다...'
                  : '질문을 입력하세요... (PDF/DOCX/이미지 첨부 가능, 최대 20MB)'
              }
              disabled={sse.isStreaming}
              style={{
                flex: 1,
                background: 'transparent',
                border: 0,
                outline: 'none',
                fontSize: 14,
                color: 'var(--hud-text)',
                padding: '8px 6px',
              }}
            />
            <button
              type="button"
              className="lg-btn"
              onClick={() => send()}
              disabled={sse.isStreaming || !input.trim()}
              style={{ borderRadius: 999 }}
            >
              {sse.isStreaming ? '생성중…' : '전송 ↑'}
            </button>
          </div>
        </section>
      </div>

      {/* v3.6 — 채팅 기록 삭제 확인 모달 */}
      {showResetConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="reset-modal-title"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowResetConfirm(false);
          }}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'color-mix(in oklab, #000 55%, transparent)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 24,
          }}
        >
          <div
            style={{
              background: 'var(--hud-surface)',
              border: '1px solid color-mix(in oklab, var(--hud-red) 30%, transparent)',
              borderRadius: 16,
              padding: '24px 28px',
              maxWidth: 420,
              width: '100%',
              boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
            }}
          >
            <h3
              id="reset-modal-title"
              style={{
                margin: '0 0 12px',
                fontSize: 16,
                fontWeight: 700,
                color: 'var(--hud-red)',
                fontFamily: 'var(--hud-font-mono)',
                letterSpacing: '0.04em',
              }}
            >
              🗑 채팅 기록 삭제
            </h3>
            <p style={{ margin: '0 0 8px', fontSize: 13, color: 'var(--hud-text)', lineHeight: 1.6 }}>
              현재 <strong style={{ color: 'var(--hud-red)' }}>{userMsgCount}개</strong>의 대화가 저장되어 있습니다.
            </p>
            <p
              style={{
                margin: '0 0 20px',
                fontSize: 12,
                color: 'var(--hud-text-dim)',
                lineHeight: 1.6,
              }}
            >
              브라우저에 저장된 모든 채팅 기록이 삭제됩니다. 삭제 직후 5초 이내에는 토스트 메시지의{' '}
              <strong>되돌리기</strong> 버튼으로 복구할 수 있습니다.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setShowResetConfirm(false)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 999,
                  border: '1px solid color-mix(in oklab, var(--hud-text) 18%, transparent)',
                  background: 'transparent',
                  color: 'var(--hud-text)',
                  fontSize: 12,
                  fontWeight: 600,
                  fontFamily: 'var(--hud-font-mono)',
                  letterSpacing: '0.04em',
                  cursor: 'pointer',
                }}
              >
                취소
              </button>
              <button
                type="button"
                onClick={handleResetConfirm}
                autoFocus
                style={{
                  padding: '8px 16px',
                  borderRadius: 999,
                  border: '1px solid var(--hud-red)',
                  background: 'color-mix(in oklab, var(--hud-red) 18%, transparent)',
                  color: 'var(--hud-red)',
                  fontSize: 12,
                  fontWeight: 700,
                  fontFamily: 'var(--hud-font-mono)',
                  letterSpacing: '0.04em',
                  cursor: 'pointer',
                }}
              >
                삭제
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
