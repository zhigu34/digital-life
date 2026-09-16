import { advanceDate, iso, monthDays, money, labels } from "./domain";
import type { Records, Page } from "./types";

export type CalendarKind = "task" | "expense" | "milestone" | "maintenance";
export interface CalendarEvent {
  kind: CalendarKind;
  id: number;
  date: string;
  title: string;
  detail: string;
  overdue: boolean;
}
export const kindLabels: Record<CalendarKind, string> = {
  task: "待办",
  expense: "费用",
  milestone: "日子",
  maintenance: "维护",
};
export const kindPages: Record<CalendarKind, Page> = {
  task: "tasks",
  expense: "expenses",
  milestone: "milestones",
  maintenance: "maintenance",
};

export interface GridCell {
  date: string;
  day: number;
  inMonth: boolean;
}

/** Monday-first month grid; ISO dates so weeks render in stable order. */
export function monthGrid(year: number, month: number): GridCell[] {
  const leading = (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() + 6) % 7;
  const cells: GridCell[] = [];
  for (let offset = 0; offset < leading; offset++) {
    const d = new Date(Date.UTC(year, month - 1, 1 - leading + offset));
    cells.push({
      date: iso(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()),
      day: d.getUTCDate(),
      inMonth: false,
    });
  }
  for (let day = 1; day <= monthDays(year, month); day++) {
    cells.push({ date: iso(year, month, day), day, inMonth: true });
  }
  while (cells.length % 7 !== 0) {
    const trailing = cells.length - leading - monthDays(year, month) + 1;
    const d = new Date(Date.UTC(year, month, trailing));
    cells.push({
      date: iso(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()),
      day: d.getUTCDate(),
      inMonth: false,
    });
  }
  return cells;
}

/**
 * Due dates of an active expense within the target month. Occurrences extend
 * from next_due in whole periods without assuming payment, mirroring the
 * server-side "due this month" semantics, and keep the month-end anchor.
 */
export function expenseOccurrences(
  expense: {
    next_due: string;
    period_months: number;
    anchor_day: number;
    active: boolean;
  },
  year: number,
  month: number,
): string[] {
  if (!expense.active) return [];
  const [dueYear, dueMonth] = expense.next_due.split("-").map(Number);
  const monthIndex = year * 12 + month - 1;
  const dueIndex = dueYear! * 12 + dueMonth! - 1;
  const periodsBehind = Math.ceil((monthIndex - dueIndex) / expense.period_months);
  const start = Math.max(0, periodsBehind);
  const dates: string[] = [];
  for (let k = start; k - start < 4; k++) {
    const candidate = advanceDate(
      expense.next_due,
      k * expense.period_months,
      expense.anchor_day,
    );
    const [y, m] = candidate.split("-").map(Number);
    if (y! > year || (y! === year && m! > month)) break;
    if (y! === year && m! === month) dates.push(candidate);
  }
  return dates;
}

/** Date a milestone lands on in the target month, or null. */
export function milestoneOccurrence(
  milestone: { date: string; repeats_yearly: boolean },
  year: number,
  month: number,
): string | null {
  const [y, m, d] = milestone.date.split("-").map(Number);
  if (milestone.repeats_yearly) {
    if (m !== month) return null;
    return iso(year, month, Math.min(d!, monthDays(year, month)));
  }
  return y === year && m === month ? milestone.date : null;
}

const kindOrder: Record<CalendarKind, number> = {
  maintenance: 0,
  expense: 1,
  task: 2,
  milestone: 3,
};

export function buildCalendarEvents(
  records: Records,
  year: number,
  month: number,
  today: string,
): Map<string, CalendarEvent[]> {
  const events = new Map<string, CalendarEvent[]>();
  const add = (event: CalendarEvent) => {
    const list = events.get(event.date) ?? [];
    list.push(event);
    events.set(event.date, list);
  };
  for (const item of records.maintenance) {
    if (!item.active) continue;
    const [y, m] = item.next_due.split("-").map(Number);
    if (y === year && m === month)
      add({
        kind: "maintenance",
        id: item.id,
        date: item.next_due,
        title: item.title,
        detail: "维护到期",
        overdue: item.next_due < today,
      });
  }
  for (const item of records.expenses) {
    for (const date of expenseOccurrences(item, year, month))
      add({
        kind: "expense",
        id: item.id,
        date,
        title: item.title,
        detail: money(item.amount_cents, item.currency),
        overdue: date < today,
      });
  }
  for (const item of records.tasks) {
    if (item.status === "done" || !item.due_date) continue;
    const [y, m] = item.due_date.split("-").map(Number);
    if (y === year && m === month)
      add({
        kind: "task",
        id: item.id,
        date: item.due_date,
        title: item.title,
        detail: labels[item.priority],
        overdue: item.due_date < today,
      });
  }
  for (const item of records.milestones) {
    const date = milestoneOccurrence(item, year, month);
    if (date)
      add({
        kind: "milestone",
        id: item.id,
        date,
        title: item.title,
        detail: item.repeats_yearly ? "每年今天" : item.date,
        overdue: false,
      });
  }
  for (const list of events.values())
    list.sort(
      (a, b) =>
        Number(b.overdue) - Number(a.overdue) ||
        kindOrder[a.kind] - kindOrder[b.kind] ||
        a.title.localeCompare(b.title, "zh-CN"),
    );
  return events;
}
