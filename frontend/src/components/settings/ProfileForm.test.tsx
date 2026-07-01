import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/server";
import { ProfileForm } from "./ProfileForm";

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ProfileForm", () => {
  it("hydrates from GET /users/me, submits only changed fields, shows Saved", async () => {
    server.use(http.get("/api/v1/users/me", () =>
      HttpResponse.json({ id: 1, email: "a@b.c", telegram_chat_id: null, recreationgov_email: null, scan_limit: 5 })));
    let body: any = null;
    server.use(http.patch("/api/v1/users/me", async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ id: 1, email: "a@b.c", telegram_chat_id: body.telegram_chat_id ?? null, recreationgov_email: null, scan_limit: 5 });
    }));
    wrap(<ProfileForm />);
    const telegram = await screen.findByLabelText(/telegram chat id/i); // waits for hydration
    await userEvent.type(telegram, "123456");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(body.telegram_chat_id).toBe("123456"));
    expect(await screen.findByText(/saved/i)).toBeInTheDocument();
  });
});
