import * as admin from 'firebase-admin';
import { onSchedule } from 'firebase-functions/v2/scheduler';

/**
 * Phase I.6 (minimal) — Visit archive scheduler.
 *
 * 일 1회 (KST 03:00) 실행. status ∈ {completed, cancelled} 인 visit 가
 * `completedAt` (또는 fallback `updatedAt`) 기준 90일 이상 경과 시
 * `/visits/{hid}/{visitId}` → `/visits_archive/{hid}/{visitId}` 이동 후 원본 삭제.
 *
 * 동작:
 *  - cutoff = now - 90 days
 *  - 한 실행당 최대 ARCHIVE_BATCH_LIMIT 건 (다음 cron 에서 이어서 — 무한 backlog 방어)
 *  - multi-location update — archive write + 원본 삭제 atomic
 *
 * Functions deploy 후 자동 cron 등록. 비용: 일 1회 + RTDB read(전체 visit) — demo 규모 무시.
 * 대규모 hospital 시 indexOn(status, completedAt) + 더 좁은 query 검토 (별도 sprint).
 *
 * RTDB rules: `/visits_archive` read = same-hospital staff/admin/platformAdmin (rules deploy 별도).
 */

const ARCHIVE_THRESHOLD_DAYS = 90;
const ARCHIVE_BATCH_LIMIT = 200;

interface VisitMinimal {
  status?: string;
  completedAt?: number;
  updatedAt?: number;
}

export const visitArchiveScheduler = onSchedule(
  {
    schedule: 'every day 03:00',
    region: 'asia-northeast3',
    timeZone: 'Asia/Seoul',
  },
  async () => {
    const db = admin.database();
    const cutoff = Date.now() - ARCHIVE_THRESHOLD_DAYS * 24 * 60 * 60 * 1000;

    const visitsSnap = await db.ref('visits').get();
    if (!visitsSnap.exists()) {
      console.log('[visitArchiveScheduler] no visits — skip');
      return;
    }

    let processed = 0;
    const updates: Record<string, unknown> = {};

    visitsSnap.forEach((hospChild) => {
      if (processed >= ARCHIVE_BATCH_LIMIT) return true;
      const hospitalId = hospChild.key;
      if (!hospitalId) return false;

      hospChild.forEach((visitChild) => {
        if (processed >= ARCHIVE_BATCH_LIMIT) return true;
        const visit = visitChild.val() as VisitMinimal;
        const id = visitChild.key;
        if (!id) return false;

        const status = visit?.status;
        if (status !== 'completed' && status !== 'cancelled') return false;

        const finishedAt = visit?.completedAt ?? visit?.updatedAt;
        if (typeof finishedAt !== 'number' || finishedAt > cutoff) return false;

        updates[`visits_archive/${hospitalId}/${id}`] = visit;
        updates[`visits/${hospitalId}/${id}`] = null;
        processed++;
        return false;
      });
      return false;
    });

    if (processed === 0) {
      console.log(`[visitArchiveScheduler] no eligible visits (cutoff=${cutoff})`);
      return;
    }

    await db.ref().update(updates);
    console.log(
      `[visitArchiveScheduler] archived ${processed} visit(s) (cutoff=${cutoff}, batch_limit=${ARCHIVE_BATCH_LIMIT})`,
    );
  },
);
