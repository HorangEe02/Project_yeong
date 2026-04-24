import { describe, it, expect, beforeEach, vi } from 'vitest';
import { createDispatcher, isChannelEnabled } from '../notifications/dispatcher';
import { renderTemplate, templateSupports, getTemplate } from '../notifications/templates';
import type {
  Channel,
  NotificationEvent,
  UserNotificationPrefs,
  SendResult,
} from '../notifications/types';
import type { SenderAdapter } from '../notifications/adapters/base';

// ═══════════════════════════════════════════════════════
// 인메모리 DB mock — admin.database.Database 의 최소 surface
// ═══════════════════════════════════════════════════════

interface FakeNode {
  [k: string]: FakeNode | unknown;
}
type Listener = (snap: { val: () => unknown; exists: () => boolean; forEach: (cb: (c: { key: string; val: () => unknown }) => boolean | void) => void }) => void;

function makeFakeDb() {
  const store: FakeNode = {};
  let pushCounter = 0;

  const getAt = (path: string): unknown => {
    const parts = path.split('/').filter(Boolean);
    let cur: unknown = store;
    for (const p of parts) {
      if (!cur || typeof cur !== 'object') return undefined;
      cur = (cur as FakeNode)[p];
    }
    return cur;
  };
  const setAt = (path: string, value: unknown): void => {
    const parts = path.split('/').filter(Boolean);
    let cur: FakeNode = store;
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i];
      if (!cur[p] || typeof cur[p] !== 'object') cur[p] = {};
      cur = cur[p] as FakeNode;
    }
    cur[parts[parts.length - 1]] = value;
  };
  const removeAt = (path: string): void => {
    const parts = path.split('/').filter(Boolean);
    let cur: FakeNode = store;
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i];
      if (!cur[p] || typeof cur[p] !== 'object') return;
      cur = cur[p] as FakeNode;
    }
    delete cur[parts[parts.length - 1]];
  };
  const mergeAt = (path: string, patch: Record<string, unknown>): void => {
    const existing = (getAt(path) as Record<string, unknown>) ?? {};
    setAt(path, { ...existing, ...patch });
  };

  function makeRef(path: string): unknown {
    return {
      path,
      async get() {
        const v = getAt(path);
        return {
          val: () => (v === undefined ? null : v),
          exists: () => v !== undefined && v !== null,
          forEach: (cb: (c: { key: string; val: () => unknown }) => boolean | void) => {
            if (!v || typeof v !== 'object') return;
            for (const [k, val] of Object.entries(v as FakeNode)) {
              const stop = cb({ key: k, val: () => val });
              if (stop === true) break;
            }
          },
        };
      },
      push() {
        pushCounter += 1;
        const newKey = `-fake${pushCounter}`;
        const childPath = `${path}/${newKey}`;
        return {
          key: newKey,
          async set(value: unknown) { setAt(childPath, value); },
          async update(patch: Record<string, unknown>) { mergeAt(childPath, patch); },
        };
      },
      async set(value: unknown) { setAt(path, value); },
      async update(patch: Record<string, unknown>) { mergeAt(path, patch); },
      async remove() { removeAt(path); },
      orderByChild(_field: string) {
        return {
          startAt(_v: number) {
            return {
              async get() {
                const v = getAt(path);
                return {
                  val: () => (v === undefined ? null : v),
                  exists: () => v !== undefined && v !== null,
                  forEach: (cb: (c: { key: string; val: () => unknown }) => boolean | void) => {
                    if (!v || typeof v !== 'object') return;
                    for (const [k, val] of Object.entries(v as FakeNode)) {
                      const stop = cb({ key: k, val: () => val });
                      if (stop === true) break;
                    }
                  },
                };
              },
            };
          },
        };
      },
    };
  }

  return {
    ref(path: string) { return makeRef(path); },
    _inspect: (path: string) => getAt(path),
    _seed: (path: string, value: unknown) => setAt(path, value),
  };
}

function mkEvent(overrides: Partial<NotificationEvent> = {}): NotificationEvent {
  return {
    type: 'queue.call',
    hospitalId: 'demo',
    targetUid: 'uid-patient',
    vars: { department: '내과', queueNumber: 5, hospitalId: 'demo', date: '2026-04-24' },
    ...overrides,
  };
}

// Mock adapters
function fakeAdapter(channel: Channel, behavior: 'sent' | 'throw'): SenderAdapter {
  return {
    channel,
    async send(_uid, _content, _event): Promise<SendResult> {
      if (behavior === 'throw') throw new Error(`${channel}_not_configured`);
      return { channel, status: 'sent', providerMessageId: `${channel}-msgid`, at: Date.now() };
    },
  };
}

describe('templates', () => {
  it('queue.call supportedChannels 포함 fcm + alimtalk + sms', () => {
    expect(templateSupports('queue.call', 'fcm')).toBe(true);
    expect(templateSupports('queue.call', 'alimtalk')).toBe(true);
    expect(templateSupports('queue.call', 'sms')).toBe(true);
    expect(templateSupports('queue.call', 'email')).toBe(false);
  });

  it('renderTemplate 변수 치환 + title/body 형태', () => {
    const r = renderTemplate('queue.call', 'fcm', { department: '내과', queueNumber: 7 });
    expect(r?.title).toBe('호출되었습니다');
    expect(r?.body).toContain('내과');
    expect(r?.body).toContain('7');
  });

  it('unsupported channel → null', () => {
    expect(renderTemplate('queue.preCall', 'email', {})).toBeNull();
  });

  it('getTemplate 모든 시나리오 정의됨', () => {
    for (const t of [
      'appointment.confirmed',
      'appointment.reminder',
      'queue.call',
      'queue.preCall',
      'payment.completed',
      'payment.request',
      'prescription.sent',
    ] as const) {
      expect(getTemplate(t)).not.toBeNull();
    }
  });
});

