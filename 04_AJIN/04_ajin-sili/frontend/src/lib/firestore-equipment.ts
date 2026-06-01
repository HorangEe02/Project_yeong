// Legacy Firestore equipment seed shim.
//
// Equipment demo data is now seeded through backend/Postgres scripts. Keeping
// these exports avoids breaking older admin/debug call sites while preventing
// Firebase Web SDK imports from entering the browser bundle.

export interface SeedResult {
  collection: string;
  written: number;
  skipped: boolean;
  reason?: string;
}

const FIREBASE_REMOVED_REASON = 'Firebase client seed path removed; use backend/Postgres seed scripts';

/** Skip legacy Firestore error-history seeding. */
export async function seedErrorHistory(_force = false): Promise<SeedResult> {
  return {
    collection: 'equipment_error_history',
    written: 0,
    skipped: true,
    reason: FIREBASE_REMOVED_REASON,
  };
}

/** Skip legacy Firestore mold seeding. */
export async function seedMolds(_force = false): Promise<SeedResult> {
  return {
    collection: 'equipment_molds',
    written: 0,
    skipped: true,
    reason: FIREBASE_REMOVED_REASON,
  };
}

/** Skip legacy Firestore equipment seeding. */
export async function seedEquipmentToFirestore(force = false): Promise<SeedResult[]> {
  return Promise.all([seedErrorHistory(force), seedMolds(force)]);
}

if (typeof window !== 'undefined' && import.meta.env.DEV) {
  (window as unknown as { __seedEquipment: typeof seedEquipmentToFirestore }).__seedEquipment =
    seedEquipmentToFirestore;
}
