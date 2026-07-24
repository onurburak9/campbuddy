import { useAdminUsers } from "../../hooks/useAdmin";
import { Spinner } from "../ui/Spinner";
import { Badge } from "../ui/Badge";

export function AdminUsersTab() {
  const { data: users, isLoading, isError } = useAdminUsers();

  if (isLoading) return <div className="flex justify-center p-8"><Spinner /></div>;
  if (isError) return <p className="p-6 text-sm text-red-600 dark:text-red-400">Failed to load users.</p>;
  if (!users?.length) return <p className="p-6 text-sm text-stone-500 dark:text-[#888]">No users found.</p>;

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-sand-200 text-stone-500 dark:border-[#222] dark:text-[#888]">
          <th className="px-4 py-2 font-medium">Email</th>
          <th className="px-4 py-2 font-medium">Scans</th>
          <th className="px-4 py-2 font-medium">Telegram</th>
          <th className="px-4 py-2 font-medium">Role</th>
          <th className="px-4 py-2 font-medium">Joined</th>
        </tr>
      </thead>
      <tbody>
        {users.map((u) => (
          <tr key={u.id} className="border-b border-sand-100 dark:border-[#1A1A1A]">
            <td className="px-4 py-2 text-stone-800 dark:text-[#EEE]">{u.email}</td>
            <td className="px-4 py-2 text-stone-600 dark:text-[#AAA]">{u.scans_used} / {u.scan_limit}</td>
            <td className="px-4 py-2 text-stone-600 dark:text-[#AAA]">{u.has_telegram ? "✓" : "–"}</td>
            <td className="px-4 py-2">
              {u.is_admin ? <Badge tone="accent">Admin</Badge> : <Badge tone="neutral">User</Badge>}
            </td>
            <td className="px-4 py-2 text-stone-600 dark:text-[#AAA]">{new Date(u.created_at).toLocaleDateString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
