import { BookOpen, FileText, MessageSquareText, Plus, Settings, SquarePen, Upload } from "lucide-react";
import { NavLink } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Workbase } from "../../types";
import { createWorkbase } from "../../api/workbases";
import { useAppStore } from "../../store/useAppStore";

export function LeftSidebar({ workbases }: { workbases: Workbase[] }) {
  const queryClient = useQueryClient();
  const activeWorkbaseId = useAppStore((state) => state.activeWorkbaseId);
  const setActiveWorkbaseId = useAppStore((state) => state.setActiveWorkbaseId);
  const openControlTab = useAppStore((state) => state.openControlTab);
  const mutation = useMutation({
    mutationFn: createWorkbase,
    onSuccess: (workbase) => {
      setActiveWorkbaseId(workbase.id);
      queryClient.invalidateQueries({ queryKey: ["workbases"] });
    }
  });

  return (
    <aside className="left-sidebar">
      <div className="brand-lockup">
        <div className="brand-mark">SS</div>
        <div>
          <strong>SourceStack AI</strong>
          <span>Research writing</span>
        </div>
      </div>

      <div className="sidebar-actions">
        <button className="primary-button" onClick={() => openControlTab("Sources")}>
          <Plus size={16} />
          New Chat
        </button>
        <button
          className="secondary-button"
          onClick={() => mutation.mutate({ name: `Workbase ${workbases.length + 1}`, description: "" })}
        >
          <SquarePen size={16} />
          New Workbase
        </button>
      </div>

      <section className="sidebar-section">
        <h2>Workbases</h2>
        <div className="workbase-list">
          {workbases.map((workbase) => (
            <button
              key={workbase.id}
              className={`workbase-row ${workbase.id === activeWorkbaseId ? "active" : ""}`}
              onClick={() => setActiveWorkbaseId(workbase.id)}
            >
              <BookOpen size={16} />
              <span>
                <strong>{workbase.name}</strong>
                <small>
                  {workbase.chunkCount ?? 0} chunks · {workbase.reportCount ?? 0} reports
                </small>
              </span>
            </button>
          ))}
          {workbases.length === 0 ? <p className="muted compact">Create a Workbase to start collecting sources.</p> : null}
        </div>
      </section>

      <section className="sidebar-section">
        <h2>Recent Chats</h2>
        <p className="recent-chat">What is RAG?</p>
        <p className="recent-chat">Explain vector search</p>
        <p className="recent-chat">Draft chapter 2</p>
      </section>

      <nav className="library-nav">
        <NavLink to="/chat">
          <MessageSquareText size={17} />
          Chat
        </NavLink>
        <NavLink to="/sources">
          <Upload size={17} />
          Sources
        </NavLink>
        <NavLink to="/reports">
          <FileText size={17} />
          Reports
        </NavLink>
        <NavLink to="/settings">
          <Settings size={17} />
          Settings
        </NavLink>
      </nav>
    </aside>
  );
}
