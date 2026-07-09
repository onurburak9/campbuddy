import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { AuthLayout } from "./AuthLayout";
import { LoginForm } from "./LoginForm";
import { Spinner } from "../ui/Spinner";

export function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <AuthLayout>
      <LoginForm />
    </AuthLayout>
  );
}
