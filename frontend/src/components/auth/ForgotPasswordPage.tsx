import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { AuthLayout } from "./AuthLayout";
import { ForgotPasswordForm } from "./ForgotPasswordForm";
import { Spinner } from "../ui/Spinner";

export function ForgotPasswordPage() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return (
    <AuthLayout>
      <ForgotPasswordForm />
    </AuthLayout>
  );
}
