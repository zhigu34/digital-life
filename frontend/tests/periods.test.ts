import { describe, expect, it } from "vitest";
import {
  cellText,
  completionCount,
  currentSlot,
  hitRate,
  isoWeekNumber,
  needsAttention,
  periodEnd,
  periodHeading,
  periodStart,
  recentPeriodStarts,
  shiftDate,
  slotsFor,
  streak,
  weekStart,
} from "../src/features/tasks/periods";
import type { GroupItem, RepeatUnit } from "../src/types";

function item(overrides: Partial<GroupItem> = {}): GroupItem {
  return {
    id: 1,
    group_id: 1,
    title: "跑步 30 分钟",
    repeat_unit: "day",
    start_date: "2026-09-01",
    created_at: "2026-09-01T00:00:00",
    recent_days: [],
    total_count: 0,
    ...overrides,
  };
}

describe("date helpers", () => {
  it("shifts across month and year boundaries", () => {
    expect(shiftDate("2026-09-30", 1)).toBe("2026-10-01");
    expect(shiftDate("2026-01-01", -1)).toBe("2025-12-31");
    expect(shiftDate("2028-02-28", 1)).toBe("2028-02-29");
  });

  it("starts every week on Monday", () => {
    expect(weekStart("2026-09-26")).toBe("2026-09-21"); // Saturday
    expect(weekStart("2026-09-21")).toBe("2026-09-21"); // Monday is its own start
    expect(weekStart("2026-09-27")).toBe("2026-09-21"); // Sunday belongs to the same week
    expect(weekStart("2027-01-01")).toBe("2026-12-28"); // crosses the year boundary
  });

  it("closes periods on their real last day", () => {
    expect(periodEnd("2026-02-01", "month")).toBe("2026-02-28");
    expect(periodEnd("2028-02-01", "month")).toBe("2028-02-29");
    expect(periodEnd("2026-09-01", "month")).toBe("2026-09-30");
    expect(periodEnd("2026-09-21", "week")).toBe("2026-09-27");
    expect(periodEnd("2026-09-26", "day")).toBe("2026-09-26");
  });

  it("numbers ISO weeks across the year boundary", () => {
    expect(isoWeekNumber("2026-01-01")).toBe(1);
    expect(isoWeekNumber("2026-09-21")).toBe(39);
    expect(isoWeekNumber("2026-12-31")).toBe(53);
    expect(isoWeekNumber("2027-01-01")).toBe(53); // still the previous ISO year
    expect(isoWeekNumber("2027-01-04")).toBe(1);
  });
});

describe("period grid", () => {
  it("walks months backwards through the year boundary", () => {
    expect(recentPeriodStarts("2026-01-15", "month", 3)).toEqual([
      "2025-11-01",
      "2025-12-01",
      "2026-01-01",
    ]);
    expect(recentPeriodStarts("2027-01-02", "week", 3)).toEqual([
      "2026-12-14",
      "2026-12-21",
      "2026-12-28",
    ]);
    expect(recentPeriodStarts("2026-09-26", "day", 3)).toEqual([
      "2026-09-24",
      "2026-09-25",
      "2026-09-26",
    ]);
  });

  it("builds contiguous grids per unit, oldest first", () => {
    const days = slotsFor(item(), "2026-09-26", 14);
    expect(days).toHaveLength(14);
    expect(days[0]!.start).toBe("2026-09-13");
    expect(days[13]!.start).toBe("2026-09-26");
    expect(days.at(-1)!.label).toBe("今天 · 9 月 26 日");
    expect(cellText("2026-09-26", "day")).toBe("六");

    const weeks = slotsFor(item({ repeat_unit: "week" }), "2026-09-26", 8);
    expect(weeks).toHaveLength(8);
    expect(weeks[0]!.start).toBe("2026-08-03");
    expect(weeks.at(-1)!.start).toBe("2026-09-21");
    expect(weeks.at(-1)!.label).toBe("本周 · 9 月 21 日–27 日");
    expect(cellText("2026-09-21", "week")).toBe("39");
    expect(weeks[6]!.label).toBe("第 38 周 · 9 月 14 日–20 日");

    const months = slotsFor(item({ repeat_unit: "month" }), "2026-09-26", 6);
    expect(months).toHaveLength(6);
    expect(months[0]!.start).toBe("2026-04-01");
    expect(months.at(-1)!.label).toBe("本月 · 2026 年 9 月");
    expect(cellText("2026-04-01", "month")).toBe("4");
  });
});

