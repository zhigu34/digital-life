import type {
  AccountKind,
  CategoryKind,
  EntryKind,
  LedgerAccount,
  LedgerEntry,
  StatsLedgerCategory,
} from "../../types";

/** The ledger page keeps four sections behind an inner tab bar. */
export type LedgerTab = "entries" | "bills" | "manage" | "report";

export const accountKindLabels: Record<AccountKind, string> = {
  cash: "现金",
  debit: "储蓄卡",
  credit: "信用卡",
  ewallet: "电子钱包",
  invest: "投资",
  other: "其他",
};

export const entryKindLabels: Record<EntryKind, string> = {
  income: "收入",
  expense: "支出",
  transfer: "转账",
};

export const categoryKindLabels: Record<CategoryKind, string> = {
  income: "收入",
  expense: "支出",
};

/** Money per currency, in cents, never mixed across currencies. */
export type Totals = Record<string, number>;

export function addCents(totals: Totals, currency: string, cents: number): Totals {
  totals[currency] = (totals[currency] ?? 0) + cents;
  return totals;
}

export function totalsSum(totals: Totals): number {
  return Object.values(totals).reduce((sum, value) => sum + value, 0);
}

/**
 * Entries touching an account. A transfer counts on both sides because it really
 * moved that money, even though it is not income or spending.
 */
export function filterByAccount(
  entries: LedgerEntry[],
  accountId: number | null,
): LedgerEntry[] {
  if (accountId === null) return entries;
  return entries.filter(
    (entry) =>
      entry.account_id === accountId ||
      entry.from_account_id === accountId ||
      entry.to_account_id === accountId,
  );
}

export interface MonthSummary {
  income: number;
  expense: number;
  net: number;
}

/** Income minus expense for one month; transfers are neither. */
export function monthlySummary(
  entries: LedgerEntry[],
  month: string,
  currency: string,
): MonthSummary {
  let income = 0;
  let expense = 0;
  for (const entry of entries) {
    if (!entry.occurred_on.startsWith(month) || entry.currency !== currency) continue;
    if (entry.kind === "income") income += entry.amount_cents;
    else if (entry.kind === "expense") expense += entry.amount_cents;
  }
  return { income, expense, net: income - expense };
}

/**
 * Net flow of one account (or of everything when accountId is null) in a month.
 * Summing this over every account equals the global net: both sides of a
 * transfer cancel out.
 */
export function accountNet(
  entries: LedgerEntry[],
  accountId: number | null,
  month: string,
  currency: string,
): number {
  let net = 0;
  for (const entry of filterByAccount(entries, accountId)) {
    if (!entry.occurred_on.startsWith(month) || entry.currency !== currency) continue;
    if (entry.kind === "income") net += entry.amount_cents;
    else if (entry.kind === "expense") net -= entry.amount_cents;
    else {
      if (entry.to_account_id === accountId) net += entry.amount_cents;
      if (entry.from_account_id === accountId) net -= entry.amount_cents;
    }
  }
  return net;
}

export interface DayGroup {
  date: string;
  entries: LedgerEntry[];
  income: Totals;
  expense: Totals;
}

/** Newest day first, newest entry first inside a day, with per-currency subtotals. */
export function groupEntriesByDay(entries: LedgerEntry[]): DayGroup[] {
  const groups = new Map<string, DayGroup>();
  for (const entry of entries) {
    const group =
      groups.get(entry.occurred_on) ??
      { date: entry.occurred_on, entries: [], income: {}, expense: {} };
    group.entries.push(entry);
    if (entry.kind === "income") addCents(group.income, entry.currency, entry.amount_cents);
    if (entry.kind === "expense") addCents(group.expense, entry.currency, entry.amount_cents);
    groups.set(entry.occurred_on, group);
  }
  return [...groups.values()]
    .map((group) => ({
      ...group,
      entries: [...group.entries].sort((a, b) => b.id - a.id),
    }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

/** "+"/"-" is always written out, so colour is never the only signal. */
export function signedAmount(
  cents: number,
  currency: string,
  kind: EntryKind,
  format: (cents: number, currency: string) => string,
): string {
  if (kind === "income") return `+${format(cents, currency)}`;
  if (kind === "expense") return `-${format(cents, currency)}`;
  return format(cents, currency);
}

export interface CategoryShare {
  id: number;
  name: string;
  amount: number;
  share: number;
}

/** Descending shares of one kind in one currency; empty rows are dropped. */
export function categoryShares(
  rows: StatsLedgerCategory[],
  kind: CategoryKind,
  currency: string,
): CategoryShare[] {
  const picked = rows
    .filter((row) => row.kind === kind && (row.totals[currency] ?? 0) > 0)
    .map((row) => ({
      id: row.category_id,
      name: row.name,
      amount: row.totals[currency] ?? 0,
    }))
    .sort((a, b) => b.amount - a.amount || a.name.localeCompare(b.name, "zh-CN"));
  const total = picked.reduce((sum, row) => sum + row.amount, 0);
  return picked.map((row) => ({ ...row, share: total ? row.amount / total : 0 }));
}

export function accountName(accounts: LedgerAccount[], id: number | null): string {
  if (id === null) return "";
  return accounts.find((account) => account.id === id)?.name ?? "已删除账户";
}

export function entryAccountLabel(entry: LedgerEntry, accounts: LedgerAccount[]): string {
  if (entry.kind === "transfer")
    return `${accountName(accounts, entry.from_account_id)} → ${accountName(accounts, entry.to_account_id)}`;
  return accountName(accounts, entry.account_id);
}

/** Months present in the loaded window, newest first. */
export function monthsOf(entries: LedgerEntry[]): string[] {
  const found = new Set(entries.map((entry) => entry.occurred_on.slice(0, 7)));
  return [...found].sort((a, b) => b.localeCompare(a));
}

/** The entry window is capped server-side; never show a partial total as exact. */
export const ENTRY_LIMIT = 500;
