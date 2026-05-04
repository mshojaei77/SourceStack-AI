import type { ReactNode } from "react";

export function EmptyState({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="empty-state">
      <h1>{title}</h1>
      <p>{children}</p>
      {actions ? <div className="empty-actions">{actions}</div> : null}
    </div>
  );
}
