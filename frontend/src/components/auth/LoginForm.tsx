import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { ApiError } from "../../api/client";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

export function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError("Invalid email or password");
      else setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Welcome back</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">Sign in to your account</p>
      </div>
      <Input id="email" label="Email" type="email" autoComplete="email"
        value={email} onChange={(e) => setEmail(e.target.value)} required />
      <Input id="password" label="Password" type="password" autoComplete="current-password"
        value={password} onChange={(e) => setPassword(e.target.value)} required />
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Signing in…" : "Sign In"}
      </Button>
    </form>
  );
}
