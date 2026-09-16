import { describe, it, expect } from "vitest";
import {
  monthLabel,
  fullMonthLabel,
  metricCurrencies,
  monthTrend,
  trendTotal,
} from "../src/stats";
import type { Stats } from "../src/types";

const stats = (): Stats => ({
  months: [
    { month: "2025-10", expense_due: { CNY: 3000 }, maintenance_cost: {} },
    { month: "2025-11", expense_due: { CNY: 3000, USD: 1500 }, maintenance_cost: {} },
    { month: "2025-12", expense_due: { CNY: 3000 }, maintenance_cost: { CNY: 8000 } },
    { month: "2026-01", expense_due: {}, maintenance_cost: {} },
  ],
  shows: { watching: 1, planned: 2, completed: 3, paused: 0, episodes_watched: 41 },
});

describe("stats helpers", () => {
  it("labels the first bar and each January with the year", () => {
    expect(monthLabel("2025-10", true)).toBe("25年10月");
    expect(monthLabel("2025-11", false)).toBe("11月");
    expect(monthLabel("2026-01", false)).toBe("26年1月");
    expect(fullMonthLabel("2026-09")).toBe("2026年9月");
  });
  it("collects currencies with CNY first", () => {
    expect(metricCurrencies(stats().months, "expense_due")).toEqual([
      "CNY",
      "USD",
    ]);
    expect(metricCurrencies(stats().months, "maintenance_cost")).toEqual([
      "CNY",
    ]);
  });
  it("builds a month trend and totals it", () => {
    const points = monthTrend(stats(), "expense_due", "CNY", (v) => `${v}`);
    expect(points.map((point) => point.value)).toEqual([3000, 3000, 3000, 0]);
    expect(points[0]).toMatchObject({ label: "25年10月", title: "2025年10月 3000" });
    expect(trendTotal(points)).toBe(9000);
  });
});
