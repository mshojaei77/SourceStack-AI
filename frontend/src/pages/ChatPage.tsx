import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePlus2, MessageSquareText, PenLine, Sparkles, X } from "lucide-react";
import { getChat, streamChatMessage } from "../api/chat";
import { createReport, exportMarkdown, exportPdf } from "../api/reports";
import { getSourceDetail, getSources } from "../api/sources";
import { ChatInput } from "../components/chat/ChatInput";
import { ChatMessage } from "../components/chat/ChatMessage";
import { EmptyState } from "../components/common/EmptyState";
import { useAppStore } from "../store/useAppStore";
import type { ChatMessage as ChatMessageType, Citation, SourceDetail } from "../types";

export function ChatPage() {
  const queryClient = useQueryClient();
  const workbaseId = useAppStore((state) => state.activeWorkbaseId);
  const settings = useAppStore((state) => state.settings);
  const selectedSourceId = useAppStore((state) => state.selectedSourceId);
  const openControlTab = useAppStore((state) => state.openControlTab);
  const setSelectedAnswer = useAppStore((state) => state.setSelectedAnswer);
  const sourceDetail = useAppStore((state) => state.sourceDetail);
  const setSourceDetail = useAppStore((state) => state.setSourceDetail);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loadingSourceId, setLoadingSourceId] = useState<string | null>(null);

  const chatQuery = useQuery({
    queryKey: ["chat", workbaseId],
    queryFn: () => getChat(workbaseId!),
    enabled: Boolean(workbaseId)
  });
  const sourcesQuery = useQuery({
    queryKey: ["sources", workbaseId],
    queryFn: () => getSources(workbaseId!),
    enabled: Boolean(workbaseId)
  });
  const sources = sourcesQuery.data ?? [];
  const reportMutation = useMutation({
    mutationFn: (payload: { title: string; content: string; sources: Record<string, unknown>[]; type: string }) =>
      createReport(workbaseId!, {
        title: payload.title,
        type: payload.type,
        content: payload.content,
        sources: payload.sources,
        generate: "none"
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports", workbaseId] })
  });

  useEffect(() => {
    const next = chatQuery.data?.messages ?? [];
    setMessages(next);
    const lastAssistant = [...next].reverse().find((message) => message.role === "assistant");
    if (!selectedMessageId && lastAssistant) {
      setSelectedMessageId(lastAssistant.id);
    }
  }, [chatQuery.data, selectedMessageId]);

  const selectedAssistant = useMemo(
    () => messages.find((message) => message.id === selectedMessageId && message.role === "assistant") ?? null,
    [messages, selectedMessageId]
  );

  useEffect(() => {
    if (!selectedAssistant || !workbaseId) {
      setSelectedAnswer(null);
      return;
    }
    setSelectedAnswer({
      title: `Answer ${new Date(selectedAssistant.createdAt || Date.now()).toISOString().slice(0, 19).replace("T", " ")}`,
      content: selectedAssistant.content,
      sources: (selectedAssistant.sources ?? []) as Record<string, unknown>[],
      workbaseName: chatQuery.data?.title || "SourceStack AI",
      messageId: selectedAssistant.id
    });
  }, [selectedAssistant, setSelectedAnswer, workbaseId, chatQuery.data]);

  const readyText = useMemo(() => {
    if (sources.length === 0) return "No sources yet. Add PDFs, Markdown files, text files, or URLs to start.";
    return `Ready to answer from ${sources.length} sources. Current mode: ${settings.retrievalMode === "curated_only" ? "Curated Only" : "Curated + Trusted Web"}.`;
  }, [settings.retrievalMode, sources.length]);

  async function send(content: string) {
    if (!workbaseId) return;
    setError("");
    const userMessage: ChatMessageType = {
      id: `local_user_${Date.now()}`,
      chatId: `${workbaseId}:default`,
      role: "user",
      content,
      createdAt: new Date().toISOString()
    };
    const assistantMessage: ChatMessageType = {
      id: `local_assistant_${Date.now()}`,
      chatId: `${workbaseId}:default`,
      role: "assistant",
      content: "",
      citations: [],
      sources: [],
      createdAt: new Date().toISOString()
    };
    setMessages((current) => [...current, userMessage, assistantMessage]);
    setSelectedMessageId(assistantMessage.id);
    setBusy(true);
    setStatus("Finding relevant sources...");
    await streamChatMessage(workbaseId, content, settings, selectedSourceId, {
      onStatus: setStatus,
      onToken: (text) =>
        setMessages((current) =>
          current.map((message) => (message.id === assistantMessage.id ? { ...message, content: message.content + text } : message))
        ),
      onCitations: (citations: Citation[], sourcesList) =>
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantMessage.id ? { ...message, citations, sources: sourcesList } : message
          )
        ),
      onDone: () => {
        setBusy(false);
        setStatus("");
        queryClient.invalidateQueries({ queryKey: ["chat", workbaseId] });
        queryClient.invalidateQueries({ queryKey: ["workbases"] });
        queryClient.invalidateQueries({ queryKey: ["sources", workbaseId] });
      },
      onError: (message) => {
        setBusy(false);
        setStatus("");
        setError(message);
      }
    });
  }

  async function openCitation(citation: Citation) {
    if (!workbaseId || !citation.sourceId) return;
    setLoadingSourceId(citation.sourceId);
    try {
      const detail = (await getSourceDetail(workbaseId, citation.sourceId)) as SourceDetail;
      setSourceDetail(detail);
      openControlTab("Sources");
    } catch {
      setError("Could not load source details for this citation.");
    } finally {
      setLoadingSourceId(null);
    }
  }

  if (!workbaseId) {
    return (
      <EmptyState title="Welcome to SourceStack AI">
        Create your first Workbase to start collecting sources and asking questions.
      </EmptyState>
    );
  }

  if (chatQuery.isLoading || sourcesQuery.isLoading) {
    return (
      <section className="chat-page">
        <div className="chat-scroll">
          <div className="loading-state">Loading Workbase chat and sources...</div>
        </div>
      </section>
    );
  }

  if (chatQuery.isError || sourcesQuery.isError) {
    return (
      <section className="chat-page">
        <div className="chat-scroll">
          <div className="error-state">Something went wrong while loading the chat. Please retry.</div>
        </div>
      </section>
    );
  }

  return (
    <section className="chat-page">
      <div className="chat-scroll">
        {messages.length === 0 ? (
          <EmptyState
            title="SourceStack AI"
            actions={
              <>
                <button className="secondary-button" onClick={() => openControlTab("Sources")}>
                  <FilePlus2 size={16} />
                  Add Sources
                </button>
                <button className="secondary-button">
                  <MessageSquareText size={16} />
                  Ask a Question
                </button>
                <button className="secondary-button">
                  <PenLine size={16} />
                  Write Article
                </button>
                <button className="secondary-button">
                  <Sparkles size={16} />
                  Draft Book Chapter
                </button>
              </>
            }
          >
            Ask questions, write articles, or create cited chapters from your trusted sources.
            <span className="ready-line">{readyText}</span>
          </EmptyState>
        ) : (
          messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              selected={selectedMessageId === message.id}
              onSelect={() => {
                if (message.role === "assistant") setSelectedMessageId(message.id);
              }}
              onSaveAsReport={() => {
                if (message.role !== "assistant") return;
                reportMutation.mutate({
                  title: `Chat Answer ${new Date().toISOString().slice(0, 10)}`,
                  type: "Research Summary",
                  content: message.content,
                  sources: (message.sources ?? []) as Record<string, unknown>[]
                });
              }}
              onExportMarkdown={() => {
                if (message.role !== "assistant") return;
                exportMarkdown({
                  title: `chat-answer-${Date.now()}`,
                  content: message.content,
                  sources: (message.sources ?? []) as Record<string, unknown>[],
                  workbase_name: chatQuery.data?.title || "SourceStack AI"
                });
              }}
              onCitationClick={openCitation}
            />
          ))
        )}
        {status ? <div className="stream-status">{status}</div> : null}
        {error ? <div className="error-state compact-error">{error}</div> : null}
        {loadingSourceId ? <div className="loading-state compact-loading">Loading source details...</div> : null}
      </div>
      <ChatInput disabled={busy} onSend={send} />
      {sourceDetail ? <SourceDetailModal detail={sourceDetail} onClose={() => setSourceDetail(null)} /> : null}
    </section>
  );
}

function SourceDetailModal({ detail, onClose }: { detail: SourceDetail; onClose: () => void }) {
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-head">
          <h2>Source Details</h2>
          <button type="button" onClick={onClose} aria-label="Close source details">
            <X size={16} />
          </button>
        </div>
        <div className="details-grid">
          <p>
            <strong>Title:</strong> {detail.title}
          </p>
          <p>
            <strong>Type:</strong> {detail.type.toUpperCase()}
          </p>
          <p>
            <strong>Trust Level:</strong> {detail.trustLevel}
          </p>
          <p>
            <strong>Tags:</strong> {detail.tags.join(", ") || "None"}
          </p>
          <p>
            <strong>Chunks:</strong> {detail.chunkCount}
          </p>
          {detail.url ? (
            <p>
              <strong>URL:</strong>{" "}
              <a href={detail.url} target="_blank" rel="noreferrer">
                Open source
              </a>
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
