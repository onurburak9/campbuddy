import { useEffect } from "react";
import { hasSeenWelcomeTour, startWelcomeTour } from "../../lib/tour";

export function WelcomePanel() {
  useEffect(() => {
    if (!hasSeenWelcomeTour()) startWelcomeTour();
  }, []);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
      <span className="text-5xl" aria-hidden>🏕️</span>
      <h2 className="text-lg font-semibold text-stone-700 dark:text-[#CCC]">Welcome to CampBuddy</h2>
      <p className="max-w-xs text-sm text-stone-500 dark:text-[#888]">
        Select a scan from the list, or create a new one to start monitoring campsite availability.
      </p>
      <button
        type="button"
        onClick={startWelcomeTour}
        className="text-sm text-forest-600 underline hover:text-forest-700 dark:text-forest-400"
      >
        Take the tour
      </button>
    </div>
  );
}
