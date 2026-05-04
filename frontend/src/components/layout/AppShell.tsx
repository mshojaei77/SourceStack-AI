import type { PropsWithChildren } from "react";
import type { Workbase } from "../../types";
import { LeftSidebar } from "./LeftSidebar";
import { RightControlPanel } from "./RightControlPanel";
import { TopBar } from "./TopBar";

type Props = PropsWithChildren<{
  workbases: Workbase[];
}>;

export function AppShell({ workbases, children }: Props) {
  return (
    <div className="app-shell">
      <LeftSidebar workbases={workbases} />
      <div className="app-main">
        <TopBar workbases={workbases} />
        <main className="workspace">{children}</main>
      </div>
      <RightControlPanel />
    </div>
  );
}
