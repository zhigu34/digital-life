/**
 * Collapse preferences for long-term task cards.
 *
 * Stored in `localStorage`, keyed per account: the page already rebuilds when the
 * user changes, but the browser storage would otherwise carry one account's
 * layout into another. Every read is defensive — a corrupt value, a quota error
 * or a blocked storage must never take the page down.
 */
export type CollapsedMap = Record<string, boolean>;

export const COLLAPSE_KEY = "digital-life:collapsed-groups";

const storageKey = (userId: number) => `${COLLAPSE_KEY}:${userId}`;

export function readCollapsed(storage: Storage | null | undefined, userId: number): CollapsedMap {
  if (!storage) return {};
  try {
    const raw = storage.getItem(storageKey(userId));
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};
    return Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>).filter(
        ([, value]) => typeof value === "boolean",
      ),
    ) as CollapsedMap;
  } catch {
    return {};
  }
}

export function writeCollapsed(
  storage: Storage | null | undefined,
  userId: number,
  map: CollapsedMap,
): void {
  if (!storage) return;
  try {
    storage.setItem(storageKey(userId), JSON.stringify(map));
  } catch {
    // Private mode or a full quota: the layout just is not remembered.
  }
}

/** Cards start collapsed; the summary row is the default view. */
export function isCollapsed(map: CollapsedMap, groupId: number): boolean {
  return map[String(groupId)] ?? true;
}

export function withCollapsed(
  map: CollapsedMap,
  groupId: number,
  collapsed: boolean,
): CollapsedMap {
  return { ...map, [String(groupId)]: collapsed };
}

export function withAllCollapsed(
  map: CollapsedMap,
  groupIds: number[],
  collapsed: boolean,
): CollapsedMap {
  const next = { ...map };
  for (const id of groupIds) next[String(id)] = collapsed;
  return next;
}
