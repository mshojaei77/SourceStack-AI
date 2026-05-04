import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileSearch, Link, MoreHorizontal, Trash2, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { addUrlSource, deleteSource, getSources, reingestSource, uploadSource } from "../api/sources";
import { useAppStore } from "../store/useAppStore";
import type { Source } from "../types";

const tabs = ["All", "Curated", "Trusted Web", "Web", "PDFs", "URLs", "Markdown"];

export function SourcesPage() {
  const navigate = useNavigate();
  const workbaseId = useAppStore((state) => state.activeWorkbaseId);
  const focusSource = useAppStore((state) => state.focusSource);
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("All");
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const sourcesQuery = useQuery({
    queryKey: ["sources", workbaseId],
    queryFn: () => getSources(workbaseId!),
    enabled: Boolean(workbaseId)
  });
  const sources = sourcesQuery.data ?? [];
  const deleteMutation = useMutation({
    mutationFn: (sourceId: string) => deleteSource(workbaseId!, sourceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources", workbaseId] })
  });
  const reingestMutation = useMutation({
    mutationFn: (sourceId: string) => reingestSource(workbaseId!, sourceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources", workbaseId] })
  });

  const filtered = useMemo(() => {
    return sources.filter((source) => {
      const matchesSearch =
        !search ||
        source.title.toLowerCase().includes(search.toLowerCase()) ||
        source.tags.some((tag) => tag.toLowerCase().includes(search.toLowerCase()));
      const matchesTab =
        activeTab === "All" ||
        (activeTab === "Curated" && source.trustLevel === "curated") ||
        (activeTab === "Trusted Web" && source.trustLevel === "trusted_domain") ||
        (activeTab === "Web" && source.trustLevel === "general_web") ||
        (activeTab === "PDFs" && source.type === "pdf") ||
        (activeTab === "URLs" && source.type === "url") ||
        (activeTab === "Markdown" && ["md", "markdown"].includes(source.type));
      return matchesSearch && matchesTab;
    });
  }, [activeTab, search, sources]);

  if (!workbaseId) {
    return <div className="page-panel">Create a Workbase before adding sources.</div>;
  }

  if (sourcesQuery.isLoading) {
    return <div className="page-panel">Loading sources...</div>;
  }

  if (sourcesQuery.isError) {
    return <div className="error-state">Could not load sources. Please retry.</div>;
  }

  return (
    <section className="page-stack">
      <div className="page-title-row">
        <div>
          <h1>Sources</h1>
          <p>Manage PDFs, Markdown files, text files, direct URLs, and trusted web material.</p>
        </div>
        <button className="primary-button" onClick={() => setModalOpen(true)}>
          <Upload size={16} />
          Add Source
        </button>
      </div>

      <div className="filter-bar">
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search sources..." />
        <select aria-label="Sort sources">
          <option>Newest first</option>
          <option>Title A-Z</option>
          <option>Most chunks</option>
        </select>
      </div>

      <div className="tab-row">
        {tabs.map((tab) => (
          <button key={tab} className={tab === activeTab ? "active" : ""} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      <div className="table-shell">
        <table className="data-table">
          <thead>
            <tr>
              <th>Badge</th>
              <th>Title</th>
              <th>Type</th>
              <th>Tags</th>
              <th>Added</th>
              <th>Chunks</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((source) => (
              <tr key={source.id}>
                <td>
                  <SourceBadge source={source} />
                </td>
                <td>
                  <strong>{source.title}</strong>
                  <small>{source.url || source.fileName}</small>
                </td>
                <td>{source.type.toUpperCase()}</td>
                <td>{source.tags.length ? source.tags.join(", ") : "No tags"}</td>
                <td>{source.createdAt?.slice(0, 10) || "Unknown"}</td>
                <td>{source.chunkCount}</td>
                <td>
                  <div className="table-actions">
                    <button
                      onClick={() => {
                        focusSource(source.id, source.title);
                        navigate("/chat");
                      }}
                    >
                      <FileSearch size={15} />
                      Ask
                    </button>
                    <button onClick={() => reingestMutation.mutate(source.id)}>
                      <MoreHorizontal size={15} />
                      Re-ingest
                    </button>
                    <button onClick={() => deleteMutation.mutate(source.id)}>
                      <Trash2 size={15} />
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 ? <div className="table-empty">No sources match your current settings. Add PDFs, URLs, Markdown, or text files to start.</div> : null}
      </div>

      {modalOpen ? <AddSourceModal workbaseId={workbaseId} onClose={() => setModalOpen(false)} /> : null}
    </section>
  );
}

function AddSourceModal({ workbaseId, onClose }: { workbaseId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<"file" | "url">("file");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState(0);
  const uploadMutation = useMutation({
    mutationFn: () => {
      if (mode === "file" && file) return uploadSource(workbaseId, file, { title, tags, notes }, setProgress);
      return addUrlSource(workbaseId, { url, title, notes, tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean) });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources", workbaseId] });
      setStatus("Source added successfully.");
      setTimeout(onClose, 650);
    },
    onError: () => setStatus("Could not read this source. Try uploading the page as a PDF or text file.")
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setProgress(0);
    setStatus(mode === "file" ? "Uploading file..." : "Reading URL...");
    uploadMutation.mutate();
  }

  return (
    <div className="modal-backdrop">
      <form className="modal" onSubmit={submit}>
        <div className="modal-head">
          <h2>Add Source</h2>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="source-mode-grid">
          <button type="button" className={mode === "file" ? "active" : ""} onClick={() => setMode("file")}>
            <Upload size={17} />
            Upload File
            <small>PDF, Markdown, or text</small>
          </button>
          <button type="button" className={mode === "url" ? "active" : ""} onClick={() => setMode("url")}>
            <Link size={17} />
            Paste URL
            <small>Documentation or article</small>
          </button>
        </div>
        {mode === "file" ? (
          <label className="file-drop">
            <input type="file" accept=".pdf,.md,.markdown,.txt" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
            <span>{file ? file.name : "Drag and drop file here, or browse files"}</span>
          </label>
        ) : (
          <input value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://example.com/docs" />
        )}
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Optional title" />
        <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="Tags: RAG, Chapter 1" />
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Notes" rows={3} />
        {status ? <p className="form-status">{status}</p> : null}
        {mode === "file" && uploadMutation.isPending ? (
          <div className="upload-progress">
            <div className="upload-progress-bar" style={{ width: `${Math.max(progress, 8)}%` }} />
          </div>
        ) : null}
        <button className="primary-button wide" disabled={uploadMutation.isPending || (mode === "file" ? !file : !url)}>
          Add Source
        </button>
      </form>
    </div>
  );
}

function SourceBadge({ source }: { source: Source }) {
  const label = source.trustLevel === "curated" ? "Curated" : source.trustLevel === "trusted_domain" ? "Trusted Web" : "Web";
  const tone = source.trustLevel === "curated" ? "curated" : source.trustLevel === "trusted_domain" ? "trusted" : "web";
  return <span className={`source-badge ${tone}`}>{label}</span>;
}
