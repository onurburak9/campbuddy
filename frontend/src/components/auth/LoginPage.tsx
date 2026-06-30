import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { NaturePanel } from "./NaturePanel";
import { LoginForm } from "./LoginForm";
import { Spinner } from "../ui/Spinner";

export function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <div className="grid h-screen grid-cols-1 md:grid-cols-2">
      <NaturePanel />
      <div className="flex items-center justify-center bg-sand-50 p-8 dark:bg-[#0D0D0D]">
        <LoginForm />
      </div>
    </div>
  );
}
