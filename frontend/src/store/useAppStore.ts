import { create } from "zustand";
import type { ChatSettings, ControlTab, SelectedAnswer, SourceDetail } from "../types";

type AppState = {
  activeWorkbaseId: string | null;
  setActiveWorkbaseId: (id: string | null) => void;
  rightPanelOpen: boolean;
  setRightPanelOpen: (open: boolean) => void;
  activeControlTab: ControlTab;
  openControlTab: (tab: ControlTab) => void;
  selectedSourceId: string | null;
  selectedSourceTitle: string;
  focusSource: (id: string | null, title?: string) => void;
  settings: ChatSettings;
  updateSettings: (patch: Partial<ChatSettings>) => void;
  selectedAnswer: SelectedAnswer | null;
  setSelectedAnswer: (value: SelectedAnswer | null) => void;
  sourceDetail: SourceDetail | null;
  setSourceDetail: (value: SourceDetail | null) => void;
};

export const useAppStore = create<AppState>((set) => ({
  activeWorkbaseId: null,
  setActiveWorkbaseId: (id) => set({ activeWorkbaseId: id }),
  rightPanelOpen: true,
  setRightPanelOpen: (open) => set({ rightPanelOpen: open }),
  activeControlTab: "Sources",
  openControlTab: (tab) => set({ activeControlTab: tab, rightPanelOpen: true }),
  selectedSourceId: null,
  selectedSourceTitle: "",
  focusSource: (id, title = "") => set({ selectedSourceId: id, selectedSourceTitle: title }),
  settings: {
    answerStyle: "Simple",
    retrievalMode: "curated_trusted",
    citationStyle: "numbered",
    citationsEnabled: true,
    technicalMode: false,
    budgetMode: true,
    modelPreset: "balanced",
    advancedMode: false,
    answerLength: "Medium",
    answerTone: "Clear"
  },
  updateSettings: (patch) => set((state) => ({ settings: { ...state.settings, ...patch } })),
  selectedAnswer: null,
  setSelectedAnswer: (value) => set({ selectedAnswer: value }),
  sourceDetail: null,
  setSourceDetail: (value) => set({ sourceDetail: value })
}));
