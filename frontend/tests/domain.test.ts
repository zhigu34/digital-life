import { describe, it, expect } from "vitest";
import {
  browserTimezone,
  calendarDate,
  daysBetween,
  countdown,
  advanceDate,
  monthlyCost,
  expenseSummary,
} from "../src/domain";
describe("calendar calculations", () => {
  it("uses the profile timezone across UTC midnight", () => {
    expect(
      calendarDate("Asia/Shanghai", new Date("2026-09-13T23:30:00Z")),
    ).toBe("2026-09-14");
    expect(
      calendarDate("America/Los_Angeles", new Date("2026-09-13T23:30:00Z")),
    ).toBe("2026-09-13");
  });
  it("counts calendar days rather than DST hours", () => {
    expect(daysBetween("2024-03-09", "2024-03-11")).toBe(2);
    expect(daysBetween("2000-02-28", "2000-03-01")).toBe(2);
  });
  it("observes leap-day anniversaries on February 28 and rolls after today", () => {
    expect(countdown("2020-02-29", true, "2025-02-27")).toBe(1);
    expect(countdown("2020-02-29", true, "2025-02-28")).toBe(0);
    expect(countdown("2020-02-29", true, "2025-03-01")).toBe(364);
    expect(countdown("2020-02-29", true, "2028-02-28")).toBe(1);
    expect(countdown("2020-02-29", false, "2025-03-01")).toBeLessThan(0);
  });
  it("preserves month-end anchors", () => {
    expect(advanceDate("2027-01-31", 1, 31)).toBe("2027-02-28");
    expect(advanceDate("2027-02-28", 1, 31)).toBe("2027-03-31");
  });
});
describe("expense summaries", () => {
  it("normalizes yearly costs to monthly cents", () =>
    expect(monthlyCost({ amount_cents: 12000, period_months: 12 })).toBe(1000));
  it("groups currencies, excludes inactive, distinguishes cost and current-month dues", () => {
    const base = {
      amount_cents: 12000,
      period_months: 12,
      next_due: "2026-09-20",
      anchor_day: 20,
      active: true,
      currency: "CNY",
    };
    expect(
      expenseSummary(
        [
          base,
          { ...base, currency: "USD", next_due: "2026-10-20" },
          { ...base, active: false },
        ],
        "2026-09-14",
      ),
    ).toEqual([
      { currency: "CNY", monthly: 1000, due: 12000 },
      { currency: "USD", monthly: 1000, due: 0 },
    ]);
  });
  it("finds current-month occurrence even when next unpaid date is overdue", () => {
    expect(
      expenseSummary(
        [
          {
            amount_cents: 1000,
            period_months: 1,
            next_due: "2026-01-31",
            anchor_day: 31,
            active: true,
            currency: "CNY",
          },
        ],
        "2026-09-14",
      )[0]?.due,
    ).toBe(1000);
  });
});
it("does not invent annual milestones before their first date", () => {
  expect(countdown("2030-10-01", true, "2026-09-14")).toBe(
    daysBetween("2026-09-14", "2030-10-01"),
  );
});
it("preserves years before 0100 when advancing months", () => {
  expect(advanceDate("0001-01-31", 1, 31)).toBe("0001-02-28");
  expect(advanceDate("0004-01-31", 1, 31)).toBe("0004-02-29");
});

describe('persisted timezone compatibility', () => {
  it('keeps the workspace usable when an old stored zone is unsupported by Intl', () => {
    expect(browserTimezone('Factory')).toBe('UTC')
    expect(calendarDate('Factory', new Date('2026-09-13T23:30:00Z'))).toBe('2026-09-13')
  })
})
