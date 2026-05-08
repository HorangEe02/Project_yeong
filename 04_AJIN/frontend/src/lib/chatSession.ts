// v3.6.1 — 채팅 세션 localStorage 영속 (사용자 격리 포함).
//
// 이전엔 chat.tsx 안에서만 정의되어 LeftSidebar 로그아웃 핸들러가 같은 키를 알 수 없었다.
// 결과: SYS_ADMIN 데모 후 다른 계정 재로그인 시 이전 사용자의 환영 메시지가 그대로 노출됨.
//
// 본 모듈은 (1) 키/스키마 단일 출처, (2) PersistedSession.userId 로 사용자 경계 강제,
// (3) 로드 시 userId 불일치하면 즉시 폐기 — 로 위 결함을 차단한다.
//
// 영속 메시지 타입은 chat.tsx 가 정의하지만, 본 모듈은 제너릭으로 다룬다 (순환 import 회피).

export const CHAT_SESSION_LS_KEY = 'ajin-chat-session-v1';

/** localStorage 5MB 한도 보호 + 합리적 컨텍스트 한도 */
export const MAX_PERSISTED_MESSAGES = 50;

export interface PersistedSession<TMessage> {
  /** 세션 소유자의 employee_id. 다른 사용자가 로그인하면 이 세션은 무효. */
  userId: string;
  msgs: TMessage[];
  compareMsgs: TMessage[];
  savedAt: number;
}

/**
 * 저장된 세션 로드.
 * `currentUserId` 와 저장된 `userId` 가 다르면 (= 다른 사용자) `null` 반환 + 즉시 폐기.
 * `currentUserId` 가 비어 있으면(아직 로그인 전) 기존 세션을 유지하지 않고 `null`.
 */
export function loadChatSession<TMessage>(
  currentUserId: string | undefined,
): PersistedSession<TMessage> | null {
  if (!currentUserId) return null;
  try {
    const raw = localStorage.getItem(CHAT_SESSION_LS_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as Partial<PersistedSession<TMessage>>;
    if (!Array.isArray(v?.msgs) || !Array.isArray(v?.compareMsgs)) return null;
    if (typeof v?.userId !== 'string' || v.userId !== currentUserId) {
      // 다른 사용자(또는 userId 없는 구버전) — 폐기
      clearChatSession();
      return null;
    }
    return {
      userId: v.userId,
      msgs: v.msgs as TMessage[],
      compareMsgs: v.compareMsgs as TMessage[],
      savedAt: typeof v.savedAt === 'number' ? v.savedAt : 0,
    };
  } catch {
    /* corrupted — 무시 */
    return null;
  }
}

export function saveChatSession<TMessage>(
  userId: string | undefined,
  msgs: TMessage[],
  compareMsgs: TMessage[],
  sanitize: (arr: TMessage[]) => TMessage[] = (arr) => arr,
): void {
  if (!userId) return; // 로그인 전엔 저장하지 않음
  try {
    const trim = (arr: TMessage[]) =>
      arr.length > MAX_PERSISTED_MESSAGES ? arr.slice(-MAX_PERSISTED_MESSAGES) : arr;
    const payload: PersistedSession<TMessage> = {
      userId,
      msgs: sanitize(trim(msgs)),
      compareMsgs: sanitize(trim(compareMsgs)),
      savedAt: Date.now(),
    };
    localStorage.setItem(CHAT_SESSION_LS_KEY, JSON.stringify(payload));
  } catch {
    /* private mode / quota 초과 — 무시 */
  }
}

export function clearChatSession(): void {
  try {
    localStorage.removeItem(CHAT_SESSION_LS_KEY);
  } catch {
    /* noop */
  }
}
