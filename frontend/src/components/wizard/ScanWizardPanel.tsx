import { useEffect, useState } from "react";
import { useScanFormState } from "../scans/useScanFormState";
import { ProviderSitesFields, DatesFiltersFields, NotificationsFields, windowNights } from "../scans/ScanForm";
import { VerticalStepIndicator } from "./VerticalStepIndicator";
import { Button } from "../ui/Button";
import { useCreateScan } from "../../hooks/useScans";
import { useAuth } from "../../contexts/AuthContext";
import { hasSeenWizardTour, startWizardProviderTour } from "../../lib/tour";

const STEPS = ["Provider & Sites", "Dates & Filters", "Notifications"];

function TourHelpButton({ className }: { className?: string }) {
  return (
    <button
      type="button"
      aria-label="Show tips for this step"
      onClick={startWizardProviderTour}
      className={
        "flex h-5 w-5 items-center justify-center rounded-full border border-sand-200 text-xs text-stone-500 " +
        "hover:bg-sand-100 dark:border-[#222] dark:text-[#888] dark:hover:bg-[#222] " +
        (className ?? "")
      }
    >
      ?
    </button>
  );
}

export function ScanWizardPanel({ onClose, onCreated }: {
  onClose: () => void; onCreated: (id: number) => void;
}) {
  const form = useScanFormState();
  const create = useCreateScan();
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (hasSeenWizardTour()) return;
    return startWizardProviderTour();
  }, []);

  const hasAnyIds = form.state.recAreaIds.length > 0 || form.state.campgroundIds.length > 0 || form.state.campsiteIds.length > 0;
  const validWindows = form.state.windows.length > 0 && form.state.windows.every((w) => w.start_date && w.end_date);
  const windowNightCounts = form.state.windows.map(windowNights).filter((n): n is number => n !== null);
  const shortestWindowNights = windowNightCounts.length ? Math.min(...windowNightCounts) : null;
  const nightsExceedWindow = shortestWindowNights !== null && form.state.nights > shortestWindowNights;

  function next() {
    setError(null);
    if (step === 0 && !hasAnyIds) { setError("Enter at least one Recreation Area, Campground, or Campsite ID."); return; }
    if (step === 1 && nightsExceedWindow) { setError(`Consecutive nights can't be longer than the shortest search window (${shortestWindowNights} nights).`); return; }
    setStep((s) => Math.min(2, s + 1));
  }

  async function onCreate() {
    setError(null);
    if (!validWindows) { setError("Add at least one search window with start and end dates."); return; }
    if (nightsExceedWindow) { setError(`Consecutive nights can't be longer than the shortest search window (${shortestWindowNights} nights).`); return; }
    try {
      const scan = await create.mutateAsync(form.toScanCreatePayload());
      onCreated(scan.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create scan");
    }
  }

  return (
    <section className="flex flex-1 overflow-hidden">
      <div className="hidden w-56 border-r border-sand-200 p-6 dark:border-[#222] md:block">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-stone-800 dark:text-[#EEE]">New Scan</h2>
          {step === 0 && <TourHelpButton />}
        </div>
        <VerticalStepIndicator steps={STEPS} current={step} />
      </div>
      <div className="flex flex-1 flex-col overflow-y-auto p-4 md:p-6">
        <div className="mb-4 flex items-center justify-between md:hidden">
          <p className="text-sm font-medium text-stone-600 dark:text-[#AAA]">
            Step {step + 1} of {STEPS.length} · {STEPS[step]}
          </p>
          {step === 0 && <TourHelpButton />}
        </div>
        <div className="max-w-xl flex-1">
          {step === 0 && <ProviderSitesFields state={form.state} set={form.set} />}
          {step === 1 && <DatesFiltersFields state={form.state} set={form.set} />}
          {step === 2 && <NotificationsFields state={form.state} set={form.set} telegramAvailable={!!user?.has_telegram} />}
          {error && <p className="mt-4 text-sm text-[#DC2626]">{error}</p>}
        </div>
        <div className="mt-6 flex justify-between border-t border-sand-200 pt-4 dark:border-[#222]">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <div className="flex gap-2">
            {step > 0 && <Button variant="secondary" onClick={() => setStep((s) => s - 1)}>Back</Button>}
            {step < 2
              ? <Button onClick={next}>Next →</Button>
              : <Button onClick={onCreate} disabled={create.isPending}>
                  {create.isPending ? "Creating…" : "Create Scan"}
                </Button>}
          </div>
        </div>
      </div>
    </section>
  );
}
