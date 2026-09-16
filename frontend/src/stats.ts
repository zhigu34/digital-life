import type { Stats, StatsMonth } from "./types";

/** Short month label; the first bar and every January also carry the year. */
export function monthLabel(month: string, isFirst: boolean): string {
  const [year, number] = month.split("-");
  const label = `${Number(number)}月`;
  return isFirst || number === "01" ? `${year!.slice(2)}年${label}` : label;
}

export function fullMonthLabel(month: string): string {
  return `${month.slice(0, 4)}年${Number(month.slice(5))}月`;
}

/** Currencies that actually appear in the chosen metric, CNY first. */
export function metricCurrencies(
  months: StatsMonth[],
  key: "expense_due" | "maintenance_cost",
): string[] {
  const found = new Set<string>();
  for (const entry of months)
    for (const currency of Object.keys(entry[key])) found.add(currency);
  return [...found].sort((a, b) =>
    a === "CNY" ? -1 : b === "CNY" ? 1 : a.localeCompare(b),
  );
}

export interface TrendPoint {
  label: string;
  value: number;
  title: string;
}

export function monthTrend(
  stats: Stats,
  key: "expense_due" | "maintenance_cost",
  currency: string,
  format: (value: number, currency: string) => string,
): TrendPoint[] {
  return stats.months.map((entry, index) => {
    const value = entry[key][currency] ?? 0;
    return {
      label: monthLabel(entry.month, index === 0),
      value,
      title: `${fullMonthLabel(entry.month)} ${format(value, currency)}`,
    };
  });
}

export function trendTotal(points: TrendPoint[]): number {
  return points.reduce((sum, point) => sum + point.value, 0);
}
