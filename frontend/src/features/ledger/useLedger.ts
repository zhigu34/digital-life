import { ref } from "vue";
import type {
  LedgerAccount,
  LedgerBook,
  LedgerCategory,
  LedgerEntry,
  LedgerPayee,
} from "../../types";
import {
  createEntry,
  deleteEntry,
  listAccounts,
  listBooks,
  listCategories,
  listEntries,
  listPayees,
  updateEntry,
} from "./api";

/**
 * Books, accounts, categories, payees and entries load together: entries render
 * names from the dictionaries, and the window (last 12 months, server-capped)
 * is small.
 */
export function useLedger() {
  const books = ref<LedgerBook[]>([]);
  const accounts = ref<LedgerAccount[]>([]);
  const categories = ref<LedgerCategory[]>([]);
  const payees = ref<LedgerPayee[]>([]);
  const entries = ref<LedgerEntry[]>([]);
  const loading = ref(false);
  const busy = ref(false);
  const error = ref("");
  let loadVersion = 0;

  /**
   * Every book's entries are loaded, never only the selected book's: switching
   * the filter has to be instant, and the server already caps the window.
   */
  async function load() {
    const version = ++loadVersion;
    loading.value = true;
    error.value = "";
    try {
      const [bookRows, accountRows, categoryRows, payeeRows, entryRows] = await Promise.all([
        listBooks(),
        listAccounts(),
        listCategories(),
        listPayees(),
        listEntries(),
      ]);
      if (version !== loadVersion) return;
      books.value = bookRows;
      accounts.value = accountRows;
      categories.value = categoryRows;
      payees.value = payeeRows;
      entries.value = entryRows;
    } catch (e) {
      if (version === loadVersion)
        error.value = e instanceof Error ? e.message : "记账数据加载失败";
      throw e;
    } finally {
      if (version === loadVersion) loading.value = false;
    }
  }

  async function reloadPayees() {
    const [payeeRows, accountRows] = await Promise.all([listPayees(), listAccounts()]);
    payees.value = payeeRows;
    accounts.value = accountRows;
  }

  async function save(entry: LedgerEntry | null, data: Record<string, unknown>) {
    busy.value = true;
    error.value = "";
    try {
      if (entry) await updateEntry(entry.id, data);
      else await createEntry(data);
      await load();
    } finally {
      busy.value = false;
    }
  }

  async function remove(entry: LedgerEntry) {
    busy.value = true;
    error.value = "";
    try {
      await deleteEntry(entry.id);
      await load();
    } finally {
      busy.value = false;
    }
  }

  function reset() {
    loadVersion++;
    books.value = [];
    accounts.value = [];
    categories.value = [];
    payees.value = [];
    entries.value = [];
    loading.value = false;
    busy.value = false;
    error.value = "";
  }

  return {
    books,
    accounts,
    categories,
    payees,
    entries,
    loading,
    busy,
    error,
    load,
    reloadPayees,
    save,
    remove,
    reset,
  };
}
