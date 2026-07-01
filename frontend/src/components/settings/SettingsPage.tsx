import { useNavigate } from "react-router-dom";
import { IconSidebar } from "../layout/IconSidebar";
import { ProfileForm } from "./ProfileForm";

export function SettingsPage() {
  const navigate = useNavigate();
  return (
    <div className="flex h-screen overflow-hidden bg-sand-50 dark:bg-[#0D0D0D]">
      <IconSidebar onOpenScans={() => navigate("/")} />
      <div className="flex flex-1 items-start justify-center overflow-y-auto p-10">
        <ProfileForm />
      </div>
    </div>
  );
}
