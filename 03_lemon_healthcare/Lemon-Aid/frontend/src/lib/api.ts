import type { AnalyzeImageInput, ApiResult, WebReadiness } from './types';

const DEFAULT_WEB_API_BASE_URL = '/api/lemon';

/**
 * Reads the browser-safe Lemon API proxy base URL.
 *
 * Returns:
 *   Same-origin API proxy URL for the React web app.
 */
export function getApiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_LEMON_WEB_API_BASE_URL || DEFAULT_WEB_API_BASE_URL).replace(
    /\/$/,
    '',
  );
}

/**
 * Builds the readiness endpoint URL for proxy or direct-backend mode.
 *
 * Returns:
 *   Readiness URL used by read-only API smoke checks.
 */
export function getApiReadinessUrl(): string {
  const baseUrl = getApiBaseUrl();
  return baseUrl.endsWith('/api/v1') ? `${baseUrl.slice(0, -'/api/v1'.length)}/ready` : `${baseUrl}/ready`;
}

/**
 * Returns deployment readiness values that can be shown in the UI.
 *
 * Returns:
 *   A browser-safe readiness snapshot for Vercel and Supabase configuration.
 */
export function getWebReadiness(): WebReadiness {
  return {
    apiBaseUrl: getApiBaseUrl(),
    supabaseConfigured: Boolean(
      process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    ),
    vercelReady: true,
  };
}

/**
 * Uploads a browser File to the existing Lemon-Aid backend image endpoints.
 *
 * Args:
 *   input: Selected file, mode, and optional authorization data.
 *
 * Returns:
 *   Normalized result for rendering by the mobile web prototype.
 */
export async function analyzeImage(input: AnalyzeImageInput): Promise<ApiResult> {
  const endpoint =
    input.mode === 'meal' ? '/meals/analyze-image' : '/supplements/analyze';
  const form = new FormData();
  form.append('image', input.file);
  form.append(
    'client_request_id',
    `web-${input.mode}-${Date.now()}-${Math.round(Math.random() * 10000)}`,
  );

  if (input.mode === 'meal') {
    form.append('meal_type', input.mealType);
  } else {
    form.append('ocr_provider', input.ocrProvider);
  }

  const headers: HeadersInit = {
    Accept: 'application/json',
  };
  if (input.bearerToken?.trim()) {
    headers.Authorization = `Bearer ${input.bearerToken.trim()}`;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}${endpoint}`, {
      method: 'POST',
      headers,
      body: form,
    });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        payload,
        message: readErrorMessage(payload) ?? `HTTP ${response.status}`,
      };
    }
    return { ok: true, status: response.status, payload };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : '알 수 없는 요청 오류',
    };
  }
}

/**
 * Performs a read-only backend readiness smoke check.
 *
 * Returns:
 *   User-facing status text summarizing OCR/YOLO readiness availability.
 */
export async function runApiReadinessSmoke(): Promise<string> {
  try {
    const response = await fetch(getApiReadinessUrl(), {
      headers: {
        Accept: 'application/json',
      },
    });
    const payload = (await response.json()) as Record<string, unknown>;
    if (!response.ok) {
      return `API readiness 오류: HTTP ${response.status}`;
    }
    const ocrProvider = readNestedString(payload, ['ocr', 'primary_provider']) ?? 'unknown';
    const ocrStatus = readConfiguredOcrStatus(payload) ?? 'unknown';
    const foodYolo = readNestedBoolean(payload, ['vision', 'food_yolo_enabled']);
    const foodModel = readNestedBoolean(payload, ['vision', 'food_yolo_model_configured']);
    return `API 연결 가능 · OCR ${ocrProvider}(${ocrStatus}) · YOLO ${statusLabel(foodYolo)} · 모델 ${statusLabel(foodModel)}`;
  } catch (error) {
    return error instanceof Error
      ? `API readiness 연결 실패: ${error.message}`
      : 'API readiness 연결 실패';
  }
}

/**
 * Performs a read-only Supabase smoke check through the Next.js runtime.
 *
 * Returns:
 *   User-facing status text for Vercel runtime Supabase connectivity.
 */
export async function runSupabaseRuntimeSmoke(): Promise<string> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/supabase-smoke`, {
      headers: {
        Accept: 'application/json',
      },
    });
    const payload = (await response.json()) as Record<string, unknown>;
    if (!response.ok || payload.ok !== true) {
      const code = typeof payload.code === 'string' ? payload.code : `HTTP ${response.status}`;
      return `Supabase runtime 오류: ${code}`;
    }
    const status = typeof payload.status === 'number' ? payload.status : response.status;
    return `Supabase runtime REST 연결 가능 · HTTP ${status}`;
  } catch (error) {
    return error instanceof Error
      ? `Supabase runtime 연결 실패: ${error.message}`
      : 'Supabase runtime 연결 실패';
  }
}

/**
 * Checks deployment readiness through the same Next.js runtime as Vercel.
 *
 * Returns:
 *   User-facing status text without env values or secret material.
 */
