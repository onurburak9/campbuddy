import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { ApiError } from "../../api/client";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

export function RegisterForm() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
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
      await register(email, password);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 403)) setError(err.message);
      else setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Create an account</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">Start tracking campsite availability</p>
      </div>
      <Input id="email" label="Email" type="email" autoComplete="email"
        value={email} onChange={(e) => setEmail(e.target.value)} required />
      <Input id="password" label="Password" type="password" autoComplete="new-password"
        value={password} onChange={(e) => setPassword(e.target.value)} minLength={8} required />
      <Input id="confirm-password" label="Confirm password" type="password" autoComplete="new-password"
        value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} minLength={8} required />
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Creating account…" : "Create Account"}
      </Button>
      <p className="text-sm text-stone-500 dark:text-[#888]">
        Already have an account? <Link to="/login" className="text-forest-600 hover:underline">Sign in</Link>
      </p>
    </form>
  );
}
