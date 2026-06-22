import type { Metadata } from 'next';

import TechShowcase from './tech-showcase';

export const metadata: Metadata = {
  title: 'Lemon Healthcare 기술 스택',
  description:
    'Lemon Healthcare(건강의신 AI)가 사용하는 프론트엔드·백엔드·모바일·AI/OCR·인프라 기술을 ' +
    'WWDC26 Liquid Glass 스타일로 정리했습니다. 비전공자도 카테고리별로 이해할 수 있어요.',
};

/**
 * /tech — 기술 스택 쇼케이스 페이지(서버 래퍼).
 *
 * Returns:
 *   WWDC26 Liquid Glass 벤토 스타일의 기술 스택 소개 화면.
 */
export default function TechPage() {
  return <TechShowcase />;
}
