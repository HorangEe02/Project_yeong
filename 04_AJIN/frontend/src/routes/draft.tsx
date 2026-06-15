// draft.tsx — canonical uiux/web_app/Draft.jsx 의 lg-* Liquid Glass 마크업.
// API 연동 (Phase 2~3): 9 endpoints — 응답 실패 시 mock fallback (Equipment 패턴 동일).
// Phase 2: 기본 UI + 3탭 + selector + SSE 스트리밍 + 7포맷 다운로드 + 품질/CC/Diff 카드.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { useUIStore, type DraftPageTab } from '@store/ui';
import { useDraftStore } from '@store/draft';
import { useAuthStore } from '@store/auth';
import { useToast } from '@store/toast';
import { useSSE } from '@hooks/useSSE';
import { useIsMobile } from '@hooks/useBreakpoint';
import { AJINMobileDraft } from '@components/uikit/AJINMobileDraft';
import {
  fetchDocTypes,
  recommendCC,
  scoreQuality,
  computeDiff,
  buildStreamV2Request,
  fetchDiagnose,
  fetchLlmOptions,
  prefillTemplate,
  uploadReference,
} from '@api/draft';
import type {
  DiagnoseResponse,
  DocCategory,
  DocTypeMeta,
  LLMOption,
  LLMProvider,
  UploadReferenceResponse,
} from '@/types/draft';
import { formatDraftOutput } from '@lib/formatDraftOutput';
import { DownloadActions } from '@components/common/DownloadActions';
import { autoPersistDraft, loadHistory, deleteDraft as firestoreDeleteDraft } from '@lib/firestore-draft';
import { TemplateCard } from '@components/draft/TemplateCard';
import { TemplateUploadCard } from '@components/draft/TemplateUploadCard';
import { VariableForm } from '@components/draft/VariableForm';
import { DraftBodyView } from '@components/draft/DraftBodyView';
import { VersionTimeline } from '@components/draft/VersionTimeline';
import { MailSendModal } from '@components/draft/MailSendModal';
import { ModelHelpPopover } from '@components/common/ModelHelpPopover';
import { ModelSelect } from '@components/chat/ModelSelect';
import type { DraftDocument } from '@/types/draft';

// ──────────────────────────────────────────────────────────────────
// Mock fallback (canonical Draft.jsx 일치)
// ──────────────────────────────────────────────────────────────────

const MOCK_DOC_TYPES: DocTypeMeta[] = [
  { id: '8d_report',   category: 'external', name_ko: '8D Report',       name_en: '8D Report',       required_fields: ['title', 'issue', 'team'] },
  { id: 'ecn',         category: 'external', name_ko: 'ECN',             name_en: 'ECN',             required_fields: ['title', 'change_reason'] },
  { id: 'ppap',        category: 'external', name_ko: 'PPAP',            name_en: 'PPAP',            required_fields: ['part_number', 'level'] },
  { id: 'fmea',        category: 'external', name_ko: 'FMEA',            name_en: 'FMEA',            required_fields: ['process', 'risk'] },
  { id: 'msa',         category: 'external', name_ko: 'MSA',             name_en: 'MSA',             required_fields: ['instrument', 'study_type'] },
  { id: 'oem_email',   category: 'external', name_ko: 'OEM 영문 이메일', name_en: 'OEM Email',       required_fields: ['recipient', 'subject'] },
  { id: 'internal_email', category: 'internal', name_ko: '사내 이메일',   name_en: 'Internal Email',  required_fields: ['recipient', 'subject'] },
  { id: 'meeting_min',    category: 'internal', name_ko: '회의록',       name_en: 'Meeting Minutes', required_fields: ['date', 'attendees'] },
  { id: 'weekly_report',  category: 'internal', name_ko: '주간 보고',     name_en: 'Weekly Report',   required_fields: ['week', 'summary'] },
  { id: 'leave_request',          category: 'internal', name_ko: '휴가 신청서',     name_en: 'Leave Request',         required_fields: ['start_date', 'reason'] },
  { id: 'business_trip_request',  category: 'internal', name_ko: '출장 신청서',     name_en: 'Business Trip Request', required_fields: ['destination', 'purpose'] },
  { id: 'resignation_letter',     category: 'internal', name_ko: '사직서',          name_en: 'Resignation Letter',    required_fields: ['last_work_date', 'reason'] },
  { id: 'personnel_notice',       category: 'internal', name_ko: '인사발령 통지',   name_en: 'Personnel Notice',      required_fields: ['target_employee', 'effective_date'] },
  { id: 'quote',                  category: 'internal', name_ko: '견적서',          name_en: 'Quote',                 required_fields: ['customer', 'items'] },
  { id: 'travel_report',          category: 'internal', name_ko: '출장 보고서',     name_en: 'Travel Report',         required_fields: ['destination', 'purpose'] },
  { id: 'spc_report',             category: 'internal', name_ko: 'SPC Report',     name_en: 'SPC Report',            required_fields: ['process', 'period'] },
];

const TONES = [
  { id: 'formal_internal', ko: '격식 (사내)', en: 'Formal (Internal)' },
  { id: 'formal_external', ko: '격식 (외부)', en: 'Formal (External)' },
  { id: 'standard',        ko: '표준',         en: 'Standard' },
  { id: 'friendly',        ko: '친근',         en: 'Friendly' },
  { id: 'concise',         ko: '간결',         en: 'Concise' },
] as const;

// EXPORT_FORMATS 상수 → DownloadActions 의 source="draft" 프리셋으로 대체.
// frontend/src/types/export.ts FORMAT_PRESETS.draft = ['docx','pdf','hwp','hwpx','odt','xlsx','csv','txt','clipboard']

// canonical Draft.jsx 의 sample (mock 시연용)
const MOCK_SAMPLE = `## PPAP Level 3 제출 안내

수신: 현대자동차 SQ팀
발신: 아진산업 품질보증팀

안녕하십니까. 아진산업 품질보증팀입니다.

귀사 신차 양산 일정에 따라 부품번호 [부품번호] 의 PPAP Level 3 제출을 안내드립니다.
포함 문서: PSW, FMEA, Control Plan, MSA, Capability Study, Sample.
제출 기한: __날짜__.

감사합니다.`;

// canonical Draft.jsx 의 mock few-shot RAG
const MOCK_FEWSHOT = [
  { name: 'PPAP_2025_Q4_001.docx', score: 0.91 },
  { name: 'PPAP_2025_Q3_007.docx', score: 0.87 },
  { name: 'PPAP_2024_BUMPER.docx', score: 0.82 },
];

// canonical Draft.jsx 의 mock diff
const MOCK_DIFF_LINES = [
  { type: 'add' as const, text: '제출 기한: __날짜__.' },
  { type: 'del' as const, text: '제출 기한: 추후 통보드리겠습니다.' },
  { type: 'mod' as const, text: '포함 문서: PSW, FMEA, Control Plan, MSA, Capability Study, Sample.' },
  { type: 'ctx' as const, text: '안녕하십니까. 아진산업 품질보증팀입니다.' },
];

// 품질 5기준 (canonical)
interface QualityCriterion {
  k: string; en: string; max: number;
}
const QUALITY_CRITERIA: QualityCriterion[] = [
  { k: '구조',   en: 'STRUCTURE',   max: 25 },
  { k: '분량',   en: 'LENGTH',      max: 20 },
  { k: '전문성', en: 'TERMINOLOGY', max: 25 },
  { k: '완성도', en: 'COMPLETION',  max: 15 },
  { k: '톤',     en: 'TONE',        max: 15 },
];

