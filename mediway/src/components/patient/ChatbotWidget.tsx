import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';
import { RefreshCw, Send } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { sendChatbotMessage } from '@/services/chatbot';
import type { ChatbotError, UIChatMessage } from '@/types/chatbot';

/**
 * 홈 탭에 배치되는 AI 안내 챗봇 위젯.
 *
 * 데이터: 서버 `hospitalChatbot` callable (이미 배포). 응답은 실시간 subscription
 * 아닌 httpsCallable 일회성. chatId 를 유지해 멀티턴 맥락 보존.
 *
 * UX 원칙 (사용자 편의):
 *  - 첫 진입 시 welcome 메시지 + 빠른 질문 제안(4) → 타이핑 없이 시작 가능
 *  - 말풍선: user 우측 primary, assistant 좌측 surface-container
 *  - typing indicator (사용자가 응답 지연을 인지)
 *  - 에러는 친근 한국어, 기술 용어/스택 트레이스 노출 없음
 *  - Rate limit 잔여량 시각화는 의도적으로 생략 (서버는 계속 enforce)
 *  - [새 대화] 버튼으로 chatId 리셋 — 주제 전환 시 컨텍스트 초기화
 *  - 입력창 하단 PII disclaimer (개인정보 금지)
 *  - IME(한국어) 조합 중엔 Enter 로 전송하지 않음 — 오전송 방지
 *  - aria-live=polite 로 스크린 리더에도 응답 전달
 *
 * 미로그인 / 익명 / profile.hospitalId 없음 시 위젯 자체를 렌더하지 않음 (null).
 */

const QUICK_SUGGESTIONS = [
  '예약 확인 방법',
  '접수는 어떻게 하나요?',
  '주차 안내',
  '진료실 위치',
];

/** 서버 rateLimit.ts LIMITS.perHour 와 동기화 — 변경 시 두 쪽 같이 수정 */
const RATE_LIMIT_PER_HOUR = 25;

const ERROR_COPY: Record<ChatbotError['code'], string> = {
  unauthenticated: '로그인 후 다시 시도해 주세요.',
  rate_limited: '잠시 후 다시 시도해 주세요.',
  invalid_argument: '질문을 다시 확인해 주세요.',
  network: '네트워크가 불안정합니다. 다시 시도해 주세요.',
  internal: '챗봇 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.',
  unknown: '일시적인 오류가 발생했습니다. 다시 시도해 주세요.',
};

const WELCOME_MESSAGE: UIChatMessage = {
  id: 'welcome',
  role: 'assistant',
  text: '안녕하세요! MediWay 안내 도우미입니다. 궁금한 점을 물어보세요.',
  createdAt: 0,
  isWelcome: true,
};

