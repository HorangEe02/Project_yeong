// Firestore 컬렉션 실시간 구독 — Day 6+ Firebase 통합용

import { useEffect, useState } from 'react';
import {
  collection,
  onSnapshot,
  query,
  type QueryConstraint,
} from 'firebase/firestore';
import { firestore } from '@lib/firebase';

export interface FirestoreDoc {
  id: string;
}

export interface FirestoreCollectionResult<T> {
  data: T[];
  loading: boolean;
  error: Error | null;
}

export function useFirestoreCollection<T extends FirestoreDoc>(
  path: string,
  ...constraints: QueryConstraint[]
): FirestoreCollectionResult<T> {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!firestore) {
      setError(new Error('Firestore 미초기화 — VITE_FIREBASE_API_KEY 확인'));
      setLoading(false);
      return;
    }
    setLoading(true);
    const q = query(collection(firestore, path), ...constraints);
    const unsub = onSnapshot(
      q,
      (snap) => {
        const docs = snap.docs.map((d) => ({ id: d.id, ...d.data() } as T));
        setData(docs);
        setLoading(false);
        setError(null);
      },
      (err) => {
        setError(err);
        setLoading(false);
      },
    );
    return () => unsub();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  return { data, loading, error };
}
