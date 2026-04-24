import * as admin from 'firebase-admin';

export interface HospitalContext {
  hospitalId: string;
  name: string;
  slug: string;
  contractStatus: string;
  features: Record<string, boolean>;
  departments: Array<{ code: string; name: string; active: boolean }>;
  announcements: Array<{ title: string; body?: string; createdAt?: number }>;
}

interface CacheEntry {
  ctx: HospitalContext;
  loadedAt: number;
}

const CACHE = new Map<string, CacheEntry>();
const TTL_MS = 5 * 60 * 1000; // 5분

/**
 * 병원 RTDB 정보를 로드해서 컴팩트한 context 객체로 반환.
 * 5분 memoize — 짧은 간격 반복 호출에서 RTDB read 절감.
 *
 * 누락된 필드는 sensible default로 채움:
 *   - features: {}
 *   - departments: []
 *   - announcements: []
 */
export async function loadHospitalContext(
  hospitalId: string,
): Promise<HospitalContext> {
  const cached = CACHE.get(hospitalId);
  if (cached && Date.now() - cached.loadedAt < TTL_MS) {
    return cached.ctx;
  }

  const db = admin.database();
  const root = db.ref(`hospitals/${hospitalId}`);

  const [profileSnap, departmentsSnap, announcementsSnap] = await Promise.all([
    root.child('profile').get(),
    root.child('departments').get(),
    root.child('announcements').limitToLast(3).get(),
  ]);

  const profile = (profileSnap.val() ?? {}) as {
    name?: string;
    slug?: string;
    contractStatus?: string;
    features?: Record<string, boolean>;
  };

  const departmentsRaw = (departmentsSnap.val() ?? {}) as Record<
    string,
    { name?: string; code?: string; active?: boolean }
  >;
  const departments = Object.entries(departmentsRaw)
    .map(([key, d]) => ({
      code: d.code ?? key,
      name: d.name ?? key,
      active: d.active !== false,
    }))
    .filter((d) => d.active);

  const announcementsRaw = (announcementsSnap.val() ?? {}) as Record<
    string,
    { title?: string; body?: string; createdAt?: number }
  >;
  const announcements = Object.values(announcementsRaw)
    .map((a) => ({
      title: a.title ?? '(제목 없음)',
      body: a.body,
      createdAt: a.createdAt,
    }))
    .sort((x, y) => (y.createdAt ?? 0) - (x.createdAt ?? 0));

  const ctx: HospitalContext = {
    hospitalId,
    name: profile.name ?? '이름 미등록 병원',
    slug: profile.slug ?? hospitalId,
    contractStatus: profile.contractStatus ?? 'unknown',
    features: profile.features ?? {},
    departments,
    announcements,
  };

  CACHE.set(hospitalId, { ctx, loadedAt: Date.now() });
  return ctx;
}

/**
 * 컨텍스트를 Gemini system instruction 문자열로 렌더.
 * 한국어·존댓말·3-5문장·안전 가이드 포함.
 */
export function renderSystemInstruction(ctx: HospitalContext): string {
  const activeFeatures = Object.entries(ctx.features)
    .filter(([, v]) => v === true)
    .map(([k]) => k);

  const deptLines =
    ctx.departments.length > 0
      ? ctx.departments.map((d) => `- ${d.name} (${d.code})`).join('\n')
      : '- (진료과 정보 없음)';

  const annLines =
    ctx.announcements.length > 0
      ? ctx.announcements
          .slice(0, 3)
          .map((a) => `- ${a.title}${a.body ? `: ${a.body.slice(0, 80)}` : ''}`)
          .join('\n')
      : '- (공지 없음)';

  return `당신은 "${ctx.name}" 공식 안내 챗봇입니다.
본 병원 정보를 근거로 친절하게 답변하세요.

[병원 프로필]
- 이름: ${ctx.name}
- Slug: ${ctx.slug}
- 계약 상태: ${ctx.contractStatus}
- 활성 기능: ${activeFeatures.length > 0 ? activeFeatures.join(', ') : '(none)'}

[진료과]
${deptLines}

[최근 공지]
${annLines}

[답변 스타일]
- 한국어, 존댓말, 3~5문장 이내
- 필요 시 이모지 1개까지 (🏥 💊 🗺️)
- 증상 질문에는 본 병원 진료과 중 2~3개 추천 + "진단이 아님" 고지 필수
- 본 병원에서 제공하지 않는 진료과는 추천 금지
- 모르는 정보는 "병원에 직접 문의 부탁드립니다"

[금지]
- 확정 진단·처방·약물 복용법·용량
- 주민번호·계좌·비밀번호 요청
- 타 병원 추천
- 원격 의료 상담으로 해석될 수 있는 발언

[응급 안내]
- 가슴통증·호흡곤란·의식저하·대량출혈·자살 징후는 즉시 119 + 응급실 + 정신건강 1393`;
}

/** 테스트용 캐시 리셋 */
export function __resetContextCacheForTest(): void {
  CACHE.clear();
}
