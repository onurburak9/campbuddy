import { useAdminScans, useAdminPauseScan, useAdminResumeScan, useAdminDeleteScan } from "../../hooks/useAdmin";
import { Spinner } from "../ui/Spinner";
import { StatusDot } from "../ui/StatusDot";
import { Button } from "../ui/Button";
import { scanStatusTone } from "../layout/ScanListItem";

export function AdminScansTab() {
  const { data: scans, isLoading } = useAdminScans();
  const pause = useAdminPauseScan();
  const resume = useAdminResumeScan();
  const del = useAdminDeleteScan();

  if (isLoading) return <div className="flex justify-center p-8"><Spinner /></div>;
  if (!scans?.length) return <p className="p-6 text-sm text-stone-500 dark:text-[#888]">No scans found.</p>;

  async function onDelete(id: number, name: string | null) {
    if (!window.confirm(`Delete scan "${name ?? `#${id}`}"? This removes all its history.`)) return;
    await del.mutateAsync(id);
  }

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-sand-200 text-stone-500 dark:border-[#222] dark:text-[#888]">
          <th className="px-4 py-2 font-medium">Owner</th>
          <th className="px-4 py-2 font-medium">Scan</th>
          <th className="px-4 py-2 font-medium">Provider</th>
          <th className="px-4 py-2 font-medium">Status</th>
          <th className="px-4 py-2 font-medium">Created</th>
          <th className="px-4 py-2 font-medium">Actions</th>
        </tr>
      </thead>
      <tbody>
        {scans.map((s) => (
          <tr key={s.id} className="border-b border-sand-100 dark:border-[#1A1A1A]">
            <td className="px-4 py-2 text-stone-800 dark:text-[#EEE]">{s.user_email}</td>
            <td className="px-4 py-2 text-stone-600 dark:text-[#AAA]">{s.name ?? `#${s.id}`}</td>
            <td className="px-4 py-2 text-stone-600 dark:text-[#AAA]">{s.provider}</td>
            <td className="px-4 py-2">
              <span className="inline-flex items-center gap-1.5">
                <StatusDot tone={scanStatusTone(s.status)} /> {s.status}
              </span>
            </td>
            <td className="px-4 py-2 text-stone-600 dark:text-[#AAA]">{new Date(s.created_at).toLocaleDateString()}</td>
            <td className="px-4 py-2">
              <div className="flex gap-2">
                {s.status === "active" ? (
                  <Button variant="secondary" size="sm" disabled={pause.isPending} onClick={() => pause.mutate(s.id)}>Pause</Button>
                ) : s.status === "paused" ? (
                  <Button variant="secondary" size="sm" disabled={resume.isPending} onClick={() => resume.mutate(s.id)}>Resume</Button>
                ) : null}
                <Button variant="danger" size="sm" disabled={del.isPending} onClick={() => onDelete(s.id, s.name)}>Delete</Button>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
