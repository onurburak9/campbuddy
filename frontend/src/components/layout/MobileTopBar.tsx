import { useAuth } from "../../contexts/AuthContext";
import { cn } from "../../lib/cn";
import { FeedbackWidget } from "../feedback/FeedbackWidget";

interface Props {
  title: string;
  onOpenSidebar?: () => void;
  onBack?: () => void;
  onNewScan?: () => void;
}

export function MobileTopBar({ title, onOpenSidebar, onBack, onNewScan }: Props) {
  const { user } = useAuth();
  const atLimit = !!user && user.scans_used >= user.scan_limit;

  return (
    <header className="flex h-12 items-center justify-between border-b border-sand-200 bg-white px-3 dark:border-[#222] dark:bg-[#1A1A1A] md:hidden">
      <div className="flex items-center gap-2">
        {onBack ? (
          <>
            <button
              aria-label="Back to scans"
              onClick={onBack}
              className="flex items-center gap-1 rounded-md px-1 py-1 text-sm font-medium text-stone-700 hover:bg-sand-100 dark:text-[#CCC] dark:hover:bg-[#222]"
            >
              <span aria-hidden>←</span> {title}
            </button>
            <FeedbackWidget className="flex h-7 w-7" />
          </>
        ) : (
          <>
            {onOpenSidebar && (
              <button
                aria-label="Open menu"
                onClick={onOpenSidebar}
                className="flex h-8 w-8 items-center justify-center rounded-md text-lg hover:bg-sand-100 dark:hover:bg-[#222]"
              >
                <span aria-hidden>☰</span>
              </button>
            )}
            <h1 className="text-sm font-semibold text-stone-800 dark:text-[#EEE]">{title}</h1>
            <FeedbackWidget className="flex h-7 w-7" />
            {user && (
              <span className="text-xs text-stone-500 dark:text-[#888]">
                {user.scans_used}/{user.scan_limit}
              </span>
            )}
          </>
        )}
      </div>
      {onNewScan && (
        <button
          aria-label="New scan"
          onClick={onNewScan}
          disabled={atLimit}
          title={atLimit ? `Scan limit reached (${user?.scan_limit})` : "New scan"}
          className={cn(
            "flex h-7 w-7 items-center justify-center rounded-md bg-forest-600 text-white hover:bg-forest-700",
            atLimit && "cursor-not-allowed opacity-50 hover:bg-forest-600"
          )}
        >
          +
        </button>
      )}
    </header>
  );
}
