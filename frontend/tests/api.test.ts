import { it, expect, vi, afterEach } from "vitest";
import { api, setCsrf } from "../src/api";
afterEach(() => vi.unstubAllGlobals());
it("sends session cookies and current CSRF on mutations", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ id: 1 }), { status: 201 }),
    );
  vi.stubGlobal("fetch", fetcher);
  setCsrf("token");
  await api("/tasks", "POST", { title: "read" });
  expect(fetcher).toHaveBeenCalledWith(
    "/api/tasks",
    expect.objectContaining({
      credentials: "same-origin",
      headers: expect.objectContaining({ "X-CSRF-Token": "token" }),
    }),
  );
});
it("clears CSRF between accounts and handles empty responses", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetcher);
  setCsrf("");
  expect(await api("/auth/logout", "POST")).toBeUndefined();
  expect(fetcher.mock.calls[0]?.[1].headers["X-CSRF-Token"]).toBeUndefined();
});
