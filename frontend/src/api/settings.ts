import { apiRequest } from "./client";

export const getSettings = () => apiRequest<Record<string, unknown>>("/api/settings");
export const getModelPresets = () => apiRequest<Record<string, string>[]>("/api/model-presets");
