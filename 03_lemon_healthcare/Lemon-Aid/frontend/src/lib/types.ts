export type AnalysisMode = 'supplement' | 'meal';

export type TabKey = 'home' | 'chat' | 'camera' | 'score' | 'settings' | 'result';

export interface AnalyzeImageInput {
  mode: AnalysisMode;
  file: File;
  bearerToken?: string;
  ocrProvider: string;
  imageRole: string;
  mealType: string;
}

export interface ApiResult {
  ok: boolean;
  status?: number;
  payload?: unknown;
  message?: string;
}

export interface WebReadiness {
  apiBaseUrl: string;
  supabaseConfigured: boolean;
  vercelReady: boolean;
}
