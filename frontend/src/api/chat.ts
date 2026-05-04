import { apiRequest } from "./client";
import type { Chat, ChatSettings, Citation } from "../types";

export const getChat = (workbaseId: string) => apiRequest<Chat>(`/api/chats/${workbaseId}:default`);

type StreamCallbacks = {
  onStatus: (message: string) => void;
  onToken: (text: string) => void;
  onCitations: (citations: Citation[], sources: Record<string, unknown>[]) => void;
  onDone: () => void;
  onError: (message: string) => void;
};

export async function streamChatMessage(
  workbaseId: string,
  content: string,
  settings: ChatSettings,
  documentId: string | null,
  callbacks: StreamCallbacks
) {
  const response = await fetch(`/api/chats/${workbaseId}:default/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content,
      retrieval_mode: settings.retrievalMode,
      answer_style: settings.answerStyle,
      technical_mode: settings.technicalMode,
      advanced_mode: settings.advancedMode,
      document_id: documentId
    })
  });
  if (!response.ok || !response.body) {
    callbacks.onError("Something went wrong while generating the answer.");
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const rawEvent of events) {
      const parsed = parseSse(rawEvent);
      if (!parsed) continue;
      if (parsed.event === "status") callbacks.onStatus(parsed.data.message);
      if (parsed.event === "token") callbacks.onToken(parsed.data.text);
      if (parsed.event === "citations") callbacks.onCitations(parsed.data.citations ?? [], parsed.data.sources ?? []);
      if (parsed.event === "done") callbacks.onDone();
      if (parsed.event === "error") callbacks.onError(parsed.data.message);
    }
  }
}

function parseSse(raw: string): { event: string; data: Record<string, any> } | null {
  const event = raw.match(/^event:\s*(.+)$/m)?.[1];
  const data = raw.match(/^data:\s*(.+)$/m)?.[1];
  if (!event || !data) return null;
  return { event, data: JSON.parse(data) };
}
