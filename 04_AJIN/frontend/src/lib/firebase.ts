// Firebase SDK 초기화 — 4 서비스 (Auth + Firestore + RTDB + Storage)
// 환경변수: .env.development.local (gitignored)

import { initializeApp, type FirebaseApp } from 'firebase/app';
import { getAuth, type Auth } from 'firebase/auth';
import { getFirestore, type Firestore } from 'firebase/firestore';
import { getDatabase, type Database } from 'firebase/database';
import { getStorage, type FirebaseStorage } from 'firebase/storage';

interface FirebaseConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  databaseURL?: string;
  storageBucket: string;
  messagingSenderId: string;
  appId: string;
}

function readConfig(): FirebaseConfig | null {
  const env = import.meta.env;
  const apiKey = env.VITE_FIREBASE_API_KEY as string | undefined;
  if (!apiKey) {
    return null; // 키 미설정 — Mock 모드만 가능
  }
  return {
    apiKey,
    authDomain: env.VITE_FIREBASE_AUTH_DOMAIN as string,
    projectId: env.VITE_FIREBASE_PROJECT_ID as string,
    databaseURL: env.VITE_FIREBASE_DATABASE_URL as string | undefined,
    storageBucket: env.VITE_FIREBASE_STORAGE_BUCKET as string,
    messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID as string,
    appId: env.VITE_FIREBASE_APP_ID as string,
  };
}

const config = readConfig();
let app: FirebaseApp | null = null;
let _auth: Auth | null = null;
let _firestore: Firestore | null = null;
let _rtdb: Database | null = null;
let _storage: FirebaseStorage | null = null;

if (config) {
  app = initializeApp(config);
  _auth = getAuth(app);
  _firestore = getFirestore(app);
  if (config.databaseURL) {
    _rtdb = getDatabase(app);
  }
  _storage = getStorage(app);
  if (import.meta.env.DEV) {
    console.info('[Firebase] Initialized:', config.projectId);
  }
} else if (import.meta.env.DEV) {
  console.warn(
    '[Firebase] VITE_FIREBASE_API_KEY 미설정 — .env.development.local 확인 필요. Mock 모드만 동작.',
  );
}

export const firebaseApp = app;
export const auth = _auth;
export const firestore = _firestore;
export const rtdb = _rtdb;
export const storage = _storage;
export const isFirebaseConfigured = () => app !== null;
