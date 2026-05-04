export type Workbase = {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
  sourceCount: number;
  chatCount: number;
  chunkCount?: number;
  reportCount?: number;
};

export type TrustLevel = "curated" | "trusted_domain" | "general_web";
export type SourceOrigin = "manual_curation" | "agent_web" | "direct_url";

export type Citation = {
  id: string;
  number: number;
  sourceId: string;
  title: string;
  url?: string;
  trustLevel: TrustLevel;
  sourceOrigin: SourceOrigin;
  excerpt: string;
  datasetId?: string;
  chunkIndex?: number;
  score?: number;
};

export type Source = {
  id: string;
  workbaseId: string;
  title: string;
  type: "pdf" | "markdown" | "text" | "url" | "web" | string;
  trustLevel: TrustLevel;
  sourceOrigin: SourceOrigin;
  tags: string[];
  url?: string;
  fileName?: string;
  chunkCount: number;
  createdAt: string;
  updatedAt: string;
  datasetIds?: string[];
  parserName?: string;
  author?: string;
  year?: string;
  accessedDate?: string;
};

export type SourceDetail = Source & {
  chunks?: {
    text?: string;
    metadata?: Record<string, unknown>;
  }[];
};

export type ChatSettings = {
  answerStyle: "Simple" | "Technical" | "Study Notes" | "Article Draft" | "Book Chapter Draft";
  retrievalMode: "all" | "curated_only" | "curated_trusted";
  citationStyle: "numbered" | "author_year" | "footnotes";
  citationsEnabled: boolean;
  technicalMode: boolean;
  budgetMode: boolean;
  modelPreset: "cheapest" | "balanced" | "best_quality" | "custom";
  advancedMode: boolean;
  answerLength: "Short" | "Medium" | "Long";
  answerTone: "Clear" | "Academic" | "Friendly" | "Professional";
};

export type ChatMessage = {
  id: string;
  chatId: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  sources?: Record<string, unknown>[];
  createdAt: string;
  settingsSnapshot?: ChatSettings;
};

export type SelectedAnswer = {
  title: string;
  content: string;
  sources: Record<string, unknown>[];
  workbaseName: string;
  messageId: string;
};

export type Chat = {
  id: string;
  workbaseId: string;
  title: string;
  messages: ChatMessage[];
};

export type Report = {
  id: string;
  workbaseId: string;
  title: string;
  type: string;
  content: string;
  sources: Record<string, unknown>[];
  createdAt: string;
  updatedAt: string;
  workbaseName: string;
};

export type ControlTab = "Sources" | "Answer" | "Citations" | "Models" | "Export";
