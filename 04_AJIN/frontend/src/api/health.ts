import { api } from './client';

export type LlmProvider = 'ollama' | 'gemini';

export interface RoutingStatus {
  primary_provider: LlmProvider;
  fallback_enabled: boolean;
  embedding_backend: 'ollama' | 'gemini' | 'auto';
}

export interface OllamaStatus {
  ok: boolean;
  base_url: string;
  is_tunnel: boolean;
  model_count: number;
  models: string[];
  error: string;
}

export interface GeminiStatus {
  api_key_present: boolean;
  model: string;
  feature_b_blocked: boolean;
}

export interface LlmStatusResponse {
  status: 'ok' | 'degraded' | 'error';
  summary: string;
  routing: RoutingStatus;
  ollama: OllamaStatus;
  gemini: GeminiStatus;
  tunnel_active: boolean;
}

export async function fetchLlmStatus(): Promise<LlmStatusResponse> {
  const { data } = await api.get<LlmStatusResponse>('/health/llm-status');
  return data;
}
