// v3.6 — Module C 첫 진입 시 동적 인사말 생성기.
//
// 이전엔 정적 INITIAL_MSGS ('프레스 트라이 SOP 알려줘' 가짜 대화) 가 표시되어
// 신입 사원·비전공 사용자가 "이게 내 메시지인가?" 혼란을 겪었음.
//
// 본 유틸은 user.username + position + department 를 조합해 자연스러운 컨텍스트형
// 인사말을 생성한다. 시간대(아침/오후/저녁) 도 반영.

import type { AuthUser } from '@store/auth';

export interface GreetingContext {
  /** 환영 메시지 본문 (마크다운 가능) */
  text: string;
  /** 메시지 메타 (출처 표시용) */
  source: 'WELCOME';
}

/**
 * 시간대 인사말 — 한국 직장 관행 기준.
 *   06-11: 좋은 아침입니다
 *   12-17: 안녕하세요
 *   18-23: 수고 많으셨습니다
 *   00-05: 늦은 시간 접속하셨네요
 */
function timeOfDay(): string {
  const hour = new Date().getHours();
  if (hour >= 6 && hour < 12) return '좋은 아침입니다';
  if (hour >= 12 && hour < 18) return '안녕하세요';
  if (hour >= 18 && hour < 24) return '수고 많으셨습니다';
  return '늦은 시간 접속하셨네요';
}

/**
 * 부서별 추천 화제 — 사용자의 부서에 맞춰 시작 질문 후보 제공.
 * 매핑에 없는 부서는 default 추천.
 */
const DEPARTMENT_TIPS: Record<string, string> = {
  품질보증팀: '8D 보고서·PPAP 절차·SPC 분석 등',
  품질혁신팀: '공정 개선·품질 데이터·고객 클레임 처리 등',
  생산기술팀: '금형 교체·CNC 셋업·공정 관리 등',
  설계팀: 'ECN 발행·도면 변경·PPAP 재제출 등',
  안전관리팀: '안전 점검·산안법 준수·재해 대응 등',
  영업팀: '고객사 응대·견적·납기 협의 등',
  구매팀: '협력사 관리·발주·입고 검사 등',
  관리부: '인사·총무·복리후생·근태 등',
  IT팀: '시스템·계정·데이터 백업 등',
};

function pickTip(department: string | undefined): string {
  // 빈 문자열도 falsy 로 처리 — 백엔드가 '' 를 돌려주는 케이스 방어.
  if (!department) return '업무 관련 SOP·법규·문서 양식 등';
  return DEPARTMENT_TIPS[department] ?? '담당 부서 업무 절차·문서 양식·관련 법규 등';
}

/**
 * 사용자 정보 기반 컨텍스트형 인사말 생성.
 *
 * 형식:
 *   "안녕하세요, {이름} {직급}님. {부서} 업무에 도움이 필요하시면 말씀해 주세요.
 *    예를 들어 {부서별 추천 화제} 에 대해 질문하실 수 있습니다.
 *    자주 찾는 질문은 우측 패널에서 확인하실 수 있습니다."
 */
export function buildWelcomeMessage(user: AuthUser | null): GreetingContext {
  const greeting = timeOfDay();

  if (!user) {
    return {
      text:
        `${greeting}. 아진산업 AI 업무 도우미입니다.\n\n` +
        `궁금하신 업무 절차·문서 양식·법규 등을 자유롭게 질문해 주세요. ` +
        `우측 패널에서는 자주 찾는 질문과 SOP·협업 가이드를 확인하실 수 있습니다.`,
      source: 'WELCOME',
    };
  }

  const name = user.username || '동료';
  const position = user.position || '';
  // `??` 대신 `||` — 백엔드가 빈 문자열을 돌려줘도 폴백되도록.
  const department =
    (user as { department?: string }).department || '소속 부서';
  // pickTip 도 '소속 부서' 같은 비-매핑 라벨에는 default tip 을 돌려준다.
  const tip = pickTip(department === '소속 부서' ? undefined : department);

  // "박준영 사원님" 처럼 직급 띄어쓰기 보정
  const honorific = position ? `${position}님` : '님';
  const fullName = `${name} ${honorific}`.trim();

  return {
    text:
      `${greeting}, **${fullName}**.\n\n` +
      `${department} 업무에 도움이 필요하시면 편하게 말씀해 주세요. ` +
      `예를 들어 *${tip}* 에 대해 질문하실 수 있습니다.\n\n` +
      `우측 패널에서는 자주 찾는 질문과 SOP·협업 가이드를 확인하실 수 있고, ` +
      `필요하시면 답변을 DOCX·XLSX·CSV·TXT 로 다운로드할 수 있습니다.`,
    source: 'WELCOME',
  };
}
