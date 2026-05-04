import { ChevronRight, Download, SlidersHorizontal } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getModelPresets, getSettings } from "../../api/settings";
import { createReport, exportMarkdown, exportPdf } from "../../api/reports";
import { useAppStore } from "../../store/useAppStore";
import type { ControlTab } from "../../types";

const tabs: ControlTab[] = ["Sources", "Answer", "Citations", "Models", "Export"];

export function RightControlPanel() {
  const queryClient = useQueryClient();
  const open = useAppStore((state) => state.rightPanelOpen);
  const setRightPanelOpen = useAppStore((state) => state.setRightPanelOpen);
  const activeTab = useAppStore((state) => state.activeControlTab);
  const openControlTab = useAppStore((state) => state.openControlTab);
  const settings = useAppStore((state) => state.settings);
  const updateSettings = useAppStore((state) => state.updateSettings);
  const selectedSourceTitle = useAppStore((state) => state.selectedSourceTitle);
  const selectedAnswer = useAppStore((state) => state.selectedAnswer);
  const activeWorkbaseId = useAppStore((state) => state.activeWorkbaseId);
  const [exportStatus, setExportStatus] = useState("");
  const { data: backendSettings } = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const { data: presets = [] } = useQuery({ queryKey: ["model-presets"], queryFn: getModelPresets });

  if (!open) {
    return (
      <aside className="right-panel collapsed">
        <button className="icon-button" aria-label="Open controls" onClick={() => setRightPanelOpen(true)}>
          <SlidersHorizontal size={18} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="right-panel">
      <div className="panel-head">
        <div>
          <strong>Controls</strong>
          <span>{settings.advancedMode ? "Advanced Mode" : "Beginner Mode"}</span>
        </div>
        <button className="icon-button" aria-label="Collapse controls" onClick={() => setRightPanelOpen(false)}>
          <ChevronRight size={18} />
        </button>
      </div>

      <div className="control-tabs">
        {tabs.map((tab) => (
          <button key={tab} className={tab === activeTab ? "active" : ""} onClick={() => openControlTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "Sources" ? (
        <div className="panel-section">
          <h3>Retrieval Mode</h3>
          <RadioRow label="All Sources" checked={settings.retrievalMode === "all"} onChange={() => updateSettings({ retrievalMode: "all" })} />
          <RadioRow label="Curated Only" checked={settings.retrievalMode === "curated_only"} onChange={() => updateSettings({ retrievalMode: "curated_only" })} />
          <RadioRow
            label="Curated + Trusted Web"
            checked={settings.retrievalMode === "curated_trusted"}
            onChange={() => updateSettings({ retrievalMode: "curated_trusted" })}
          />
          <h3>Ask Scope</h3>
          <div className="source-scope">
            <strong>{selectedSourceTitle ? "One Source Only" : "Entire Workbase"}</strong>
            <span>{selectedSourceTitle || "All eligible sources are available for the next answer."}</span>
          </div>
          <Toggle label="Technical Mode" checked={settings.technicalMode} onChange={(technicalMode) => updateSettings({ technicalMode })} />
          <div className="badge-row">
            <span className="source-badge curated">Curated</span>
            <span className="source-badge trusted">Trusted Web</span>
            <span className="source-badge web">Web</span>
          </div>
          {settings.advancedMode ? (
            <div className="advanced-box">
              <span>Retrieval candidates: {String((backendSettings?.backend as Record<string, unknown> | undefined)?.retrievalCandidateCount ?? 30)}</span>
              <span>Final context chunks: {String((backendSettings?.backend as Record<string, unknown> | undefined)?.finalContextChunks ?? 8)}</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {activeTab === "Answer" ? (
        <div className="panel-section">
          <h3>Answer Style</h3>
          {(["Simple", "Technical", "Study Notes", "Article Draft", "Book Chapter Draft"] as const).map((style) => (
            <RadioRow key={style} label={style} checked={settings.answerStyle === style} onChange={() => updateSettings({ answerStyle: style })} />
          ))}
          <h3>Length</h3>
          <Segmented
            values={["Short", "Medium", "Long"]}
            value={settings.answerLength}
            onChange={(answerLength) => updateSettings({ answerLength: answerLength as typeof settings.answerLength })}
          />
          <h3>Tone</h3>
          <Segmented
            values={["Clear", "Academic", "Friendly", "Professional"]}
            value={settings.answerTone}
            onChange={(answerTone) => updateSettings({ answerTone: answerTone as typeof settings.answerTone })}
          />
          {settings.advancedMode ? (
            <div className="advanced-box">
              <span>Temperature: 0.3</span>
              <span>Max output tokens: 1800</span>
            </div>
          ) : null}
        </div>
      ) : null}

      {activeTab === "Citations" ? (
        <div className="panel-section">
          <Toggle label="Citations" checked={settings.citationsEnabled} onChange={(citationsEnabled) => updateSettings({ citationsEnabled })} />
          <h3>Citation Style</h3>
          <RadioRow label="Numbered [1]" checked={settings.citationStyle === "numbered"} onChange={() => updateSettings({ citationStyle: "numbered" })} />
          <RadioRow label="Author-Year" checked={settings.citationStyle === "author_year"} onChange={() => updateSettings({ citationStyle: "author_year" })} />
          <RadioRow label="Markdown Footnotes" checked={settings.citationStyle === "footnotes"} onChange={() => updateSettings({ citationStyle: "footnotes" })} />
          <h3>Warnings</h3>
          <Toggle label="Warn on weak support" checked={true} onChange={() => undefined} />
          <Toggle label="References at bottom" checked={true} onChange={() => undefined} />
        </div>
      ) : null}

      {activeTab === "Models" ? (
        <div className="panel-section">
          <Toggle label="Budget Mode" checked={settings.budgetMode} onChange={(budgetMode) => updateSettings({ budgetMode })} />
          <h3>Model Preset</h3>
          {(["cheapest", "balanced", "best_quality", "custom"] as const).map((preset) => (
            <RadioRow
              key={preset}
              label={preset.replace("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}
              checked={settings.modelPreset === preset}
              onChange={() => updateSettings({ modelPreset: preset })}
            />
          ))}
          <p className="muted">Balanced is recommended for most research writing.</p>
          {settings.advancedMode ? (
            <div className="advanced-box">
              {presets.map((preset) => (
                <span key={preset.id}>
                  {preset.label}: {preset.model}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {activeTab === "Export" ? (
        <div className="panel-section">
          <h3>Export Current Answer</h3>
          <button
            className="secondary-button wide"
            disabled={!selectedAnswer}
            onClick={async () => {
              if (!selectedAnswer) return;
              setExportStatus("Preparing Markdown export...");
              try {
                await exportMarkdown({
                  title: selectedAnswer.title,
                  content: selectedAnswer.content,
                  sources: selectedAnswer.sources,
                  workbase_name: selectedAnswer.workbaseName
                });
                setExportStatus("Markdown export is ready.");
              } catch {
                setExportStatus("Markdown export failed.");
              }
            }}
          >
            <Download size={16} />
            Markdown
          </button>
          <button
            className="secondary-button wide"
            disabled={!selectedAnswer}
            onClick={async () => {
              if (!selectedAnswer) return;
              setExportStatus("Preparing PDF export...");
              try {
                await exportPdf({
                  title: selectedAnswer.title,
                  content: selectedAnswer.content,
                  sources: selectedAnswer.sources,
                  workbase_name: selectedAnswer.workbaseName
                });
                setExportStatus("PDF export is ready.");
              } catch {
                setExportStatus("PDF export failed. Check if Pandoc is available.");
              }
            }}
          >
            <Download size={16} />
            PDF
          </button>
          <button
            className="secondary-button wide"
            disabled={!selectedAnswer || !activeWorkbaseId}
            onClick={async () => {
              if (!selectedAnswer || !activeWorkbaseId) return;
              setExportStatus("Saving answer as report...");
              try {
                await createReport(activeWorkbaseId, {
                  title: selectedAnswer.title,
                  type: "Research Summary",
                  content: selectedAnswer.content,
                  sources: selectedAnswer.sources,
                  generate: "none"
                });
                queryClient.invalidateQueries({ queryKey: ["reports", activeWorkbaseId] });
                setExportStatus("Saved as report.");
              } catch {
                setExportStatus("Could not save this answer as a report.");
              }
            }}
          >
            Save as Report
          </button>
          <h3>Include</h3>
          <Toggle label="Inline citations" checked={true} onChange={() => undefined} />
          <Toggle label="References" checked={true} onChange={() => undefined} />
          <Toggle label="Source list" checked={true} onChange={() => undefined} />
          {!selectedAnswer ? <p className="muted">Select an assistant answer in Chat to export.</p> : null}
          {exportStatus ? <p className="muted">{exportStatus}</p> : null}
          <p className="muted">PDF export requires Pandoc on the backend server.</p>
        </div>
      ) : null}
    </aside>
  );
}

function RadioRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <label className="radio-row">
      <input type="radio" checked={checked} onChange={onChange} />
      <span>{label}</span>
    </label>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="toggle-row">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

function Segmented({ values, value, onChange }: { values: string[]; value: string; onChange: (value: string) => void }) {
  return (
    <div className="segmented">
      {values.map((item) => (
        <button key={item} className={item === value ? "active" : ""} onClick={() => onChange(item)}>
          {item}
        </button>
      ))}
    </div>
  );
}
