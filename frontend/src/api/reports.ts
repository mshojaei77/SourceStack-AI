import { apiRequest, downloadBlob } from "./client";
import type { Report } from "../types";

export const getReports = (workbaseId: string) => apiRequest<Report[]>(`/api/workbases/${workbaseId}/reports`);

export const createReport = (
  workbaseId: string,
  payload: {
    title: string;
    type: string;
    content?: string;
    sources?: Record<string, unknown>[];
    generate?: "none" | "article" | "chapter" | "glossary";
    topic?: string;
    goal?: string;
    retrieval_mode?: string;
  }
) =>
  apiRequest<Report>(`/api/workbases/${workbaseId}/reports`, {
    method: "POST",
    body: JSON.stringify(payload)
  });

export const updateReport = (workbaseId: string, reportId: string, payload: Partial<Report>) =>
  apiRequest<Report>(`/api/reports/${reportId}`, {
    method: "PATCH",
    body: JSON.stringify({ ...payload, workbase_id: workbaseId })
  });

export const exportMarkdown = (payload: { title: string; content: string; sources: Record<string, unknown>[]; workbase_name: string }) =>
  downloadBlob("/api/exports/markdown", payload, `${payload.title}.md`);

export const exportPdf = (payload: { title: string; content: string; sources: Record<string, unknown>[]; workbase_name: string }) =>
  downloadBlob("/api/exports/pdf", payload, `${payload.title}.pdf`);
