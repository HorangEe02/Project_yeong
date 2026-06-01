import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/tokens.css';
import './styles/breakpoints.css';
import './styles/theme.css';
import './styles/components.css';
import './styles/animations.css';
import './styles/lg-theme.css'; // canonical Liquid Glass design system (uiux v2)
import './styles/neural.css'; // v3.5 Neural Expressive overlay — activated by [data-neural="on"]
// v3.5 — 모바일 전용 Liquid Glass v3 lensing layer (uiux/.../mobile-theme + v3).
// .aj-mobile 클래스 wrapper 가 활성 시 layered glass + specular edge + lens refraction 적용.
// _shell.tsx 가 isMobile && data-neural 시 .aj-mobile 클래스 부착.
import './styles/mobile-theme.css';
import './styles/mobile-theme-v3.css';
import './index.css';
import './styles/responsive-overrides.css';
import './i18n';
import App from './App';
import { ToastContainer } from '@components/ui/Toast';

// v3.9 — Vite 공식 vite:preloadError 이벤트 처리.
// Vercel 재배포 시 chunk hash 가 바뀌면 stale index.html 캐시를 가진 브라우저가
// 옛 chunk URL 로 dynamic import 시도 → 새 deployment 에 그 hash 없음 → 실패.
// 이 listener 가 자동으로 한 번만 location.reload() 호출하여 새 index.html 을 받아 옴.
// sessionStorage 가드로 무한 reload 방지 (새 빌드도 실패하면 정지).
// 참고: https://vitejs.dev/guide/build.html#load-error-handling
const VITE_RELOAD_KEY = '__vite_preload_reloaded';
window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault();
  if (sessionStorage.getItem(VITE_RELOAD_KEY) === '1') {
    // 이미 한 번 reload 했는데 또 실패 — 실제 버그. ErrorBoundary 에 표시되게 둠.
    return;
  }
  sessionStorage.setItem(VITE_RELOAD_KEY, '1');
  window.location.reload();
});
// 정상 페이지 로드되면 reload 가드 초기화
window.addEventListener('load', () => {
  sessionStorage.removeItem(VITE_RELOAD_KEY);
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <ToastContainer />
  </StrictMode>,
);
