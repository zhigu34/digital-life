export function browserTimezone(timezone: string): string {
  if (["Factory", "localtime", "posixrules"].includes(timezone) || /^(posix|right)\//.test(timezone)) return "UTC";
  try {
    new Intl.DateTimeFormat("en", { timeZone: timezone });
    return timezone;
  } catch {
    return "UTC";
  }
}
export function calendarDate(timezone: string, now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: browserTimezone(timezone),
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}
const stamp = (date: string) => Date.parse(`${date}T00:00:00Z`);
export function daysBetween(from: string, to: string): number {
  return Math.round((stamp(to) - stamp(from)) / 86400000);
}
export const iso = (year: number, month: number, day: number) =>
  `${year.toString().padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
export const monthDays = (year: number, month: number) =>
  month === 2
    ? year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
      ? 29
      : 28
    : [4, 6, 9, 11].includes(month)
      ? 30
      : 31;
export function advanceDate(
  date: string,
  months: number,
  anchor: number,
): string {
  const [y, m] = date.split("-").map(Number);
  const target = new Date(0);
  target.setUTCFullYear(y!, m! - 1 + months, 1);
  const year = target.getUTCFullYear(),
    month = target.getUTCMonth() + 1;
  return iso(year, month, Math.min(anchor, monthDays(year, month)));
}
export function countdown(
  date: string,
  yearly: boolean,
  today: string,
): number {
  if (!yearly) return daysBetween(today, date);
  const [, month, day] = date.split("-").map(Number);
  let year = Math.max(Number(date.slice(0, 4)), Number(today.slice(0, 4)));
  let occurrence = iso(year, month!, Math.min(day!, monthDays(year, month!)));
  if (occurrence < today) {
    year++;
    occurrence = iso(year, month!, Math.min(day!, monthDays(year, month!)));
  }
  return daysBetween(today, occurrence);
}
export function monthlyCost(expense: {
  amount_cents: number;
  period_months: number;
}): number {
  return expense.amount_cents / expense.period_months;
}
export function expenseSummary(
  expenses: {
    amount_cents: number;
    period_months: number;
    next_due: string;
    anchor_day: number;
    active: boolean;
    currency: string;
  }[],
  today: string,
) {
  const totals = new Map<
    string,
    { currency: string; monthly: number; due: number }
  >();
  for (const item of expenses) {
    if (!item.active) continue;
    const row = totals.get(item.currency) ?? {
      currency: item.currency,
      monthly: 0,
      due: 0,
    };
    row.monthly += monthlyCost(item);
    const [ty, tm] = today.split("-").map(Number);
    const [dy, dm] = item.next_due.split("-").map(Number);
    const distance = (ty! - dy!) * 12 + tm! - dm!;
    if (distance >= 0 && distance % item.period_months === 0)
      row.due += item.amount_cents;
    totals.set(item.currency, row);
  }
  return [...totals.values()];
}
export function money(cents: number, currency = "CNY") {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(cents / 100);
}
export const labels: Record<string, string> = {
  todo: "待办",
  doing: "进行中",
  waiting: "等待中",
  done: "已完成",
  planned: "想看",
  watching: "在看",
  completed: "已看完",
  paused: "暂搁",
  anime: "动漫",
  tv: "剧集",
  movie: "电影",
  low: "低优先",
  normal: "普通",
  high: "高优先",
  airing: "连载中",
  ended: "已完结",
  upcoming: "未开播",
  released: "已上映",
  active: "进行中",
};
