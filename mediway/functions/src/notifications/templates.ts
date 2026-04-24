import type {
  Channel,
  NotificationEventType,
  RenderedContent,
} from './types';

/**
 * 시나리오별 템플릿 레지스트리.
 *
 * - `supportedChannels`: 해당 시나리오가 지원하는 채널 목록 (심사 완료된 알림톡 템플릿 유무 등).
 * - `render(channel, vars)`: 채널별로 content 렌더.
 *
 * 카카오 알림톡 실연결 (F5d) 시 `alimtalkCode` 필드가 templates 항목에 추가되어
 * 실제 템플릿 id 매핑 가능. 현재는 공통 render 함수만 노출.
 */

interface TemplateSpec {
  supportedChannels: Channel[];
  render: (channel: Channel, vars: Record<string, string | number>) => RenderedContent;
  /** 알림톡 템플릿 코드 (심사 후 주입). F5a 에서는 미사용. */
  alimtalkCode?: string;
}

function v(vars: Record<string, string | number>, key: string, fallback = ''): string {
  return String(vars[key] ?? fallback);
}

const TEMPLATES: Record<NotificationEventType, TemplateSpec> = {
  'appointment.confirmed': {
    supportedChannels: ['alimtalk', 'fcm', 'sms', 'email'],
    render: (_ch, vars) => ({
      title: '예약 확인',
      body: `${v(vars, 'name', '환자')}님, ${v(vars, 'date')} ${v(vars, 'time')} ${v(vars, 'department')} 진료가 예약되었습니다.`,
    }),
  },
  'appointment.reminder': {
    supportedChannels: ['alimtalk', 'fcm', 'sms'],
    render: (_ch, vars) => ({
      title: '예약 리마인더',
      body: `${v(vars, 'name', '환자')}님, 1시간 뒤 ${v(vars, 'department')} 진료가 예정되어 있습니다. 미리 도착해 주세요.`,
    }),
  },
  'queue.call': {
    supportedChannels: ['fcm', 'alimtalk', 'sms'],
    render: (_ch, vars) => ({
      title: '호출되었습니다',
      body: `${v(vars, 'department')} ${v(vars, 'queueNumber')}번 환자님, 진료실로 이동해 주세요.`,
      extras: {
        type: 'queue_call',
        hospitalId: String(vars.hospitalId ?? ''),
        department: String(vars.department ?? ''),
        date: String(vars.date ?? ''),
        queueNumber: String(vars.queueNumber ?? ''),
      },
    }),
  },
  'queue.preCall': {
    supportedChannels: ['fcm'],
    render: (_ch, vars) => ({
      title: '곧 호출 예정',
      body: `내 앞 ${v(vars, 'aheadCount', '1')}명, 약 5분 내 ${v(vars, 'department')} 호출 예정입니다.`,
    }),
  },
  'payment.completed': {
    supportedChannels: ['alimtalk', 'fcm', 'email'],
    render: (_ch, vars) => ({
      title: '결제 완료',
      body: `${v(vars, 'amount')}원 결제가 완료되었습니다. 영수증을 확인해 주세요.`,
      extras: { receiptUrl: String(vars.receiptUrl ?? '') },
    }),
  },
  'payment.request': {
    supportedChannels: ['alimtalk', 'fcm', 'sms'],
    render: (_ch, vars) => ({
      title: '결제 요청',
      body: `${v(vars, 'name', '')}님이 ${v(vars, 'amount')}원 결제를 요청했습니다.`,
      extras: { paymentLinkUrl: String(vars.paymentLinkUrl ?? '') },
    }),
  },
  'prescription.sent': {
    supportedChannels: ['alimtalk', 'fcm', 'sms', 'email'],
    render: (_ch, vars) => ({
      title: '처방전 전송',
      body: `처방전이 ${v(vars, 'pharmacy')}으로 전송되었습니다.`,
    }),
  },
};

export function getTemplate(type: NotificationEventType): TemplateSpec | null {
  return TEMPLATES[type] ?? null;
}

export function templateSupports(
  type: NotificationEventType,
  channel: Channel,
): boolean {
  const t = getTemplate(type);
  return !!t && t.supportedChannels.includes(channel);
}

export function renderTemplate(
  type: NotificationEventType,
  channel: Channel,
  vars: Record<string, string | number>,
): RenderedContent | null {
  const t = getTemplate(type);
  if (!t || !t.supportedChannels.includes(channel)) return null;
  return t.render(channel, vars);
}
