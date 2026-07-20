import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { auth } from "../../api/auth";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await auth.forgotPassword(email);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (submitted) {
    return (
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Check your email</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">
          If an account exists for {email}, we've sent a link to reset your password.
        </p>
        <Link to="/login" className="text-sm text-forest-600 hover:underline">Back to sign in</Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Forgot password?</h1>
        <p className="text-sm text-stone-500 dark:text-[#888]">Enter your email and we'll send you a reset link</p>
      </div>
      <Input id="email" label="Email" type="email" autoComplete="email"
        value={email} onChange={(e) => setEmail(e.target.value)} required />
      {error && <p className="text-sm text-[#DC2626]">{error}</p>}
      <Button type="submit" disabled={busy} className="w-full">
        {busy ? "Sending…" : "Send reset link"}
      </Button>
      <p className="text-sm text-stone-500 dark:text-[#888]">
        <Link to="/login" className="text-forest-600 hover:underline">Back to sign in</Link>
      </p>
    </form>
  );
}
