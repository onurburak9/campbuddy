import { useState } from "react";
import { useScan } from "../../hooks/useScans";
import { Tabs } from "../ui/Tabs";
import { Spinner } from "../ui/Spinner";
import { ScanDetailHeader } from "./ScanDetailHeader";
import { OverviewTab } from "./OverviewTab";
import { ResultsTab } from "./ResultsTab";
import { RunHistoryTab } from "./RunHistoryTab";
import { SettingsTab } from "./SettingsTab";

type TabId = "overview" | "results" | "runs" | "settings";
const TABS = [
  { id: "overview", label: "Overview" },
  { id: "results", label: "Results" },
  { id: "runs", label: "Run History" },
  { id: "settings", label: "Settings" },
];

export function ScanDetailPanel({ scanId, onDeleted }: { scanId: number; onDeleted: () => void }) {
  const { data: scan, isLoading } = useScan(scanId);
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  if (isLoading || !scan)
    return <div className="flex flex-1 items-center justify-center"><Spinner /></div>;

  return (
    <section className="flex flex-1 flex-col overflow-hidden">
      <ScanDetailHeader scan={scan} onDeleted={onDeleted} onEdit={() => setActiveTab("settings")} />
      <div className="px-6">
        <Tabs tabs={TABS} active={activeTab} onChange={(id) => setActiveTab(id as TabId)} />
      </div>
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {activeTab === "overview" && <OverviewTab scan={scan} />}
        {activeTab === "results" && <ResultsTab scanId={scan.id} />}
        {activeTab === "runs" && <RunHistoryTab scanId={scan.id} />}
        {activeTab === "settings" && <SettingsTab scan={scan} />}
      </div>
    </section>
  );
}
