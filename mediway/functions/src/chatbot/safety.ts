import { detectIntent } from './intent';

export const STANDARD_DISCLAIMER = '본 답변은 진단이 아니며 최종 판단은 의료진이 합니다.';

export const EMERGENCY_RESPONSE = `🚨 응급 증상이 의심됩니다.

즉시 119에 전화하거나 가까운 응급실로 오세요.
정신건강 위기 상담: 1393 (24시간 무료)

본 대화는 의학적 진단이 아닙니다.`;

/**
 * 응급 키워드 감지. intent가 'escalate'로 분류되면 LLM 우회해
 * 하드코드 안전 응답으로 대체.
 */
export function checkEmergency(text: string): boolean {
  return detectIntent(text) === 'escalate';
}

/**
 * LLM 호출 우회용 응급 응답.
 */
export function emergencyResponse(): string {
  return EMERGENCY_RESPONSE;
}

/**
 * PII 요청 감지 — 주민번호, 계좌번호, 비밀번호, 본인확인번호.
 */
const PII_PATTERNS: RegExp[] = [
  /주민.{0,3}(등록)?.{0,3}번호/,
  /계좌.{0,3}번호/,
  /비밀.?번호|pin.?번호|pw/i,
  /카드.{0,3}번호/,
];

export function checkPiiRequest(text: string): boolean {
  return PII_PATTERNS.some((p) => p.test(text));
}

export const PII_REFUSAL_RESPONSE = `개인정보(주민번호·계좌·비밀번호 등)는 챗봇으로 처리할 수 없습니다. 필요 시 병원 내 데스크로 문의해 주세요.

본 답변은 진단이 아니며 최종 판단은 의료진이 합니다.`;

/**
 * LLM 응답 후처리: disclaimer가 없으면 말미에 추가.
 */
export function applyDisclaimer(reply: string): string {
  const trimmed = reply.trim();
  if (!trimmed) return STANDARD_DISCLAIMER;
  if (
    trimmed.includes('진단이 아니') ||
    trimmed.includes('의학적 진단이 아닙')
  ) {
    return trimmed;
  }
  return `${trimmed}\n\n${STANDARD_DISCLAIMER}`;
}

/**
 * 사용자 입력 기본 샌디화: 과도한 공백·제어문자 제거.
 */
export function sanitizeUserText(text: string): string {
  return text.replace(/[\u0000-\u001F\u007F]+/g, ' ').replace(/\s+/g, ' ').trim();
}
