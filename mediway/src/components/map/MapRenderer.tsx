import type { MapRendererProps } from '@/types/map-renderer';
import { useMapRendererContext } from './MapRendererContext';
import { SvgNativeMapRenderer } from './svg-renderer/SvgNativeMapRenderer';

/**
 * 다형성 지도 렌더러.
 * MapRendererContext의 rendererType에 따라 적절한 구현체로 디스패치합니다.
 * Leaflet 렌더러는 Phase G에서 추가됩니다.
 */
export function MapRenderer(props: MapRendererProps) {
  const { rendererType } = useMapRendererContext();

  switch (rendererType) {
    case 'leaflet':
      // Phase G에서 LeafletMapRenderer 추가 예정
      return <SvgNativeMapRenderer {...props} />;
    case 'svg-native':
    default:
      return <SvgNativeMapRenderer {...props} />;
  }
}
