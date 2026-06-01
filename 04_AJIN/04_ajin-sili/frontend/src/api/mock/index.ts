// Mock API 클라이언트 — VITE_USE_MOCK=true 일 때 활성
// axios 인스턴스를 가로채는 게 아니라, api/* 모듈에서 직접 호출

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

export * from './handlers';
