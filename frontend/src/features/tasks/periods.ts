import type { GroupItem, RepeatUnit, TaskGroup } from "../../types";

/**
 * Period maths for long-term tasks. Nothing here talks to the network and
 * nothing is stored: a period is satisfied by any completion inside it, so the
 * state of a day, week or month is derived from the completion days the server
 * returns plus the user's "today".
 */

export type PeriodState = "done" | "missed" | "pending" | "before";

export interface PeriodSlot {
  /** First day of the period. */
  start: string;
  /** Last day of the period, inclusive. */
  end: string;
  state: PeriodState;
  /** Completions inside this period. */
  count: number;
  label: string;
  /** Short text for the grid cell. */
  cell: string;
}

function iso(day: Date): string {
  return day.toISOString().slice(0, 10);
}

export function shiftDate(date: string, days: number): string {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + days);
  return iso(day);
}

/** Monday of the week containing `date`; the app's calendars are Monday-first. */
export function weekStart(date: string): string {
  const day = new Date(`${date}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
  return iso(day);
}

export function periodStart(date: string, unit: RepeatUnit): string {
  if (unit === "day") return date;
  if (unit === "week") return weekStart(date);
  return `${date.slice(0, 7)}-01`;
}

export function periodEnd(start: string, unit: RepeatUnit): string {
  if (unit === "day") return start;
  if (unit === "week") return shiftDate(start, 6);
  const [year, month] = start.split("-").map(Number) as [number, number];
  return iso(new Date(Date.UTC(year, month, 0)));
}

export function previousPeriodStart(start: string, unit: RepeatUnit): string {
  if (unit === "day") return shiftDate(start, -1);
  if (unit === "week") return shiftDate(start, -7);
  const [year, month] = start.split("-").map(Number) as [number, number];
  return iso(new Date(Date.UTC(year, month - 2, 1)));
}

export function nextPeriodStart(start: string, unit: RepeatUnit): string {
  if (unit === "day") return shiftDate(start, 1);
  if (unit === "week") return shiftDate(start, 7);
  const [year, month] = start.split("-").map(Number) as [number, number];
  return iso(new Date(Date.UTC(year, month, 1)));
}

/** The `count` periods ending with the one that contains `today`, oldest first. */
export function recentPeriodStarts(today: string, unit: RepeatUnit, count: number): string[] {
  const starts = [periodStart(today, unit)];
  for (let index = 1; index < count; index++) {
    starts.push(previousPeriodStart(starts[index - 1]!, unit));
  }
  return starts.reverse();
}

export function completionCount(days: string[], start: string, end: string): number {
  return days.filter((day) => day >= start && day <= end).length;
}

/** ISO week number, so cross-year weeks label as 2026-W53 rather than W1. */
export function isoWeekNumber(date: string): number {
  const target = new Date(`${date}T00:00:00Z`);
  target.setUTCDate(target.getUTCDate() - ((target.getUTCDay() + 6) % 7) + 3);
  const firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4));
  firstThursday.setUTCDate(
    firstThursday.getUTCDate() - ((firstThursday.getUTCDay() + 6) % 7) + 3,
  );
  return 1 + Math.round((target.getTime() - firstThursday.getTime()) / (7 * 86400000));
}

export function shortDate(date: string): string {
  const [, month, day] = date.split("-").map(Number) as [number, number, number];
  return `${month} 月 ${day} 日`;
}

export function weekdayLabel(date: string): string {
  return ["日", "一", "二", "三", "四", "五", "六"][
    new Date(`${date}T12:00:00Z`).getUTCDay()
  ]!;
}

export function periodRangeLabel(start: string, unit: RepeatUnit): string {
  const end = periodEnd(start, unit);
  if (unit === "month") {
    const [year, month] = start.split("-").map(Number) as [number, number];
    return `${year} 年 ${month} 月`;
  }
  if (unit === "week") {
    // Same month reads better without repeating it: 9 月 21 日–27 日.
    const tail = start.slice(0, 7) === end.slice(0, 7) ? `${Number(end.slice(8))} 日` : shortDate(end);
    return `${shortDate(start)}–${tail}`;
  }
  return shortDate(start);
}

/** Heading such as "本周 · 9 月 21 日–27 日" or "第 38 周 · 9 月 14 日–20 日". */
export function periodHeading(start: string, unit: RepeatUnit, today: string): string {
  const current = periodStart(today, unit) === start;
  if (unit === "day") return current ? `今天 · ${shortDate(start)}` : shortDate(start);
  if (unit === "week") {
    const name = current ? "本周" : `第 ${isoWeekNumber(start)} 周`;
    return `${name} · ${periodRangeLabel(start, "week")}`;
  }
  return `${current ? "本月 · " : ""}${periodRangeLabel(start, "month")}`;
}

export function cellText(start: string, unit: RepeatUnit): string {
  if (unit === "day") return weekdayLabel(start);
  if (unit === "week") return String(isoWeekNumber(start));
  return String(Number(start.slice(5, 7)));
}

/** How many periods a card shows: days, weeks or months. */
export function gridCount(unit: RepeatUnit): number {
  if (unit === "day") return 14;
  return unit === "week" ? 8 : 6;
}

/** Window used for the hit rate: finished periods only. */
export function rateWindow(unit: RepeatUnit): number {
  if (unit === "day") return 30;
  return unit === "week" ? 8 : 6;
}

/**
 * A recorded completion is a fact and always wins: a day filled in before the
 * item's start date still shows as done (and keeps the streak alive). Only the
 * *empty* periods are classified, and those are expected once they reach the
 * start date and until the group is archived — outside that they are neither
 * satisfied nor missed.
 */
export function periodState(
  item: GroupItem,
  start: string,
  today: string,
  archivedOn?: string | null,
): PeriodState {
  const end = periodEnd(start, item.repeat_unit);
  if (completionCount(item.recent_days, start, end) > 0) return "done";
  if (end < item.start_date) return "before";
  if (archivedOn && start > archivedOn) return "before";
  return end < today ? "missed" : "pending";
}

export function periodSlot(
  item: GroupItem,
  start: string,
  today: string,
  archivedOn?: string | null,
): PeriodSlot {
  const end = periodEnd(start, item.repeat_unit);
  return {
    start,
    end,
    state: periodState(item, start, today, archivedOn),
    count: completionCount(item.recent_days, start, end),
    label: periodHeading(start, item.repeat_unit, today),
    cell: cellText(start, item.repeat_unit),
  };
}

export function slotsFor(
  item: GroupItem,
  today: string,
  count: number,
  archivedOn?: string | null,
): PeriodSlot[] {
  return recentPeriodStarts(today, item.repeat_unit, count).map((start) =>
    periodSlot(item, start, today, archivedOn),
  );
}

export function currentSlot(
  item: GroupItem,
  today: string,
  archivedOn?: string | null,
): PeriodSlot {
  return periodSlot(item, periodStart(today, item.repeat_unit), today, archivedOn);
}

/**
 * Consecutive satisfied periods. An unfinished current period does not break the
 * run — a week item checked on Monday keeps its streak through Sunday.
 */
export function streak(item: GroupItem, today: string, archivedOn?: string | null): number {
  let cursor = periodStart(today, item.repeat_unit);
  if (periodState(item, cursor, today, archivedOn) !== "done") {
    cursor = previousPeriodStart(cursor, item.repeat_unit);
  }
  let total = 0;
  while (periodState(item, cursor, today, archivedOn) === "done") {
    total += 1;
    cursor = previousPeriodStart(cursor, item.repeat_unit);
  }
  return total;
}

/** Satisfied finished periods over the unit's window; the current one is open. */
export function hitRate(
  item: GroupItem,
  today: string,
  archivedOn?: string | null,
): { done: number; expected: number } {
  const window = rateWindow(item.repeat_unit);
  const starts = recentPeriodStarts(today, item.repeat_unit, window + 1).slice(0, window);
  let done = 0;
  let expected = 0;
  for (const start of starts) {
    const state = periodState(item, start, today, archivedOn);
    if (state === "before") continue;
    expected += 1;
    if (state === "done") done += 1;
  }
  return { done, expected };
}

/** True when the item still needs attention in the period running right now. */
export function needsAttention(
  item: GroupItem,
  today: string,
  archivedOn?: string | null,
): boolean {
  return currentSlot(item, today, archivedOn).state === "pending";
}

export function streakUnit(unit: RepeatUnit): string {
  if (unit === "day") return "天";
  return unit === "week" ? "周" : "个月";
}

export function repeatLabel(unit: RepeatUnit): string {
  if (unit === "day") return "每天";
  return unit === "week" ? "本周内完成" : "本月内完成";
}

/** How many items owe work in the period running now, and how many delivered. */
export function groupProgress(
  group: TaskGroup,
  today: string,
): { satisfied: number; expected: number } {
  let satisfied = 0;
  let expected = 0;
  for (const item of group.items) {
    const state = currentSlot(item, today, group.archived_on).state;
    if (state === "done") satisfied += 1;
    if (state !== "before") expected += 1;
  }
  return { satisfied, expected };
}

export interface GroupStats {
  /** Earliest known day: the first completion, or the earliest start date. */
  since: string | null;
  sustainedDays: number;
  lastOn: string | null;
  daysSinceLast: number | null;
  totalCount: number;
  satisfied: number;
  expected: number;
}

function daysBetween(from: string, to: string): number {
  return Math.round(
    (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86400000,
  );
}

/**
 * The time dimension of a group: how long it has been running, when it was last
 * touched, and how much has been recorded. Derived from completion dates only —
 * nothing extra is stored for it.
 *
 * An archived group stops counting on its archiving day, so a finished group
 * keeps a frozen "已坚持" figure instead of growing forever.
 */
export function groupStats(group: TaskGroup, today: string): GroupStats {
  const lastOn = group.items
    .flatMap((item) => item.recent_days)
    .reduce<string | null>((latest, day) => (!latest || day > latest ? day : latest), null);
  const starts = group.items.map((item) => item.start_date);
  const candidates = lastOn ? [...starts, lastOn] : starts;
  const since = candidates.length ? candidates.reduce((a, b) => (a < b ? a : b)) : null;
  const until = group.archived_on && group.archived_on < today ? group.archived_on : today;
  const sustainedDays = since && since <= until ? daysBetween(since, until) + 1 : 0;
  const progress = groupProgress(group, today);
  return {
    since,
    sustainedDays,
    lastOn,
    daysSinceLast: lastOn ? daysBetween(lastOn, today) : null,
    totalCount: group.items.reduce((sum, item) => sum + item.total_count, 0),
    satisfied: progress.satisfied,
    expected: progress.expected,
  };
}

/** "今天 / 昨天 / 3 天前 / 还没有" — the collapsed row shows this live. */
export function lastActivityLabel(stats: GroupStats): string {
  if (!stats.lastOn || stats.daysSinceLast === null) return "还没有打卡";
  if (stats.daysSinceLast <= 0) return "最近打卡：今天";
  if (stats.daysSinceLast === 1) return "最近打卡：昨天";
  return `最近打卡：${stats.daysSinceLast} 天前`;
}
