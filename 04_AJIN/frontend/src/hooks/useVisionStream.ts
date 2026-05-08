// Day 5 Phase 4-B — 비전 채팅 스트리밍 훅 (multipart)
// 백엔드 /chat/vision 은 현재 단일 JSON 응답(OnboardingChatResponse)이므로
// 토큰을 한 번에 emit + done 으로 변환하여 useSSE 와 동일한 콜백 인터페이스를 제공한다.
// 향후 백엔드가 SSE 로 전환되면 fetchEventSource 로 대체할 수 있도록 동일 시그니처 유지.

import { useCallback, useRef, useState } from 'react';
import type { SSEMeta } from '@hooks/useSSE';
import { useChatStore } from '@store/chat';
import { buildVisionUrl, prepareVisionAttachment } from '@api/vision';
import { authHeaders } from '@api/onboarding';

interface UseVisionStreamOptions {
  onToken?: (chunk: string) => void;
  onMetadata?: (meta: Record<string, unknown>) => void;
  onDone?: (finalMeta: Record<string, unknown>) => void;
  onError?: (msg: string, raw?: unknown) => void;
}

export interface VisionStartArgs {
  query: string;
  file: File;
  department?: string;
  model?: string;
}

interface UseVisionStreamReturn {
  isStreaming: boolean;
  meta: SSEMeta;
  start: (args: VisionStartArgs) => Promise<void>;
  stop: () => void;
}

interface VisionResponse {
  response: string;
  model_used: string;
  source: string;
}

export function useVisionStream(options: UseVisionStreamOptions = {}): UseVisionStreamReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const [meta, setMeta] = useState<SSEMeta>({});
  const ctrlRef = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    ctrlRef.current?.abort();
    ctrlRef.current = null;
    setIsStreaming(false);
  }, []);

  const start = useCallback(
    async ({ query, file, department, model }: VisionStartArgs) => {
      stop();
      setMeta({});
      setIsStreaming(true);
      const ctrl = new AbortController();
      ctrlRef.current = ctrl;

      try {
        // 1) Storage 업로드 시도 — Auth 미통합이면 imageUrl=undefined
        const { imageUrl } = await prepareVisionAttachment(file);
        if (imageUrl) {
          // user 메시지의 imageUrl 메타를 갱신 (썸네일 즉시 반영)
          useChatStore.getState().updateActiveUserMeta({ imageUrl });
        }

        // 2) 백엔드 /chat/vision 호출 (multipart)
        const fd = new FormData();
        fd.append('query', query);
        if (department) fd.append('department', department);
        if (model) fd.append('model', model);
        fd.append('file', file);

        const res = await fetch(buildVisionUrl(), {
          method: 'POST',
          headers: { ...authHeaders() },
          body: fd,
          signal: ctrl.signal,
        });
        if (!res.ok) {
          let detail = `${res.status}`;
          try {
            const j = (await res.json()) as { detail?: string };
            if (j?.detail) detail = j.detail;
          } catch {
            /* noop */
          }
          throw new Error(`비전 응답 실패: ${detail}`);
        }
        const json = (await res.json()) as VisionResponse;

        // 3) metadata → token (한 덩어리) → done 로 변환
        const metadata = {
          provider: 'gemini',
          model: json.model_used,
          fallback_from: null,
        };
        setMeta((prev) => ({
          ...prev,
          provider: 'gemini',
          model: json.model_used,
          fallbackFrom: null,
        }));
        options.onMetadata?.(metadata);
        options.onToken?.(json.response);
        const finalMeta = {
          final_provider: 'gemini',
          final_model: json.model_used,
          source: json.source,
        };
        options.onDone?.(finalMeta);
        setIsStreaming(false);
      } catch (e) {
        if ((e as Error).name === 'AbortError') {
          setIsStreaming(false);
          return;
        }
        const msg = e instanceof Error ? e.message : String(e);
        options.onError?.(msg, e);
        setIsStreaming(false);
      } finally {
        ctrlRef.current = null;
      }
    },
    [options, stop],
  );

  return { isStreaming, meta, start, stop };
}
