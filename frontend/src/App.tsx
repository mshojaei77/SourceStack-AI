import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getWorkbases } from "./api/workbases";
import { AppShell } from "./components/layout/AppShell";
import { ChatPage } from "./pages/ChatPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SourcesPage } from "./pages/SourcesPage";
import { useAppStore } from "./store/useAppStore";

export default function App() {
  const { data: workbases = [] } = useQuery({ queryKey: ["workbases"], queryFn: getWorkbases });
  const activeWorkbaseId = useAppStore((state) => state.activeWorkbaseId);
  const setActiveWorkbaseId = useAppStore((state) => state.setActiveWorkbaseId);

  useEffect(() => {
    if (!activeWorkbaseId && workbases.length > 0) {
      setActiveWorkbaseId(workbases[0].id);
    }
    if (activeWorkbaseId && workbases.length > 0 && !workbases.some((item) => item.id === activeWorkbaseId)) {
      setActiveWorkbaseId(workbases[0].id);
    }
  }, [activeWorkbaseId, setActiveWorkbaseId, workbases]);

  return (
    <AppShell workbases={workbases}>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </AppShell>
  );
}
