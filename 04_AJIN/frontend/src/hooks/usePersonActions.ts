// usePersonActions — Module A · 인원 카드/드로어용 4종 액션 훅.
// W3 산출물: 메일 / 멘션 복사 / 초안 작성 / 챗봇 문의 통합.
//   - mailto: 핸들링 + 권한 가드
//   - 클립보드 복사 (이름·직급·이메일)
//   - /draft 진입 + prefill state
//   - /chat 진입 + prefill context

import { useNavigate } from 'react-router-dom';
import { useToast } from '@store/toast';
import type { FilteredEmployee } from '@lib/visibility';

export interface PersonActions {
  mail: (emp: FilteredEmployee) => void;
  copyMention: (emp: FilteredEmployee) => Promise<void>;
  draft: (emp: FilteredEmployee) => void;
  askChat: (emp: FilteredEmployee) => void;
}

export function usePersonActions(): PersonActions {
  const navigate = useNavigate();
  const { addToast } = useToast();

  return {
    mail(emp) {
      // F5 — 사내 이메일은 PARTIAL/FULL 모두 사용 가능. 빈 값일 때만 가드.
      if (!emp.email) {
        addToast({ type: 'warning', message: '이메일 정보가 없습니다.' });
        return;
      }
      window.location.href = `mailto:${emp.email}`;
    },

    async copyMention(emp) {
      const mention = `@${emp.name} ${emp.position} (${emp.team})${
        emp.email ? ` <${emp.email}>` : ''
      }`;
      try {
        await navigator.clipboard.writeText(mention);
        addToast({
          type: 'success',
          message: '멘션이 클립보드에 복사되었습니다.',
        });
      } catch {
        addToast({
          type: 'error',
          message: '클립보드 복사에 실패했습니다.',
        });
      }
    },

    draft(emp) {
      if (emp.visibility !== 'FULL') {
        addToast({ type: 'warning', message: '타 부서 사원 정보는 권한이 제한됩니다.' });
        return;
      }
      navigate('/draft', {
        state: {
          prefillRecipient: emp.name,
          prefillPosition: emp.position,
          prefillTeam: emp.team,
          prefillEmail: emp.email,
        },
      });
    },

    askChat(emp) {
      navigate('/chat', {
        state: {
          prefillContext: {
            kind: 'person',
            employeeId: emp.id,
            name: emp.name,
            team: emp.team,
            hq: emp.hq,
            position: emp.position,
          },
          prefillPrompt: `${emp.team} ${emp.position} ${emp.name}님에 대해 알려줘. 어떤 업무를 담당하시나요?`,
        },
      });
    },
  };
}
