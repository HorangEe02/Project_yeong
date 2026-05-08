import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/tokens.css';
import './styles/theme.css';
import './styles/components.css';
import './styles/animations.css';
import './styles/lg-theme.css'; // canonical Liquid Glass design system (uiux v2)
import './index.css';
import './i18n';
import App from './App';
import { ToastContainer } from '@components/ui/Toast';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <ToastContainer />
  </StrictMode>,
);
