// SSE 스트리밍 훅 — Day 4 C 도우미 차단 해제
// 백엔드 표준 포맷: {type: "metadata"|"token"|"done"|"error", content: str|null, metadata: dict|null}
// FastAPI /api/onboarding/chat (POST + SSE) 호환
// v3.3 Phase F-3 — action_card / detection 이벤트 추가 (Phase E 백엔드 정합).

import { useCallback, useRef, useState } from 'react';
import { fetchEventSource, type FetchEventSourceInit } from '@microsoft/fetch-event-source';
import { useAuthStore } from '@store/auth';
import type { ActionCard } from '@/components/chat/cards/types';

export type StreamEventType =
  | 'metadata'
  | 'token'
  | 'done'
  | 'error'
  | 'detection'
  | 'action_card';

export interface StreamEvent {
  type: StreamEventType;
  content: string | null;
  metadata: Record<string, unknown> | null;
}

// v3.3 Phase F-3 — 액션 디텍터 메타 (action_card 직전에 도착).
export interface DetectionEvent {
  kind: ActionCard['kind'];
  confidence: number;
  matched_keyword: string;
}

export interface SSEMeta {
  provider?: string;
  model?: string;
  fallbackFrom?: string | null;
  finalProvider?: string;
  finalModel?: string;
  ttftMs?: number;
  latencyMs?: number;
}

interface UseSSEOptions {
  onToken?: (chunk: string) => void;
  onMetadata?: (meta: Record<string, unknown>) => void;
  onDone?: (finalMeta: Record<string, unknown>) => void;
  onError?: (msg: string, raw?: unknown) => void;
  /** Plan v1.0 — /draft/stream-v2 의 stage 이벤트 (classify/rag/security/llm/render) */
  onStage?: (stage: {
    name: string;
    status: 'running' | 'ok' | 'warn' | 'error';
    meta?: Record<string, unknown>;
  }) => void;
  /** v3.3 Phase F-3 — action_card 이벤트 (백엔드 inline_actions 활성 시 송출). */
  onActionCard?: (card: ActionCard) => void;
  /** v3.3 Phase F-3 — detection 이벤트 (action_card 직전, 디버그/UX 인디케이터용). */
  onDetection?: (det: DetectionEvent) => void;
}

export interface SSEStartArgs {
  url: string;
  body: unknown;
  signal?: AbortSignal;
}

interface UseSSEReturn {
  text: string;
  isStreaming: boolean;
  meta: SSEMeta;
  start: (args: SSEStartArgs) => Promise<void>;
  stop: () => void;
  reset: () => void;
}

function pickString(meta: Record<string, unknown>, key: string): string | undefined {
  const v = meta[key];
  return typeof v === 'string' ? v : undefined;
}

function pickNumber(meta: Record<string, unknown>, key: string): number | undefined {
  const v = meta[key];
  return typeof v === 'number' ? v : undefined;
}

