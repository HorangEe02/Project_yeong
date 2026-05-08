// PlotlyChart — react-plotly.js/factory 패턴 (CJS interop 우회).
// react-plotly.js 는 CJS only (package.json 에 "module" 필드 없음).
// Vite ESM interop 이 default 매핑 실패 → factory(Plotly) 로 직접 컴포넌트 생성.
//
// ⚠️ 런타임은 'plotly.js/dist/plotly.min' 사용 (사전 번들된 브라우저 전용 빌드).
//    소스 ESM 'plotly.js' 는 Node 빌트인(stream/buffer/util)에 의존 → Vite externalize → TypeError.
//    dist 빌드는 모든 의존이 번들 내부로 inlining 되어 있어 안전.

import { useMemo } from 'react';
import type { Data, Layout, Config } from 'plotly.js';
// @ts-expect-error — dist 빌드는 별도 .d.ts 미제공이나 동일한 Plotly API 노출.
import Plotly from 'plotly.js/dist/plotly.min';
// react-plotly.js/factory 는 Babel CJS (`exports.default = fn`).
// Vite optimizer 가 default 를 풀어주지 못하는 경우(namespace 객체 반환) 방어적 unwrap.
import factoryModule from 'react-plotly.js/factory';
import { useThemeStore } from '@store/theme';

// react-plotly.js Plot 컴포넌트는 다양한 prop 을 받기에 any 타입 prop 으로 안전하게 처리.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyComponent = React.ComponentType<any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const createPlotlyComponent: (plotly: unknown) => AnyComponent =
  typeof factoryModule === 'function'
    ? (factoryModule as any)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    : ((factoryModule as any).default as any);

const Plot: AnyComponent = createPlotlyComponent(Plotly);

interface Props {
  data: Data[];
  layout?: Partial<Layout>;
  config?: Partial<Config>;
  className?: string;
  style?: React.CSSProperties;
  onClick?: (event: Readonly<Plotly.PlotMouseEvent>) => void;
}

const baseLayoutLight: Partial<Layout> = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Pretendard, "Noto Sans KR", sans-serif', color: '#2C241A', size: 12 },
  hoverlabel: {
    bgcolor: '#FFFFFF',
    bordercolor: '#D89400',
    font: { family: 'Pretendard, "Noto Sans KR", sans-serif', color: '#2C241A', size: 12 },
  },
  colorway: ['#D89400', '#2D8A4E', '#2980B9', '#E8A317', '#C0392B', '#5C4E3C'],
  margin: { l: 50, r: 30, t: 30, b: 50 },
};

const baseLayoutDark: Partial<Layout> = {
  ...baseLayoutLight,
  font: { family: 'Pretendard, "Noto Sans KR", sans-serif', color: '#E8E1D5', size: 12 },
  hoverlabel: {
    bgcolor: '#1c2636',
    bordercolor: '#FCB132',
    font: { family: 'Pretendard, "Noto Sans KR", sans-serif', color: '#E8E1D5', size: 12 },
  },
  colorway: ['#FCB132', '#2D8A4E', '#2980B9', '#E8A317', '#C0392B', '#D5CFC5'],
};

const defaultConfig: Partial<Config> = {
  displaylogo: false,
  responsive: true,
  modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
};

export function PlotlyChart({ data, layout, config, className, style, onClick }: Props) {
  const theme = useThemeStore((s) => s.resolved());

  const mergedLayout = useMemo<Partial<Layout>>(() => {
    const base = theme === 'light' ? baseLayoutLight : baseLayoutDark;
    return { ...base, ...layout, autosize: true };
  }, [theme, layout]);

  const mergedConfig = useMemo<Partial<Config>>(
    () => ({ ...defaultConfig, ...config }),
    [config],
  );

  return (
    <Plot
      data={data}
      layout={mergedLayout}
      config={mergedConfig}
      useResizeHandler
      style={{ width: '100%', height: '100%', minHeight: 300, ...style }}
      className={className}
      onClick={onClick}
    />
  );
}
