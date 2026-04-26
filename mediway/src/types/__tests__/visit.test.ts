import { describe, it, expect } from 'vitest';
import {
  isOutpatientVisit,
  isInpatientVisit,
  isCheckupVisit,
  isEmergencyVisit,
  isActiveStatus,
  VISIT_TYPE_REQUIRED_FIELDS,
  VISIT_NOTES_MAX_LENGTH,
  type Visit,
} from '../visit';

function baseVisit(overrides: Partial<Visit> = {}): Visit {
  return {
    visitId: 'v1',
    patientUid: 'uid-1',
    hospitalId: 'demo',
    type: 'outpatient',
    status: 'scheduled',
    zone: 'Zone A-1',
    department: 'IM',
    createdAt: 1700000000000,
    updatedAt: 1700000000000,
    createdBy: 'admin-1',
    ...overrides,
  };
}

// =====================================================================
// Type guards
// =====================================================================

describe('Visit type guards', () => {
  it('isOutpatientVisit — type=outpatient + department 존재 → true', () => {
    const v = baseVisit({ type: 'outpatient', department: 'IM' });
    expect(isOutpatientVisit(v)).toBe(true);
  });

  it('isOutpatientVisit — type=outpatient 인데 department 누락 → false', () => {
    const v = baseVisit({ type: 'outpatient', department: undefined });
    expect(isOutpatientVisit(v)).toBe(false);
  });

  it('isInpatientVisit — type=inpatient + ward + room → true', () => {
    const v = baseVisit({ type: 'inpatient', ward: '3W', room: '302', department: undefined });
    expect(isInpatientVisit(v)).toBe(true);
  });

  it('isInpatientVisit — type=inpatient 인데 ward 누락 → false', () => {
    const v = baseVisit({ type: 'inpatient', ward: undefined, room: '302' });
    expect(isInpatientVisit(v)).toBe(false);
  });

  it('isInpatientVisit — type=inpatient 인데 room 누락 → false', () => {
    const v = baseVisit({ type: 'inpatient', ward: '3W', room: undefined });
    expect(isInpatientVisit(v)).toBe(false);
  });

  it('isCheckupVisit — type=checkup → true (zone 만 있으면 OK)', () => {
    const v = baseVisit({ type: 'checkup', department: undefined });
    expect(isCheckupVisit(v)).toBe(true);
  });

  it('isEmergencyVisit — type=emergency + department=ER → true', () => {
    const v = baseVisit({ type: 'emergency', department: 'ER' });
    expect(isEmergencyVisit(v)).toBe(true);
  });

  it('type guard 들은 mutually exclusive — outpatient 는 다른 type guard 모두 false', () => {
    const out = baseVisit({ type: 'outpatient', department: 'IM' });
    expect(isInpatientVisit(out)).toBe(false);
    expect(isCheckupVisit(out)).toBe(false);
    expect(isEmergencyVisit(out)).toBe(false);
  });
});

// =====================================================================
// VISIT_TYPE_REQUIRED_FIELDS
// =====================================================================

describe('VISIT_TYPE_REQUIRED_FIELDS', () => {
  it('outpatient — patientUid + zone + department', () => {
    expect(VISIT_TYPE_REQUIRED_FIELDS.outpatient).toEqual([
      'patientUid',
      'zone',
      'department',
    ]);
  });

  it('inpatient — patientUid + ward + room (zone 제외)', () => {
    expect(VISIT_TYPE_REQUIRED_FIELDS.inpatient).toEqual([
      'patientUid',
      'ward',
      'room',
    ]);
  });

  it('checkup — patientUid + zone', () => {
    expect(VISIT_TYPE_REQUIRED_FIELDS.checkup).toEqual(['patientUid', 'zone']);
  });

  it('emergency — patientUid + zone + department', () => {
    expect(VISIT_TYPE_REQUIRED_FIELDS.emergency).toEqual([
      'patientUid',
      'zone',
      'department',
    ]);
  });

  it('readonly — runtime 변경 불가 (Object.freeze)', () => {
    expect(Object.isFrozen(VISIT_TYPE_REQUIRED_FIELDS)).toBe(true);
    expect(Object.isFrozen(VISIT_TYPE_REQUIRED_FIELDS.outpatient)).toBe(true);
  });
});

// =====================================================================
// Status helpers
// =====================================================================

describe('isActiveStatus', () => {
  it('checked-in → true', () => {
    expect(isActiveStatus('checked-in')).toBe(true);
  });

  it('in-progress → true', () => {
    expect(isActiveStatus('in-progress')).toBe(true);
  });

  it('scheduled → false', () => {
    expect(isActiveStatus('scheduled')).toBe(false);
  });

  it('completed → false', () => {
    expect(isActiveStatus('completed')).toBe(false);
  });

  it('cancelled → false', () => {
    expect(isActiveStatus('cancelled')).toBe(false);
  });
});

// =====================================================================
// Constants
// =====================================================================

describe('VISIT_NOTES_MAX_LENGTH', () => {
  it('500 자 cap', () => {
    expect(VISIT_NOTES_MAX_LENGTH).toBe(500);
  });
});
