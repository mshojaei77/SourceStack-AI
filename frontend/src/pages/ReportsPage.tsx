import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FilePlus2, Save } from "lucide-react";
import { createReport, exportMarkdown, exportPdf, getReports, updateReport } from "../api/reports";
import { useAppStore } from "../store/useAppStore";
import type { Report } from "../types";

const reportTabs = ["All", "Articles", "Book Chapters", "Summaries", "Study Notes"];

export function ReportsPage() {
  const workbaseId = useAppStore((state) => state.activeWorkbaseId);
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("All");
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [newTitle, setNewTitle] = useState("");
  const [newType, setNewType] = useState("Article");
  const [newGoal, setNewGoal] = useState("");
  const reportsQuery = useQuery({
    queryKey: ["reports", workbaseId],
    queryFn: () => getReports(workbaseId!),
    enabled: Boolean(workbaseId)
  });
  const reports = reportsQuery.data ?? [];
  const createMutation = useMutation({
    mutationFn: () => {
      const generate = newType === "Book Chapter" ? "chapter" : newType === "Study Notes" ? "glossary" : "article";
      return createReport(workbaseId!, {
        title: newTitle || `Report ${reports.length + 1}`,
        type: newType,
        generate,
        topic: newTitle || "Research summary",
        goal: newGoal,
        retrieval_mode: "curated_trusted"
      });
    },
    onSuccess: (report) => {
      setSelectedReportId(report.id);
      setNewTitle("");
      setNewGoal("");
      queryClient.invalidateQueries({ queryKey: ["reports", workbaseId] });
    }
  });
  const saveMutation = useMutation({
    mutationFn: ({ reportId, content }: { reportId: string; content: string }) =>
      updateReport(workbaseId!, reportId, { content }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports", workbaseId] })
  });

  const filtered = useMemo(() => {
    return reports.filter((report) => {
      if (activeTab === "All") return true;
      if (activeTab === "Articles") return report.type.toLowerCase().includes("article");
      if (activeTab === "Book Chapters") return report.type.toLowerCase().includes("chapter");
      if (activeTab === "Summaries") return report.type.toLowerCase().includes("summary");
      if (activeTab === "Study Notes") return report.type.toLowerCase().includes("study");
      return true;
    });
  }, [activeTab, reports]);

  const selectedReport = filtered.find((report) => report.id === selectedReportId) ?? filtered[0] ?? null;

  if (!workbaseId) {
    return <div className="page-panel">Create a Workbase before creating reports.</div>;
  }

  if (reportsQuery.isLoading) {
    return <div className="page-panel">Loading reports...</div>;
  }

  if (reportsQuery.isError) {
    return <div className="error-state">Could not load reports. Please retry.</div>;
  }

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  return (
    <section className="page-stack">
      <div className="page-title-row">
        <div>
          <h1>Reports</h1>
          <p>Generate, edit, and export saved articles, chapters, summaries, and study notes.</p>
        </div>
      </div>

      <form className="create-strip" onSubmit={submitCreate}>
        <div className="strip-field">
          <label>Title</label>
          <input value={newTitle} onChange={(event) => setNewTitle(event.target.value)} placeholder="Intro to RAG" />
        </div>
        <div className="strip-field">
          <label>Type</label>
          <select value={newType} onChange={(event) => setNewType(event.target.value)}>
            <option>Article</option>
            <option>Book Chapter</option>
            <option>Summary</option>
            <option>Study Notes</option>
          </select>
        </div>
        <div className="strip-field">
          <label>Goal</label>
          <input value={newGoal} onChange={(event) => setNewGoal(event.target.value)} placeholder="Beginner-friendly overview with citations" />
        </div>
        <button className="primary-button" disabled={createMutation.isPending}>
          <FilePlus2 size={16} />
          New Report
        </button>
      </form>

      <div className="tab-row">
        {reportTabs.map((tab) => (
          <button key={tab} className={tab === activeTab ? "active" : ""} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </div>

      <div className="reports-layout">
        <div className="table-shell">
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Type</th>
                <th>Workbase</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((report) => (
                <tr key={report.id} className={selectedReport?.id === report.id ? "selected-row" : ""} onClick={() => setSelectedReportId(report.id)}>
                  <td>{report.title}</td>
                  <td>{report.type}</td>
                  <td>{report.workbaseName}</td>
                  <td>{(report.updatedAt || report.createdAt || "").slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 ? <div className="table-empty">No reports yet. Save a chat answer or generate one from your sources.</div> : null}
        </div>

        {selectedReport ? (
          <ReportEditor
            key={selectedReport.id}
            report={selectedReport}
            onSave={(content) => saveMutation.mutate({ reportId: selectedReport.id, content })}
          />
        ) : (
          <div className="report-editor">
            <h2>Report Editor</h2>
            <p>Select a report to edit and export.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function ReportEditor({ report, onSave }: { report: Report; onSave: (content: string) => void }) {
  const [content, setContent] = useState(report.content);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      onSave(content);
    } finally {
      setTimeout(() => setSaving(false), 300);
    }
  }

  return (
    <div className="report-editor">
      <div className="editor-head">
        <div>
          <h2>{report.title}</h2>
          <p>
            {report.type} · Sources used: {report.sources.length}
          </p>
        </div>
        <div className="editor-actions">
          <button className="secondary-button" onClick={save}>
            <Save size={16} />
            {saving ? "Saving..." : "Save"}
          </button>
          <button
            className="secondary-button"
            onClick={() =>
              exportMarkdown({
                title: report.title,
                content,
                sources: report.sources,
                workbase_name: report.workbaseName
              })
            }
          >
            <Download size={16} />
            Markdown
          </button>
          <button
            className="secondary-button"
            onClick={() =>
              exportPdf({
                title: report.title,
                content,
                sources: report.sources,
                workbase_name: report.workbaseName
              })
            }
          >
            <Download size={16} />
            PDF
          </button>
        </div>
      </div>
      <textarea className="report-textarea" value={content} onChange={(event) => setContent(event.target.value)} />
    </div>
  );
}
