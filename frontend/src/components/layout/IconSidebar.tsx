import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTheme } from "../../contexts/ThemeContext";
import { useAuth } from "../../contexts/AuthContext";
import { cn } from "../../lib/cn";

const FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function IconSidebar({ onOpenScans, open = false, onClose }: {
  onOpenScans: () => void;
  open?: boolean;
  onClose?: () => void;
}) {
  const { theme, toggle } = useTheme();
  const { logout, user } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const navRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const closeMenuTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

  const openAccountMenu = () => {
    if (closeMenuTimerRef.current) {
      clearTimeout(closeMenuTimerRef.current);
      closeMenuTimerRef.current = null;
    }
    setAccountMenuOpen(true);
  };
  const scheduleCloseAccountMenu = () => {
    closeMenuTimerRef.current = setTimeout(() => setAccountMenuOpen(false), 250);
  };

  useEffect(() => {
    return () => {
      if (closeMenuTimerRef.current) clearTimeout(closeMenuTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!open || !onClose) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    previousFocusRef.current = document.activeElement as HTMLElement | null;
    const focusables = navRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    focusables?.[0]?.focus();

    return () => {
      previousFocusRef.current?.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const focusables = navRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(() => {
    if (!accountMenuOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setAccountMenuOpen(false); };
    const onClickOutside = (e: MouseEvent) => {
      if (accountMenuRef.current && !accountMenuRef.current.contains(e.target as Node)) setAccountMenuOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClickOutside);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClickOutside);
    };
  }, [accountMenuOpen]);

  const closeDrawer = () => onClose?.();
  const iconBtn = "flex h-12 w-12 items-center justify-center rounded-lg transition-colors";

  return (
    <>
      {open && (
        <div
          data-testid="sidebar-backdrop"
          aria-hidden
          onClick={closeDrawer}
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
        />
      )}
      <nav
        ref={navRef}
        className={cn(
          "flex w-16 flex-col items-center justify-between border-r border-sand-200 bg-white py-3 dark:border-[#222] dark:bg-[#1A1A1A]",
          "fixed left-0 top-0 z-50 h-full transition-transform md:static md:z-auto md:h-auto md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex flex-col items-center gap-2">
          <div className="mb-2 flex h-12 w-12 items-center justify-center" aria-hidden>
            <img src="/icons/camping.svg" alt="" className="h-9 w-9" />
          </div>
          <Link to="/" onClick={() => { onOpenScans(); closeDrawer(); }} aria-label="Scans" title="Scans"
            className={cn(iconBtn, pathname === "/" ? "bg-forest-50 dark:bg-[#222]" : "hover:bg-sand-100 dark:hover:bg-[#222]")}>
            <img src="/icons/mountain.svg" alt="" className="h-7 w-7" />
          </Link>
          <Link to="/settings" data-tour="settings-link" onClick={closeDrawer} aria-label="Settings" title="Settings"
            className={cn(iconBtn, pathname === "/settings" ? "bg-forest-50 dark:bg-[#222]" : "hover:bg-sand-100 dark:hover:bg-[#222]")}>
            <img src="/icons/gear.svg" alt="" className="h-7 w-7" />
          </Link>
        </div>
        <div
          ref={accountMenuRef}
          className="relative flex flex-col items-center"
          onMouseEnter={openAccountMenu}
          onMouseLeave={scheduleCloseAccountMenu}
        >
          {accountMenuOpen && (
            <div
              role="menu"
              className="absolute bottom-0 left-full z-50 ml-2 w-48 rounded-lg border border-sand-200 bg-white py-1 shadow-lg dark:border-[#222] dark:bg-[#1A1A1A]"
            >
              <button
                role="menuitem"
                onClick={toggle}
                className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm text-stone-700 hover:bg-sand-100 dark:text-[#CCC] dark:hover:bg-[#222]"
              >
                <img src={theme === "dark" ? "/icons/sun.svg" : "/icons/moon.svg"} alt="" className="h-5 w-5" />
                {theme === "dark" ? "Light mode" : "Dark mode"}
              </button>
              <button
                role="menuitem"
                onClick={() => { setAccountMenuOpen(false); logout().then(() => navigate("/login", { replace: true })); }}
                className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm text-stone-700 hover:bg-sand-100 dark:text-[#CCC] dark:hover:bg-[#222]"
              >
                <img src="/icons/door.svg" alt="" className="h-5 w-5" />
                Log out
              </button>
            </div>
          )}
          <button
            aria-label={`Account menu for ${user?.email ?? ""}`}
            aria-expanded={accountMenuOpen}
            aria-haspopup="menu"
            onClick={openAccountMenu}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-forest-600 text-base font-semibold text-white"
          >
            {user?.email?.[0]?.toUpperCase() ?? "?"}
          </button>
        </div>
      </nav>
    </>
  );
}
