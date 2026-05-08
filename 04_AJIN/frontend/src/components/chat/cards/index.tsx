// v3.3 Phase F — 인-챗 액션 카드 5종 + 통합 라우터.

import { ComplianceCard } from './ComplianceCard';
import { DocumentCard } from './DocumentCard';
import { DraftCard } from './DraftCard';
import { EmployeeCard } from './EmployeeCard';
import { ErrorCard } from './ErrorCard';
import type { ActionCard } from './types';

export { ComplianceCard, DocumentCard, DraftCard, EmployeeCard, ErrorCard };
export type * from './types';

interface ActionCardRouterProps {
  card: ActionCard;
  onOpen?: (url: string) => void;     // navigate(url) 주입 — Phase F-4
  onLoginClick?: () => void;          // 비인증 EmployeeCard 폴백
}

/**
 * SSE action_card 이벤트의 {kind, payload} 를 받아 5종 카드 컴포넌트로 라우팅.
 * payload 타입은 kind 에 따라 dynamic — TS discriminated union 으로 안전.
 */
export function ActionCardRouter({ card, onOpen, onLoginClick }: ActionCardRouterProps) {
  switch (card.kind) {
    case 'document':
      return <DocumentCard payload={card.payload} />;
    case 'draft':
      return <DraftCard payload={card.payload} onOpen={onOpen} />;
    case 'compliance':
      return <ComplianceCard payload={card.payload} onOpen={onOpen} />;
    case 'employee':
      return <EmployeeCard payload={card.payload} onLoginClick={onLoginClick} />;
    case 'error':
      return <ErrorCard payload={card.payload} onOpen={onOpen} />;
    default: {
      // exhaustive — TS 가 unreachable 보장 (5 kind 외 추가 시 컴파일 실패).
      void (card satisfies never);
      return null;
    }
  }
}
