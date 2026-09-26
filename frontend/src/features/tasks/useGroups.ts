import { ref } from "vue";
import type { GroupItem, TaskGroup } from "../../types";
import {
  checkItem,
  createGroup,
  createItem,
  deleteGroup,
  deleteItem,
  getGroup,
  listGroups,
  undoCompletion,
  updateGroup,
  updateItem,
  type GroupPayload,
  type ItemPayload,
} from "./api";

/**
 * Long-term tasks own their data: the page loads them itself, and every change
 * reports the fresh snapshot up so the today overview stays in step without a
 * global reload.
 */
export function useGroups(sync: (groups: TaskGroup[]) => void) {
  const groups = ref<TaskGroup[]>([]);
  const loading = ref(false);
  const busy = ref(false);
  const error = ref("");
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
    report();
  }

  function replaceGroup(updated: TaskGroup) {
    const index = groups.value.findIndex((row) => row.id === updated.id);
    if (index >= 0) groups.value[index] = updated;
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

  async function add(payload: GroupPayload) {
    busy.value = true;
    error.value = "";
    try {
      await createGroup(payload);
      await load();
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

  function reset() {
    loadVersion++;
    groups.value = [];
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
    load,
    check,
    undo,
    add,
    update,
    remove,
    addItem,
    saveItem,
    removeItem,
    reset,
  };
}
