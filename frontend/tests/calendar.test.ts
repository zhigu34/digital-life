import { describe, it, expect } from "vitest";
import {
  monthGrid,
  expenseOccurrences,
  milestoneOccurrence,
  buildCalendarEvents,
} from "../src/calendar";
import type { Records } from "../src/types";

const emptyRecords = (): Records => ({
  tasks: [],
  expenses: [],
  shows: [],
  milestones: [],
  maintenance: [],
  notes: [],
});

describe("calendar month grid", () => {
  it("lays out September 2026 Monday-first with trailing October days", () => {
    const cells = monthGrid(2026, 9);
    expect(cells).toHaveLength(35);
    expect(cells[0]).toEqual({ date: "2026-08-31", day: 31, inMonth: false });
    expect(cells[1]).toEqual({ date: "2026-09-01", day: 1, inMonth: true });
    expect(cells[30]).toEqual({ date: "2026-09-30", day: 30, inMonth: true });
    expect(cells[34]).toEqual({ date: "2026-10-04", day: 4, inMonth: false });
  });
  it("starts a month exactly on Monday without padding", () => {
    // 2026-06-01 is a Monday.
    const cells = monthGrid(2026, 6);
    expect(cells[0]).toEqual({ date: "2026-06-01", day: 1, inMonth: true });
    expect(cells.every((cell) => cell.inMonth || cell.date > "2026-06-30")).toBe(
      true,
    );
  });
});

describe("expense occurrences", () => {
  it("marks the current month from a monthly expense", () => {
    expect(
      expenseOccurrences(
        {
          next_due: "2026-09-10",
          period_months: 1,
          anchor_day: 10,
          active: true,
        },
        2026,
        9,
      ),
    ).toEqual(["2026-09-10"]);
  });
  it("extrapolates quarterly occurrences without assuming payment", () => {
    const expense = {
      next_due: "2026-01-15",
      period_months: 3,
      anchor_day: 15,
      active: true,
    };
    expect(expenseOccurrences(expense, 2026, 7)).toEqual(["2026-07-15"]);
    expect(expenseOccurrences(expense, 2026, 9)).toEqual([]);
    expect(expenseOccurrences(expense, 2027, 1)).toEqual(["2027-01-15"]);
  });
  it("keeps the month-end anchor like the pay action does", () => {
    expect(
      expenseOccurrences(
        {
          next_due: "2026-01-31",
          period_months: 1,
          anchor_day: 31,
          active: true,
        },
        2026,
        2,
      ),
    ).toEqual(["2026-02-28"]);
    expect(
      expenseOccurrences(
        {
          next_due: "2026-01-31",
          period_months: 1,
          anchor_day: 31,
          active: true,
        },
        2026,
        3,
      ),
    ).toEqual(["2026-03-31"]);
  });
  it("skips inactive expenses and future-only months", () => {
    expect(
      expenseOccurrences(
        {
          next_due: "2026-09-10",
          period_months: 1,
          anchor_day: 10,
          active: false,
        },
        2026,
        9,
      ),
    ).toEqual([]);
    expect(
      expenseOccurrences(
        {
          next_due: "2026-12-10",
          period_months: 12,
          anchor_day: 10,
          active: true,
        },
        2026,
        9,
      ),
    ).toEqual([]);
  });
});

describe("milestone occurrences", () => {
    it("clamps yearly leap-day milestones to February 28 in common years", () => {
    expect(milestoneOccurrence({ date: "2020-02-29", repeats_yearly: true }, 2026, 2)).toBe(
      "2026-02-28",
    );
    expect(milestoneOccurrence({ date: "2020-02-29", repeats_yearly: true }, 2028, 2)).toBe(
      "2028-02-29",
    );
  });
  it("shows one-off milestones only on their exact month", () => {
    expect(milestoneOccurrence({ date: "2026-10-01", repeats_yearly: false }, 2026, 10)).toBe(
      "2026-10-01",
    );
    expect(milestoneOccurrence({ date: "2026-10-01", repeats_yearly: false }, 2027, 10)).toBeNull();
    expect(milestoneOccurrence({ date: "2026-05-05", repeats_yearly: true }, 2026, 6)).toBeNull();
  });
});

describe("calendar events", () => {
  const today = "2026-09-16";
  it("collects due items across collections and flags overdue ones first", () => {
    const records = emptyRecords();
    records.tasks.push(
      {
        id: 1,
        title: "过期任务",
        notes: "",
        status: "todo",
        due_date: "2026-09-10",
        priority: "high",
        created_at: "2026-09-01T00:00:00Z",
      },
      {
        id: 2,
        title: "已完成任务",
        notes: "",
        status: "done",
        due_date: "2026-09-11",
        priority: "normal",
        created_at: "2026-09-01T00:00:00Z",
      },
    );
    records.expenses.push({
      id: 3,
      title: "视频会员",
      amount_cents: 2500,
      currency: "CNY",
      period_months: 1,
      next_due: "2026-09-20",
      anchor_day: 20,
      active: true,
      notes: "",
    });
    records.maintenance.push(
      {
        id: 4,
        title: "滤芯",
        notes: "",
        period_value: 6,
        period_unit: "months",
        remind_days: 14,
        active: true,
        last_completed: "2026-03-15",
        next_due: "2026-09-15",
      },
      {
        id: 5,
        title: "停用事项",
        notes: "",
        period_value: 1,
        period_unit: "months",
        remind_days: 0,
        active: false,
        last_completed: "2026-08-01",
        next_due: "2026-09-01",
      },
    );
    records.milestones.push({
      id: 6,
      title: "领证纪念日",
      date: "2020-09-21",
      repeats_yearly: true,
      notes: "",
    });
    const events = buildCalendarEvents(records, 2026, 9, today);
    expect(events.get("2026-09-10")?.map((event) => event.title)).toEqual([
      "过期任务",
    ]);
    expect(events.get("2026-09-10")?.[0]?.overdue).toBe(true);
    expect(events.get("2026-09-11")).toBeUndefined();
    expect(events.get("2026-09-15")?.[0]?.kind).toBe("maintenance");
    expect(events.get("2026-09-20")?.[0]?.detail).toBe("¥25.00");
    expect(events.get("2026-09-21")?.[0]?.title).toBe("领证纪念日");
    const mixed = events.get("2026-09-15")!;
    expect(mixed.every((event) => event.kind !== "maintenance" || event.overdue)).toBe(true);
  });
});
