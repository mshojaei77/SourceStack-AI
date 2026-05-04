import { FormEvent, KeyboardEvent, useState } from "react";
import { ArrowUp, Paperclip } from "lucide-react";
import { useAppStore } from "../../store/useAppStore";

export function ChatInput({ disabled, onSend }: { disabled: boolean; onSend: (value: string) => void }) {
  const [value, setValue] = useState("");
  const settings = useAppStore((state) => state.settings);
  const openControlTab = useAppStore((state) => state.openControlTab);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className="chat-composer" onSubmit={submit}>
      <textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Ask SourceStack AI..."
        rows={3}
        disabled={disabled}
      />
      <div className="composer-footer">
        <div className="composer-chips">
          <button type="button" className="chip" onClick={() => openControlTab("Sources")}>
            <Paperclip size={14} />
            Add Source
          </button>
          <button type="button" className="chip chip-blue" onClick={() => openControlTab("Answer")}>
            {settings.answerStyle}
          </button>
          <button type="button" className="chip" onClick={() => openControlTab("Sources")}>
            {settings.retrievalMode === "curated_only" ? "Curated Only" : "Source Mode"}
          </button>
          <button type="button" className="chip" onClick={() => openControlTab("Citations")}>
            Citations {settings.citationsEnabled ? "On" : "Off"}
          </button>
          <button type="button" className="chip" onClick={() => openControlTab("Models")}>
            {settings.budgetMode ? "Budget Mode" : "Standard Cost"}
          </button>
        </div>
        <button className="send-button" type="submit" disabled={disabled || !value.trim()} aria-label="Send message">
          <ArrowUp size={18} />
        </button>
      </div>
    </form>
  );
}