describe('isChannelEnabled', () => {
  const event = mkEvent();
  it('prefs 없으면 allow', () => {
    expect(isChannelEnabled({} as UserNotificationPrefs, event, 'fcm')).toBe(true);
  });
  it('revokedAt 있으면 전체 block', () => {
    expect(isChannelEnabled({ revokedAt: 1 }, event, 'fcm')).toBe(false);
  });
  it('channels.fcm=false → block', () => {
    expect(isChannelEnabled({ channels: { fcm: false } }, event, 'fcm')).toBe(false);
    expect(isChannelEnabled({ channels: { fcm: false } }, event, 'sms')).toBe(true);
  });
  it('scenarios["queue.call"]=false → block', () => {
    expect(
      isChannelEnabled({ scenarios: { 'queue.call': false } }, event, 'fcm'),
    ).toBe(false);
  });
});

describe('dispatcher — cascade', () => {
  let db: ReturnType<typeof makeFakeDb>;

  beforeEach(() => {
    db = makeFakeDb();
  });

  it('fcm adapter만 성공 → fcm 선택 + 로그 기록', async () => {
    const adapters = {
      alimtalk: fakeAdapter('alimtalk', 'throw'),
      fcm: fakeAdapter('fcm', 'sent'),
    };
    const dispatcher = createDispatcher(
      db as unknown as import('firebase-admin').database.Database,
      adapters,
    );
    const out = await dispatcher.send(mkEvent());
    expect(out.deliveredChannel).toBe('fcm');
    const sentAttempt = out.attempts.find((a) => a.status === 'sent');
    expect(sentAttempt?.channel).toBe('fcm');

    // 로그 저장 확인
    const logs = db._inspect('notification_logs/uid-patient') as Record<string, unknown>;
    expect(Object.keys(logs).length).toBe(1);
  });

  it('prefs.channels.fcm=false 이면 fcm skipped — SMS stub 로 fallthrough 실패', async () => {
    db._seed('users/uid-patient/notifications', { channels: { fcm: false } });
    const adapters = {
      alimtalk: fakeAdapter('alimtalk', 'throw'),
      fcm: fakeAdapter('fcm', 'sent'),
      sms: fakeAdapter('sms', 'throw'),
    };
    const dispatcher = createDispatcher(
      db as unknown as import('firebase-admin').database.Database,
      adapters,
    );
    const out = await dispatcher.send(mkEvent());
    const fcmAttempt = out.attempts.find((a) => a.channel === 'fcm');
    expect(fcmAttempt?.status).toBe('skipped');
    expect(fcmAttempt?.errorCode).toBe('pref_disabled');
    expect(out.deliveredChannel).toBeNull();
  });

  it('revokedAt 설정 시 모든 채널 skipped', async () => {
    db._seed('users/uid-patient/notifications', { revokedAt: 1 });
    const adapters = { fcm: fakeAdapter('fcm', 'sent') };
    const dispatcher = createDispatcher(
      db as unknown as import('firebase-admin').database.Database,
      adapters,
    );
    const out = await dispatcher.send(mkEvent());
    expect(out.deliveredChannel).toBeNull();
    expect(out.attempts.every((a) => a.status === 'skipped')).toBe(true);
  });

  it('template 이 채널 미지원이면 skipped (queue.preCall → email 제외됨)', async () => {
    const adapters = {
      alimtalk: fakeAdapter('alimtalk', 'throw'),
      fcm: fakeAdapter('fcm', 'sent'),
      sms: fakeAdapter('sms', 'throw'),
      email: fakeAdapter('email', 'sent'),
    };
    const dispatcher = createDispatcher(
      db as unknown as import('firebase-admin').database.Database,
      adapters,
    );
    const out = await dispatcher.send(mkEvent({ type: 'queue.preCall', vars: { aheadCount: 1, department: '내과' } }));
    expect(out.deliveredChannel).toBe('fcm');
    const skip = out.attempts.filter(a => a.status === 'skipped' && a.errorCode === 'template_unsupported');
    expect(skip.length).toBeGreaterThan(0);
  });

  it('idempotencyKey 재전송 시 duplicate 감지', async () => {
    const adapters = { fcm: fakeAdapter('fcm', 'sent') };
    const dispatcher = createDispatcher(
      db as unknown as import('firebase-admin').database.Database,
      adapters,
    );
    const event = mkEvent({ idempotencyKey: 'queue-call-abc' });
    const first = await dispatcher.send(event);
    const second = await dispatcher.send(event);
    expect(first.logId).toBeTruthy();
    expect(second.duplicateOfLogId).toBe(first.logId);
  });

  it('adapter 없는 채널은 no_adapter 로 skipped', async () => {
    const adapters = { fcm: fakeAdapter('fcm', 'sent') };
    const dispatcher = createDispatcher(
      db as unknown as import('firebase-admin').database.Database,
      adapters,
    );
    const out = await dispatcher.send(mkEvent());
    const noAdapter = out.attempts.filter(a => a.errorCode === 'no_adapter');
    expect(noAdapter.length).toBeGreaterThan(0);
  });
});
