import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/config/firebase', () => ({
  db: {} as object,
  isFirebaseConfigured: () => true,
}));

const getMock = vi.fn();
const setMock = vi.fn();
const updateMock = vi.fn();
const onValueMock = vi.fn();

vi.mock('firebase/database', () => ({
  ref: (_db: unknown, path: string) => ({ path }),
  get: (r: { path: string }) => getMock(r.path),
  set: (r: { path: string }, value: unknown) => setMock(r.path, value),
  update: (r: { path: string }, value: unknown) => updateMock(r.path, value),
  onValue: (
    r: { path: string },
    cb: (snap: unknown) => void,
    err?: (e: Error) => void,
  ) => onValueMock(r.path, cb, err),
}));

import {
  isValidSlug,
  listHospitals,
  listActiveHospitals,
  getHospital,
  getHospitalProfile,
  subscribeHospitalProfile,
  createHospital,
  updateHospitalProfile,
  setHospitalContractStatus,
} from '../hospitals';
import {
  DEFAULT_HOSPITAL_FEATURES,
  type HospitalProfile,
} from '@/types/hospital';

const baseProfile: HospitalProfile = {
  name: 'Demo Hospital',
  slug: 'demo',
  themeColor: '#004e9f',
  contractStatus: 'active',
  features: DEFAULT_HOSPITAL_FEATURES,
  createdAt: 1_000,
  updatedAt: 1_000,
};

beforeEach(() => {
  getMock.mockReset();
  setMock.mockReset();
  updateMock.mockReset();
  onValueMock.mockReset();
});

describe('isValidSlug', () => {
  it.each([
    ['demo', true],
    ['smch', true],
    ['hospital-a', true],
    ['ab', true],
    ['ab12', true],
    ['a', false], // 너무 짧음
    ['Hospital', false], // 대문자 금지
    ['-demo', false], // 하이픈 시작 금지
    ['demo-', false], // 하이픈 종료 금지
    ['demo_1', false], // 언더스코어 금지
    ['a'.repeat(33), false], // 길이 초과
  ])('slug %s → %s', (slug, expected) => {
    expect(isValidSlug(slug)).toBe(expected);
  });
});

describe('listHospitals (hospital_index)', () => {
  it('빈 상태 → 빈 배열', async () => {
    getMock.mockResolvedValueOnce({ exists: () => false });
    const result = await listHospitals();
    expect(result).toEqual([]);
  });

  it('index 엔트리를 요약으로 반환', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({
        demo: {
          slug: 'demo',
          name: 'Demo',
          themeColor: '#004e9f',
          contractStatus: 'active',
        },
        smch: {
          slug: 'smch',
          name: 'SMC',
          themeColor: '#009688',
          contractStatus: 'pilot',
        },
      }),
    });
    const result = await listHospitals();
    expect(result).toHaveLength(2);
    expect(result[0].id).toBe('demo');
    expect(result[1].slug).toBe('smch');
    expect(getMock).toHaveBeenCalledWith('hospital_index');
  });
});

describe('listActiveHospitals', () => {
  it('active/pilot만 필터', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => ({
        a: {
          slug: 'a',
          name: 'A',
          themeColor: '#000',
          contractStatus: 'active',
        },
        b: {
          slug: 'b',
          name: 'B',
          themeColor: '#000',
          contractStatus: 'pilot',
        },
        c: {
          slug: 'c',
          name: 'C',
          themeColor: '#000',
          contractStatus: 'paused',
        },
      }),
    });
    const result = await listActiveHospitals();
    expect(result.map((h) => h.id).sort()).toEqual(['a', 'b']);
  });
});

