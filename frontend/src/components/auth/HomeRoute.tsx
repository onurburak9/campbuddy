import { useAuth } from "../../contexts/AuthContext";
import { Spinner } from "../ui/Spinner";
import { LandingPage } from "../landing/LandingPage";

/** "/" shows the dashboard to signed-in users and the public landing page to everyone else. */
export function HomeRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (!isAuthenticated) return <LandingPage />;
  return <>{children}</>;
}
