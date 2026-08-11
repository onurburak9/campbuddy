import { fetchApi } from "./client";

export const feedback = {
  submit: (pagePath: string, message: string) =>
    fetchApi<void>("/feedback", {
      method: "POST",
      body: JSON.stringify({ page_path: pagePath, message }),
    }),
};
