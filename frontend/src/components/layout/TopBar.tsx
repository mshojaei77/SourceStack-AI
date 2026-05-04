import { Download, PanelRightClose, PanelRightOpen, Search } from "lucide-react";
import type { Workbase } from "../../types";
import { useAppStore } from "../../store/useAppStore";

export function TopBar({ workbases }: { workbases: Workbase[] }) {
  const activeWorkbaseId = useAppStore((state) => state.activeWorkbaseId);
  const setActiveWorkbaseId = useAppStore((state) => state.setActiveWorkbaseId);
  const settings = useAppStore((state) => state.settings);
  const rightPanelOpen = useAppStore((state) => state.rightPanelOpen);
  const setRightPanelOpen = useAppStore((state) => state.setRightPanelOpen);
  const openControlTab = useAppStore((state) => state.openControlTab);

  return (
    <header className="top-bar">
      <div className="top-context">
        <select
          className="select-control workbase-select"
          value={activeWorkbaseId ?? ""}
          onChange={(event) => setActiveWorkbaseId(event.target.value || null)}
          aria-label="Workbase"
        >
          {workbases.length === 0 ? <option value="">No Workbase</option> : null}
          {workbases.map((workbase) => (
            <option key={workbase.id} value={workbase.id}>
              {workbase.name}
            </option>
          ))}
        </select>
        <button className="chip chip-blue" onClick={() => openControlTab("Sources")}>
          {settings.retrievalMode === "curated_only" ? "Curated Only" : settings.retrievalMode === "curated_trusted" ? "Curated + Trusted Web" : "All Sources"}
        </button>
        <button className="chip" onClick={() => openControlTab("Answer")}>
          {settings.answerStyle}
        </button>
      </div>
      <div className="top-actions">
        <div className="top-search">
          <Search size={15} />
          <span>Search sources...</span>
        </div>
        <button className="icon-button" aria-label="Export" onClick={() => openControlTab("Export")}>
          <Download size={18} />
        </button>
        <button className="icon-button" aria-label="Toggle controls" onClick={() => setRightPanelOpen(!rightPanelOpen)}>
          {rightPanelOpen ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
        </button>
      </div>
    </header>
  );
}
