// Legacy Firebase compatibility shim.
//
// Firebase client access has been removed from the browser bundle. Keep these
// exports while older call sites are retired so imports fail closed instead of
// pulling Firebase SDK code into production builds.

export const firebaseApp = null;
export const auth = null;
export const firestore = null;
export const rtdb = null;
export const storage = null;

export const isFirebaseConfigured = () => false;
export const isFirebaseWriteEnabled = () => false;
export const isFirebaseReadFallbackEnabled = () => false;
