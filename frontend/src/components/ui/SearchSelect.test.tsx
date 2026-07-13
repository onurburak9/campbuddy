import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchSelect } from "./SearchSelect";

describe("SearchSelect", () => {
  it("does not search below 2 characters", async () => {
    const search = vi.fn().mockResolvedValue([]);
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={vi.fn()} search={search} />);
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "y");
    await new Promise((r) => setTimeout(r, 350));
    expect(search).not.toHaveBeenCalled();
  });

  it("searches (debounced) at 2+ characters and shows results", async () => {
    const search = vi.fn().mockResolvedValue([{ id: 2991, name: "Yosemite National Park" }]);
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={vi.fn()} search={search} />);
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "yo");
    await waitFor(() => expect(search).toHaveBeenCalledWith("yo"), { timeout: 1000 });
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
  });

  it("selects a result and calls onChange with it appended", async () => {
    const search = vi.fn().mockResolvedValue([{ id: 2991, name: "Yosemite National Park" }]);
    const onChange = vi.fn();
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={onChange} search={search} />);
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "yo");
    await waitFor(() => screen.getByText("Yosemite National Park"));
    await userEvent.click(screen.getByText("Yosemite National Park"));
    expect(onChange).toHaveBeenCalledWith([{ id: 2991, name: "Yosemite National Park" }]);
  });

  it("removes a selected chip", async () => {
    const onChange = vi.fn();
    render(
      <SearchSelect
        label="Recreation Areas"
        selected={[{ id: 2991, name: "Yosemite National Park" }]}
        onChange={onChange}
        search={vi.fn().mockResolvedValue([])}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: /remove yosemite national park/i }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("shows an error message when search rejects", async () => {
    const search = vi.fn().mockRejectedValue(new Error("Search temporarily unavailable"));
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={vi.fn()} search={search} />);
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "yo");
    await waitFor(() => expect(screen.getByText(/search temporarily unavailable/i)).toBeInTheDocument());
  });

  it("adds a chip by raw id via the fallback input", async () => {
    const onChange = vi.fn();
    render(<SearchSelect label="Recreation Areas" selected={[]} onChange={onChange} search={vi.fn().mockResolvedValue([])} />);
    await userEvent.type(screen.getByLabelText(/add by id/i), "1074");
    await userEvent.click(screen.getByRole("button", { name: /^add$/i }));
    expect(onChange).toHaveBeenCalledWith([{ id: 1074, name: "ID 1074" }]);
  });

  it("uses renderResult to customize how each result row is displayed", async () => {
    const search = vi.fn().mockResolvedValue([{ id: 2991, name: "Yosemite National Park", state: "CA" }]);
    render(
      <SearchSelect
        label="Recreation Areas"
        selected={[]}
        onChange={vi.fn()}
        search={search}
        renderResult={(item: any) => <span>{item.name} — {item.state}</span>}
      />
    );
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "yo");
    await waitFor(() => expect(screen.getByText("Yosemite National Park — CA")).toBeInTheDocument());
  });

  it("hides the results dropdown when clicking outside", async () => {
    const search = vi.fn().mockResolvedValue([{ id: 2991, name: "Yosemite National Park" }]);
    render(
      <div>
        <SearchSelect label="Recreation Areas" selected={[]} onChange={vi.fn()} search={search} />
        <button>Outside</button>
      </div>
    );
    await userEvent.type(screen.getByRole("textbox", { name: /recreation areas/i }), "yo");
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Outside" }));
    expect(screen.queryByText("Yosemite National Park")).not.toBeInTheDocument();
  });

  it("reopens the results dropdown when typing again after an outside click", async () => {
    const search = vi.fn().mockResolvedValue([{ id: 2991, name: "Yosemite National Park" }]);
    render(
      <div>
        <SearchSelect label="Recreation Areas" selected={[]} onChange={vi.fn()} search={search} />
        <button>Outside</button>
      </div>
    );
    const input = screen.getByRole("textbox", { name: /recreation areas/i });
    await userEvent.type(input, "yo");
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Outside" }));
    expect(screen.queryByText("Yosemite National Park")).not.toBeInTheDocument();
    await userEvent.type(input, "s");
    await waitFor(() => expect(screen.getByText("Yosemite National Park")).toBeInTheDocument());
  });
});