describe("period state", () => {
  const today = "2026-09-26";

  it("reads a satisfied period from any completion inside it", () => {
    const weekly = item({
      repeat_unit: "week" as RepeatUnit,
      recent_days: ["2026-09-14"], // previous week
    });
    expect(currentSlot(weekly, today).state).toBe("pending");
    expect(slotsFor(weekly, today, 2)[0]!.state).toBe("done");
    expect(slotsFor(weekly, today, 2)[0]!.count).toBe(1);
  });

  it("counts every completion inside the period", () => {
    const weekly = item({
      repeat_unit: "week",
      recent_days: ["2026-09-21", "2026-09-23", "2026-09-26"],
    });
    expect(currentSlot(weekly, today).count).toBe(3);
    expect(currentSlot(weekly, today).state).toBe("done");
  });

  it("never calls the running period missed", () => {
    // Monday morning: the week has barely started and must not look failed.
    expect(currentSlot(item({ repeat_unit: "week" }), "2026-09-21").state).toBe("pending");
    expect(currentSlot(item({ repeat_unit: "month" }), "2026-09-01").state).toBe("pending");
  });

  it("marks a finished period without completions as missed", () => {
    const slots = slotsFor(item(), today, 3);
    expect(slots.map((slot) => slot.state)).toEqual(["missed", "missed", "pending"]);
  });

  it("ignores periods before the start date and after archiving", () => {
    const late = item({ start_date: "2026-09-21" });
    const slots = slotsFor(late, today, 14);
    expect(slots[0]!.state).toBe("before");
    expect(slots[13]!.state).toBe("pending");

    // The archiving day is still expected; later periods are not.
    const archived = item({ start_date: "2026-09-21", recent_days: ["2026-09-22"] });
    const after = slotsFor(archived, today, 5, "2026-09-23");
    expect(after.map((slot) => slot.state)).toEqual([
      "done",
      "missed",
      "before",
      "before",
      "before",
    ]);
  });
});

describe("metrics", () => {
  const today = "2026-09-26";

  it("keeps a streak alive while the current period is open", () => {
    const daily = item({
      recent_days: ["2026-09-24", "2026-09-25"],
      start_date: "2026-09-24",
    });
    expect(completionCount(daily.recent_days, "2026-09-24", "2026-09-25")).toBe(2);
    // Today is still open, so it neither counts nor breaks the run.
    expect(streak(daily, today)).toBe(2);
  });

  it("counts a day filled in before the start date", () => {
    // An item created today but backfilled for yesterday: the record is a fact,
    // so the cell shows as done and the streak includes it.
    const daily = item({
      start_date: today,
      recent_days: ["2026-09-25", "2026-09-26"],
    });
    expect(slotsFor(daily, today, 3).map((slot) => slot.state)).toEqual([
      "before",
      "done",
      "done",
    ]);
    expect(streak(daily, today)).toBe(2);
  });

  it("resets the streak on the first missed period", () => {
    const daily = item({
      recent_days: ["2026-09-20", "2026-09-21", "2026-09-24", "2026-09-25", "2026-09-26"],
      start_date: "2026-09-20",
    });
    expect(streak(daily, today)).toBe(3);
  });

  it("counts streak in whole periods for weekly and monthly items", () => {
    const weekly = item({
      repeat_unit: "week",
      start_date: "2026-09-14",
      recent_days: ["2026-09-14", "2026-09-21"],
    });
    expect(streak(weekly, today)).toBe(2);

    const monthly = item({
      repeat_unit: "month",
      start_date: "2026-07-01",
      recent_days: ["2026-07-04", "2026-09-02"],
    });
    expect(streak(monthly, today)).toBe(1);
  });

  it("rates only finished, expected periods", () => {
    const daily = item({
      start_date: "2026-09-24",
      recent_days: ["2026-09-24", "2026-09-25", "2026-09-26"],
    });
    // 24th and 25th are finished and satisfied; the running 26th is excluded,
    // and the days before the start date never enter the denominator.
    expect(hitRate(daily, today)).toEqual({ done: 2, expected: 2 });

    const weekly = item({
      repeat_unit: "week",
      start_date: "2026-08-03",
      recent_days: ["2026-08-03", "2026-08-10", "2026-08-24", "2026-09-21"],
    });
    // Eight finished weeks are examined, but the oldest starts before the item
    // did, so it never enters the denominator; today's week is still open.
    expect(hitRate(weekly, today)).toEqual({ done: 3, expected: 7 });
  });

  it("flags only items that still owe work in the running period", () => {
    expect(needsAttention(item({ repeat_unit: "week" }), today)).toBe(true);
    expect(needsAttention(item({ recent_days: [today] }), today)).toBe(false);
    expect(needsAttention(item({ repeat_unit: "week" }), today, "2026-09-20")).toBe(false);
    expect(periodStart(today, "month")).toBe("2026-09-01");
    expect(periodHeading("2026-09-01", "month", today)).toBe("本月 · 2026 年 9 月");
  });
});
