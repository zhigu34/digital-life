import { ref } from "vue";
import type { Show } from "../../types";
import { advanceShow, createShow, deleteShow, listShows, updateShow } from "./api";

export function useShows() {
  const shows = ref<Show[]>([]);
  const loading = ref(false);
  const busy = ref(false);
  const error = ref("");
  let loadVersion = 0;

  async function load() {
    const version = ++loadVersion;
    loading.value = true;
    error.value = "";
    try {
      const result = await listShows();
      if (version === loadVersion) shows.value = result;
    } catch (e) {
      if (version === loadVersion) error.value = e instanceof Error ? e.message : "追剧记录加载失败";
      throw e;
    } finally {
      if (version === loadVersion) loading.value = false;
    }
  }

  async function create(data: Record<string, unknown>) {
    busy.value = true;
    error.value = "";
    try { await createShow(data); await load(); }
    finally { busy.value = false; }
  }

  async function update(id: number, data: Record<string, unknown>) {
    busy.value = true;
    error.value = "";
    try { await updateShow(id, data); await load(); }
    finally { busy.value = false; }
  }

  async function remove(id: number) {
    busy.value = true;
    error.value = "";
    try { await deleteShow(id); await load(); }
    finally { busy.value = false; }
  }

  async function advance(id: number) {
    busy.value = true;
    error.value = "";
    try { await advanceShow(id); await load(); }
    finally { busy.value = false; }
  }

  function reset() {
    loadVersion++;
    shows.value = [];
    loading.value = false;
    busy.value = false;
    error.value = "";
  }

  return { shows, loading, busy, error, load, create, update, remove, advance, reset };
}