// ──────────────────────────────────────────────────────────────────
// Plan v1.0 — 진단 결과 → 친절한 한 줄 안내 (시연 환경 자동 인식)
// Plan v3.0 — base_url 기반으로 "Mac Ollama 의도 + 일시 미연결" vs "진정한 Gemini 모드" 구분
// ──────────────────────────────────────────────────────────────────
function _diagnoseHint(d: DiagnoseResponse): string {
  const ollamaUrl = ((d.ollama.meta?.base_url as string) || '').trim();
  const isLocalOllamaIntended = /^https?:\/\//.test(ollamaUrl);

  // 1) Mac Ollama 의도 + 일시 미연결 (Cloud Run cold start, Mac sleep, Tunnel propagation 지연)
  if (!d.ollama.ok && isLocalOllamaIntended) {
    return `로컬 Ollama 연결 검증 중 — Cloud Run cold start (~30초) 또는 Mac/Tunnel 점검 후 자동 복구. 페이지가 자동 새로고침합니다.`;
  }

  // 2) 진정한 Gemini 단독 모드 (OLLAMA_BASE_URL 빈값 + Gemini 키 OK)
  if (!d.ollama.ok && d.gemini.ok && d.templates.ok && d.prompts.ok && !isLocalOllamaIntended) {
    return '클라우드 시연 환경 — 로컬 Ollama 대신 Gemini 3.5 Flash 로 자동 동작합니다.';
  }

  if (!d.ollama.ok) return `Ollama 미기동 — 로컬 시연 시 \`ollama serve\` 실행 또는 클라우드 환경에서 Gemini 사용`;
  if (!d.pipeline.ok) return `DraftPipeline 미부팅 — ${d.pipeline.detail}`;
  if (!d.templates.ok) return `템플릿 DB 누락 — ${d.templates.detail}`;
  if (!d.prompts.ok) return `프롬프트 누락 — ${d.prompts.detail}`;
  return '백엔드 일부 항목 점검 필요 — 진단 카드 확인';
}

// ──────────────────────────────────────────────────────────────────
// Tabs
// ──────────────────────────────────────────────────────────────────

const MAIN_TABS: { k: DraftPageTab; en: string; ko: string }[] = [
  { k: 'internal', en: 'INTERNAL', ko: '내부용 문서' },
  { k: 'external', en: 'EXTERNAL', ko: '외부용 문서' },
  { k: 'history',  en: 'HISTORY',  ko: '문서 이력' },
];

// ──────────────────────────────────────────────────────────────────
// Component
// ──────────────────────────────────────────────────────────────────

export function Draft() {
  const isMobile = useIsMobile();
  if (isMobile) return <AJINMobileDraft />;
  return <DraftDesktop />;
}

