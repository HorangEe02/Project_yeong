import { createContext, useContext, type ReactNode } from 'react';
import type { MapRendererType } from '@/types/map-renderer';

interface MapRendererContextValue {
  rendererType: MapRendererType;
}

const MapRendererContext = createContext<MapRendererContextValue>({
  rendererType: 'svg-native',
});

export function MapRendererProvider({
  type,
  children,
}: {
  type: MapRendererType;
  children: ReactNode;
}) {
  return (
    <MapRendererContext.Provider value={{ rendererType: type }}>
      {children}
    </MapRendererContext.Provider>
  );
}

export function useMapRendererContext() {
  return useContext(MapRendererContext);
}
