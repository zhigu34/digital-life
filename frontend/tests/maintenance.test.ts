import { describe, expect, it } from "vitest";
import {
  nextMaintenanceDate,
  maintenanceTiming,
  maintenanceReminders,
} from "../src/maintenance";
import { calendarDate } from "../src/domain";
const item = {
  id: 1,
  title: "净水器滤芯",
  notes: "",
  period_value: 1,
  period_unit: "months" as const,
  remind_days: 7,
  active: true,
  last_completed: "2026-01-31",
  next_due: "2026-02-28",
};
describe("maintenance calendar recurrence", () => {
  it("uses the actual completion day for each month, without a billing anchor", () => {
    expect(nextMaintenanceDate("2026-01-31", 1, "months")).toBe("2026-02-28");
    expect(nextMaintenanceDate("2026-02-28", 1, "months")).toBe("2026-03-28");
    expect(nextMaintenanceDate("2000-01-31", 1, "months")).toBe("2000-02-29");
  });
  it("adds calendar days across DST and leap boundaries", () => {
    expect(nextMaintenanceDate("2026-03-07", 2, "days")).toBe("2026-03-09");
    expect(nextMaintenanceDate("2024-02-28", 2, "days")).toBe("2024-03-01");
  });
  it("rejects overflow and periods outside the API contract", () => {
    expect(() => nextMaintenanceDate("9999-12-31", 1, "days")).toThrow();
    expect(() => nextMaintenanceDate("9999-12-31", 1, "months")).toThrow();
    expect(() => nextMaintenanceDate("2026-01-01", 121, "months")).toThrow();
    expect(() => nextMaintenanceDate("2026-01-01", 1.5, "days")).toThrow();
  });
});
describe("maintenance reminder display", () => {
  it("uses the account calendar date and includes the exact reminder boundary", () => {
    const today = calendarDate(
      "Asia/Shanghai",
      new Date("2026-02-20T23:00:00Z"),
    );
    expect(maintenanceTiming(item, today)).toEqual({
      elapsed: 21,
      remaining: 7,
      label: "剩余 7 天",
      remind: true,
    });
    expect(maintenanceTiming(item, "2026-02-20").remind).toBe(false);
  });
  it("distinguishes due today, overdue and inactive items", () => {
    expect(maintenanceTiming(item, "2026-02-28").label).toBe("今天到期");
    expect(maintenanceTiming(item, "2026-03-02").label).toBe("逾期 2 天");
    expect(maintenanceTiming({ ...item, active: false }, "2026-03-02")).toEqual(
      { elapsed: 30, remaining: -2, label: "已停用", remind: false },
    );
  });
  it("removes inactive and distant reminders, sorts most overdue first", () => {
    expect(
      maintenanceReminders(
        [
          item,
          { ...item, id: 2, next_due: "2026-02-15" },
          { ...item, id: 3, active: false },
          { ...item, id: 4, next_due: "2026-03-01" },
        ],
        "2026-02-21",
      ).map((x) => x.id),
    ).toEqual([2, 1]);
  });
});