function DraftDesktop() {
  // ── Tab state (persist) ────────────────────────────────
  const tab = useUIStore((s) => s.draftPageTab);
  const setTab = useUIStore((s) => s.setDraftPageTab);
  const currentUser = useAuthStore((s) => s.user);
  const canViewDiagnostics = (currentUser?.role_level ?? 0) >= 5;

  // ── Draft state ────────────────────────────────────────
  const docTypes = useDraftStore((s) => s.docTypes);
  const setDocTypes = useDraftStore((s) => s.setDocTypes);
  const docTypeId = useDraftStore((s) => s.docTypeId);
  const setDocTypeId = useDraftStore((s) => s.setDocTypeId);
  const toneId = useDraftStore((s) => s.toneId);
  const setToneId = useDraftStore((s) => s.setToneId);
  const meta = useDraftStore((s) => s.meta);
  const setMeta = useDraftStore((s) => s.setMeta);
  const userRequest = useDraftStore((s) => s.userRequest);
  const setUserRequest = useDraftStore((s) => s.setUserRequest);
  // 부록 4 — F-fav
  const favoritedDocTypes = useDraftStore((s) => s.favoritedDocTypes);
  const toggleFavorite = useDraftStore((s) => s.toggleFavorite);
  // 부록 6 — P4-1 / P4-3 / P4-4
  const prefsBaseVersion = useDraftStore((s) => s.prefsBaseVersion);
  const setPrefsBaseVersion = useDraftStore((s) => s.setPrefsBaseVersion);
  const deptRecommendations = useDraftStore((s) => s.deptRecommendations);
  const setDeptRecommendations = useDraftStore((s) => s.setDeptRecommendations);
  const personalPicks = useDraftStore((s) => s.personalPicks);
  const setPersonalPicks = useDraftStore((s) => s.setPersonalPicks);
  // 부록 4 — F-toast (부록 5 P3-4 — TTL 적용)
  const { addToast } = useToast();
  useEffect(() => {
    const KEY = 'ajin_draft_toast:v2';
    const TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7일
    import('@/utils/flagTTL').then(({ isFlagFresh, markFlag }) => {
      if (isFlagFresh(KEY)) return;
      addToast({
        type: 'info',
        message:
          '흐름이 새로 정렬됐습니다. 템플릿을 먼저 선택하면 주제/컨텍스트 영역이 활성화됩니다.',
        duration: 6000,
      });
      markFlag(KEY, TTL_MS);
    });
  }, []);

  // 부록 5 P3-1 + 부록 6 P4-1/P4-3/P4-4 — 마운트 시 서버에서 prefs/추천 fetch
  useEffect(() => {
    let cancelled = false;
    import('@api/draft').then((m) => {
      // P3-1 + P4-4: prefs + base_version
      m.fetchDraftPrefsV2()
        .then((r) => {
          if (cancelled) return;
          const serverFavs = r.favorited_doc_types ?? [];
          setPrefsBaseVersion(r.updated_at ?? '');
          if (serverFavs.length > 0) {
            const state = useDraftStore.getState();
            if (
              serverFavs.length !== state.favoritedDocTypes.length ||
              !serverFavs.every((id) => state.favoritedDocTypes.includes(id))
            ) {
              useDraftStore.setState({ favoritedDocTypes: serverFavs });
            }
          }
        })
        .catch(() => {});
      // P4-1: 부서 추천
      m.fetchDeptRecommendations(3)
        .then((r) => {
          if (cancelled) return;
          setDeptRecommendations(r.recommendations.map((x) => x.doc_type_id));
        })
        .catch(() => setDeptRecommendations([]));
      // P4-3: 개인 자주 사용
      m.fetchPersonalPicks(5)
        .then((r) => {
          if (cancelled) return;
          setPersonalPicks(r.picks.map((x) => x.doc_type_id));
        })
        .catch(() => setPersonalPicks([]));
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 부록 5 P3-1 + 부록 6 P4-4 — 즐겨찾기 변경 시 merge PUT
  const favSyncRef = useRef<number | null>(null);
  const prevFavsRef = useRef<string[]>(favoritedDocTypes);
  useEffect(() => {
    if (favSyncRef.current !== null) {
      window.clearTimeout(favSyncRef.current);
    }
    // remove_ids 계산 — 이전 상태에서 사라진 항목 (사용자 명시 제거)
    const prevFavs = prevFavsRef.current;
    const removedIds = prevFavs.filter((id) => !favoritedDocTypes.includes(id));
    prevFavsRef.current = favoritedDocTypes;

    favSyncRef.current = window.setTimeout(() => {
      import('@api/draft').then(({ updateDraftPrefsMerge }) => {
        updateDraftPrefsMerge(favoritedDocTypes, prefsBaseVersion, removedIds)
          .then((r) => {
            // 서버가 merge 한 결과를 다시 store 에 반영 (다른 기기 변경 흡수)
            if (r.updated_at) setPrefsBaseVersion(r.updated_at);
            const merged = r.favorited_doc_types ?? [];
            if (r.conflict_detected) {
              // silent merge — 즐겨찾기는 low-stakes (부록 6 결정)
              useDraftStore.setState({ favoritedDocTypes: merged });
              prevFavsRef.current = merged;
            }
          })
          .catch(() => {
            // 비인증·네트워크 오류는 무시 — 로컬 persist 가 영구 보존
          });
      });
    }, 300);
    return () => {
      if (favSyncRef.current !== null) {
        window.clearTimeout(favSyncRef.current);
      }
    };
  }, [favoritedDocTypes, prefsBaseVersion, setPrefsBaseVersion]);

  // v3.6 — 사용자 업로드 참조 양식 (DOCX/PDF/HWP/HWPX/TXT/MD)
  // 업로드 → 백엔드 텍스트 추출 → uploadedRef.text 가 stream-v2 payload 의 reference_template_text 로 전달
  const [uploadedRef, setUploadedRef] = useState<UploadReferenceResponse | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  const handleRefUpload = useCallback(async (file: File) => {
    setUploadBusy(true);
    setUploadError(null);
    try {
      const res = await uploadReference(file);
      setUploadedRef(res);
      if (!res.ok && res.warning) {
        setUploadError(res.warning);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setUploadError(`업로드 실패: ${msg}`);
      setUploadedRef(null);
    } finally {
      setUploadBusy(false);
    }
  }, []);

  const handleRefClear = useCallback(() => {
    setUploadedRef(null);
    setUploadError(null);
    if (uploadInputRef.current) uploadInputRef.current.value = '';
  }, []);

  // ── /search 또는 /equipment 알람에서 prefill state 와 함께 진입 시 textarea 자동 입력 ──
  // W2 (P0): /equipment AlertsSubTab → 8D Report 액션 → location.state.prefill 본문 채움
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  // v4.7 Sprint 2 P0 (축 ③) — URL 쿼리 ?template=spc_violation&violation_id=...
  //   알람 토스트 "메일 초안" 클릭 → /draft?template=spc_violation&violation_id=v-001 진입.
  //   prefill_engine 호출 → subject/body 채움 후 textarea + draft output 으로 주입.
  const [spcPrefillSubject, setSpcPrefillSubject] = useState<string>('');
  const [spcPrefillTo, setSpcPrefillTo] = useState<string>('');
  const [spcPrefillCc, setSpcPrefillCc] = useState<string>('');
  useEffect(() => {
    const tmpl = searchParams.get('template');
    const vid = searchParams.get('violation_id');
    if (tmpl !== 'spc_violation' || !vid) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await prefillTemplate('spc_violation', vid);
        if (cancelled) return;
        // textarea: 사용자 인풋 영역에는 short subject 만 (LLM 호출 불필요한 직접 prefill).
        setUserRequest(r.subject);
        // 결과 영역 (output) 에 본문 직접 주입 — 메일 발송 모달의 body source.
        useDraftStore.getState().setOutput(r.body);
        setSpcPrefillSubject(r.subject);
        setSpcPrefillTo(r.to.map((p) => p.email).filter(Boolean).join(', '));
        setSpcPrefillCc(r.cc.map((p) => p.email).filter(Boolean).join(', '));
        // 1회 사용 후 query param 제거 (새로고침 시 중복 호출 방지).
        const next = new URLSearchParams(searchParams);
        next.delete('template');
        next.delete('violation_id');
        setSearchParams(next, { replace: true });
      } catch {
        // 조회 실패 시 무시 — 사용자에게는 빈 폼.
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    const s = (location.state ?? {}) as {
      prefillRecipient?: string;
      prefillPosition?: string;
      prefillTeam?: string;
      prefillEmail?: string;
      prefill?: string;        // W2: 알람 → 8D Report 작성 본문
      doc_type?: string;       // W2: 추천 문서 유형 (예: '8D')
    };

    let prefilled = '';
    if (s.prefillRecipient) {
      const parts = [s.prefillRecipient];
      if (s.prefillPosition) parts.push(s.prefillPosition);
      const who = parts.join(' ');
      const team = s.prefillTeam ? `(${s.prefillTeam})` : '';
      const email = s.prefillEmail ? `\n수신: ${s.prefillEmail}` : '';
      prefilled = `${who}${team} 앞으로 다음 내용을 작성해주세요:${email}\n\n`;
    } else if (s.prefill) {
      prefilled = s.prefill;
    }

    if (!prefilled) return;

    setUserRequest(prefilled);

    // state 1회 사용 후 정리 — 새로고침/뒤로가기 시 재적용 방지
    window.history.replaceState({}, '');

    // 다음 tick 에서 textarea 포커스 + 커서 끝
    setTimeout(() => {
      const ta = requestTextareaRef.current;
      if (ta) {
        ta.focus();
        ta.setSelectionRange(prefilled.length, prefilled.length);
      }
    }, 50);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const output = useDraftStore((s) => s.output);
  const setOutput = useDraftStore((s) => s.setOutput);
  const appendStreamToken = useDraftStore((s) => s.appendStreamToken);
  const isStreaming = useDraftStore((s) => s.isStreaming);
  const setStreaming = useDraftStore((s) => s.setStreaming);
  const resetGeneration = useDraftStore((s) => s.resetGeneration);
  const quality = useDraftStore((s) => s.quality);
  const setQuality = useDraftStore((s) => s.setQuality);
  const ccRec = useDraftStore((s) => s.ccRec);
  const setCCRec = useDraftStore((s) => s.setCCRec);
  const lastSavedContent = useDraftStore((s) => s.lastSavedContent);
  const hasEdits = useDraftStore((s) => s.hasEdits);
  const diff = useDraftStore((s) => s.diff);
  const setDiff = useDraftStore((s) => s.setDiff);

  // B6 v4.0 — 메일 발송 모달
  const [mailModalOpen, setMailModalOpen] = useState(false);

  // ── Plan v1.0 — provider/modelId 셀렉터 + stage 진행 상태 ──
  const provider = useDraftStore((s) => s.provider);
  const modelId = useDraftStore((s) => s.modelId);
  const setProvider = useDraftStore((s) => s.setProvider);
  const setModelId = useDraftStore((s) => s.setModelId);
  const stages = useDraftStore((s) => s.stages);
  const pushStage = useDraftStore((s) => s.pushStage);
  const clearStages = useDraftStore((s) => s.clearStages);

  // ── Local UI state ─────────────────────────────────────
  const [globalApiError, setGlobalApiError] = useState<string | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [ccLoading, setCcLoading] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareLoading, setCompareLoading] = useState(false);
  // P1 — 30초 토큰 미도착 시 안내 칩 표시
  const [showSlowHint, setShowSlowHint] = useState(false);

  // Plan v1.0 — 진단 / LLM 옵션
  const [diagnose, setDiagnose] = useState<DiagnoseResponse | null>(null);
  const [llmOptions, setLlmOptions] = useState<LLMOption[]>([]);

  // ── 현재 활성 카테고리 (internal/external) ─────────────
  const activeCategory: DocCategory = tab === 'external' ? 'external' : 'internal';

  // ── Phase 4: Firestore 이력 ─────────────────────────────
  const [historyDocs, setHistoryDocs] = useState<DraftDocument[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // ── Mount: doc-types + diagnose + llm-options 병렬 로드 ──
  useEffect(() => {
    (async () => {
      const diagnoseRequest = canViewDiagnostics
        ? fetchDiagnose()
        : Promise.resolve<DiagnoseResponse | null>(null);
      const [dt, dg, opt] = await Promise.allSettled([
        fetchDocTypes(),
        diagnoseRequest,
        fetchLlmOptions('draft'),
      ] as const);

      // doc-types
      if (dt.status === 'fulfilled' && dt.value.items?.length) {
        setDocTypes(dt.value.items);
      } else {
        setDocTypes(MOCK_DOC_TYPES);
        if (dt.status === 'rejected') {
          console.warn('[draft] doc-types 로드 실패:', dt.reason);
        }
      }

      // diagnose 배너
      if (!canViewDiagnostics) {
        setDiagnose(null);
      } else if (dg.status === 'fulfilled' && dg.value) {
        setDiagnose(dg.value);
        if (!dg.value.summary_ok) {
          setGlobalApiError(_diagnoseHint(dg.value));
        }
      } else if (dg.status === 'rejected') {
        setGlobalApiError('백엔드 연결 실패 — 시연 모드 (Mock 데이터). 백엔드 서버 가동을 확인해 주세요.');
      }

      // llm-options — Feature B 에서는 Gemini 가 blocked=true 로 내려옴
      if (opt.status === 'fulfilled' && opt.value.options?.length) {
        setLlmOptions(opt.value.options);
        // 현재 store 의 (provider, modelId) 가 옵션에 없거나 사용 불가 → 기본값 적용
        const cur = opt.value.options.find(
          (o) => o.provider === provider && o.id === modelId && o.available && !o.blocked,
        );
        if (!cur && opt.value.default_provider && opt.value.default_id) {
          setProvider(opt.value.default_provider as LLMProvider);
          setModelId(opt.value.default_id);
        }
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canViewDiagnostics]);

  // ── Plan v3.0 — diagnose + llm-options 주기적 polling (15초)
  // Cloud Run cold start / Mac sleep / Tunnel 끊김 등 환경 변화를 자동 반영.
  // document.hidden 일 때는 멈춤 (탭 비활성 시 부담 절감).
  useEffect(() => {
    let cancelled = false;
    const POLL_MS = 15_000;

    const tick = async () => {
      if (cancelled || (typeof document !== 'undefined' && document.hidden)) return;
      try {
        const diagnoseRequest = canViewDiagnostics
          ? fetchDiagnose()
          : Promise.resolve<DiagnoseResponse | null>(null);
        const [dg, opt] = await Promise.allSettled([
          diagnoseRequest,
          fetchLlmOptions('draft'),
        ] as const);
        if (cancelled) return;

        if (!canViewDiagnostics) {
          setDiagnose(null);
        } else if (dg.status === 'fulfilled' && dg.value) {
          setDiagnose(dg.value);
          if (dg.value.summary_ok) {
            setGlobalApiError(null);
          } else {
            setGlobalApiError(_diagnoseHint(dg.value));
          }
        }

        if (opt.status === 'fulfilled' && opt.value.options?.length) {
          setLlmOptions(opt.value.options);
        }
      } catch {
        /* ignore — 네트워크 일시 오류는 다음 tick 에서 복구 */
      }
    };

    const id = window.setInterval(() => void tick(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canViewDiagnostics]);

  // ── 카테고리별 doc-types 필터 ──────────────────────────
  const filteredDocTypes = useMemo(() => {
    const base = (docTypes.length ? docTypes : MOCK_DOC_TYPES).filter(
      (d) => d.category === activeCategory,
    );
    // 부록 6 정렬 우선순위: 즐겨찾기(★) > 개인 자주 사용 > 부서 추천 > 나머지
    const favSet = new Set(favoritedDocTypes);
    const personalSet = new Set(personalPicks);
    const deptSet = new Set(deptRecommendations);
    const rank = (id: string) => {
      if (favSet.has(id)) return 0;
      if (personalSet.has(id)) return 1;
      if (deptSet.has(id)) return 2;
      return 3;
    };
    return [...base].sort((a, b) => {
      const ra = rank(a.id);
      const rb = rank(b.id);
      if (ra !== rb) return ra - rb;
      return 0; // 동일 priority 는 base 순서 유지
    });
  }, [docTypes, activeCategory, favoritedDocTypes, personalPicks, deptRecommendations]);

  // 부록 5 P3-2 — TF-IDF 백엔드 추천 (500ms debounce + 3s timeout). 자유 입력 → POST /draft/recommend
  const [recommendedIds, setRecommendedIds] = useState<string[]>([]);
  useEffect(() => {
    const q = (userRequest || '').trim();
    if (!q) {
      setRecommendedIds([]);
      return;
    }
    const t = setTimeout(() => {
      import('@api/draft').then(({ fetchDraftRecommend }) => {
        fetchDraftRecommend(q, 2)
          .then((r) => {
            // 현재 카테고리 탭의 docType id 와 매칭되는 것만 노출
            const validIds = new Set(filteredDocTypes.map((d) => d.id));
            setRecommendedIds(
              (r.doc_type_ids || []).filter((id) => validIds.has(id)),
            );
          })
          .catch(() => {
            // 네트워크/타임아웃: 추천 없음 (사용자가 카드 직접 픽 — 정상 흐름)
            setRecommendedIds([]);
          });
      });
    }, 500);
    return () => clearTimeout(t);
  }, [userRequest, filteredDocTypes]);

  // 카테고리 변경 시 docTypeId 재정렬
  useEffect(() => {
    if (tab === 'history') return;
    if (!filteredDocTypes.find((d) => d.id === docTypeId) && filteredDocTypes.length > 0) {
      setDocTypeId(filteredDocTypes[0].id);
    }
  }, [tab, filteredDocTypes, docTypeId, setDocTypeId]);

  // ── SSE 스트리밍 ───────────────────────────────────────
  const ranAutoActionsRef = useRef(false);

  const sse = useSSE({
    onToken: (chunk) => appendStreamToken(chunk),
    onStage: (stage) => {
      pushStage({ name: stage.name, status: stage.status, meta: stage.meta });
    },
    onDone: () => {
      setStreaming(false);
      // v3.6 — LLM 출력 포스트-프로세서: 줄바꿈 누락 보정 (Qwen 3.5 등이 한 단락으로 출력하는 케이스 대응)
      // 마크다운 헤더(**키:**) + 한국어 종결어미 패턴 기반 자동 단락 분리.
      // 사용자가 textarea 에서 바로 복사·붙여넣기 했을 때 자연스러운 양식으로 보이도록 함.
      const currentOutput = useDraftStore.getState().output;
      const formatted = formatDraftOutput(currentOutput);
      if (formatted && formatted !== currentOutput) {
        setOutput(formatted);
      }
      // 자동 후속 호출 (1회)
      if (!ranAutoActionsRef.current) {
        ranAutoActionsRef.current = true;
        void runQualityScore();
        void runCcRecommend();
        // Phase 4: Firestore 자동 영구화 (fire-and-forget)
        void persistCurrentDraft();
      }
    },
    onError: (msg) => {
      setStreaming(false);
      console.warn('[draft-sse]', msg);
      // Plan v1.0 — 자동 mock fallback 제거. 명시 토글(localStorage.draft_mock=1) 일 때만 시연.
      const mockToggle =
        typeof window !== 'undefined' && window.localStorage.getItem('draft_mock') === '1';
      if (!output && mockToggle) {
        simulateMockStream();
      } else if (!output) {
        setGlobalApiError(`생성 실패: ${msg} — 모델/네트워크를 확인하고 다시 시도해 주세요.`);
      }
    },
  });

  // mock 스트리밍 (백엔드 SSE 미응답 시 시연용)
  const simulateMockStream = useCallback(() => {
    setStreaming(true);
    setOutput('');
    let i = 0;
    const tick = () => {
      i += 6;
      setOutput(MOCK_SAMPLE.slice(0, i));
      if (i < MOCK_SAMPLE.length) {
        setTimeout(tick, 18);
      } else {
        setStreaming(false);
        // mock 시연도 quality/cc 자동 호출
        if (!ranAutoActionsRef.current) {
          ranAutoActionsRef.current = true;
          void runQualityScore();
          void runCcRecommend();
        }
      }
    };
    setTimeout(tick, 150);
  }, [setOutput, setStreaming]);

  const onGenerate = useCallback(() => {
    if (isStreaming) return;
    ranAutoActionsRef.current = false;
    resetGeneration();
    clearStages();
    setStreaming(true);

    const docType = docTypes.find((d) => d.id === docTypeId)?.name_ko ?? docTypeId;
    const tone = TONES.find((t) => t.id === toneId)?.ko ?? toneId;

    // Plan v1.0 — Feature B 보안: provider 가 'gemini' 면 백엔드가 차단하지만,
    // 프론트에서도 옵션 자체에 blocked=true 가 있으면 ollama 로 강제 다운그레이드.
    const selected = llmOptions.find((o) => o.provider === provider && o.id === modelId);
    let effectiveProvider: LLMProvider = provider;
    let effectiveModel: string = modelId;
    if (selected?.blocked || (selected && !selected.available)) {
      const fallback = llmOptions.find((o) => o.available && !o.blocked);
      if (fallback) {
        effectiveProvider = fallback.provider;
        effectiveModel = fallback.id;
      }
    }

    const { url, body } = buildStreamV2Request({
      doc_type: docType || 'general',
      tone,
      meta: { ...meta },
      user_request: userRequest,
      language: 'ko',
      context: activeCategory,
      provider: effectiveProvider,
      model: effectiveModel,
      render_template: true,
      // v3.6 — 사용자 업로드 양식 텍스트 (있으면 LLM 프롬프트에 prepend)
      reference_template_text: uploadedRef?.text ?? '',
      reference_template_name: uploadedRef?.filename ?? '',
    });

    void sse.start({ url, body }).catch((e) => {
      console.warn('[draft-sse-v2] start 실패:', e);
      setStreaming(false);
      // Plan v1.0 — 명시 토글일 때만 mock fallback
      const mockToggle =
        typeof window !== 'undefined' && window.localStorage.getItem('draft_mock') === '1';
      if (mockToggle) {
        simulateMockStream();
      } else {
        setGlobalApiError(
          `생성 시작 실패: ${e instanceof Error ? e.message : String(e)} — 백엔드 상태를 확인해 주세요.`,
        );
      }
    });
  }, [
    isStreaming,
    docTypes,
    docTypeId,
    toneId,
    meta,
    userRequest,
    activeCategory,
    provider,
    modelId,
    uploadedRef,
    llmOptions,
    sse,
    setStreaming,
    resetGeneration,
    clearStages,
    simulateMockStream,
  ]);

  // ── P1 — 생성 중 취소 ──────────────────────────────────
  const onCancel = useCallback(() => {
    sse.stop();
    setStreaming(false);
    setShowSlowHint(false);
  }, [sse, setStreaming]);

  // ── P1 — 30초 토큰 미도착 시 안내 칩 노출 ──────────────
  useEffect(() => {
    if (!isStreaming) {
      setShowSlowHint(false);
      return;
    }
    const t = window.setTimeout(() => {
      // 30초 경과 시점에서도 streaming 중 + output 비어있으면 안내
      const st = useDraftStore.getState();
      if (st.isStreaming && !st.output) {
        setShowSlowHint(true);
      }
    }, 30_000);
    return () => window.clearTimeout(t);
  }, [isStreaming]);

  // 첫 토큰 도착 시 안내 칩 즉시 해제
  useEffect(() => {
    if (output && showSlowHint) setShowSlowHint(false);
  }, [output, showSlowHint]);

  // ── 품질 평가 자동 호출 ────────────────────────────────
  const runQualityScore = useCallback(async () => {
    const text = useDraftStore.getState().output;
    if (!text || text.length < 50) return;
    setQualityLoading(true);
    try {
      const res = await scoreQuality({
        text,
        doc_type: docTypeId,
      });
      setQuality(res);
    } catch (e) {
      console.warn('[draft-quality]', e);
      // mock fallback
      setQuality({
        total_score: 87,
        grade: 'B+',
        scores: {
          structure: 24, structure_max: 25,
          length: 18, length_max: 20,
          terminology: 22, terminology_max: 25,
          completeness: 13, completeness_max: 15,
          tone: 10, tone_max: 15,
        },
        improvements: ['__날짜__ 채우기', '분량 +120자 권장'],
        details: {},
      });
    } finally {
      setQualityLoading(false);
    }
  }, [docTypeId, setQuality]);

  // ── CC 추천 자동 호출 ──────────────────────────────────
  const runCcRecommend = useCallback(async () => {
    setCcLoading(true);
    try {
      const res = await recommendCC({
        doc_type: docTypeId,
        sender_department: '품질보증팀',
        recipient: meta.recipient ?? '',
      });
      setCCRec(res);
    } catch (e) {
      console.warn('[draft-cc]', e);
      // mock fallback (canonical 그대로)
      setCCRec({
        groups: [
          { tier: 'required',    label_ko: '필수', label_en: 'REQUIRED',    departments: ['현대차 SQ팀', '영업1팀'] },
          { tier: 'recommended', label_ko: '권장', label_en: 'RECOMMENDED', departments: ['품질본부장'] },
          { tier: 'optional',    label_ko: '선택', label_en: 'OPTIONAL',    departments: ['생산기술팀'] },
        ],
        doc_type: docTypeId,
        sender_department: '품질보증팀',
      });
    } finally {
      setCcLoading(false);
    }
  }, [docTypeId, meta.recipient, setCCRec]);

  // ── Phase 4: Firestore 자동 영구화 ─────────────────────
  const persistCurrentDraft = useCallback(async () => {
    const text = useDraftStore.getState().output;
    if (!text || text.trim().length < 50) return;
    const q = useDraftStore.getState().quality;
    try {
      await autoPersistDraft({
        docTypeId,
        toneId,
        context: activeCategory,
        meta: {
          title: meta.title || (docTypes.find((d) => d.id === docTypeId)?.name_ko ?? '초안'),
          recipient: meta.recipient,
          cc: meta.cc,
        },
        content: text,
        qualityTotal: q?.total_score,
        qualityGrade: q?.grade,
      });
    } catch (e) {
      console.warn('[draft] persist 실패:', e);
    }
  }, [docTypeId, toneId, activeCategory, meta, docTypes]);

  // ── Phase 4: 이력 탭 진입 시 Firestore 로드 ─────────────
  const reloadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const docs = await loadHistory(30);
      setHistoryDocs(docs);
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : String(e));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'history') {
      void reloadHistory();
    }
  }, [tab, reloadHistory]);

  const onDeleteHistoryDoc = useCallback(
    async (id: string) => {
      if (!confirm('이 초안을 삭제하시겠습니까?')) return;
      const ok = await firestoreDeleteDraft(id);
      if (ok) {
        setHistoryDocs((arr) => arr.filter((d) => d.id !== id));
      }
    },
    [],
  );

  // ── P3-4: "원본 ↔ 편집본" 비교 트리거 ─────────────────
  const onCompareOriginal = useCallback(async () => {
    if (!lastSavedContent || lastSavedContent === output) return;
    setCompareLoading(true);
    try {
      const res = await computeDiff({ old: lastSavedContent, new: output, context_lines: 3 });
      setDiff(res);
      setCompareOpen(true);
    } catch (e) {
      console.warn('[draft-diff]', e);
      // 클라이언트 단순 diff fallback (라인 비교)
      const oldLines = lastSavedContent.split('\n');
      const newLines = output.split('\n');
      const fallbackLines = [];
      const max = Math.max(oldLines.length, newLines.length);
      let added = 0;
      let removed = 0;
      for (let i = 0; i < max; i++) {
        if (oldLines[i] === undefined) {
          fallbackLines.push({ type: 'add' as const, text: newLines[i] });
          added++;
        } else if (newLines[i] === undefined) {
          fallbackLines.push({ type: 'del' as const, text: oldLines[i] });
          removed++;
        } else if (oldLines[i] !== newLines[i]) {
          fallbackLines.push({ type: 'del' as const, text: oldLines[i] });
          fallbackLines.push({ type: 'add' as const, text: newLines[i] });
          added++;
          removed++;
        } else {
          fallbackLines.push({ type: 'ctx' as const, text: oldLines[i] });
        }
      }
      setDiff({
        lines: fallbackLines,
        stats: { added, removed, unchanged: max - added - removed, similarity: 1 - (added + removed) / Math.max(max, 1) },
      });
      setCompareOpen(true);
    } finally {
      setCompareLoading(false);
    }
  }, [lastSavedContent, output, setDiff]);

  // ── 사용자 편집 시 quality/cc 재평가 트리거 ────────────
  const onReevaluate = useCallback(async () => {
    await Promise.all([runQualityScore(), runCcRecommend()]);
  }, [runQualityScore, runCcRecommend]);

  // 다운로드(9포맷) — DownloadActions 컴포넌트 내부 처리.
  // (clipboard / hwp / hwpx → frontend / 나머지 → backend)

  // ── Render ─────────────────────────────────────────────
  return (
    <div className="page lg-page" data-screen-label="B · Document Draft">
      <section className="lg-hero">
        <div className="lg-hero-eyebrow">DOCUMENT SEARCH & DRAFTING · MODULE B</div>
        <h1 className="lg-display">문서 검색 / 작성</h1>
        <p className="lg-sub">
          이메일·보고서·8D·PPAP·신청서 등 13가지 사내 문서를 AI가 대신 초안 작성. 회사 양식 파일을 업로드하면 그 구조 그대로 작성되고, 사내 SOP·용어집·과거 작성 이력을 자동으로 참고해 일관된 결과를 만들어 드립니다.
        </p>
        {globalApiError && (
          <div
            style={{
              marginTop: 12,
              padding: '8px 12px',
              borderRadius: 8,
              background: 'color-mix(in oklab, var(--hud-orange) 12%, transparent)',
              border: '1px solid color-mix(in oklab, var(--hud-orange) 30%, transparent)',
              fontSize: 12,
              color: 'var(--hud-orange)',
              fontFamily: 'var(--hud-font-mono)',
            }}
          >
            ⚠ {globalApiError}
          </div>
        )}

        {/* Plan v1.0 §1.2 — 진단 칩 (5개 의존성 — 초심자도 즉시 원인 파악 가능)
            클라우드 시연 환경: Ollama 미기동은 ✓ 회색 (정상), Gemini fallback 동작 */}
        {diagnose && !diagnose.summary_ok && (
          <div
            style={{
              marginTop: 10,
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6,
              alignItems: 'center',
            }}
          >
            <span className="lg-mini" style={{ marginRight: 4 }}>점검:</span>
            {[
              { k: 'ollama',    name: 'Ollama',     ok: diagnose.ollama.ok,    detail: diagnose.ollama.detail },
              { k: 'gemini',    name: 'Gemini key', ok: diagnose.gemini.ok,    detail: diagnose.gemini.detail },
              { k: 'pipeline',  name: 'Pipeline',   ok: diagnose.pipeline.ok,  detail: diagnose.pipeline.detail },
              { k: 'templates', name: 'Templates',  ok: diagnose.templates.ok, detail: diagnose.templates.detail },
              { k: 'prompts',   name: 'Prompts',    ok: diagnose.prompts.ok,   detail: diagnose.prompts.detail },
            ].map((c) => (
              <span
                key={c.k}
                className="lg-pill"
                title={c.detail}
                style={{
                  fontSize: 11,
                  color: c.ok ? 'var(--hud-green, #4ade80)' : 'var(--hud-orange)',
                  borderColor: c.ok
                    ? 'color-mix(in oklab, var(--hud-green, #4ade80) 30%, transparent)'
                    : 'color-mix(in oklab, var(--hud-orange) 30%, transparent)',
                }}
              >
                {c.ok ? '✓' : '⚠'} {c.name}
              </span>
            ))}
          </div>
        )}
      </section>

      {/* MAIN TABS */}
      <div className="lg-tabs">
        {MAIN_TABS.map((t) => (
          <button
            key={t.k}
            className={'lg-tab' + (tab === t.k ? ' on' : '')}
            onClick={() => setTab(t.k)}
          >
            <span className="en">{t.en}</span>
            <span className="ko">{t.ko}</span>
          </button>
        ))}
      </div>

      {/* INTERNAL / EXTERNAL */}
      {tab !== 'history' && (
        <div className="lg-grid lg-grid-2-1">
          {/* ─── 좌(2fr): 작성 카드 ─── */}
          <section className="lg-card">
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">REQUEST · 작성 요청</div>
                <h2 className="lg-h2">무엇을 작성할까요?</h2>
              </div>
              {/* Plan v1.0 — pill 자리에 모델 셀렉터 (Qwen / Gemma — Gemini 는 보안 차단)
                  v3.6 — Chat 페이지(C 기능) 와 동일한 ModelSelect 도입 (Use case 그룹화 + 호버 카드 + 다크모드 대응).
                  feature='draft' → 백엔드가 draft 컨텍스트 옵션 (Gemini blocked) 반환.
                  ModelHelpPopover 는 ModelSelect 옆에 별도 배치. */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  gap: 8,
                  minWidth: 240,
                  margin: 0,
                }}
              >
                <div style={{ flex: 1, minWidth: 220 }}>
                  <ModelSelect
                    value={modelId ? { provider, model: modelId } : null}
                    onChange={(next) => {
                      if (next) {
                        setProvider(next.provider as LLMProvider);
                        setModelId(next.model);
                      }
                      // next 가 null (자동) → store 의 현재 default 유지
                    }}
                    feature="draft"
                    disabled={isStreaming}
                  />
                </div>
                <ModelHelpPopover modelId={modelId} />
              </div>
            </div>

            {/* B2 v4.0 — 구조화 변수 입력 폼 (필수★ + 그룹 + placeholder 예시).
                선택된 doc_type 의 var_metadata 를 기반으로 자동 생성. 값은 meta.custom_fields 에 저장. */}
            {(() => {
              const selectedDoc = filteredDocTypes.find((d) => d.id === docTypeId);
              const vars = selectedDoc?.var_metadata ?? [];
              if (vars.length === 0) return null;
              const customFields = (meta.custom_fields ?? {}) as Record<string, string>;
              return (
                <VariableForm
                  variables={vars}
                  values={customFields}
                  onChange={(name, value) =>
                    setMeta({
                      custom_fields: { ...customFields, [name]: value },
                    })
                  }
                />
              );
            })()}

            {/* 부록 3 — 권장 변경: TEMPLATE PICK 을 1차 anchor 로 위로.
                기존 자유 입력 + REFERENCE TEMPLATE 단독 영역은 11번째 카드 + 카드 픽 후 펼쳐지는 영역으로 통합. */}
            <div style={{ marginTop: 14, marginBottom: 14 }}>
              <div className="lg-eyebrow" style={{ marginBottom: 10 }}>
                TEMPLATE PICK · 템플릿 선택 ({filteredDocTypes.length}종 + 사용자 양식)
              </div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                  gap: 12,
                }}
              >
                {filteredDocTypes.map((d) => (
                  <TemplateCard
                    key={d.id}
                    doc={d}
                    selected={d.id === docTypeId}
                    onSelect={(picked) => setDocTypeId(picked.id)}
                    isFavorited={favoritedDocTypes.includes(d.id)}
                    onToggleFavorite={toggleFavorite}
                    recommended={recommendedIds.includes(d.id)}
                    deptRecommended={deptRecommendations.includes(d.id)}
                    personalPick={personalPicks.includes(d.id)}
                  />
                ))}
                {/* 11번째 카드 — 사용자 양식 업로드 */}
                <TemplateUploadCard
                  uploadedRef={uploadedRef}
                  uploadBusy={uploadBusy}
                  uploadError={uploadError}
                  onUpload={(f) => void handleRefUpload(f)}
                  onClear={handleRefClear}
                />
              </div>
            </div>

            {/* 카드 미선택 안내 (CTA) */}
            {!docTypeId && (
              <div
                style={{
                  marginBottom: 14,
                  padding: '10px 14px',
                  border: '1px solid var(--hud-orange, #E8A317)',
                  background: 'rgba(232,163,23,0.10)',
                  color: 'var(--hud-orange, #E8A317)',
                  fontSize: 13,
                  borderRadius: 2,
                }}
              >
                위에서 템플릿을 먼저 선택하세요. 선택 후 주제·어조·생성 버튼이 활성화됩니다.
              </div>
            )}

            {/* 부록 3 — docTypeId 미선택 시 dimmed 처리 (페이지 흐름 유지) */}
            <div
              style={{
                opacity: docTypeId ? 1 : 0.4,
                pointerEvents: docTypeId ? 'auto' : 'none',
                transition: 'opacity 0.2s ease',
              }}
            >
              <div className="lg-field" style={{ marginBottom: 14 }}>
                <label>주제 / 컨텍스트 (자유 입력)</label>
                <textarea
                  ref={requestTextareaRef}
                  className="lg-textarea"
                  value={userRequest}
                  onChange={(e) => setUserRequest(e.target.value)}
                  rows={3}
                  placeholder="예: 이번 주 PPAP 진행 현황 / 협력사 회신 안내"
                />
                <details style={{ marginTop: 6, fontSize: 11, color: 'var(--hud-text-dim)' }}>
                  <summary style={{ cursor: 'pointer' }}>예시 더 보기</summary>
                  <div style={{ marginTop: 4, lineHeight: 1.5 }}>
                    · 현대차 SQ팀에 PPAP Level 3 제출 안내 — 구조화 변수 외 추가 컨텍스트<br/>
                    · 회의 결과 요약 (참석자, 주요 안건, 결정 사항)<br/>
                    · 휴가 신청 사유 + 인수인계 계획
                  </div>
                </details>
              </div>

            <div
              className="lg-filter-grid"
              style={{ gridTemplateColumns: '1fr 2fr auto', gap: 14, alignItems: 'flex-end' }}
            >
              <div className="lg-field">
                <label>어조 · TONE</label>
                <select value={toneId} onChange={(e) => setToneId(e.target.value)}>
                  {TONES.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.ko}
                    </option>
                  ))}
                </select>
              </div>
              <div className="lg-field">
                <label>문서 유형 · {filteredDocTypes.length}종</label>
                <select value={docTypeId} onChange={(e) => setDocTypeId(e.target.value)}>
                  {filteredDocTypes.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name_ko}
                    </option>
                  ))}
                </select>
              </div>
              {isStreaming ? (
                <button
                  type="button"
                  className="lg-btn ghost sm"
                  onClick={onCancel}
                  title="진행 중인 생성 요청을 중단합니다"
                >
                  ■ 중단
                </button>
              ) : (
                <button type="button" className="lg-btn" onClick={onGenerate}>
                  생성 ▶
                </button>
              )}
            </div>
            </div>{/* /dimmed wrapper (부록 3) */}

            <div className="lg-output-box">
              <div className="lg-output-h">
                <span>OUTPUT · 생성 결과</span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                  {showSlowHint && (() => {
                    // stage-aware hint: Gemini 가 running 중이면 정보형, 아니면 경고형
                    const lastLlm = [...stages].reverse().find((s) => s.name === 'llm');
                    const meta = (lastLlm?.meta ?? {}) as Record<string, unknown>;
                    const prov = String(meta.provider ?? '');
                    const isGeminiThinking =
                      lastLlm?.status === 'running' && (prov === 'gemini' || provider === 'gemini');
                    const color = isGeminiThinking
                      ? 'var(--hud-primary, #f59e0b)'
                      : 'var(--hud-orange)';
                    const text = isGeminiThinking
                      ? '✱ Gemini 사고 중 — Pro 는 첫 토큰까지 ~30s, Flash 는 즉시'
                      : '⚠ 응답 지연 — 다른 모델로 재시도 권장';
                    const tip = isGeminiThinking
                      ? 'Gemini 3.5 Flash 는 thinking 모드로 reasoning 후 응답합니다. Flash 모델은 thinking 없이 즉시 streaming.'
                      : '모델 cold start / 네트워크 buffering 가능성';
                    return (
                      <span
                        className="lg-pill"
                        title={tip}
                        style={{
                          fontSize: 11,
                          color,
                          borderColor: `color-mix(in oklab, ${color} 30%, transparent)`,
                        }}
                      >
                        {text}
                      </span>
                    );
                  })()}
                  <span className="lg-mini">
                    {isStreaming ? '스트리밍 중' : output ? '완료' : '대기'}
                  </span>
                </span>
              </div>
              {/* Streaming 중에는 read-only pre (커서 효과 유지) — 완료 시 사용자 편집 textarea */}
              {isStreaming || !output ? (
                <pre
                  className={'lg-output' + (isStreaming ? ' streaming-cursor' : '')}
                  style={{ whiteSpace: 'pre-wrap' }}
                >
                  {output || '생성 결과가 여기에 스트리밍됩니다.'}
                </pre>
              ) : (
                <textarea
                  className="lg-output"
                  value={output}
                  onChange={(e) => setOutput(e.target.value, { fromUser: true })}
                  spellCheck={false}
                  style={{
                    width: '100%',
                    minHeight: 240,
                    maxHeight: 480,
                    resize: 'vertical',
                    whiteSpace: 'pre-wrap',
                    border: 'none',
                    outline: 'none',
                    background: 'transparent',
                    fontFamily: 'var(--hud-font)',
                    fontSize: 14,
                    lineHeight: 1.65,
                    color: 'var(--hud-text)',
                  }}
                />
              )}
              {/* B3 v4.0 — 섹션별 부분 수정 (명시적 마커가 있을 때만 자동 노출) */}
              {output && !isStreaming && (
                <DraftBodyView
                  body={output}
                  onBodyChange={(newBody) => setOutput(newBody, { fromUser: false })}
                  docType={docTypeId}
                  tone={toneId}
                />
              )}

              {/* B6 v4.0 — 메일 발송 진입 버튼 (output 완료 시 노출) */}
              {output && !isStreaming && (
                <div
                  style={{
                    marginTop: 14,
                    display: 'flex',
                    justifyContent: 'flex-end',
                    gap: 8,
                  }}
                >
                  <button
                    type="button"
                    className="lg-btn"
                    onClick={() => setMailModalOpen(true)}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                    title="메일 발송 모달 열기 (Mock 발송)"
                  >
                    메일로 보내기 →
                  </button>
                </div>
              )}
              {output && (
                <DownloadActions
                  content={output}
                  basename={`draft_${docTypeId || 'general'}_${new Date().toISOString().slice(0, 10)}`}
                  source="draft"
                  metadata={{
                    title: meta.title || (docTypes.find((d) => d.id === docTypeId)?.name_ko ?? '초안'),
                    doc_type: docTypeId || 'general',
                  }}
                  prepend={
                    hasEdits ? (
                      <>
                        <button
                          type="button"
                          className="lg-chip"
                          onClick={() => void onCompareOriginal()}
                          disabled={compareLoading || isStreaming}
                          title="원본(LLM 생성본) ↔ 편집본 차이 비교"
                        >
                          {compareLoading ? '...' : '↔ 원본 비교'}
                        </button>
                        <button
                          type="button"
                          className="lg-chip"
                          onClick={() => void onReevaluate()}
                          disabled={qualityLoading || ccLoading || isStreaming}
                          title="편집본 기준으로 품질·CC 재평가"
                        >
                          {qualityLoading || ccLoading ? '...' : '↻ 재평가'}
                        </button>
                      </>
                    ) : null
                  }
                />
              )}
            </div>
          </section>

          {/* ─── 우(1fr): 사이드 스택 ─── */}
          <aside className="lg-stack">
            {/* QUALITY */}
            <section className="lg-card lg-card-tight">
              <div className="lg-eyebrow">QUALITY · 품질 평가</div>
              <div className="lg-quality-h">
                <div className="lg-score">
                  {Math.round(quality?.total_score ?? 0)}
                  <span>/100</span>
                </div>
                <div className="lg-grade">{quality?.grade ?? '—'}</div>
              </div>
              <div className="lg-quality-bars">
                {QUALITY_CRITERIA.map((c, idx) => {
                  const fieldNames = ['structure', 'length', 'terminology', 'completeness', 'tone'] as const;
                  const score = quality
                    ? Math.round(quality.scores[fieldNames[idx]] ?? 0)
                    : 0;
                  return (
                    <div key={c.k} className="lg-q-row">
                      <div className="lg-q-l">
                        <span className="ko">{c.k}</span>
                        <span className="en">{c.en}</span>
                      </div>
                      <div className="lg-q-bar">
                        <span style={{ width: `${(score / c.max) * 100}%` }} />
                      </div>
                      <span className="lg-q-v">
                        {score}
                        <i>/{c.max}</i>
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="lg-q-tip">
                {qualityLoading
                  ? '평가 중…'
                  : quality?.improvements?.length
                  ? `개선: ${quality.improvements.slice(0, 2).join(' · ')}`
                  : '생성 후 자동 평가됩니다.'}
              </div>
            </section>

            {/* CC */}
            <section className="lg-card lg-card-tight">
              <div className="lg-eyebrow">
                CC · 자동 추천
                {ccLoading && <span className="dim" style={{ marginLeft: 8, fontSize: 11 }}>로딩…</span>}
              </div>
              {(ccRec?.groups ?? [
                { tier: 'required',    label_ko: '필수', label_en: 'REQUIRED',    departments: [] as string[] },
                { tier: 'recommended', label_ko: '권장', label_en: 'RECOMMENDED', departments: [] as string[] },
                { tier: 'optional',    label_ko: '선택', label_en: 'OPTIONAL',    departments: [] as string[] },
              ]).map((group) => {
                const colorMap: Record<string, string> = {
                  required: 'red',
                  recommended: 'amber',
                  optional: 'gray',
                };
                return (
                  <div key={group.tier} className={'lg-cc-row tier-' + colorMap[group.tier]}>
                    <span className="lg-cc-l">{group.label_ko}</span>
                    <div className="lg-cc-chips">
                      {group.departments.length > 0 ? (
                        group.departments.map((d) => (
                          <span key={d} className="lg-cc-chip">
                            {d}
                            <i>{
                              group.tier === 'required' ? 'OEM'
                              : group.tier === 'recommended' ? '결재'
                              : group.tier === 'frequent' ? '자주 함께'
                              : '참조'
                            }</i>
                          </span>
                        ))
                      ) : (
                        <span className="dim" style={{ fontSize: 12 }}>—</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </section>

            {/* FEW-SHOT RAG / STAGES — Plan v1.0: 단계 라이브 진행 + 참조 목록 */}
            <section className="lg-card lg-card-tight">
              <div className="lg-eyebrow">
                {stages.length > 0 ? 'PIPELINE · 단계 진행' : 'FEW-SHOT · RAG 컨텍스트'}
              </div>
              {stages.length > 0 ? (
                <>
                  {stages.map((s, i) => {
                    const icon =
                      s.status === 'ok' ? '✓' :
                      s.status === 'error' ? '✕' :
                      s.status === 'warn' ? '⚠' : '…';
                    const color =
                      s.status === 'ok' ? 'var(--hud-green, #4ade80)' :
                      s.status === 'error' ? 'var(--hud-red, #f87171)' :
                      s.status === 'warn' ? 'var(--hud-orange)' :
                      'var(--hud-text)';
                    const meta = s.meta as Record<string, unknown> | undefined;
                    const provLabel = meta?.provider ? String(meta.provider) : '';
                    const modelLabel = meta?.model ? String(meta.model) : '';
                    return (
                      <div key={i} className="lg-fs-row">
                        <span style={{ color }}>
                          {icon} {s.name.toUpperCase()}
                          {(provLabel || modelLabel) && (
                            <i style={{ marginLeft: 8, fontSize: 11, opacity: 0.7 }}>
                              {provLabel}{modelLabel ? ` · ${modelLabel}` : ''}
                            </i>
                          )}
                        </span>
                        <span className="lg-conf">{s.status}</span>
                      </div>
                    );
                  })}
                  <div className="lg-fs-foot">
                    LLM Router · {provider} · {modelId}
                  </div>
                </>
              ) : (
                <>
                  {MOCK_FEWSHOT.map((row) => (
                    <div key={row.name} className="lg-fs-row">
                      <span>{row.name}</span>
                      <span className="lg-conf">{row.score.toFixed(2)}</span>
                    </div>
                  ))}
                  <div className="lg-fs-foot">ChromaDB · BGE-M3 1024d · 584건</div>
                </>
              )}
            </section>
          </aside>
        </div>
      )}

      {/* HISTORY */}
      {tab === 'history' && (
        <>
          {/* B4 v4.0 — 버전 관리 타임라인 (사용자별 영속 + 검토 워크플로우) */}
          <VersionTimeline
            onLoadVersion={(rendered) => {
              setOutput(rendered, { fromUser: false });
              setTab('internal');
            }}
          />
          <section className="lg-card">
          <div className="lg-card-h">
            <div>
              <div className="lg-eyebrow">HISTORY · 문서 이력</div>
              <h2 className="lg-h2">
                서버 저장소 영구화 {historyDocs.length}건{' '}
                <span className="lg-h2-sub">/ 최근 30개 표시</span>
              </h2>
            </div>
            <div className="lg-actions">
              <button
                className="lg-btn ghost sm"
                onClick={() => void reloadHistory()}
                disabled={historyLoading}
              >
                {historyLoading ? '로딩…' : '↻ 새로고침'}
              </button>
            </div>
          </div>

          {historyError && (
            <div
              style={{
                padding: '10px 14px',
                marginBottom: 14,
                borderRadius: 8,
                background: 'color-mix(in oklab, var(--hud-orange) 12%, transparent)',
                border: '1px solid color-mix(in oklab, var(--hud-orange) 30%, transparent)',
                fontSize: 12,
                color: 'var(--hud-orange)',
                fontFamily: 'var(--hud-font-mono)',
              }}
            >
              ⚠ 서버 저장소 연결 실패 — {historyError}
            </div>
          )}

          <div className="lg-table-wrap">
            <table className="lg-table">
              <thead>
                <tr>
                  <th>제목</th>
                  <th>유형</th>
                  <th>맥락</th>
                  <th>일시</th>
                  <th>품질</th>
                  <th>상태</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {historyDocs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="lg-empty">
                      {historyLoading
                        ? '이력 로딩 중...'
                        : '이력이 없습니다. 초안을 생성하면 자동으로 서버 저장소에 저장됩니다.'}
                    </td>
                  </tr>
                ) : (
                  historyDocs.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <b>{d.meta?.title || '(제목 없음)'}</b>
                        {d.meta?.recipient && (
                          <span className="dim" style={{ fontSize: 11, marginLeft: 8 }}>
                            → {d.meta.recipient}
                          </span>
                        )}
                      </td>
                      <td className="mono dim">{d.doc_type}</td>
                      <td>
                        <span className="lg-pos">
                          {d.context === 'internal' ? '내부' : '외부'}
                        </span>
                      </td>
                      <td className="mono dim">
                        {new Date(d.updated_at).toLocaleString('ko-KR', {
                          dateStyle: 'short',
                          timeStyle: 'short',
                        })}
                      </td>
                      <td className="mono">
                        {d.quality
                          ? `${Math.round(d.quality.total_score)} / 100 (${d.quality.grade})`
                          : '—'}
                      </td>
                      <td>
                        <span
                          className={
                            'lg-state-pill ' +
                            (d.status === 'completed' ? 'ok' : d.status === 'archived' ? 'warn' : '')
                          }
                        >
                          {d.status.toUpperCase()}
                        </span>
                      </td>
                      <td>
                        <button
                          className="lg-btn ghost sm"
                          onClick={() => {
                            // 재편집: 본문/메타를 store 에 적재 후 internal 탭으로 이동
                            setOutput(d.content, { fromUser: false });
                            if (d.meta?.title) setMeta({ title: d.meta.title });
                            if (d.meta?.recipient) setMeta({ recipient: d.meta.recipient });
                            setDocTypeId(d.doc_type);
                            setToneId(d.tone);
                            setTab(d.context === 'external' ? 'external' : 'internal');
                          }}
                        >
                          재편집
                        </button>{' '}
                        <button
                          className="lg-btn ghost sm"
                          onClick={() => void onDeleteHistoryDoc(d.id)}
                          title="삭제"
                        >
                          삭제
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* 시연용 mock diff 미리보기 (이력 없거나 시연 모드 시) */}
          {historyDocs.length === 0 && !historyLoading && (
            <div className="lg-diff">
              <div className="lg-eyebrow" style={{ marginTop: 18, marginBottom: 10 }}>
                DIFF SAMPLE · 시연용 (실 이력 추가 시 비교 모달에서 확인)
              </div>
              {MOCK_DIFF_LINES.map((line, i) => (
                <div key={i} className={`lg-diff-line ${line.type}`}>
                  {line.type === 'add' && '+ '}
                  {line.type === 'del' && '− '}
                  {line.type === 'mod' && '~ '}
                  {line.type === 'ctx' && '  '}
                  {line.text}
                </div>
              ))}
            </div>
          )}
        </section>
        </>
      )}

      {/* B6 v4.0 — 메일 발송 모달
          Feature B Sprint 1 P0 (plan §14.2):
            - versionId 는 현재 draft route 에서 미추적. 0 전달 → 백엔드 412
              block_no_version 으로 사용자에게 "승인 필요" 안내.
              Sprint 2 에서 version_db state 연동 시 실 id 전달.
            - meta.cc 는 사용자가 직접 입력한 CC. ccRec (recommendCC 결과) 의
              departments 는 컴포넌트 1339L 에서 별도 UI 카드로 표시. */}
      <MailSendModal
        isOpen={mailModalOpen}
        onClose={() => setMailModalOpen(false)}
        body={output}
        defaultSubject={
          spcPrefillSubject ||
          meta.title ||
          (docTypes.find((d) => d.id === docTypeId)?.name_ko ?? '')
        }
        docType={docTypeId}
        prefillTo={spcPrefillTo || meta.recipient || ''}
        prefillCc={spcPrefillCc || (meta.cc ?? []).join(', ')}
        versionId={0}
        internalDomains={['ajin.co.kr']}
      />

      {/* P3-3: Diff Modal — 원본(LLM) ↔ 편집본 비교 */}
      {compareOpen && (
        <div
          className="ui-modal-scrim"
          role="dialog"
          aria-modal="true"
          aria-label="원본 편집본 비교"
          onClick={() => setCompareOpen(false)}
        >
          <div
            className="ui-modal size-lg lg-card"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 920, width: '90%', maxHeight: '85vh', overflow: 'auto' }}
          >
            <div className="lg-card-h">
              <div>
                <div className="lg-eyebrow">DIFF · 원본 ↔ 편집본</div>
                <h2 className="lg-h2">버전 비교</h2>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {diff && (
                  <span className="lg-pill">
                    +{diff.stats.added} / −{diff.stats.removed} · 유사도{' '}
                    {Math.round((diff.stats.similarity || 0) * 100)}%
                  </span>
                )}
                <button
                  className="lg-btn ghost sm"
                  onClick={() => setCompareOpen(false)}
                  aria-label="닫기"
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="lg-diff" style={{ maxHeight: '55vh', overflow: 'auto' }}>
              {!diff || diff.lines.length === 0 ? (
                <div className="lg-diff-line">변경 사항이 없습니다.</div>
              ) : (
                diff.lines.map((line, i) => (
                  <div key={i} className={`lg-diff-line ${line.type}`}>
                    {line.type === 'add' && '+ '}
                    {line.type === 'del' && '− '}
                    {line.type === 'mod' && '~ '}
                    {(line.type === 'ctx' || line.type === 'header') && '  '}
                    {line.text}
                  </div>
                ))
              )}
            </div>
            <div
              style={{
                marginTop: 18,
                paddingTop: 14,
                borderTop: '1px dashed color-mix(in oklab, var(--hud-text) 10%, transparent)',
                display: 'flex',
                justifyContent: 'flex-end',
                gap: 8,
              }}
            >
              <button className="lg-btn ghost sm" onClick={() => setCompareOpen(false)}>
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
