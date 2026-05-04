import { apiRequest } from "./client";
import type { Source } from "../types";

export const getSources = (workbaseId: string) => apiRequest<Source[]>(`/api/workbases/${workbaseId}/sources`);

export const uploadSource = (
  workbaseId: string,
  file: File,
  metadata: { title: string; notes: string; tags: string },
  onProgress?: (percent: number) => void
) => {
  const form = new FormData();
  form.append("file", file);
  form.append("title", metadata.title);
  form.append("notes", metadata.notes);
  form.append("tags", metadata.tags);
  return new Promise<Record<string, unknown>>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `/api/workbases/${workbaseId}/sources/upload`);
    request.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) return;
      onProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(JSON.parse(request.responseText));
      } else {
        reject(new Error(request.responseText || "Upload failed"));
      }
    };
    request.onerror = () => reject(new Error("Upload failed"));
    request.send(form);
  });
};

export const addUrlSource = (workbaseId: string, payload: { url: string; title: string; notes?: string; tags: string[] }) =>
  apiRequest<Record<string, unknown>>(`/api/workbases/${workbaseId}/sources/url`, {
    method: "POST",
    body: JSON.stringify(payload)
  });

export const deleteSource = (workbaseId: string, sourceId: string) =>
  apiRequest<void>(`/api/sources/${sourceId}?workbase_id=${encodeURIComponent(workbaseId)}`, { method: "DELETE" });

export const reingestSource = (workbaseId: string, sourceId: string) =>
  apiRequest<Record<string, unknown>>(`/api/sources/${sourceId}/reingest?workbase_id=${encodeURIComponent(workbaseId)}`, {
    method: "POST"
  });

export const getSourceDetail = (workbaseId: string, sourceId: string) =>
  apiRequest<Source & { chunks: Record<string, unknown>[] }>(`/api/sources/${sourceId}?workbase_id=${encodeURIComponent(workbaseId)}`);
