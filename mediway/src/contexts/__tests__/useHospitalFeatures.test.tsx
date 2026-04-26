import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import type { ReactNode } from 'react';
import type { HospitalProfile } from '@/types/hospital';
import {
  FEATURE_DEFAULTS,
  HospitalProvider,
  useHospitalFeatures,
  useFeature,
} from '../HospitalContext';

/** 테스트용 Probe — features 매트릭스를 JSON 으로 렌더 */
function FeaturesProbe() {
  const f = useHospitalFeatures();
  return <pre data-testid="features">{JSON.stringify(f)}</pre>;
}

function FlagProbe({ k }: { k: string }) {
  const v = useFeature(k);
  return <span data-testid="flag">{v ? 'on' : 'off'}</span>;
}

function wrap(profile: HospitalProfile, children: ReactNode) {
  return render(
    <HospitalProvider value={{ slug: 'demo', profile }}>{children}</HospitalProvider>,
  );
}

describe('FEATURE_DEFAULTS', () => {
  it('appointments + chatbot default true', () => {
    expect(FEATURE_DEFAULTS.appointments).toBe(true);
    expect(FEATURE_DEFAULTS.chatbot).toBe(true);
  });

  it('나머지 default false', () => {
    expect(FEATURE_DEFAULTS.inpatient).toBe(false);
    expect(FEATURE_DEFAULTS.checkup).toBe(false);
    expect(FEATURE_DEFAULTS.payment).toBe(false);
    expect(FEATURE_DEFAULTS.prescription).toBe(false);
    expect(FEATURE_DEFAULTS.aiTriage).toBe(false);
    expect(FEATURE_DEFAULTS.familyDelegation).toBe(false);
    expect(FEATURE_DEFAULTS.healthRecords).toBe(false);
    expect(FEATURE_DEFAULTS.parking).toBe(false);
  });

  it('frozen — 런타임 변경 불가', () => {
    expect(Object.isFrozen(FEATURE_DEFAULTS)).toBe(true);
  });
});

describe('useHospitalFeatures', () => {
  it('profile.features=undefined → defaults 그대로', () => {
    const profile: HospitalProfile = { id: 'demo', name: 'X' };
    const { getByTestId } = wrap(profile, <FeaturesProbe />);
    const got = JSON.parse(getByTestId('features').textContent ?? '{}');
    expect(got.appointments).toBe(true);
    expect(got.chatbot).toBe(true);
    expect(got.aiTriage).toBe(false);
    expect(got.inpatient).toBe(false);
  });

  it('RTDB partial → 부분 override (default 보존)', () => {
    const profile: HospitalProfile = {
      id: 'demo',
      name: 'X',
      features: { aiTriage: true, inpatient: true },
    };
    const { getByTestId } = wrap(profile, <FeaturesProbe />);
    const got = JSON.parse(getByTestId('features').textContent ?? '{}');
    expect(got.aiTriage).toBe(true);
    expect(got.inpatient).toBe(true);
    // 미명시 default 유지
    expect(got.appointments).toBe(true);
    expect(got.chatbot).toBe(true);
    expect(got.checkup).toBe(false);
  });

  it('RTDB 가 default true 인 키를 false 로 덮어쓸 수 있음', () => {
    const profile: HospitalProfile = {
      id: 'demo',
      name: 'X',
      features: { appointments: false, chatbot: false },
    };
    const { getByTestId } = wrap(profile, <FeaturesProbe />);
    const got = JSON.parse(getByTestId('features').textContent ?? '{}');
    expect(got.appointments).toBe(false);
    expect(got.chatbot).toBe(false);
  });

  it('알 수 없는 key 도 RTDB 에 명시되면 그대로 노출', () => {
    const profile: HospitalProfile = {
      id: 'demo',
      name: 'X',
      features: { customExperimental: true },
    };
    const { getByTestId } = wrap(profile, <FeaturesProbe />);
    const got = JSON.parse(getByTestId('features').textContent ?? '{}');
    expect(got.customExperimental).toBe(true);
    // defaults 기본값들은 그대로
    expect(got.appointments).toBe(true);
  });

  it('반환 객체는 frozen — render 결과 변조 시도 차단', () => {
    function FreezeProbe() {
      const f = useHospitalFeatures();
      const isFrozen = Object.isFrozen(f);
      return <span data-testid="frozen">{isFrozen ? 'yes' : 'no'}</span>;
    }
    const profile: HospitalProfile = { id: 'demo', name: 'X' };
    const { getByTestId } = wrap(profile, <FreezeProbe />);
    expect(getByTestId('frozen').textContent).toBe('yes');
  });
});

describe('useFeature', () => {
  it('default true key → true', () => {
    const profile: HospitalProfile = { id: 'demo', name: 'X' };
    const { getByTestId } = wrap(profile, <FlagProbe k="appointments" />);
    expect(getByTestId('flag').textContent).toBe('on');
  });

  it('default false key → false', () => {
    const profile: HospitalProfile = { id: 'demo', name: 'X' };
    const { getByTestId } = wrap(profile, <FlagProbe k="aiTriage" />);
    expect(getByTestId('flag').textContent).toBe('off');
  });

  it('RTDB 가 true 로 enable', () => {
    const profile: HospitalProfile = {
      id: 'demo',
      name: 'X',
      features: { aiTriage: true },
    };
    const { getByTestId } = wrap(profile, <FlagProbe k="aiTriage" />);
    expect(getByTestId('flag').textContent).toBe('on');
  });

  it('알 수 없는 key → false', () => {
    const profile: HospitalProfile = { id: 'demo', name: 'X' };
    const { getByTestId } = wrap(profile, <FlagProbe k="unknown.flag" />);
    expect(getByTestId('flag').textContent).toBe('off');
  });

  it('RTDB 의 non-boolean 값은 false 처리 (defensive)', () => {
    const profile: HospitalProfile = {
      id: 'demo',
      name: 'X',
      // 타입은 boolean 강제하지만 RTDB 가 깨진 값을 보낼 수 있어 방어
      features: { appointments: 'yes' as unknown as boolean },
    };
    const { getByTestId } = wrap(profile, <FlagProbe k="appointments" />);
    expect(getByTestId('flag').textContent).toBe('off');
  });
});
