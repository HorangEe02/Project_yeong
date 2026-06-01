// ErrorBoundary — 페이지 단위 에러 격리 (전체 앱 빈 화면 방지)

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: (err: Error, reset: () => void) => ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) {
      console.error('[ErrorBoundary]', error, info.componentStack);
    }
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.fallback) {
      return this.props.fallback(error, this.reset);
    }

    return (
      <div
        role="alert"
        style={{
          margin: '24px auto',
          maxWidth: 720,
          padding: 24,
          border: '1px solid var(--hud-red)',
          background: 'color-mix(in oklab, var(--hud-red) 8%, transparent)',
          fontFamily: 'var(--hud-font)',
        }}
      >
        <div
          style={{
            color: 'var(--hud-red)',
            fontSize: 13,
            fontWeight: 700,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            marginBottom: 8,
          }}
        >
          ● 페이지 렌더링 오류
        </div>
        <h2 style={{ margin: '8px 0', fontSize: 18 }}>일시적인 문제가 발생했습니다</h2>
        <p style={{ color: 'var(--hud-text-dim)', fontSize: 13, lineHeight: 1.6 }}>
          {error.message || '알 수 없는 오류'}
        </p>
        <pre
          style={{
            fontSize: 11,
            background: 'var(--hud-surface)',
            border: '1px solid var(--hud-border)',
            padding: 8,
            marginTop: 12,
            overflowX: 'auto',
            color: 'var(--hud-text-dim)',
            maxHeight: 200,
          }}
        >
          {error.stack?.split('\n').slice(0, 5).join('\n')}
        </pre>
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          <button className="btn primary sm" onClick={this.reset}>
            다시 시도
          </button>
          <button className="btn ghost sm" onClick={() => window.location.reload()}>
            새로고침
          </button>
          <button
            className="btn ghost sm"
            onClick={() => {
              window.location.href = '/';
            }}
          >
            대시보드로 이동
          </button>
        </div>
      </div>
    );
  }
}
