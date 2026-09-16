import type { CheckInItem } from "./types";

export function shiftDate(date: string, delta: number): string {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + delta);
  return day.toISOString().slice(0, 10);
}

/**
 * Consecutive checked days ending today. An unchecked today keeps the run
 * alive through yesterday; once yesterday is also missing the streak resets.
 */
export function currentStreak(days: string[], today: string): number {
  const checked = new Set(days);
  let cursor = checked.has(today) ? today : shiftDate(today, -1);
  if (!checked.has(cursor)) return 0;
  let streak = 0;
  while (checked.has(cursor)) {
    streak += 1;
    cursor = shiftDate(cursor, -1);
  }
  return streak;
}

/** The most recent `count` calendar days ending today, oldest first. */
export function lastDays(today: string, count: number): string[] {
  return Array.from({ length: count }, (_, index) => shiftDate(today, index - count + 1));
}

export function countInRange(days: string[], from: string, to: string): number {
  return days.filter((day) => day >= from && day <= to).length;
}

export function weekdayLabel(date: string): string {
  return ["日", "一", "二", "三", "四", "五", "六"][
    new Date(`${date}T12:00:00Z`).getUTCDay()
  ]!;
}

export function isDoneToday(item: CheckInItem, today: string): boolean {
  return item.days.includes(today);
}

/** Days since the latest check-in; null when never checked. */
export function daysSinceLastCheck(item: CheckInItem, today: string): number | null {
  if (!item.days.length) return null;
  const latest = item.days[item.days.length - 1]!;
  return Math.round(
    (Date.parse(`${today}T00:00:00Z`) - Date.parse(`${latest}T00:00:00Z`)) / 86400000,
  );
}
