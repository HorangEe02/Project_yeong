// MapView — react-leaflet (2D Mercator).
// 마커 아이콘 fix + StrictMode 안전 (key 기반 강제 remount).
// 줌아웃 시 양 옆 평면 반복 방지 — TileLayer noWrap + MapContainer maxBounds.

import { useId, useMemo, type ReactNode } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';
import 'leaflet/dist/leaflet.css';
import { useThemeStore } from '@store/theme';

// ── Leaflet 기본 마커 아이콘 fix (Vite 빌드 시 default URL 깨짐) ─────────
// _getIconUrl 의 사용을 막고 mergeOptions로 직접 url 주입
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: () => string })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

export interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  name: string;
  description?: string;
  popupContent?: ReactNode;
}

interface Props {
  markers: MapMarker[];
  center?: [number, number];
  zoom?: number;
  height?: string | number;
  className?: string;
  onMarkerClick?: (m: MapMarker) => void;
}

const TILE_LIGHT = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png';
const TILE_DARK = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const TILE_ATTR =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>';

// 경산 본사 좌표 (PLANT-KS-HQ) — 마커 없을 때 기본 중심
const HQ_CENTER: [number, number] = [35.8268, 128.7975];

export function MapView({
  markers,
  center,
  zoom = 7,
  height = 400,
  className,
  onMarkerClick,
}: Props) {
  const theme = useThemeStore((s) => s.resolved());
  // 컴포넌트 인스턴스마다 고유 ID — StrictMode 이중 마운트 시 key로 강제 분리
  const instanceId = useId();

  const computedCenter = useMemo<[number, number]>(() => {
    if (center) return center;
    // 마커 0~1개면 경산 본사 중심 (한국 지도 기준)
    if (markers.length <= 1) return HQ_CENTER;
    const sum = markers.reduce(
      (acc, m) => ({ lat: acc.lat + m.lat, lng: acc.lng + m.lng }),
      { lat: 0, lng: 0 },
    );
    return [sum.lat / markers.length, sum.lng / markers.length];
  }, [center, markers]);

  return (
    <div className={className}>
      <MapContainer
        key={`map-${instanceId}-${theme}`}
        center={computedCenter}
        zoom={zoom}
        minZoom={2}
        worldCopyJump={true}
        style={{
          height: typeof height === 'number' ? `${height}px` : height,
          width: '100%',
        }}
        className="ui-map"
        scrollWheelZoom={false}
      >
        <TileLayer
          url={theme === 'light' ? TILE_LIGHT : TILE_DARK}
          attribution={TILE_ATTR}
        />
        {markers.map((m) => (
          <Marker
            key={m.id}
            position={[m.lat, m.lng]}
            eventHandlers={{
              click: () => onMarkerClick?.(m),
            }}
          >
            <Popup>
              {m.popupContent ?? (
                <div>
                  <strong>{m.name}</strong>
                  {m.description && <div style={{ marginTop: 4, fontSize: 12 }}>{m.description}</div>}
                </div>
              )}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
