import type { IntentKind } from './providers/shared';

interface IntentRule {
  intent: IntentKind;
  patterns: RegExp[];
}

/**
 * 규칙 기반 intent 감지. 위에서부터 순차 매칭 (escalate·triage 우선).
 * 어떤 규칙도 매칭 안 되면 'general'. 향후 LLM 기반 분류기로 확장 가능.
 *
 * 주의: escalate는 safety.ts에서도 동일 키워드 재검사 (double check) — intent가 바뀌더라도
 * safety.checkEmergency가 즉시 응급 응답 반환.
 */
const RULES: IntentRule[] = [
  {
    intent: 'escalate',
    patterns: [
      /가슴.{0,3}통증|흉통|호흡.{0,2}곤란|숨.{0,3}(못|안).?쉬|의식.{0,2}(잃|없)/,
      /대량.{0,2}출혈|피가.{0,3}(많이|멈추지)/,
      /자살|자해|죽고.{0,2}싶|죽어.{0,2}버리/,
    ],
  },
  {
    intent: 'triage',
    patterns: [
      /증상|통증|기침|열(?:이|나|있|올)|어지[럽러]|두통|복통|소화불량|구토|설사|발진|가렵|근육통|관절/,
      /아파[요다]?|아픕니다|아프네|쑤[시셔]|쿡쿡|결려|저려/,
    ],
  },
  {
    intent: 'appointment_help',
    patterns: [
      /예약|접수|(진료.{0,3})?방문.{0,3}(하|싶)|예약.{0,3}(하|할|방법)/,
    ],
  },
  {
    intent: 'direction',
    patterns: [
      /어디(?:있|인|에)|위치|찾아가|오시는.?길|주소|응급실.{0,3}어|어떻게.?가/,
    ],
  },
  {
    intent: 'hospital_info',
    patterns: [
      /진료.?시간|영업.?시간|주차|전화|연락처|휴진|휴일|휴무|점심시간/,
    ],
  },
  {
    intent: 'department_info',
    patterns: [
      /(내과|외과|소아|정형|응급의학|가정의학|영상의학|진료과|부서).{0,3}(어느|어떤|있|없|소개|설명)?/,
    ],
  },
];

export function detectIntent(text: string): IntentKind {
  const trimmed = text.trim();
  if (!trimmed) return 'general';
  for (const rule of RULES) {
    if (rule.patterns.some((p) => p.test(trimmed))) {
      return rule.intent;
    }
  }
  return 'general';
}
