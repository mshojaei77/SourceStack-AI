import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSettings } from "../api/settings";
import { useAppStore } from "../store/useAppStore";

export function SettingsPage() {
  const settings = useAppStore((state) => state.settings);
  const updateSettings = useAppStore((state) => state.updateSettings);
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: getSettings });
  const data = settingsQuery.data;
  const backend = useMemo(() => (data?.backend as Record<string, unknown> | undefined), [data]);

  if (settingsQuery.isLoading) {
    return <div className="page-panel">Loading settings...</div>;
  }

  if (settingsQuery.isError) {
    return <div className="error-state">Could not load settings. Please retry.</div>;
  }

  return (
    <section className="page-stack">
      <div className="page-title-row">
        <div>
          <h1>Settings</h1>
          <p>Control defaults, retrieval behavior, citation policy, models, and export behavior.</p>
        </div>
      </div>

      <div className="settings-grid">
        <section className="settings-card">
          <h2>General</h2>
          <label className="setting-row">
            <span>Default Answer Style</span>
            <select
              value={settings.answerStyle}
              onChange={(event) =>
                updateSettings({
                  answerStyle: event.target.value as typeof settings.answerStyle
                })
              }
            >
              <option>Simple</option>
              <option>Technical</option>
              <option>Study Notes</option>
              <option>Article Draft</option>
              <option>Book Chapter Draft</option>
            </select>
          </label>
          <label className="setting-row">
            <span>Default Retrieval Mode</span>
            <select
              value={settings.retrievalMode}
              onChange={(event) =>
                updateSettings({
                  retrievalMode: event.target.value as typeof settings.retrievalMode
                })
              }
            >
              <option value="all">All Sources</option>
              <option value="curated_only">Curated Only</option>
              <option value="curated_trusted">Curated + Trusted Web</option>
            </select>
          </label>
          <label className="setting-row">
            <span>Theme</span>
            <select defaultValue="system">
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
          <label className="setting-row toggle">
            <span>Advanced Mode</span>
            <input
              type="checkbox"
              checked={settings.advancedMode}
              onChange={(event) => updateSettings({ advancedMode: event.target.checked })}
            />
          </label>
        </section>

        <section className="settings-card">
          <h2>Sources</h2>
          <label className="setting-row toggle">
            <span>Technical Mode default</span>
            <input
              type="checkbox"
              checked={settings.technicalMode}
              onChange={(event) => updateSettings({ technicalMode: event.target.checked })}
            />
          </label>
          <label className="setting-row">
            <span>Trusted domain whitelist</span>
            <textarea
              value={(backend?.trustedDomainWhitelist as string[] | undefined)?.join("\n") ?? ""}
              readOnly
              rows={8}
            />
          </label>
          <p className="muted">Duplicate handling is automatic: repeated uploads or URLs skip existing chunks.</p>
        </section>

        <section className="settings-card">
          <h2>Citations</h2>
          <label className="setting-row toggle">
            <span>Citations enabled</span>
            <input
              type="checkbox"
              checked={settings.citationsEnabled}
              onChange={(event) => updateSettings({ citationsEnabled: event.target.checked })}
            />
          </label>
          <label className="setting-row">
            <span>Citation style</span>
            <select
              value={settings.citationStyle}
              onChange={(event) =>
                updateSettings({
                  citationStyle: event.target.value as typeof settings.citationStyle
                })
              }
            >
              <option value="numbered">Numbered [1]</option>
              <option value="author_year">Author-Year</option>
              <option value="footnotes">Markdown Footnotes</option>
            </select>
          </label>
          <p className="muted">MVP defaults to numbered citations and references at the bottom.</p>
        </section>

        <section className="settings-card">
          <h2>Models and Cost</h2>
          <label className="setting-row">
            <span>Model preset</span>
            <select
              value={settings.modelPreset}
              onChange={(event) =>
                updateSettings({
                  modelPreset: event.target.value as typeof settings.modelPreset
                })
              }
            >
              <option value="cheapest">Cheapest</option>
              <option value="balanced">Balanced</option>
              <option value="best_quality">Best Quality</option>
              <option value="custom">Custom</option>
            </select>
          </label>
          <label className="setting-row toggle">
            <span>Budget Mode</span>
            <input
              type="checkbox"
              checked={settings.budgetMode}
              onChange={(event) => updateSettings({ budgetMode: event.target.checked })}
            />
          </label>
          <div className="settings-meta">
            <span>Embedding model: {String(backend?.embeddingModel ?? "n/a")}</span>
            <span>Reranker: {String(backend?.rerankerModel ?? "n/a")}</span>
            <span>Retrieval candidates: {String(backend?.retrievalCandidateCount ?? "n/a")}</span>
            <span>Final context chunks: {String(backend?.finalContextChunks ?? "n/a")}</span>
          </div>
        </section>

        <section className="settings-card">
          <h2>Export</h2>
          <label className="setting-row">
            <span>Default export format</span>
            <select defaultValue="markdown">
              <option value="markdown">Markdown</option>
              <option value="pdf">PDF</option>
            </select>
          </label>
          <label className="setting-row toggle">
            <span>PDF export enabled</span>
            <input type="checkbox" checked={Boolean(backend?.pdfExportAvailable)} readOnly />
          </label>
          <p className="muted">
            {backend?.pdfExportAvailable
              ? "PDF export is available."
              : "PDF export requires Pandoc on the backend server. Markdown export is available."}
          </p>
        </section>

        <section className="settings-card">
          <h2>Advanced</h2>
          <div className="settings-meta">
            <span>Chunk size: {String(backend?.chunkSize ?? "n/a")}</span>
            <span>Chunk overlap: {String(backend?.chunkOverlap ?? "n/a")}</span>
            <span>SearxNG: {String(backend?.searxngUrl ?? "n/a")}</span>
            <span>Qdrant: {String(backend?.qdrantUrl ?? "n/a")}</span>
          </div>
          <button className="danger-button" type="button">
            Reset settings
          </button>
        </section>
      </div>
    </section>
  );
}
