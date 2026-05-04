import { Copy, FileDown, RefreshCcw, Save, ShieldCheck } from "lucide-react";
import type { ChatMessage as ChatMessageType, Citation } from "../../types";

type Props = {
  message: ChatMessageType;
  selected?: boolean;
  onSelect?: () => void;
  onSaveAsReport?: () => void;
  onExportMarkdown?: () => void;
  onCitationClick?: (citation: Citation) => void;
};

export function ChatMessage({ message, selected, onSelect, onSaveAsReport, onExportMarkdown, onCitationClick }: Props) {
  const isUser = message.role === "user";
  return (
    <article className={`chat-message ${isUser ? "user" : "assistant"} ${selected ? "selected-message" : ""}`} onClick={onSelect}>
      <div className="message-head">
        <strong>{isUser ? "You" : "SourceStack AI"}</strong>
        <div className="message-actions">
          <button
            aria-label="Copy"
            onClick={(event) => {
              event.stopPropagation();
              navigator.clipboard.writeText(message.content || "");
            }}
          >
            <Copy size={15} />
          </button>
          {!isUser ? (
            <>
              <button aria-label="Regenerate" onClick={(event) => event.stopPropagation()}>
                <RefreshCcw size={15} />
              </button>
              <button
                aria-label="Save as report"
                onClick={(event) => {
                  event.stopPropagation();
                  onSaveAsReport?.();
                }}
              >
                <Save size={15} />
              </button>
              <button
                aria-label="Export Markdown"
                onClick={(event) => {
                  event.stopPropagation();
                  onExportMarkdown?.();
                }}
              >
                <FileDown size={15} />
              </button>
              <button aria-label="Check Citations" onClick={(event) => event.stopPropagation()}>
                <ShieldCheck size={15} />
              </button>
            </>
          ) : null}
        </div>
      </div>
      <div className="message-content">{message.content || <span className="stream-caret">Writing answer...</span>}</div>
      {!isUser && message.citations?.length ? (
        <div className="references">
          <strong>References</strong>
          {message.citations.map((citation) => (
            <a
              key={citation.id}
              href={citation.url || "#"}
              target="_blank"
              rel="noreferrer"
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onCitationClick?.(citation);
              }}
            >
              [{citation.number}] {badgeLabel(citation.trustLevel)} {citation.title}
            </a>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function badgeLabel(value: string) {
  if (value === "curated") return "[Curated]";
  if (value === "trusted_domain") return "[Trusted Web]";
  return "[Web]";
}
