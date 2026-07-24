import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { IconSidebar } from "../layout/IconSidebar";
import { MobileTopBar } from "../layout/MobileTopBar";
import { Tabs } from "../ui/Tabs";
import { AdminUsersTab } from "./AdminUsersTab";
import { AdminScansTab } from "./AdminScansTab";

const TABS = [
  { id: "users", label: "Users" },
  { id: "scans", label: "Scans" },
];

export function AdminPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("users");

  if (user && !user.is_admin) return <Navigate to="/" replace />;

  return (
    <div className="flex h-screen overflow-hidden bg-sand-50 dark:bg-[#0D0D0D]">
      <IconSidebar
        onOpenScans={() => navigate("/")}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <MobileTopBar title="Admin" onOpenSidebar={() => setSidebarOpen(true)} />
        <div className="flex flex-1 flex-col overflow-y-auto p-4 md:p-6">
          <Tabs tabs={TABS} active={activeTab} onChange={setActiveTab} />
          <div className="mt-4 overflow-x-auto rounded-lg border border-sand-200 dark:border-[#222]">
            {activeTab === "users" ? <AdminUsersTab /> : <AdminScansTab />}
          </div>
        </div>
      </div>
    </div>
  );
}
