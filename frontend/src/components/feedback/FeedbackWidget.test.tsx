import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { server } from "../../test/server";
import { FeedbackWidget } from "./FeedbackWidget";

function renderWidget(path = "/scans/12") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <FeedbackWidget />
    </MemoryRouter>
  );
}

describe("FeedbackWidget", () => {
  it("submits the current page path and message, then shows a success state", async () => {
    let body: unknown;
    server.use(
      http.post("/api/v1/feedback", async ({ request }) => {
        body = await request.json();
        return new HttpResponse(null, { status: 202 });
      })
    );
    renderWidget("/scans/12");
    await userEvent.click(screen.getByRole("button", { name: /feedback/i }));
    await userEvent.type(screen.getByRole("textbox"), "The button does nothing");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(screen.getByText(/thanks/i)).toBeInTheDocument());
    expect(body).toEqual({ page_path: "/scans/12", message: "The button does nothing" });
  });

  it("shows an inline error and preserves the message when the request fails", async () => {
    server.use(http.post("/api/v1/feedback", () => HttpResponse.json({ detail: "down" }, { status: 502 })));
    renderWidget();
    await userEvent.click(screen.getByRole("button", { name: /feedback/i }));
    await userEvent.type(screen.getByRole("textbox"), "Still broken");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(screen.getByText(/couldn.t send feedback/i)).toBeInTheDocument());
    expect(screen.getByRole("textbox")).toHaveValue("Still broken");
  });

  it("disables the send button until a message is entered", async () => {
    renderWidget();
    await userEvent.click(screen.getByRole("button", { name: /feedback/i }));
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
    await userEvent.type(screen.getByRole("textbox"), "x");
    expect(screen.getByRole("button", { name: /send/i })).not.toBeDisabled();
  });
});