function newMessageId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function ChatbotWidget() {
  const user = useAuthStore((s) => s.user);
  const profile = useAuthStore((s) => s.profile);
  const hospitalId = profile?.hospitalId ?? null;
  const isAnon = user?.isAnonymous ?? true;

  const [messages, setMessages] = useState<UIChatMessage[]>([WELCOME_MESSAGE]);
  const [chatId, setChatId] = useState<string | undefined>(undefined);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [remainingHour, setRemainingHour] = useState<number | null>(null);
  const composingRef = useRef(false);
  const threadRef = useRef<HTMLDivElement | null>(null);

  // thread 하단 auto-scroll
  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending]);

  const showQuickSuggestions = useMemo(
    () => messages.length <= 1 && !sending,
    [messages.length, sending],
  );

  const handleSend = useCallback(
    async (rawText: string) => {
      const userText = rawText.trim();
      if (!userText || sending || !hospitalId) return;

      setErrorMsg(null);
      setInput('');
      const userMsg: UIChatMessage = {
        id: newMessageId(),
        role: 'user',
        text: userText,
        createdAt: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setSending(true);

      try {
        const res = await sendChatbotMessage({
          hospitalId,
          userText,
          chatId,
        });
        const botMsg: UIChatMessage = {
          id: newMessageId(),
          role: 'assistant',
          text: res.reply,
          createdAt: Date.now(),
        };
        setMessages((prev) => [...prev, botMsg]);
        if (res.chatId) setChatId(res.chatId);
        if (res.rateLimit) setRemainingHour(res.rateLimit.remainingHour);
      } catch (err) {
        const typed = err as ChatbotError;
        const copy = ERROR_COPY[typed.code] ?? ERROR_COPY.unknown;
        setErrorMsg(copy);
        if (typed.code === 'rate_limited') setRemainingHour(0);
      } finally {
        setSending(false);
      }
    },
    [chatId, hospitalId, sending],
  );

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter') return;
    if (e.shiftKey) return; // Shift+Enter → newline
    if (composingRef.current) return; // IME 조합 중엔 전송 금지
    e.preventDefault();
    void handleSend(input);
  };

  const handleNewConversation = () => {
    setMessages([WELCOME_MESSAGE]);
    setChatId(undefined);
    setInput('');
    setErrorMsg(null);
  };

  if (!user || isAnon || !hospitalId) return null;

  return (
    <section
      aria-label="AI 챗봇"
      className="flex flex-col gap-3 rounded-xl bg-surface-container-lowest p-4"
    >
      <header className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-on-surface">AI 안내 도우미</h3>
          {remainingHour !== null && (
            <span
              className="rounded-full bg-surface-container px-2 py-0.5 text-[11px] font-medium text-on-surface-variant tabular-nums"
              aria-label={`시간당 남은 질문 ${remainingHour} / ${RATE_LIMIT_PER_HOUR}`}
              title="시간당 사용 가능한 질문 수"
            >
              남은 질문 {remainingHour}/{RATE_LIMIT_PER_HOUR}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={handleNewConversation}
          className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-on-surface-variant hover:bg-surface-container"
          aria-label="새 대화 시작"
          disabled={sending}
        >
          <RefreshCw className="h-3.5 w-3.5" />
          새 대화
        </button>
      </header>

      <div
        ref={threadRef}
        role="log"
        aria-live="polite"
        className="flex h-64 flex-col gap-2 overflow-y-auto rounded-lg bg-surface-container-low p-3"
      >
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {sending && <TypingIndicator />}
        {errorMsg && (
          <div className="self-start rounded-lg bg-surface-container p-2 text-xs text-primary">
            {errorMsg}
          </div>
        )}
      </div>

      {showQuickSuggestions && (
        <div className="flex flex-wrap gap-2">
          {QUICK_SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => handleSend(s)}
              className="rounded-full border border-outline-variant px-3 py-1 text-xs text-on-surface hover:bg-surface-container"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => {
            composingRef.current = true;
          }}
          onCompositionEnd={() => {
            composingRef.current = false;
          }}
          placeholder="질문을 입력하세요"
          aria-label="질문 입력"
          rows={1}
          disabled={sending}
          className="min-h-[40px] flex-1 resize-none rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-sm text-on-surface disabled:opacity-50"
        />
        <button
          type="button"
          onClick={() => void handleSend(input)}
          disabled={sending || !input.trim()}
          aria-label="전송"
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-on-primary disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
      <p className="text-[11px] text-on-surface-variant">
        개인정보(이름·주민등록번호·연락처 등)는 입력하지 마세요. AI 답변은 참고용이며 진단이 아닙니다.
      </p>
    </section>
  );
}

function MessageBubble({ message }: { message: UIChatMessage }) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
          isUser
            ? 'bg-primary text-on-primary'
            : 'bg-surface-container-lowest text-on-surface'
        }`}
      >
        {message.text}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="rounded-lg bg-surface-container-lowest px-3 py-2 text-sm text-on-surface-variant">
        <span className="inline-flex gap-1">
          <span className="h-2 w-2 animate-pulse rounded-full bg-on-surface-variant" />
          <span
            className="h-2 w-2 animate-pulse rounded-full bg-on-surface-variant"
            style={{ animationDelay: '0.15s' }}
          />
          <span
            className="h-2 w-2 animate-pulse rounded-full bg-on-surface-variant"
            style={{ animationDelay: '0.3s' }}
          />
        </span>
      </div>
    </div>
  );
}
