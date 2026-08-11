import { useState } from "react";
import { useLocation } from "react-router-dom";
import { feedback } from "../../api/feedback";
import { Button } from "../ui/Button";
import { cn } from "../../lib/cn";

type Status = "idle" | "submitting" | "success" | "error";

export function FeedbackWidget() {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<Status>("idle");

  const close = () => {
    setOpen(false);
    setMessage("");
    setStatus("idle");
  };

  const submit = async () => {
    if (!message.trim()) return;
    setStatus("submitting");
    try {
      await feedback.submit(location.pathname, message.trim());
      setStatus("success");
      setTimeout(close, 2000);
    } catch {
      setStatus("error");
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 rounded-full bg-forest-600 px-4 py-2 text-sm font-medium text-white shadow-lg hover:bg-forest-700"
      >
        Feedback
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-md border border-sand-200 bg-white p-4 dark:border-[#222] dark:bg-[#1A1A1A]">
            <h2 className="mb-2 text-sm font-medium text-stone-900 dark:text-[#EEE]">Send feedback</h2>
            {status === "success" ? (
              <p className="text-sm text-forest-600">Thanks — filed!</p>
            ) : (
              <>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={4}
                  placeholder="What's going on?"
                  disabled={status === "submitting"}
                  className={cn(
                    "w-full rounded-md border bg-white px-3 py-2 text-sm text-stone-900 outline-none",
                    "border-sand-200 focus:border-forest-600 focus:ring-1 focus:ring-forest-600",
                    "dark:border-[#222] dark:bg-[#1A1A1A] dark:text-[#EEE]"
                  )}
                />
                {status === "error" && (
                  <p className="mt-1 text-sm text-[#DC2626]">Couldn't send feedback, try again.</p>
                )}
                <div className="mt-3 flex justify-end gap-2">
                  <Button variant="ghost" size="sm" onClick={close} disabled={status === "submitting"}>
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={submit}
                    disabled={status === "submitting" || !message.trim()}
                  >
                    {status === "submitting" ? "Sending…" : "Send"}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}
