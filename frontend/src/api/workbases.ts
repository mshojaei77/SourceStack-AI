import { apiRequest } from "./client";
import type { Workbase } from "../types";

export const getWorkbases = () => apiRequest<Workbase[]>("/api/workbases");

export const createWorkbase = (payload: { name: string; description?: string }) =>
  apiRequest<Workbase>("/api/workbases", {
    method: "POST",
    body: JSON.stringify(payload)
  });

export const patchWorkbase = (id: string, payload: Partial<Pick<Workbase, "name" | "description">>) =>
  apiRequest<Workbase>(`/api/workbases/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });

export const deleteWorkbase = (id: string) =>
  apiRequest<void>(`/api/workbases/${id}`, {
    method: "DELETE"
  });
