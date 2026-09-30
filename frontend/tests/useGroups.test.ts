import { beforeEach, describe, expect, it, vi } from "vitest";
import type { GroupItem, TaskGroup } from "../src/types";
import * as api from "../src/features/tasks/api";
import { useGroups } from "../src/features/tasks/useGroups";

vi.mock("../src/features/tasks/api", () => ({
  listGroups: vi.fn(),
  getGroup: vi.fn(),
  createGroup: vi.fn(),
  updateGroup: vi.fn(),
  deleteGroup: vi.fn(),
  createItem: vi.fn(),
  updateItem: vi.fn(),
  deleteItem: vi.fn(),
  listCompletions: vi.fn(),
  checkItem: vi.fn(),
  undoCompletion: vi.fn(),
  groupLog: vi.fn(),
}));

function item(overrides: Partial<GroupItem> = {}): GroupItem {
  return {
    id: 10,
    group_id: 1,
    title: "喝八杯水",
    repeat_unit: "day",
    start_date: "2026-09-01",
    created_at: "2026-09-01T08:00:00",
    recent_days: [],
    total_count: 0,
    ...overrides,
  };
}

function group(overrides: Partial<TaskGroup> = {}): TaskGroup {
  return {
    id: 1,
    title: "晨间习惯",
    notes: "",
    archived: false,
    archived_on: null,
    created_at: "2026-09-01T08:00:00",
    items: [item()],
    ...overrides,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("long-term task data loading", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps a check-in when a list request started earlier resolves afterwards", async () => {
    // Regression: the mount/refresh request used to overwrite a completion that
    // was saved while it was still in flight, so the item looked unchecked even
    // though the backend had stored it (the intermittent CI failure).
    vi.mocked(api.listGroups).mockResolvedValueOnce([group()]);
    const snapshots: TaskGroup[][] = [];
    const store = useGroups((rows) => snapshots.push(rows), 1);
    await store.load();

    const refresh = deferred<TaskGroup[]>();
    vi.mocked(api.listGroups).mockReturnValueOnce(refresh.promise);
    const pending = store.load();

    vi.mocked(api.checkItem).mockResolvedValue(
      item({ recent_days: ["2026-09-30"], total_count: 1 }),
    );
    await store.check(1, 10, { completed_on: "2026-09-30" });

    refresh.resolve([group()]); // pre-check-in rows arrive last
    await pending;

    expect(store.groups.value[0].items[0].recent_days).toEqual(["2026-09-30"]);
    expect(store.groups.value[0].items[0].total_count).toBe(1);
    expect(snapshots.at(-1)?.[0].items[0].total_count).toBe(1);
    expect(store.loading.value).toBe(false);
  });

  it("stops the spinner when a change supersedes the request behind it", async () => {
    vi.mocked(api.listGroups).mockResolvedValueOnce([group()]);
    const store = useGroups(() => {}, 1);
    await store.load();

    const stuck = deferred<TaskGroup[]>();
    vi.mocked(api.listGroups).mockReturnValueOnce(stuck.promise);
    const pending = store.load();
    expect(store.loading.value).toBe(true);

    vi.mocked(api.checkItem).mockResolvedValue(item({ recent_days: ["2026-09-30"] }));
    await store.check(1, 10);

    expect(store.loading.value).toBe(false);
    stuck.resolve([group()]);
    await pending;
    expect(store.groups.value[0].items[0].recent_days).toEqual(["2026-09-30"]);
  });

  it("still applies a load nobody superseded", async () => {
    vi.mocked(api.listGroups).mockResolvedValueOnce([group()]);
    const store = useGroups(() => {}, 1);
    await store.load();
    expect(store.groups.value).toHaveLength(1);
    expect(store.loading.value).toBe(false);

    vi.mocked(api.listGroups).mockResolvedValueOnce([group({ title: "夜间习惯" })]);
    await store.load();
    expect(store.groups.value[0].title).toBe("夜间习惯");
    expect(store.loading.value).toBe(false);
  });
});
