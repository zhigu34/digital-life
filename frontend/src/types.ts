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
export interface StatsMonth {
  month: string;
  expense_due: Record<string, number>;
  maintenance_cost: Record<string, number>;
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
}
export interface Records {
  tasks: Task[];
  expenses: Expense[];
  shows: Show[];
  milestones: Milestone[];
  maintenance: Maintenance[];
}
export type Page =
  | "today"
  | "calendar"
  | Collection
  | "maintenance"
  | "profile"
  | "admin";
