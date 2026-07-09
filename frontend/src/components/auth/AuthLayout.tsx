import { type ReactNode } from "react";
import { NaturePanel } from "./NaturePanel";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid h-screen grid-cols-1 md:grid-cols-2">
      <NaturePanel />
      <div className="flex items-center justify-center bg-sand-50 p-8 dark:bg-[#0D0D0D]">
        {children}
      </div>
    </div>
  );
}
