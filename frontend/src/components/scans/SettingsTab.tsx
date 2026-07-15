import { useState } from "react";
import { useScanFormState } from "./useScanFormState";
import { ProviderSitesFields, DatesFiltersFields, NotificationsFields, windowNights } from "./ScanForm";
import { Button } from "../ui/Button";
import { useUpdateScan } from "../../hooks/useScans";
import { useAuth } from "../../contexts/AuthContext";
import type { Scan } from "../../types";

export function SettingsTab({ scan }: { scan: Scan }) {
  const form = useScanFormState(scan);
  const update = useUpdateScan();
  const { user } = useAuth();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const windowNightCounts = form.state.windows.map(windowNights).filter((n): n is number => n !== null);
  const shortestWindowNights = windowNightCounts.length ? Math.min(...windowNightCounts) : null;
  const nightsExceedWindow = shortestWindowNights !== null && form.state.nights > shortestWindowNights;

  async function onSave() {
    setSaved(false);
    setError(null);
    if (nightsExceedWindow) { setError(`Consecutive nights can't be longer than the shortest search window (${shortestWindowNights} nights).`); return; }
    try {
      await update.mutateAsync({ id: scan.id, payload: form.toScanUpdatePayload() });
      setSaved(true);
    } catch {
      // error surfaced via update.isError in the UI
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <ProviderSitesFields state={form.state} set={form.set} />
      <DatesFiltersFields state={form.state} set={form.set} />
      <NotificationsFields
        state={form.state}
        set={form.set}
        telegramAvailable={!!user?.has_telegram}
      />
      <div className="flex items-center gap-3">
        <Button onClick={onSave} disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save"}
        </Button>
        {saved && <span className="text-sm text-[#22C55E]">Saved</span>}
        {update.isError && <span className="text-sm text-[#DC2626]">Save failed</span>}
        {error && <span className="text-sm text-[#DC2626]">{error}</span>}
      </div>
    </div>
  );
}
