import { useState } from "react";
import { useProfile, useUpdateProfile } from "../../hooks/useProfile";
import { Input } from "../ui/Input";
import { Button } from "../ui/Button";
import { Toggle } from "../ui/Toggle";
import { Spinner } from "../ui/Spinner";
import type { Profile, ProfileUpdatePayload } from "../../types";

export function ProfileForm() {
  const { data: profile, isLoading } = useProfile();
  if (isLoading || !profile)
    return <div className="flex justify-center py-8"><Spinner /></div>;
  return <ProfileFields profile={profile} />;
}

function ProfileFields({ profile }: { profile: Profile }) {
  const update = useUpdateProfile();
  const [email, setEmail] = useState(profile.email);
  const [telegram, setTelegram] = useState(profile.telegram_chat_id ?? "");
  const [recEmail, setRecEmail] = useState(profile.recreationgov_email ?? "");
  const [recPassword, setRecPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [saved, setSaved] = useState(false);

  async function onSave() {
    setSaved(false);
    const payload: ProfileUpdatePayload = {};
    if (email && email !== profile.email) payload.email = email;
    if (telegram !== (profile.telegram_chat_id ?? "")) payload.telegram_chat_id = telegram;
    if (recEmail !== (profile.recreationgov_email ?? "")) payload.recreationgov_email = recEmail;
    if (recPassword) payload.recreationgov_password = recPassword;
    try {
      await update.mutateAsync(payload);
      setSaved(true);
      setRecPassword("");
    } catch {
      // error surfaced via update.isError in the UI
    }
  }

  return (
    <div className="w-full max-w-md space-y-4">
      <h1 className="text-2xl font-bold text-stone-900 dark:text-[#EEE]">Settings</h1>
      <Input label="Email address" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <Input label="Telegram Chat ID" value={telegram} onChange={(e) => setTelegram(e.target.value)} />
      <Input label="Recreation.gov email" type="email" value={recEmail}
        onChange={(e) => setRecEmail(e.target.value)} />
      <Input label="Recreation.gov password" type={showPassword ? "text" : "password"}
        value={recPassword} onChange={(e) => setRecPassword(e.target.value)}
        placeholder="Leave blank to keep current" />
      <Toggle label="Show password" checked={showPassword} onChange={setShowPassword} />
      <div className="flex items-center gap-3">
        <Button onClick={onSave} disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save"}
        </Button>
        {saved && <span className="text-sm text-[#22C55E]">Saved</span>}
        {update.isError && <span className="text-sm text-[#DC2626]">Save failed</span>}
      </div>
    </div>
  );
}
