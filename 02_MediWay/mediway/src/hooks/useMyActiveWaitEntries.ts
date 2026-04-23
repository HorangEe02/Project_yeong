import { useEffect, useState } from 'react';
import { useHospital } from '@/hooks/useHospital';
import { useAuthStore } from '@/stores/authStore';
import { subscribeMyEntries } from '@/services/waitQueue';
import { isActiveStatus, type WaitEntryIndex } from '@/types/wait-queue';

/**
 * 환자 본인의 활성(waiting/called/in-progress) 대기 엔트리만 실시간 구독.
 *
 * SeniorHome 4 타일의 "내 순번" 뱃지 등 가벼운 노출에 재사용.
 * 정렬은 subscribeMyEntries 측에서 number 오름차순 보장.
 */
export function useMyActiveWaitEntries(): Array<
  WaitEntryIndex & { id: string }
> {
  const { slug } = useHospital();
  const uid = useAuthStore((s) => s.user?.uid);
  const [entries, setEntries] = useState<
    Array<WaitEntryIndex & { id: string }>
  >([]);

  useEffect(() => {
    if (!slug || !uid) {
      setEntries([]);
      return;
    }
    return subscribeMyEntries(slug, uid, (list) => {
      setEntries(list.filter((e) => isActiveStatus(e.status)));
    });
  }, [slug, uid]);

  return entries;
}