export async function runDeploymentStatusSmoke(): Promise<string> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/deployment-status`, {
      headers: {
        Accept: 'application/json',
      },
    });
    const payload = (await response.json()) as Record<string, unknown>;
    const backendReady = readNestedBoolean(payload, ['backend', 'ok']);
    const supabaseReady = readNestedBoolean(payload, ['supabase', 'ok']);
    const backendCode = readNestedString(payload, ['backend', 'code']);
    const supabaseCode = readNestedString(payload, ['supabase', 'code']);
    if (!response.ok || payload.ok !== true) {
      return `배포 준비 미완료 · backend ${backendCode ?? statusLabel(backendReady)} · supabase ${supabaseCode ?? statusLabel(supabaseReady)}`;
    }
    return `배포 준비 가능 · backend ${statusLabel(backendReady)} · supabase ${statusLabel(supabaseReady)}`;
  } catch (error) {
    return error instanceof Error
      ? `배포 상태 확인 실패: ${error.message}`
      : '배포 상태 확인 실패';
  }
}

/**
 * Builds a deterministic sample response for UI-only feature tests.
 *
 * Args:
 *   mode: Supplement or meal result mode.
 *
 * Returns:
 *   A payload shaped like the current backend preview contract.
 */
export function buildSamplePayload(mode: 'supplement' | 'meal'): unknown {
  if (mode === 'meal') {
    return {
      analysis_id: 'sample-meal-analysis',
      meal_id: '00000000-0000-4000-8000-000000000001',
      status: 'requires_review',
      meal_type: 'lunch',
      food_candidates: [
        {
          display_name: '현미밥',
          portion_amount: 1,
          portion_unit: '공기',
          kcal: 310,
          confidence: 0.82,
          source: 'vision',
        },
      ],
      warning_codes: ['review_required'],
      pipeline_metadata: {
        detector_used: true,
        classifier_used: true,
        raw_image_stored: false,
        raw_provider_payload_stored: false,
      },
    };
  }
  return {
    analysis_id: 'sample-supplement-analysis',
    status: 'requires_review',
    parsed_product: {
      product_name: '멀티비타민 포 우먼',
      manufacturer: '샘플 제조사',
    },
    ingredient_candidates: [
      {
        display_name: '비타민 D',
        amount: 25,
        unit: 'ug',
        confidence: 0.91,
      },
      {
        display_name: '칼슘',
        amount: 300,
        unit: 'mg',
        confidence: 0.86,
      },
    ],
    intake_method: {
      text: '1일 1회, 1회 1정씩 물과 함께 섭취',
      confidence: 0.88,
    },
    precautions: [
      {
        text: '임신, 수유 중이거나 질환이 있는 경우 전문가와 상담하세요.',
        severity: 'warning',
        confidence: 0.84,
      },
    ],
    missing_required_sections: [],
    warnings: ['requires_user_confirmation'],
    pipeline_metadata: {
      ocr_status: 'success',
      vision_status: 'skipped',
      llm_status: 'success',
      ocr_provider: 'sample',
      ocr_text_present: true,
      raw_image_stored: false,
      raw_ocr_text_stored: false,
    },
    recommendation_preview: {
      summary: '일일 권장량과 현재 복용 이력을 함께 확인해야 합니다.',
      safety_level: 'review',
    },
  };
}

function readErrorMessage(payload: unknown): string | undefined {
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }
  const record = payload as Record<string, unknown>;
  const detail = record.detail;
  if (typeof detail === 'string') {
    return detail;
  }
  const message = record.message;
  return typeof message === 'string' ? message : undefined;
}

function readNestedBoolean(record: Record<string, unknown>, path: string[]): boolean | undefined {
  let value: unknown = record;
  for (const key of path) {
    if (!value || typeof value !== 'object') {
      return undefined;
    }
    value = (value as Record<string, unknown>)[key];
  }
  return typeof value === 'boolean' ? value : undefined;
}

function readNestedString(record: Record<string, unknown>, path: string[]): string | undefined {
  let value: unknown = record;
  for (const key of path) {
    if (!value || typeof value !== 'object') {
      return undefined;
    }
    value = (value as Record<string, unknown>)[key];
  }
  return typeof value === 'string' ? value : undefined;
}

function readConfiguredOcrStatus(record: Record<string, unknown>): string | undefined {
  const ocr = record.ocr;
  if (!ocr || typeof ocr !== 'object') {
    return undefined;
  }
  const providers = (ocr as Record<string, unknown>).providers;
  if (!Array.isArray(providers)) {
    return undefined;
  }
  const configured = providers.find((provider) => {
    return (
      provider &&
      typeof provider === 'object' &&
      (provider as Record<string, unknown>).selector === 'configured'
    );
  });
  if (!configured || typeof configured !== 'object') {
    return undefined;
  }
  const status = (configured as Record<string, unknown>).status;
  return typeof status === 'string' ? status : undefined;
}

function statusLabel(value: boolean | undefined): string {
  if (value === true) return 'ready';
  if (value === false) return 'not ready';
  return 'unknown';
}
