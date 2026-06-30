import { useState } from "react";
import { IconSidebar } from "./IconSidebar";
import { ScanListPanel } from "./ScanListPanel";
import { ScanDetailPanel } from "../scans/ScanDetailPanel";
import { WelcomePanel } from "../scans/WelcomePanel";
import { ScanWizardPanel } from "../wizard/ScanWizardPanel";

export function DashboardLayout() {
  const [selectedScanId, setSelectedScanId] = useState<number | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  const selectScan = (id: number) => { setWizardOpen(false); setSelectedScanId(id); };

  return (
    <div className="flex h-screen overflow-hidden bg-sand-50 dark:bg-[#0D0D0D]">
      <IconSidebar onOpenScans={() => setWizardOpen(false)} />
      <ScanListPanel
        selectedScanId={selectedScanId}
        onSelect={selectScan}
        onNewScan={() => { setSelectedScanId(null); setWizardOpen(true); }}
      />
      {wizardOpen ? (
        <ScanWizardPanel
          onClose={() => setWizardOpen(false)}
          onCreated={(id) => { setWizardOpen(false); setSelectedScanId(id); }}
        />
      ) : selectedScanId != null ? (
        <ScanDetailPanel scanId={selectedScanId} onDeleted={() => setSelectedScanId(null)} />
      ) : (
        <WelcomePanel />
      )}
    </div>
  );
}
