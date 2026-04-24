import { describe, it, expect, vi } from 'vitest';

vi.mock('@/config/firebase', () => ({
  db: {},
  auth: { currentUser: null },
  isFirebaseConfigured: () => false,
}));
vi.mock('firebase/database', () => ({}));

import { applyFilter, computeStats } from '../adminUsers';
import type { AdminUserRow } from '@/types/admin';

const sampleRows: AdminUserRow[] = [
  {
    uid: 'u1',
    email: 'alice@hospital.org',
    displayName: 'Alice',
    role: 'staff',
    status: 'active',
    providers: ['password'],
    department: '내과',
    createdAt: 1,
    updatedAt: 1,
  },
  {
    uid: 'u2',
    email: 'bob@example.com',
    displayName: 'Bob',
    role: 'patient',
    status: 'suspended',
    providers: ['google'],
    createdAt: 2,
    updatedAt: 2,
  },
  {
    uid: 'u3',
    email: 'admin@example.com',
    displayName: '관리자',
    role: 'admin',
    status: 'active',
    providers: ['password'],
    createdAt: 3,
    updatedAt: 3,
  },
];

describe('applyFilter', () => {
  it('역할로 필터링', () => {
    const r = applyFilter(sampleRows, { role: 'staff' });
    expect(r).toHaveLength(1);
    expect(r[0].uid).toBe('u1');
  });

  it('상태로 필터링', () => {
    expect(applyFilter(sampleRows, { status: 'suspended' })).toHaveLength(1);
  });

  it('텍스트로 필터링 (이름/이메일/부서)', () => {
    expect(applyFilter(sampleRows, { q: '내과' })).toHaveLength(1);
    expect(applyFilter(sampleRows, { q: 'bob' })).toHaveLength(1);
    expect(applyFilter(sampleRows, { q: 'HOSPITAL' })).toHaveLength(1);
  });

  it('필터 조합', () => {
    expect(
      applyFilter(sampleRows, { role: 'patient', status: 'active' }),
    ).toHaveLength(0);
  });
});

describe('computeStats', () => {
  it('역할별·상태별 카운트', () => {
    const s = computeStats(sampleRows, 5);
    expect(s.totalUsers).toBe(3);
    expect(s.staffCount).toBe(1);
    expect(s.patientCount).toBe(1);
    expect(s.adminCount).toBe(1);
    expect(s.activeCount).toBe(2);
    expect(s.suspendedCount).toBe(1);
    expect(s.activeSessions).toBe(5);
  });
});
