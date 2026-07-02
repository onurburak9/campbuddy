import { useState } from "react";
import { IconSidebar } from "./IconSidebar";
import { MobileTopBar } from "./MobileTopBar";
import { ScanListPanel } from "./ScanListPanel";
import { ScanDetailPanel } from "../scans/ScanDetailPanel";
import { WelcomePanel } from "../scans/WelcomePanel";
import { ScanWizardPanel } from "../wizard/ScanWizardPanel";
import { cn } from "../../lib/cn";

export function DashboardLayout() {
  const [selectedScanId, setSelectedScanId] = useState<number | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const showingDetail = wizardOpen || selectedScanId != null;
  const selectScan = (id: number) => { setWizardOpen(false); setSelectedScanId(id); };
  const back = () => { setWizardOpen(false); setSelectedScanId(null); };

  return (
    <div className="flex h-screen overflow-hidden bg-sand-50 dark:bg-[#0D0D0D]">
      <IconSidebar
        onOpenScans={() => setWizardOpen(false)}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="flex flex-1 flex-col overflow-hidden">
        <MobileTopBar
          title="Scans"
          {...(showingDetail
            ? { onBack: back }
            : { onOpenSidebar: () => setSidebarOpen(true), onNewScan: () => { setSelectedScanId(null); setWizardOpen(true); } })}
        />
        <div className="flex flex-1 overflow-hidden">
          <div className={cn("min-w-0", showingDetail ? "hidden md:flex" : "flex w-full md:w-auto")}>
            <ScanListPanel
              selectedScanId={selectedScanId}
              onSelect={selectScan}
              onNewScan={() => { setSelectedScanId(null); setWizardOpen(true); }}
            />
          </div>
          <div className={cn("flex-1 overflow-hidden", showingDetail ? "flex" : "hidden md:flex")}>
            {wizardOpen ? (
              <ScanWizardPanel
                onClose={back}
                onCreated={(id) => { setWizardOpen(false); setSelectedScanId(id); }}
              />
            ) : selectedScanId != null ? (
              <ScanDetailPanel scanId={selectedScanId} onDeleted={() => setSelectedScanId(null)} />
            ) : (
              <WelcomePanel />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