export function useSSE(options: UseSSEOptions = {}): UseSSEReturn {
  const [text, setText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [meta, setMeta] = useState<SSEMeta>({});
  const ctrlRef = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    ctrlRef.current?.abort();
    ctrlRef.current = null;
    setIsStreaming(false);
  }, []);

  const reset = useCallback(() => {
    setText('');
    setMeta({});
    setIsStreaming(false);
  }, []);

  const start = useCallback(
    async ({ url, body, signal }: SSEStartArgs) => {
      stop();
      setText('');
      setMeta({});
      setIsStreaming(true);
      const ctrl = new AbortController();
      ctrlRef.current = ctrl;
      // Plan v1.0 — done 이후 onerror/onclose 발동 시 onError 콜백 무시 (false positive 방지)
      let doneSeen = false;
      // Plan v1.0 — 60초 안에 첫 token 이 도착 안 하면 LLM/프록시 stall 의심 — abort + 명확한 에러.
      // stage 이벤트는 빠르게 흘러도 LLM 단에서 막힐 수 있으므로 token 단위로 판정.
      let firstTokenSeen = false;
      const stallTimer = setTimeout(() => {
        if (!firstTokenSeen && !doneSeen) {
          options.onError?.(
            'LLM 응답이 60초 내에 도착하지 않았습니다 — 모델 cold start, 네트워크/프록시 buffering, 또는 Ollama 서버 정지 가능성. 다른 모델로 시도하거나 잠시 후 다시 시도해 주세요.',
          );
          ctrl.abort();
        }
      }, 60_000);

      const linkedSignal = signal
        ? AbortSignal.any?.([ctrl.signal, signal]) ?? ctrl.signal
        : ctrl.signal;

      const token = useAuthStore.getState().accessToken;

      try {
        await fetchEventSource(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            // Plan v1.0 — 일부 프록시/SW 가 Content-Type 을 변경하는 환경에서도
            // SSE 응답을 받기 위해 Accept 명시 + onopen 에서 status 만 검증.
            Accept: 'text/event-stream',
            'Cache-Control': 'no-cache',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(body),
          signal: linkedSignal,
          openWhenHidden: true,
          // Plan v1.0 — 라이브러리 기본 onopen 은 content-type 'text/event-stream' 만 허용.
          // 일부 사용자 환경(회사 프록시/SW)이 헤더를 'text/html' 로 변환하는 경우가 있어
          // status 200 만 검증하여 통과시킨다 (응답 본문이 SSE 포맷이면 onmessage 가 정상 파싱).
          async onopen(response) {
            if (response.ok) {
              return;
            }
            throw new Error(`SSE open 실패 — HTTP ${response.status}: ${response.statusText}`);
          },
          onmessage(ev) {
            if (!ev.data) return;

            // ── Plan v1.0 — /draft/stream-v2 named events 분기 ──
            // 'event: stage|token|done' 가 명시된 경우 새 프로토콜.
            // 명시 없으면 (default 'message') 레거시 envelope JSON.
            const eventName = ev.event ?? '';
            if (eventName === 'token') {
              const chunk = ev.data;
              if (chunk) {
                firstTokenSeen = true; // 실제 LLM 토큰 1개라도 오면 stall timer 해제
                setText((prev) => prev + chunk);
                options.onToken?.(chunk);
              }
              return;
            }
            if (eventName === 'stage') {
              try {
                const stage = JSON.parse(ev.data) as {
                  name: string;
                  status: 'running' | 'ok' | 'warn' | 'error';
                  meta?: Record<string, unknown>;
                };
                options.onStage?.(stage);
                if (stage.meta) {
                  setMeta((prev) => ({
                    ...prev,
                    provider: pickString(stage.meta!, 'provider') ?? prev.provider,
                    model: pickString(stage.meta!, 'model') ?? prev.model,
                    finalProvider:
                      pickString(stage.meta!, 'final_provider') ?? prev.finalProvider,
                    finalModel: pickString(stage.meta!, 'final_model') ?? prev.finalModel,
                  }));
                }
              } catch {
                /* ignore malformed stage */
              }
              return;
            }
            if (eventName === 'done') {
              doneSeen = true;
              setIsStreaming(false);
              try {
                const m = JSON.parse(ev.data) as Record<string, unknown>;
                options.onDone?.(m);
              } catch {
                options.onDone?.({});
              }
              return;
            }

            // ── 레거시 envelope (eventName === '' || 'message') ──
            let parsed: StreamEvent;
            try {
              parsed = JSON.parse(ev.data) as StreamEvent;
            } catch {
              return; // heartbeat / invalid — 무시
            }

            switch (parsed.type) {
              case 'metadata': {
                const m = parsed.metadata ?? {};
                setMeta((prev) => ({
                  ...prev,
                  provider: pickString(m, 'provider') ?? prev.provider,
                  model: pickString(m, 'model') ?? prev.model,
                  fallbackFrom:
                    'fallback_from' in m
                      ? (m.fallback_from as string | null)
                      : prev.fallbackFrom,
                  finalProvider: pickString(m, 'final_provider') ?? prev.finalProvider,
                  finalModel: pickString(m, 'final_model') ?? prev.finalModel,
                  ttftMs: pickNumber(m, 'ttft_ms') ?? prev.ttftMs,
                  latencyMs: pickNumber(m, 'latency_ms') ?? prev.latencyMs,
                }));
                options.onMetadata?.(m);
                break;
              }
              case 'token':
                if (parsed.content) {
                  const chunk = parsed.content;
                  firstTokenSeen = true; // 레거시 envelope 도 token 도착 시점에 stall timer 해제
                  setText((prev) => prev + chunk);
                  options.onToken?.(chunk);
                }
                break;
              case 'done':
                doneSeen = true;
                setIsStreaming(false);
                options.onDone?.(parsed.metadata ?? {});
                break;
              case 'error':
                setIsStreaming(false);
                options.onError?.(parsed.content ?? 'unknown', parsed.metadata);
                break;
              case 'detection': {
                // v3.3 Phase F-3 — Phase E 백엔드의 액션 디텍터 결과
                const raw = ev.data;
                try {
                  const det = JSON.parse(raw) as Record<string, unknown>;
                  const kind = det.kind as ActionCard['kind'] | undefined;
                  if (kind) {
                    options.onDetection?.({
                      kind,
                      confidence: typeof det.confidence === 'number' ? det.confidence : 0,
                      matched_keyword:
                        typeof det.matched_keyword === 'string' ? det.matched_keyword : '',
                    });
                  }
                } catch {
                  /* malformed — 무시 */
                }
                break;
              }
              case 'action_card': {
                // v3.3 Phase F-3 — Phase E 백엔드의 카드 페이로드
                const raw = ev.data;
                try {
                  const evt = JSON.parse(raw) as { kind?: string; payload?: unknown };
                  if (evt.kind && evt.payload) {
                    options.onActionCard?.({
                      kind: evt.kind as ActionCard['kind'],
                      payload: evt.payload as ActionCard['payload'],
                    } as ActionCard);
                  }
                } catch {
                  /* malformed — 무시 */
                }
                break;
              }
            }
          },
          onerror(err) {
            // Plan v1.0 — done 이벤트 이미 수신했으면 false positive 무시
            if (doneSeen) {
              setIsStreaming(false);
              throw err;
            }
            options.onError?.(err instanceof Error ? err.message : String(err), err);
            setIsStreaming(false);
            throw err; // throw → 재시도 중단
          },
          onclose() {
            setIsStreaming(false);
          },
        } satisfies FetchEventSourceInit);
      } catch (e) {
        // Plan v1.0 — done 이미 수신 → onError 콜백 억제 (false positive 방지)
        if (!doneSeen && (e as Error).name !== 'AbortError') {
          options.onError?.(e instanceof Error ? e.message : String(e), e);
        }
        setIsStreaming(false);
      } finally {
        clearTimeout(stallTimer);
        ctrlRef.current = null;
      }
    },
    [options, stop],
  );

  return { text, isStreaming, meta, start, stop, reset };
}
