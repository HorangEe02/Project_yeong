import {
  ALLOWED_DEPARTMENTS,
  type AllowedDepartment,
  type TriageRecommendation,
} from './types';

/**
 * Gemini 에 전달하는 system instruction.
 *
 * 응답 규약:
 *   - JSON 만 출력 (markdown / 추가 텍스트 금지)
 *   - 정확히 3개의 추천
 *   - department 는 ALLOWED_DEPARTMENTS 의 한국어 키 중 하나
 *   - confidence 0..1 내림차순 정렬
 *   - reason 1~2 문장
 *
 * Hospital 별 진료과 목록도 받아 prompt 에 주입할 수 있지만, 본 sprint 에선
 * 표준 15개 목록으로 단순화 — hospital.departments 와의 매핑은 후속 sprint.
 */
export function buildTriageSystemInstruction(): string {
  const list = ALLOWED_DEPARTMENTS.join(', ');
  return `당신은 환자가 작성한 증상 설명을 분석해 가장 적합한 진료과를 추천하는 의료 도우미입니다.

규칙:
1. 진단을 내리지 않습니다. "추천" 으로만 표현하세요.
2. 응답은 다음 JSON 스키마만 출력하세요. 마크다운/설명/머리말 모두 금지:
   {
     "recommendations": [
       { "department": "<진료과>", "confidence": <0..1>, "reason": "<1~2 문장 한국어>" }
     ]
   }
3. 정확히 3 개의 추천을 반환하세요. confidence 는 가장 적합한 진료과부터 내림차순.
4. department 는 다음 목록 중에서만 선택하세요: ${list}.
5. 응급 상황 (가슴 통증·심한 출혈·의식 저하·호흡 곤란 등) 이면 응급의학과를 1순위로 권하고
   reason 에 "즉시 119 또는 응급실 권장" 을 명시하세요.
6. 진료과 외 콘텐츠 (자살 충동·정신건강 위기 등) 가 의심되면 정신건강의학과를 1순위로,
   reason 에 정신건강 위기상담(1393) 를 안내하세요.

[좋은 예시]
입력: "2일째 기침과 미열이 있어요"
출력:
{"recommendations":[{"department":"내과","confidence":0.85,"reason":"기침과 발열은 호흡기·전신 감염 가능성이 높아 내과 진료가 우선입니다."},{"department":"가정의학과","confidence":0.55,"reason":"가벼운 감기 증상을 종합적으로 평가받기에 적합합니다."},{"department":"이비인후과","confidence":0.40,"reason":"기침 원인이 인후·기관지 자극일 수 있어 이비인후과 협진을 고려해 볼 수 있습니다."}]}`;
}

/**
 * Gemini text 응답으로부터 JSON 객체 추출.
 * 모델이 markdown code fence 를 두르거나 머리말을 붙이는 경우 정리.
 *
 * @returns parse 결과 또는 null (실패 → fallback)
 */
export function parseTriageJson(raw: string): {
  recommendations: TriageRecommendation[];
} | null {
  if (!raw) return null;
  let text = raw.trim();

  // ```json ... ``` 또는 ``` ... ``` 제거
  const fence = text.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
  if (fence) text = fence[1].trim();

  // 첫 { 부터 마지막 } 까지 추출 — 모델이 머리말 붙이는 케이스 흡수
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  if (start < 0 || end < 0 || end <= start) return null;
  const slice = text.slice(start, end + 1);

  let parsed: unknown;
  try {
    parsed = JSON.parse(slice);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== 'object') return null;
  const obj = parsed as { recommendations?: unknown };
  if (!Array.isArray(obj.recommendations)) return null;

  const recs: TriageRecommendation[] = [];
  for (const r of obj.recommendations) {
    if (!r || typeof r !== 'object') continue;
    const o = r as {
      department?: unknown;
      confidence?: unknown;
      reason?: unknown;
    };
    if (typeof o.department !== 'string') continue;
    if (typeof o.confidence !== 'number' || !Number.isFinite(o.confidence)) continue;
    if (typeof o.reason !== 'string') continue;
    if (!ALLOWED_DEPARTMENTS.includes(o.department as AllowedDepartment)) continue;
    const conf = Math.max(0, Math.min(1, o.confidence));
    const reason = o.reason.trim().slice(0, 200);
    if (!reason) continue;
    recs.push({ department: o.department, confidence: conf, reason });
  }
  if (recs.length === 0) return null;
  return { recommendations: recs };
}

/**
 * 응급 상황 fallback — LLM 호출 우회 시 사용.
 */
export function emergencyFallback(): TriageRecommendation[] {
  return [
    {
      department: '응급의학과',
      confidence: 1,
      reason: '응급 가능성이 의심됩니다. 즉시 119 또는 가까운 응급실로 이동하세요.',
    },
  ];
}

/**
 * Gemini 응답이 JSON 으로 검증 실패한 경우의 fallback — 일반 진료과 1건만.
 */
export function genericFallback(): TriageRecommendation[] {
  return [
    {
      department: '가정의학과',
      confidence: 0.5,
      reason: '입력하신 증상으로 정확한 진료과를 추천하기 어렵습니다. 가정의학과에서 종합 평가를 받아 보시거나 병원 안내데스크에 문의해 주세요.',
    },
  ];
}
