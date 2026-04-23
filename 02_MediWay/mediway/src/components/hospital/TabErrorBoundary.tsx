import { Component, type ErrorInfo, type ReactNode } from 'react';

/**
 * 탭별 Error Boundary — 한 탭의 렌더 에러가 다른 탭을 깨뜨리지 않게 격리.
 *
 * v2 §Phase 2 "원칙 7계명" 중 "Tab 간 독립" 구현.
 */
export interface TabErrorBoundaryProps {
  tabLabel: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class TabErrorBoundary extends Component<TabErrorBoundaryProps, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[${this.props.tabLabel}] 탭 렌더 에러`, error, info);
  }

  private reset = () => this.setState({ error: null });

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="p-6 text-center" role="alert">
          <p className="mb-2 font-medium">
            {this.props.tabLabel} 탭을 불러오지 못했습니다
          </p>
          <p className="mb-4 text-sm text-on-surface-variant">
            {this.state.error.message}
          </p>
          <button
            type="button"
            onClick={this.reset}
            className="rounded-lg border border-outline-variant px-4 py-2 text-sm"
          >
            다시 시도
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
