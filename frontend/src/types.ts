export interface User {
  id: number;
  username: string;
  display_name: string;
  birthday: string | null;
  timezone: string;
  theme: "light" | "dark" | "system";
  is_admin: boolean;
  is_active: boolean;
}
export interface Task {
  id: number;
  title: string;
  notes: string;
  status: "todo" | "doing" | "waiting" | "done";
  due_date: string | null;
  priority: "low" | "normal" | "high";
  /** Derived by the server: the day the task was closed, null while open. */
  completed_on: string | null;
  created_at: string;
}

/** How often a long-term check item is expected inside a period. */
export type RepeatUnit = "day" | "week" | "month";

/**
 * One check item inside a long-term task. A week item is satisfied by any
 * completion inside that week — there is no fixed weekday to hit.
 */
export interface GroupItem {
  id: number;
  group_id: number;
  title: string;
  repeat_unit: RepeatUnit;
  start_date: string;
  created_at: string;
  /** Recent completion days, oldest first (bounded window). */
  recent_days: string[];
  total_count: number;
}

export interface TaskGroup {
  id: number;
  title: string;
  notes: string;
  archived: boolean;
  archived_on: string | null;
  created_at: string;
  items: GroupItem[];
}

export interface TaskCompletion {
  id: number;
  item_id: number;
  completed_on: string;
  note: string;
  created_at: string;
}
export interface Expense {
  id: number;
  title: string;
  amount_cents: number;
  currency: string;
  period_months: number;
  next_due: string;
  anchor_day: number;
  active: boolean;
  notes: string;
  account_id: number | null;
  category_id: number | null;
  payee_id: number | null;
  /** The book this bill is filed under; null only for rows no book ever claimed. */
  book_id: number | null;
}
export interface Show {
  id: number;
  title: string;
  media_type: "anime" | "tv" | "movie";
  status: "planned" | "watching" | "completed" | "paused";
  progress: number;
  total: number | null;
  score: number | null;
  notes: string;
  update_weekday: number | null;
  source: "bangumi" | "tmdb" | null;
  source_id: number | null;
  source_url: string | null;
  poster_path: string | null;
  seasons: number | null;
  air_status: "airing" | "ended" | "upcoming" | "released" | null;
  release_year: number | null;
  completed_on: string | null;
}
export interface Milestone {
  id: number;
  title: string;
  date: string;
  repeats_yearly: boolean;
  notes: string;
}
export interface Maintenance {
  id: number;
  title: string;
  notes: string;
  period_value: number;
  period_unit: "days" | "months";
  remind_days: number;
  active: boolean;
  last_completed: string;
  next_due: string;
}
export interface Note {
  id: number;
  content: string;
  entry_date: string;
  created_at: string;
}
export interface Project {
  id: number;
  title: string;
  notes: string;
  status: "active" | "paused" | "done";
  created_at: string;
}
export interface MaintenanceLog {
  id: number;
  maintenance_id: number;
  completed_on: string;
  notes: string;
  cost_cents: number | null;
  currency: string;
  created_at: string;
}
export type Collection = "tasks" | "expenses" | "shows" | "milestones";
export type RecordItem = Task | Expense | Show | Milestone;
export type AccountKind = "cash" | "debit" | "credit" | "ewallet" | "invest" | "other";
export type CategoryKind = "income" | "expense";
export type PayeeKind = "merchant" | "org" | "person";
export type EntryKind = "income" | "expense" | "transfer";
export const currencies = ["CNY", "USD", "EUR", "JPY", "HKD"] as const;
/**
 * A named container that scopes entries and bills. Accounts stay shared, so a
 * book never changes a balance — it only groups what was earned or spent.
 */
export interface LedgerBook {
  id: number;
  name: string;
  archived: boolean;
  sort_order: number;
  created_at: string;
}
export interface LedgerAccount {
  id: number;
  name: string;
  kind: AccountKind;
  currency: string;
  opening_balance_cents: number;
  archived: boolean;
  sort_order: number;
  /** Derived by the server from opening balance plus every entry. */
  balance_cents: number;
  created_at: string;
}
export interface LedgerCategory {
  id: number;
  name: string;
  kind: CategoryKind;
  archived: boolean;
  sort_order: number;
  created_at: string;
}
export interface LedgerPayee {
  id: number;
  name: string;
  kind: PayeeKind;
  archived: boolean;
  sort_order: number;
  created_at: string;
}
export interface LedgerEntry {
  id: number;
  occurred_on: string;
  kind: EntryKind;
  amount_cents: number;
  currency: string;
  account_id: number | null;
  from_account_id: number | null;
  to_account_id: number | null;
  category_id: number | null;
  payee_id: number | null;
  /** Scopes the entry to a book for reporting; account balances still span all of them. */
  book_id: number | null;
  note: string;
  /** Set when a recurring bill generated this entry. */
  expense_id: number | null;
  created_at: string;
}
export interface StatsMonth {
  month: string;
  expense_due: Record<string, number>;
  maintenance_cost: Record<string, number>;
  ledger_income: Record<string, number>;
  ledger_expense: Record<string, number>;
}
export interface StatsLedgerCategory {
  category_id: number;
  name: string;
  kind: CategoryKind;
  totals: Record<string, number>;
}
export interface StatsLedgerPayee {
  payee_id: number | null;
  name: string;
  totals: Record<string, number>;
}
export interface ShowsSummary {
  watching: number;
  planned: number;
  completed: number;
  paused: number;
  episodes_watched: number;
}
export interface Stats {
  months: StatsMonth[];
  shows: ShowsSummary;
  ledger: {
    categories: StatsLedgerCategory[];
    payees: StatsLedgerPayee[];
  };
}
export interface Bookmark {
  id: number;
  url: string;
  title: string;
  note: string;
  folder: string | null;
  starred: boolean;
  visit_count: number;
  last_visited_at: string | null;
  created_at: string;
}
export interface Records {
  tasks: Task[];
  expenses: Expense[];
  shows: Show[];
  milestones: Milestone[];
  maintenance: Maintenance[];
  notes: Note[];
  /** Snapshot of long-term tasks, kept so the today overview can read them. */
  groups: TaskGroup[];
  projects: Project[];
}
export type Page =
  | "today"
  | "calendar"
  | Collection
  | "maintenance"
  | "notes"
  | "projects"
  | "bookmarks"
  | "profile"
  | "admin";
