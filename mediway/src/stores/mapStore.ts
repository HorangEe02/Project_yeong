import { create } from 'zustand';
import type { MapRendererType } from '@/types/map-renderer';

interface MapState {
  rendererType: MapRendererType;
  currentFloor: number;
  selectedPoiId: string | null;
  setRendererType: (type: MapRendererType) => void;
  setCurrentFloor: (floor: number) => void;
  setSelectedPoiId: (poiId: string | null) => void;
}

export const useMapStore = create<MapState>((set) => ({
  rendererType: 'svg-native',
  currentFloor: 1,
  selectedPoiId: null,
  setRendererType: (type) => set({ rendererType: type }),
  setCurrentFloor: (floor) => set({ currentFloor: floor }),
  setSelectedPoiId: (poiId) => set({ selectedPoiId: poiId }),
}));
