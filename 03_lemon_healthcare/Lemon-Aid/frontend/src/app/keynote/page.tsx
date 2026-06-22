import type { Metadata } from 'next';

import Keynote from './keynote';

export const metadata: Metadata = {
  title: 'Lemon AID — Keynote',
  description:
    '사진 한 장으로 영양제를 이해하는 AI. YOLO·OCR·로컬 LLM(Ollama·Gemma4) 파이프라인을 ' +
    'WWDC 스타일로 소개하는 쇼케이스.',
};

/**
 * /keynote — WWDC 스타일 키노트 쇼케이스 페이지(서버 래퍼).
 *
 * Returns:
 *   클라이언트 스크롤 키노트 컴포넌트.
 */
export default function KeynotePage() {
  return <Keynote />;
}
