import { describe, expect, it } from "vitest";
import {
  COLLAPSE_KEY,
  isCollapsed,
  readCollapsed,
  withAllCollapsed,
  withCollapsed,
  writeCollapsed,
} from "../src/features/tasks/collapse";

/** Minimal in-memory Storage so the preference store is testable without a browser. */
function fakeStorage(initial: Record<string, string> = {}) {
  const data = { ...initial };
  return {
    data,
    getItem: (key: string) => data[key] ?? null,
    setItem: (key: string, value: string) => {
      data[key] = value;
    },
  } as unknown as Storage;
}

function throwingStorage() {
  return {
    getItem: () => {
      throw new Error("blocked");
    },
    setItem: () => {
      throw new Error("quota");
    },
  } as unknown as Storage;
}

describe("collapse preferences", () => {
  it("treats an unknown group as collapsed", () => {
    expect(isCollapsed({}, 7)).toBe(true);
    expect(isCollapsed({ "7": false }, 7)).toBe(false);
    expect(isCollapsed({ "7": false }, 8)).toBe(true);
  });

  it("round-trips per account and keeps accounts apart", () => {
    const storage = fakeStorage();
    const alice = withCollapsed(withCollapsed({}, 1, false), 2, true);
    writeCollapsed(storage, 11, alice);
    expect(readCollapsed(storage, 11)).toEqual({ "1": false, "2": true });
    expect(readCollapsed(storage, 22)).toEqual({});
    expect(storage.data[`${COLLAPSE_KEY}:11`]).toBeDefined();
  });

  it("applies a bulk collapse to the given groups only", () => {
    const map = withAllCollapsed({ "3": false }, [1, 2], true);
    expect(map).toEqual({ "3": false, "1": true, "2": true });
    const opened = withAllCollapsed(map, [1, 2], false);
    expect(opened).toEqual({ "3": false, "1": false, "2": false });
  });

  it("survives corrupt or unreadable storage", () => {
    expect(readCollapsed(fakeStorage({ [`${COLLAPSE_KEY}:5`]: "{not json" }), 5)).toEqual({});
    expect(readCollapsed(fakeStorage({ [`${COLLAPSE_KEY}:5`]: '"a string"' }), 5)).toEqual({});
    expect(readCollapsed(fakeStorage({ [`${COLLAPSE_KEY}:5`]: '{"1":"yes","2":true}' }), 5)).toEqual({
      "2": true,
    });
    expect(readCollapsed(throwingStorage(), 5)).toEqual({});
    expect(readCollapsed(null, 5)).toEqual({});
    expect(() => writeCollapsed(throwingStorage(), 5, { "1": true })).not.toThrow();
    expect(() => writeCollapsed(null, 5, { "1": true })).not.toThrow();
  });
});
