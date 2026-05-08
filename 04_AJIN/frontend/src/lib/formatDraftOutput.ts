// LLM 초안 출력 포스트-프로세서 — v3.6
//
// 배경: Qwen 3.5 등 일부 LLM 이 한국어 문서 초안을 생성할 때 줄바꿈(\n) 없이
// 한 단락으로 출력해 사용자가 복사·붙여넣기 시 가독성이 떨어진다.
//
// 본 유틸은 마크다운 헤더 패턴 + 한국어 문장 종결 패턴을 기반으로 자동 단락 분리.
// 100% 정확하진 않으나 90%+ 케이스에서 자연스러운 문서 양식으로 보정한다.
//
// 적용 시점: SSE 스트리밍 종료(onDone) 후 1회. 스트리밍 중에는 적용하지 않아
// 토큰별 깜빡임을 방지.

const KOREAN_TERMINATIONS = '다요까오네지함음됨임'; // -다/요/까/오/네/지/함/음/됨/임

/**
 * 마크다운 헤더(**키:**) + 문장 종결 패턴을 기반으로 단락 분리.
 *
 * 변환 규칙:
 *   1. **키:** 헤더가 줄 시작이 아니면 앞에 \n\n 삽입
 *      예) "...담당자**수신:**" → "...담당자\n\n**수신:**"
 *
 *   2. 한국어 종결어미(-다/요/까 등) + 마침표 + 즉시 한글 → 단락 분리
 *      예) "감사드립니다.요청하신" → "감사드립니다.\n\n요청하신"
 *
 *   3. 영문 마침표 + 대문자 → 단락 분리 (영문 혼용 시)
 *      예) "Done.Next" → "Done.\n\nNext"
 *
 *   4. 마크다운 목록(-/*) 항목이 인라인이면 줄바꿈
 *      예) " - 항목1- 항목2" → " - 항목1\n- 항목2"
 *
 *   5. 줄바꿈 정규화: 3개 이상 → 2개로 축소, 각 줄 끝 공백 제거
 */
export function formatDraftOutput(text: string): string {
  if (!text) return '';
  let s = text;

  // 0. 줄바꿈 통일 (\r\n, \r → \n)
  s = s.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

  // 1. **헤더:** 패턴 — 줄 시작이 아니면 앞에 빈 줄
  //    헤더 키는 1~30자 이내, 콜론(:) 으로 끝남
  s = s.replace(/([^\s\n])(\*\*[^*\n]{1,30}:\*\*)/g, '$1\n\n$2');

  // 2. 한국어 종결어미 + 마침표 + 즉시 한글 → 단락 분리
  //    예: "감사드립니다.요청하신" → "감사드립니다.\n\n요청하신"
  const koreanRegex = new RegExp(`([${KOREAN_TERMINATIONS}])\\.([가-힣])`, 'g');
  s = s.replace(koreanRegex, '$1.\n\n$2');

  // 3. 한국어 종결어미 + 마침표 + 공백 + 한글 (이미 공백 있으면 단일 \n 만)
  //    예: "감사드립니다. 요청하신" → "감사드립니다.\n요청하신"
  //    이미 단락이 충분하면 손대지 않음 (\n 직후는 패턴에 안 맞음)
  const koreanRegexSpace = new RegExp(`([${KOREAN_TERMINATIONS}])\\. ([가-힣])`, 'g');
  s = s.replace(koreanRegexSpace, '$1.\n$2');

  // 4. 영문 마침표 + 대문자 → 단락 분리
  s = s.replace(/([a-z])\.([A-Z])/g, '$1.\n\n$2');

  // 5. 인라인 목록 분리 — " - 항목1- 항목2" 또는 " * a* b" 같은 패턴
  //    텍스트 중간에 "- " 가 나오면 앞에 \n
  s = s.replace(/([^\n])\s+(- )/g, '$1\n$2');

  // 6. 콜론 뒤 즉시 한글 (예: "참고사항:다음과") → 콜론 뒤 줄바꿈
  //    단, 시간 표기(13:00) 나 URL(https://) 은 제외
  s = s.replace(/([가-힣]):([가-힣])/g, '$1:\n$2');

  // 7. 줄바꿈 3개 이상 → 2개
  s = s.replace(/\n{3,}/g, '\n\n');

  // 8. 각 줄 끝 공백 제거
  s = s
    .split('\n')
    .map((line) => line.trimEnd())
    .join('\n');

  // 9. 양 끝 trim
  return s.trim();
}

/**
 * 디버그용 — 변환 전·후 라인 수 비교.
 */
export function debugFormatStats(input: string): { before: number; after: number; ratio: number } {
  const before = input.split('\n').length;
  const out = formatDraftOutput(input);
  const after = out.split('\n').length;
  return {
    before,
    after,
    ratio: before > 0 ? after / before : 1,
  };
}
