import { describe, it, expect } from "vitest";
import {
  shiftDate,
  currentStreak,
  lastDays,
  countInRange,
  weekdayLabel,
  daysSinceLastCheck,
} from "../src/checkin";
import type { CheckInItem } from "../src/types";

const item = (days: string[]): CheckInItem => ({
  id: 1,
  title: "健身1小时",
  notes: "",
  kind: "daily",
  active: true,
  created_at: "2026-09-01T00:00:00Z",
  days,
  total_count: days.length,
});

describe("check-in helpers", () => {
  it("shifts dates across month and year boundaries", () => {
    expect(shiftDate("2026-03-01", -1)).toBe("2026-02-28");
    expect(shiftDate("2026-12-31", 1)).toBe("2027-01-01");
  });
  it("counts a streak ending today and keeps yesterday's run alive", () => {
    expect(currentStreak(["2026-09-14", "2026-09-15", "2026-09-16"], "2026-09-16")).toBe(3);
    expect(currentStreak(["2026-09-14", "2026-09-15"], "2026-09-16")).toBe(2);
    expect(currentStreak(["2026-09-13", "2026-09-14"], "2026-09-16")).toBe(0);
    expect(currentStreak(["2026-09-16"], "2026-09-16")).toBe(1);
    expect(currentStreak([], "2026-09-16")).toBe(0);
  });
  it("lists the last days oldest first and counts within a range", () => {
    expect(lastDays("2026-09-16", 7)).toEqual([
      "2026-09-10",
      "2026-09-11",
      "2026-09-12",
      "2026-09-13",
      "2026-09-14",
      "2026-09-15",
      "2026-09-16",
    ]);
    expect(countInRange(["2026-09-10", "2026-09-16", "2026-09-20"], "2026-09-10", "2026-09-16")).toBe(2);
  });
  it("labels weekdays and reports distance to the latest check", () => {
    expect(weekdayLabel("2026-09-16")).toBe("三");
    expect(weekdayLabel("2026-09-13")).toBe("日");
    expect(daysSinceLastCheck(item(["2026-09-14"]), "2026-09-16")).toBe(2);
    expect(daysSinceLastCheck(item(["2026-09-16"]), "2026-09-16")).toBe(0);
    expect(daysSinceLastCheck(item([]), "2026-09-16")).toBeNull();
  });
});
