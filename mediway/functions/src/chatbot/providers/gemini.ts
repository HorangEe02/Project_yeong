import axios, { AxiosError } from 'axios';
import type { ChatMessage } from './shared';

interface GeminiContent {
  role: 'user' | 'model';
  parts: Array<{ text: string }>;
}

interface GeminiRequest {
  systemInstruction?: { parts: Array<{ text: string }> };
  contents: GeminiContent[];
  generationConfig?: {
    temperature?: number;
    maxOutputTokens?: number;
    topP?: number;
    topK?: number;
  };
  safetySettings?: Array<{ category: string; threshold: string }>;
}

interface GeminiResponse {
  candidates?: Array<{
    content?: { parts?: Array<{ text?: string }> };
    finishReason?: string;
  }>;
  promptFeedback?: { blockReason?: string };
  usageMetadata?: {
    promptTokenCount?: number;
    candidatesTokenCount?: number;
    totalTokenCount?: number;
  };
}

export interface GeminiChatResult {
  reply: string;
  tokensIn: number;
  tokensOut: number;
  finishReason: string | null;
  blockReason: string | null;
}

/**
 * Google AI Studio Gemini `generateContent` 호출.
 * REST endpoint: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
 * 인증: URL query `?key={API_KEY}`
 *
 * 주의:
 *   - apiKey는 절대 로그에 찍지 말 것 (Axios error interceptor 대신 수동 catch)
 *   - safetySettings는 Gemini 기본값 유지 (모든 BLOCK_MEDIUM_AND_ABOVE)
 */
export async function geminiChat(params: {
  apiKey: string;
  model?: string;
  systemInstruction: string;
  history: ChatMessage[];
  userText: string;
  temperature?: number;
  maxOutputTokens?: number;
}): Promise<GeminiChatResult> {
  const model = params.model ?? 'gemini-2.5-flash';
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(params.apiKey)}`;

  const contents: GeminiContent[] = [
    ...params.history.map((m) => ({
      role: m.role,
      parts: [{ text: m.text }],
    })),
    { role: 'user' as const, parts: [{ text: params.userText }] },
  ];

  const body: GeminiRequest = {
    systemInstruction: { parts: [{ text: params.systemInstruction }] },
    contents,
    generationConfig: {
      temperature: params.temperature ?? 0.3,
      maxOutputTokens: params.maxOutputTokens ?? 512,
    },
  };

  try {
    const r = await axios.post<GeminiResponse>(url, body, {
      timeout: 30_000,
      headers: { 'Content-Type': 'application/json' },
    });
    const candidate = r.data.candidates?.[0];
    const reply =
      candidate?.content?.parts?.map((p) => p.text ?? '').join('').trim() ?? '';
    return {
      reply,
      tokensIn: r.data.usageMetadata?.promptTokenCount ?? 0,
      tokensOut: r.data.usageMetadata?.candidatesTokenCount ?? 0,
      finishReason: candidate?.finishReason ?? null,
      blockReason: r.data.promptFeedback?.blockReason ?? null,
    };
  } catch (err) {
    // apiKey가 URL에 있으므로 error 메시지를 그대로 전파하지 않음
    const axErr = err as AxiosError<{ error?: { message?: string; status?: string } }>;
    const status = axErr.response?.status ?? 0;
    const serverMsg = axErr.response?.data?.error?.message ?? axErr.message;
    const safe = new Error(`Gemini API 오류 (status=${status}): ${serverMsg}`);
    (safe as Error & { status?: number }).status = status;
    throw safe;
  }
}
