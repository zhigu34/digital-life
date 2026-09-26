import { ref } from "vue";
import type { GroupItem, GroupLogEntry, TaskGroup } from "../../types";
import {
  checkItem,
  createGroup,
  createItem,
  deleteGroup,
  deleteItem,
  getGroup,
  groupLog,
  listGroups,
  undoCompletion,
  updateGroup,
  updateItem,
  type GroupPayload,
  type ItemPayload,
} from "./api";
import {
  readCollapsed,
  withAllCollapsed,
  withCollapsed,
  writeCollapsed,
  type CollapsedMap,
} from "./collapse";

/** Enough log lines to cover a busy group without turning the panel into a feed. */
export const LOG_LIMIT = 12;

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

/**
 * Long-term tasks own their data: the page loads them itself, and every change
 * reports the fresh snapshot up so the today overview stays in step without a
 * global reload.
 *
 * Collapse preferences belong to the account, the activity log is fetched per
 * group only when a card is expanded.
 */
export function useGroups(sync: (groups: TaskGroup[]) => void, userId: number) {
  const groups = ref<TaskGroup[]>([]);
  const loading = ref(false);
  const busy = ref(false);
  const error = ref("");
  const collapsed = ref<CollapsedMap>(readCollapsed(storage(), userId));
  const logs = ref<Record<number, GroupLogEntry[]>>({});
  const logLoading = ref<Record<number, boolean>>({});
  let loadVersion = 0;

  function report() {
    sync(groups.value);
  }

  async function load() {
    const version = ++loadVersion;
    loading.value = true;
    error.value = "";
    try {
      const result = await listGroups();
      if (version === loadVersion) {
        groups.value = result;
        report();
      }
    } catch (e) {
      if (version === loadVersion) {
        error.value = e instanceof Error ? e.message : "长期任务加载失败";
      }
      throw e;
    } finally {
      if (version === loadVersion) loading.value = false;
    }
  }

  function replaceItem(groupId: number, updated: GroupItem) {
    const group = groups.value.find((row) => row.id === groupId);
    if (!group) return;
    const index = group.items.findIndex((item) => item.id === updated.id);
    if (index >= 0) group.items[index] = updated;
    forgetLog(groupId);
    report();
  }

  function replaceGroup(updated: TaskGroup) {
    const index = groups.value.findIndex((row) => row.id === updated.id);
    if (index >= 0) groups.value[index] = updated;
    forgetLog(updated.id);
    report();
  }

  /** A single completion patches the local item: no full reload on every tap. */
  async function check(groupId: number, itemId: number, payload: Record<string, unknown> = {}) {
    busy.value = true;
    error.value = "";
    try {
      replaceItem(groupId, await checkItem(groupId, itemId, payload));
    } finally {
      busy.value = false;
    }
  }

  async function undo(groupId: number, itemId: number, on: string) {
    busy.value = true;
    error.value = "";
    try {
      await undoCompletion(groupId, itemId, on);
      replaceGroup(await getGroup(groupId));
    } finally {
      busy.value = false;
    }
  }

  /** Returns the created group so the caller can expand what it just wrote. */
  async function add(payload: GroupPayload) {
    busy.value = true;
    error.value = "";
    try {
      const created = await createGroup(payload);
      await load();
      return created;
    } finally {
      busy.value = false;
    }
  }

  async function update(id: number, payload: Record<string, unknown>) {
    busy.value = true;
    error.value = "";
    try {
      replaceGroup(await updateGroup(id, payload));
    } finally {
      busy.value = false;
    }
  }

  async function remove(id: number) {
    busy.value = true;
    error.value = "";
    try {
      await deleteGroup(id);
      await load();
    } finally {
      busy.value = false;
    }
  }

  async function addItem(groupId: number, payload: ItemPayload) {
    busy.value = true;
    error.value = "";
    try {
      await createItem(groupId, payload);
      replaceGroup(await getGroup(groupId));
    } finally {
      busy.value = false;
    }
  }

  async function saveItem(groupId: number, itemId: number, payload: Record<string, unknown>) {
    busy.value = true;
    error.value = "";
    try {
      replaceItem(groupId, await updateItem(groupId, itemId, payload));
    } finally {
      busy.value = false;
    }
  }

  async function removeItem(groupId: number, itemId: number) {
    busy.value = true;
    error.value = "";
    try {
      await deleteItem(groupId, itemId);
      replaceGroup(await getGroup(groupId));
    } finally {
      busy.value = false;
    }
  }

  function forgetLog(groupId: number) {
    if (logs.value[groupId]) delete logs.value[groupId];
  }

  /** Cached per group: re-expanding a card does not refetch, a change does. */
  async function loadLog(groupId: number) {
    if (logs.value[groupId] || logLoading.value[groupId]) return;
    logLoading.value[groupId] = true;
    try {
      logs.value[groupId] = await groupLog(groupId, LOG_LIMIT);
    } finally {
      logLoading.value[groupId] = false;
    }
  }

  function setCollapsed(groupId: number, value: boolean) {
    collapsed.value = withCollapsed(collapsed.value, groupId, value);
    writeCollapsed(storage(), userId, collapsed.value);
  }

  function setAllCollapsed(groupIds: number[], value: boolean) {
    collapsed.value = withAllCollapsed(collapsed.value, groupIds, value);
    writeCollapsed(storage(), userId, collapsed.value);
  }

  function reset() {
    loadVersion++;
    groups.value = [];
    logs.value = {};
    logLoading.value = {};
    loading.value = false;
    busy.value = false;
    error.value = "";
    report();
  }

  return {
    groups,
    loading,
    busy,
    error,
    collapsed,
    logs,
    logLoading,
    load,
    check,
    undo,
    add,
    update,
    remove,
    addItem,
    saveItem,
    removeItem,
    loadLog,
    forgetLog,
    setCollapsed,
    setAllCollapsed,
    reset,
  };
}