describe('getHospital / getHospitalProfile', () => {
  it('존재하지 않으면 null', async () => {
    getMock.mockResolvedValueOnce({ exists: () => false });
    expect(await getHospital('ghost')).toBeNull();
  });

  it('getHospitalProfile은 profile만 조회', async () => {
    getMock.mockResolvedValueOnce({
      exists: () => true,
      val: () => baseProfile,
    });
    const result = await getHospitalProfile('demo');
    expect(getMock).toHaveBeenCalledWith('hospitals/demo/profile');
    expect(result).toEqual(baseProfile);
  });
});

describe('subscribeHospitalProfile', () => {
  it('snapshot 존재 시 profile 콜백', () => {
    let capturedCb: ((snap: unknown) => void) | null = null;
    onValueMock.mockImplementationOnce((_path, cb) => {
      capturedCb = cb;
      return () => {};
    });
    const received: (HospitalProfile | null)[] = [];
    subscribeHospitalProfile('demo', (p) => received.push(p));
    capturedCb!({ exists: () => true, val: () => baseProfile });
    expect(received[0]).toEqual(baseProfile);
  });

  it('snapshot 없으면 null 콜백', () => {
    let capturedCb: ((snap: unknown) => void) | null = null;
    onValueMock.mockImplementationOnce((_path, cb) => {
      capturedCb = cb;
      return () => {};
    });
    const received: (HospitalProfile | null)[] = [];
    subscribeHospitalProfile('ghost', (p) => received.push(p));
    capturedCb!({ exists: () => false });
    expect(received[0]).toBeNull();
  });
});

describe('createHospital', () => {
  it('유효한 slug로 신규 생성 — profile + index fan-out', async () => {
    getMock.mockResolvedValueOnce({ exists: () => false });
    updateMock.mockResolvedValueOnce(undefined);
    const result = await createHospital({ slug: 'new-h', name: 'New' });
    expect(result.slug).toBe('new-h');
    expect(result.contractStatus).toBe('pilot');
    expect(result.features).toEqual(DEFAULT_HOSPITAL_FEATURES);
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan).toHaveProperty('hospitals/new-h/profile');
    expect(fan).toHaveProperty('hospital_index/new-h');
  });

  it('slug 정규화 (공백·대문자 제거)', async () => {
    getMock.mockResolvedValueOnce({ exists: () => false });
    updateMock.mockResolvedValueOnce(undefined);
    await createHospital({ slug: '  DEMO2  ', name: 'D2' });
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(Object.keys(fan)).toEqual(
      expect.arrayContaining([
        'hospitals/demo2/profile',
        'hospital_index/demo2',
      ]),
    );
  });

  it('유효하지 않은 slug → throw', async () => {
    await expect(
      createHospital({ slug: 'BadSlug!', name: 'X' }),
    ).rejects.toThrow(/유효하지 않은 slug/);
  });

  it('중복 slug → throw', async () => {
    getMock.mockResolvedValueOnce({ exists: () => true, val: () => baseProfile });
    await expect(
      createHospital({ slug: 'demo', name: 'Dup' }),
    ).rejects.toThrow(/이미 사용 중/);
  });
});

describe('updateHospitalProfile / setHospitalContractStatus', () => {
  it('updatedAt 자동 갱신 + index name 동기화', async () => {
    updateMock.mockResolvedValueOnce(undefined);
    const before = Date.now();
    await updateHospitalProfile('demo', { name: 'Renamed' });
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan['hospitals/demo/profile/updatedAt']).toBeGreaterThanOrEqual(before);
    expect(fan['hospitals/demo/profile/name']).toBe('Renamed');
    expect(fan['hospital_index/demo/name']).toBe('Renamed');
  });

  it('setHospitalContractStatus도 main + index 동기 업데이트', async () => {
    updateMock.mockResolvedValueOnce(undefined);
    await setHospitalContractStatus('demo', 'paused');
    const [, fan] = updateMock.mock.calls[0] as [unknown, Record<string, unknown>];
    expect(fan['hospitals/demo/profile/contractStatus']).toBe('paused');
    expect(fan['hospital_index/demo/contractStatus']).toBe('paused');
  });
});
