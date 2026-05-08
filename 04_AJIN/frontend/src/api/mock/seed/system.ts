// 시스템 메트릭 / 데이터 수집 / 시스템 정보 시드

/**
 * v3.6 — "사업장 상태" 메트릭으로 교체.
 * 이전 형상(employees/errorCodes/departments/testAccounts)은 시스템 정보 섹션의
 * data 필드로 이전됨 (중복 표기 제거).
 *
 * 메트릭 카드 매핑:
 *   1. 가동 설비:    equipmentOnline / equipmentTotal
 *   2. 금일 SPC 알람: dashboard.tsx 가 RTDB live_alarms + ALARMS(F 모듈) 합산
 *   3. 법규 미해결:   openAlarms / criticalAlarms (D 모듈 severity)
 *   4. 시스템 응답:   latencyMs · qps
 */
export const METRICS = {
  equipmentOnline: 25,
  equipmentTotal: 25,
  openAlarms: 1,
  criticalAlarms: 1,
  latencyMs: 124,
  qps: 8.4,
};

export interface IngestionItem {
  label: string;
  current: number;
  total: number;
}

export const INGESTION: IngestionItem[] = [
  { label: 'errors', current: 201, total: 201 },
  { label: 'molds', current: 25, total: 25 },
  { label: 'spc', current: 5, total: 5 },
  { label: 'drawings', current: 15, total: 15 },
  { label: 'inspections', current: 9, total: 9 },
];

export const SYSTEM_HEALTH = {
  gpu: 42,
  latencyMs: 124,
  qps: 8400,
  // 실제 LLMRouter 폴백 체인: Gemini 2.5 Pro → Ollama (qwen3.5/gemma4) → LM Studio
  llmEngines: [
    'Gemini 2.5 Pro',
    'Qwen 3.5 (9B/4B)',
    'Gemma 4 (e4b/e2b)',
    'LM Studio (옵션)',
  ],
  // 비전 모드: Gemini 2.5 Pro 1순위 + Ollama Gemma 4 (Qwen 비전 미지원)
  visionModels: ['Gemini 2.5 Pro (Multimodal)', 'Gemma 4 e4b/e2b'],
  // 임베딩 모델 — Ollama bge-m3 기본, EMBEDDING_BACKEND=gemini 시 Gemini Embeddings
  embeddingModels: ['bge-m3 (Ollama, 기본)', 'Gemini Embeddings (폴백)'],
  mlModels: [
    'Intent Classifier (TF-IDF+LR)',
    'Error TF-IDF',
    'SPC Isolation Forest',
    'Mold XGBoost',
    'Markov Chain',
    'Doc Quality Scorer',
    'Reg Risk RandomForest',
  ],
  rbacLevels: 6,
  permissions: 28,
};

export const SECURITY_LOG = [
  '[AUTH] JWT_VALIDATED',
  '[RBAC] ACCESS_GRANTED',
  '[SYNC] CHROMADB_UP',
  '[LLM] ENGINE_ONLINE',
  '[BACKEND] CLOUDFLARE_TUNNEL_OK',
];

/**
 * 대시보드 시스템 정보 — 실제 백엔드 설정 (.env + core/llm_router.py) 기준.
 *
 * LLM 폴백 체인 (mode 별):
 *   - CHAT/DRAFT:   gemini-2.5-pro → qwen3.5:9b → gemma4:e4b → lm_studio
 *   - VISION:       gemini-2.5-pro → gemma4:e4b (qwen 비전 미지원)
 *   - SUMMARY:      gemini-2.5-pro → qwen3.5:4b → gemma4:e2b
 *   - INTENT:       gemini-2.5-pro → qwen3.5:4b
 *   - EMBEDDING:    bge-m3 (단일, 폴백시 Gemini Embeddings)
 *
 * Circuit Breaker: 3회 실패 → 60초 OPEN, HealthRegistry 로 자동 복구.
 */
export const SYSTEM_INFO = {
  llm: [
    'Gemini 2.5 Pro (1순위)',
    'Qwen 3.5 9B/4B (사내)',
    'Gemma 4 e4b/e2b (경량)',
    'LM Studio (옵션)',
  ],
  vision: ['Gemini 2.5 Pro Multimodal', 'Gemma 4 e4b/e2b'],
  embedding: 'bge-m3 (Ollama) · Gemini Embeddings 폴백',
  ml: '7 종 (Intent · Error TF-IDF · SPC IF · Mold XGB · Markov · DocQual · RegRisk)',
  router: 'LLMRouter 폴백 체인 + Circuit Breaker (3회/60초)',
  data: {
    employees: 329,
    errorCodes: 201,
    molds: 25,
    spcProcesses: 5,
    glossary: 297,
    fewShotRag: 584,
  },
  rbac: '6단계 + 28 세부 권한 + 부서 30',
};
