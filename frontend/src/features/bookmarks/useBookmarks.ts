import { ref } from "vue";
import type { Bookmark } from "../../types";
import {
  createBookmark,
  deleteBookmark,
  listBookmarks,
  updateBookmark,
  visitBookmark,
} from "./api";

export function useBookmarks() {
  const bookmarks = ref<Bookmark[]>([]);
  const loading = ref(false);
  const busy = ref(false);
  const error = ref("");
  let loadVersion = 0;

  async function load() {
    const version = ++loadVersion;
    loading.value = true;
    error.value = "";
    try {
      const result = await listBookmarks();
      if (version === loadVersion) bookmarks.value = result;
    } catch (e) {
      if (version === loadVersion) {
        error.value = e instanceof Error ? e.message : "书签加载失败";
      }
      throw e;
    } finally {
      if (version === loadVersion) loading.value = false;
    }
  }

  async function create(data: Record<string, unknown>) {
    busy.value = true;
    error.value = "";
    try {
      await createBookmark(data);
      await load();
    } finally {
      busy.value = false;
    }
  }

  async function update(id: number, data: Record<string, unknown>) {
    busy.value = true;
    error.value = "";
    try {
      await updateBookmark(id, data);
      await load();
    } finally {
      busy.value = false;
    }
  }

  async function remove(id: number) {
    busy.value = true;
    error.value = "";
    try {
      await deleteBookmark(id);
      await load();
    } finally {
      busy.value = false;
    }
  }

  /** Counts one opening of the link; it never rewrites the editable fields. */
  async function visit(id: number) {
    try {
      const updated = await visitBookmark(id);
      const index = bookmarks.value.findIndex((item) => item.id === id);
      if (index >= 0) bookmarks.value[index] = updated;
    } catch {
      // A failed counter must not block the user from opening the site.
    }
  }

  function reset() {
    loadVersion++;
    bookmarks.value = [];
    loading.value = false;
    busy.value = false;
    error.value = "";
  }

  return { bookmarks, loading, busy, error, load, create, update, remove, visit, reset };
}
