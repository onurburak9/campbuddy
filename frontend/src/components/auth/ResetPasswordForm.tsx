import { useState, type FormEvent } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { ApiError } from "../../api/client";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

export function ResetPasswordForm() {
  const { resetPassword } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setBusy(true);
    try {
      await resetPassword(token, password);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) setError(err.message);
      else setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Set a new password</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">Choose a new password for your account</p>
      </div>
      <Input id="password" label="New password" type="password" autoComplete="new-password"
        value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
      <Input id="confirm-password" label="Confirm password" type="password" autoComplete="new-password"
        value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} minLength={8} required />
      {error && (
        <p className="text-sm text-[#DC2626]">
          {error} <Link to="/forgot-password" className="underline">Request a new link</Link>
        </p>
      )}
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Resetting…" : "Reset password"}
      </Button>
    </form>
  );
}
