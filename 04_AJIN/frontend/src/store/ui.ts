import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type ChatPageTab = 'chat' | 'learn';
export type EquipmentSubTab = 'overview' | 'alerts' | 'equipment' | 'predictive' | 'spc' | 'ml';
export type EquipmentMainTab = 'overview' | 'manual_error' | 'inspection';
export type DraftPageTab = 'internal' | 'external' | 'history';

interface UIState {
  rightPanelOpen: boolean;
  sidebarCollapsed: boolean;
  mobileNavOpen: boolean;
  isStreaming: boolean;
  noteBoxExpanded: boolean;
  chatPageTab: ChatPageTab;
  equipmentMainTab: EquipmentMainTab;
  equipmentSubTab: EquipmentSubTab;
  draftPageTab: DraftPageTab;
  activeAlarmCount: number;
  toggleRightPanel: () => void;
  setRightPanelOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  toggleMobileNav: () => void;
  setMobileNavOpen: (open: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  toggleNoteBox: () => void;
  setNoteBoxExpanded: (expanded: boolean) => void;
  setChatPageTab: (tab: ChatPageTab) => void;
  setEquipmentMainTab: (tab: EquipmentMainTab) => void;
  setEquipmentSubTab: (tab: EquipmentSubTab) => void;
  setDraftPageTab: (tab: DraftPageTab) => void;
  incActiveAlarms: () => void;
  clearAlarms: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      rightPanelOpen: true,
      sidebarCollapsed: false,
      mobileNavOpen: false,
      isStreaming: false,
      noteBoxExpanded: true,
      chatPageTab: 'chat',
      equipmentMainTab: 'overview',
      equipmentSubTab: 'overview',
      draftPageTab: 'internal',
      activeAlarmCount: 0,
      toggleRightPanel: () =>
        set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
      setRightPanelOpen: (open) => set({ rightPanelOpen: open }),
      toggleSidebar: () =>
        set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      toggleMobileNav: () =>
        set((s) => ({ mobileNavOpen: !s.mobileNavOpen })),
      setMobileNavOpen: (open) => set({ mobileNavOpen: open }),
      setStreaming: (isStreaming) => set({ isStreaming }),
      toggleNoteBox: () =>
        set((s) => ({ noteBoxExpanded: !s.noteBoxExpanded })),
      setNoteBoxExpanded: (expanded) => set({ noteBoxExpanded: expanded }),
      setChatPageTab: (chatPageTab) => set({ chatPageTab }),
      setEquipmentMainTab: (equipmentMainTab) => set({ equipmentMainTab }),
      setEquipmentSubTab: (equipmentSubTab) => set({ equipmentSubTab }),
      setDraftPageTab: (draftPageTab) => set({ draftPageTab }),
      incActiveAlarms: () =>
        set((s) => ({ activeAlarmCount: s.activeAlarmCount + 1 })),
      clearAlarms: () => set({ activeAlarmCount: 0 }),
    }),
    {
      name: 'ajin-ui',
      partialize: (state) => ({
        rightPanelOpen: state.rightPanelOpen,
        sidebarCollapsed: state.sidebarCollapsed,
        noteBoxExpanded: state.noteBoxExpanded,
        chatPageTab: state.chatPageTab,
        equipmentMainTab: state.equipmentMainTab,
        equipmentSubTab: state.equipmentSubTab,
        draftPageTab: state.draftPageTab,
      }),
    },
  ),
);
