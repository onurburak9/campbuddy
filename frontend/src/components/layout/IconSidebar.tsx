import { Link, useLocation } from "react-router-dom";
import { useTheme } from "../../contexts/ThemeContext";
import { useAuth } from "../../contexts/AuthContext";
import { cn } from "../../lib/cn";

export function IconSidebar({ onOpenScans }: { onOpenScans: () => void }) {
  const { theme, toggle } = useTheme();
  const { logout, user } = useAuth();
  const { pathname } = useLocation();

  const iconBtn = "flex h-10 w-10 items-center justify-center rounded-lg text-xl transition-colors";
  return (
    <nav className="flex w-[52px] flex-col items-center justify-between border-r border-sand-200 bg-white py-3 dark:border-[#222] dark:bg-[#1A1A1A]">
      <div className="flex flex-col items-center gap-2">
        <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg bg-forest-600 text-white" aria-hidden>⛺</div>
        <Link to="/" onClick={onOpenScans} aria-label="Scans"
          className={cn(iconBtn, pathname === "/" ? "bg-forest-50 dark:bg-[#222]" : "hover:bg-sand-100 dark:hover:bg-[#222]")}>
          <span aria-hidden>⛺</span>
        </Link>
        <Link to="/settings" aria-label="Settings"
          className={cn(iconBtn, pathname === "/settings" ? "bg-forest-50 dark:bg-[#222]" : "hover:bg-sand-100 dark:hover:bg-[#222]")}>
          <span aria-hidden>⚙️</span>
        </Link>
      </div>
      <div className="flex flex-col items-center gap-2">
        <button aria-label="Toggle theme" onClick={toggle}
          className={cn(iconBtn, "hover:bg-sand-100 dark:hover:bg-[#222]")}>
          <span aria-hidden>{theme === "dark" ? "☀️" : "🌙"}</span>
        </button>
        <button aria-label={`Log out ${user?.email ?? ""}`} onClick={() => logout()}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-forest-600 text-sm font-semibold text-white">
          {user?.email?.[0]?.toUpperCase() ?? "?"}
        </button>
      </div>
    </nav>
  );
}
