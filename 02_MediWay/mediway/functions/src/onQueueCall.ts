import * as admin from 'firebase-admin';
import { onValueUpdated } from 'firebase-functions/v2/database';

/** FCM multicast 응답 형식 */
export interface FcmMulticastResponse {
  successCount: number;
  failureCount: number;
}

/** 테스트용 의존성 주입 */
export interface QueueCallDeps {
  getTokens: (uid: string) => Promise<string[]>;
  send: (msg: {
    tokens: string[];
    notification: { title: string; body: string };
    data: Record<string, string>;
  }) => Promise<FcmMulticastResponse>;
}

export interface QueueEntryShape {
  status?: string;
  patientUid?: string;
  department?: string;
  number?: number;
}

/**
 * 대기열 entry 상태가 'called'로 전이된 경우에만 FCM 푸시 발송.
 * Cloud Function trigger와 독립적으로 테스트 가능하게 분리.
 */
export async function dispatchCallNotification(
  params: { hospitalId: string; entryId: string },
  before: QueueEntryShape | null,
  after: QueueEntryShape | null,
  deps: QueueCallDeps,
): Promise<{ skipped: true; reason: string } | { skipped: false } & FcmMulticastResponse> {
  if (!after) return { skipped: true, reason: 'after-null' };
  if (after.status !== 'called') return { skipped: true, reason: 'not-called' };
  if (before?.status === 'called') return { skipped: true, reason: 'already-called' };
  if (!after.patientUid) return { skipped: true, reason: 'no-patient-uid' };

  const tokens = await deps.getTokens(after.patientUid);
  if (tokens.length === 0) return { skipped: true, reason: 'no-tokens' };

  const title = '진료 호출 알림';
  const body = `${after.department ?? '진료'} · 순번 ${after.number ?? '-'}번 — 진료실로 이동해 주세요`;

  const resp = await deps.send({
    tokens,
    notification: { title, body },
    data: {
      type: 'queue-call',
      hospitalId: params.hospitalId,
      entryId: params.entryId,
      department: String(after.department ?? ''),
      number: String(after.number ?? ''),
    },
  });
  return { skipped: false, ...resp };
}

/** 기본 의존성 — admin.database() / admin.messaging() */
function defaultDeps(): QueueCallDeps {
  return {
    getTokens: async (uid) => {
      const snap = await admin.database().ref(`user_fcm_tokens/${uid}`).get();
      if (!snap.exists()) return [];
      const raw = snap.val() as Record<string, { token: string } | string>;
      return Object.values(raw)
        .map((v) => (typeof v === 'string' ? v : v.token))
        .filter((t): t is string => typeof t === 'string' && t.length > 0);
    },
    send: (msg) => admin.messaging().sendEachForMulticast(msg),
  };
}

/**
 * 트리거: `/hospitals/{hospitalId}/wait_queue/{department}/{date}/{entryId}` 업데이트.
 * 실제 FCM 발송은 dispatchCallNotification으로 위임.
 */
// RTDB onValueUpdated 트리거는 asia-northeast3에서 미지원.
// `mediway-demo-default-rtdb.firebaseio.com` 인스턴스는 us-central1에 위치하므로
// Cloud Function 리전도 us-central1로 맞춘다.
export const onQueueCall = onValueUpdated(
  {
    ref: '/hospitals/{hospitalId}/wait_queue/{department}/{date}/{entryId}',
    region: 'us-central1',
  },
  async (event) => {
    const result = await dispatchCallNotification(
      {
        hospitalId: event.params.hospitalId,
        entryId: event.params.entryId,
      },
      event.data.before.val() as QueueEntryShape | null,
      event.data.after.val() as QueueEntryShape | null,
      defaultDeps(),
    );
    if (result.skipped) {
      console.log(`[onQueueCall] skipped: ${result.reason}`);
    } else {
      console.log(
        `[onQueueCall] sent=${result.successCount} failed=${result.failureCount}`,
      );
    }
  },
);
