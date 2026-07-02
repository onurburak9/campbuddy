import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { IconSidebar } from "../layout/IconSidebar";
import { MobileTopBar } from "../layout/MobileTopBar";
import { ProfileForm } from "./ProfileForm";

export function SettingsPage() {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return (
    <div className="flex h-screen overflow-hidden bg-sand-50 dark:bg-[#0D0D0D]">
      <IconSidebar
        onOpenScans={() => navigate("/")}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <MobileTopBar title="Settings" onOpenSidebar={() => setSidebarOpen(true)} />
        <div className="flex flex-1 items-start justify-center overflow-y-auto p-6 md:p-10">
          <ProfileForm />
        </div>
      </div>
    </div>
  );
}
