import { advanceDate, daysBetween } from "./domain";
import type { Maintenance } from "./types";

/** Form preview only; the server always computes the persisted due date. */
export function nextMaintenanceDate(
  completed: string,
  period: number,
  unit: "days" | "months",
): string {
  if (
    !Number.isInteger(period) ||
    period < 1 ||
    period > (unit === "months" ? 120 : 3650)
  )
    throw new RangeError("周期超出允许范围");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(completed))
    throw new RangeError("请选择完成日期");
  let result: string;
  if (unit === "months")
    result = advanceDate(completed, period, Number(completed.slice(-2)));
  else {
    const date = new Date(`${completed}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + period);
    result = date.toISOString().slice(0, 10);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(result))
    throw new RangeError("下次到期日期超出允许范围");
  return result;
}
export function maintenanceTiming(
  item: Pick<
    Maintenance,
    "last_completed" | "next_due" | "active" | "remind_days"
  >,
  today: string,
) {
  const elapsed = daysBetween(item.last_completed, today),
    remaining = daysBetween(today, item.next_due);
  return {
    elapsed,
    remaining,
    label: !item.active
      ? "已停用"
      : remaining < 0
        ? `逾期 ${-remaining} 天`
        : remaining === 0
          ? "今天到期"
          : `剩余 ${remaining} 天`,
    remind: item.active && remaining <= item.remind_days,
  };
}
export function maintenanceReminders(
  items: Maintenance[],
  today: string,
): Maintenance[] {
  return items
    .filter((item) => maintenanceTiming(item, today).remind)
    .sort((a, b) => a.next_due.localeCompare(b.next_due) || a.id - b.id);
}
