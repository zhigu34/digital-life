<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import type { Expense, LedgerEntry, Stats } from "../../types";
import { api } from "../../api";
import { money } from "../../domain";
import { metricCurrencies } from "../../stats";
import {
  filterBillsByBook,
  filterByAccount,
  filterByBook,
  monthlySummary,
  type LedgerTab,
} from "./ledger";
import { useLedger } from "./useLedger";
import AppIcon from "../../components/AppIcon.vue";
import EntryList from "./EntryList.vue";
import EntryForm from "./EntryForm.vue";
import BillPanel from "./BillPanel.vue";
import BookPanel from "./BookPanel.vue";
import AccountPanel from "./AccountPanel.vue";
import CategoryPanel from "./CategoryPanel.vue";
import PayeePanel from "./PayeePanel.vue";
import ReportPanel from "./ReportPanel.vue";

const props = defineProps<{
  stats: Stats | null;
  today: string;
  bills: Expense[];
  createRequest?: number;
  /** A bill deep link (calendar, today's cards) opens on its own section. */
  startTab?: LedgerTab | null;
}>();
const emit = defineEmits<{
  sync: [bills: Expense[]];
  error: [error: unknown];
  notice: [message: string];
}>();

const ledger = useLedger();
const { books, accounts, categories, payees, entries, loading, busy, error } = ledger;
const tabs: [LedgerTab, string][] = [
  ["entries", "流水"],
  ["bills", "账单"],
  ["manage", "管理"],
  ["report", "报表"],
];
const tab = ref<LedgerTab>(props.startTab ?? "entries");
const bookFilter = ref<number | null>(null);
const accountFilter = ref<number | null>(null);
const editing = ref<LedgerEntry | null | undefined>(undefined);
const formError = ref("");

const month = computed(() => props.today.slice(0, 7));
const currency = computed(
  () => metricCurrencies(props.stats?.months ?? [], "ledger_expense")[0] ?? "CNY",
);
const filteredAccount = computed(
  () => accounts.value.find((row) => row.id === accountFilter.value) ?? null,
);
const selectedBook = computed(() => books.value.find((row) => row.id === bookFilter.value) ?? null);
/** Every book's rows are already loaded, so switching the filter stays instant. */
const bookEntries = computed(() => filterByBook(entries.value, bookFilter.value));
const bookBills = computed(() => filterBillsByBook(props.bills, bookFilter.value));

/**
 * Book-scoped numbers come from the server, so the cards, the bill projection and
 * the report always agree with each other. "全部账本" reuses the snapshot the app
 * already loaded instead of asking for the same window twice.
 */
const scopedStats = ref<Stats | null>(props.stats);
async function loadScopedStats() {
  if (bookFilter.value === null) {
    scopedStats.value = props.stats;
    return;
  }
  scopedStats.value = await api<Stats>(
    `/stats?end_month=${month.value}&book_id=${bookFilter.value}`,
  );
}
watch(
  () => props.stats,
  (next) => {
    if (bookFilter.value === null) scopedStats.value = next;
  },
);
watch(bookFilter, () => {
  // Both filters at once reads as "no data"; picking a book starts a fresh view.
  accountFilter.value = null;
  loadScopedStats().catch((e) => emit("error", e));
});
watch(books, (rows) => {
  // A book can be deleted from the manage tab; never keep filtering by a ghost.
  if (bookFilter.value !== null && !rows.some((row) => row.id === bookFilter.value))
    bookFilter.value = null;
});

/** Account-scoped numbers come from the loaded entries, so list and cards agree. */
const local = computed(() =>
  monthlySummary(
    filterByAccount(bookEntries.value, accountFilter.value),
    month.value,
    currency.value,
  ),
);
const summary = computed(() => {
  if (accountFilter.value !== null) return local.value;
  const row = scopedStats.value?.months.find((item) => item.month === month.value);
  const income = row?.ledger_income[currency.value] ?? 0;
  const expense = row?.ledger_expense[currency.value] ?? 0;
  return { income, expense, net: income - expense };
});
const summaryPrefix = computed(() => {
  if (filteredAccount.value) return `${filteredAccount.value.name} · `;
  if (selectedBook.value) return `${selectedBook.value.name} · `;
  return "";
});
const summaryNote = computed(() =>
  accountFilter.value !== null ? "按已加载流水统计" : "来自服务端统计",
);

async function reload(notice?: string) {
  try {
    await ledger.load();
    if (bookFilter.value !== null) await loadScopedStats();
    if (notice) emit("notice", notice);
  } catch (e) {
    emit("error", e);
  }
}
function openEntry(item?: LedgerEntry) {
  formError.value = "";
  editing.value = item ?? null;
}
function closeEntry() {
  editing.value = undefined;
  formError.value = "";
}
async function saveEntry(data: Record<string, unknown>) {
  formError.value = "";
  try {
    await ledger.save(editing.value ?? null, data);
    const wasEdit = !!editing.value;
    closeEntry();
    emit("notice", wasEdit ? "流水已更新" : "记下了这一笔");
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存失败";
  }
}
async function removeEntry(item: LedgerEntry) {
  if (!window.confirm("确定删除这笔流水？账户余额会随之变化。")) return;
  try {
    await ledger.remove(item);
    closeEntry();
    emit("notice", "流水已删除");
  } catch (e) {
    emit("error", e);
  }
}
function viewAccountEntries(accountId: number) {
  accountFilter.value = accountId;
  tab.value = "entries";
}
function viewBookEntries(bookId: number) {
  bookFilter.value = bookId;
  tab.value = "entries";
}
async function refreshPayees() {
  try {
    await ledger.reloadPayees();
  } catch (e) {
    emit("error", e);
  }
}
/** Confirming a bill can create an entry and move a balance, so reload both sides. */
async function syncBills(bills: Expense[]) {
  emit("sync", bills);
  await reload();
}

watch(
  () => props.createRequest,
  (next, previous) => {
    if (next !== undefined && next !== previous) openEntry();
  },
);
onMounted(() => {
  void reload();
  if (props.createRequest) openEntry();
});
</script>

<template>
  <section class="page collection-page ledger-page">
    <div v-if="error" class="global-error" role="alert"><span>{{ error }}</span><button class="text-button" @click="reload()">重新加载</button></div>
    <div v-if="loading" class="loading-line" role="status" aria-label="正在同步记账数据"></div>

    <header class="page-heading">
      <div>
        <span class="eyebrow">KNOW WHERE IT GOES</span>
        <h1>记账<span class="heading-count">{{ entries.length }}</span></h1>
        <p>记下每一笔收支，账户余额、账单与报表都由这些流水算出来。</p>
      </div>
      <button class="button primary" @click="openEntry()"><AppIcon name="plus" :size="18" />记一笔</button>
    </header>

    <div class="ledger-book-bar">
      <label class="select-field"><span>账本</span><select :value="bookFilter ?? ''" @change="bookFilter = Number(($event.target as HTMLSelectElement).value) || null"><option value="">全部账本</option><option v-for="row in books" :key="row.id" :value="row.id">{{ row.name }}{{ row.archived ? "（已归档）" : "" }}</option></select></label>
      <p class="summary-note">{{ selectedBook ? `只看「${selectedBook.name}」的流水、账单与报表；账户余额仍是所有账本的合计。` : "账本是流水上的标签，用来归集专项开销；账户与余额所有账本共用。" }}</p>
      <button v-if="selectedBook" class="text-button" @click="bookFilter = null"><AppIcon name="close" :size="14" />清除</button>
    </div>

    <section class="ledger-summary" aria-label="本月收支">
      <div class="summary-card"><span>{{ summaryPrefix }}本月支出</span><strong class="expense-text">{{ money(summary.expense, currency) }}</strong><small>{{ summaryNote }}</small></div>
      <div class="summary-card"><span>{{ summaryPrefix }}本月收入</span><strong class="income-text">{{ money(summary.income, currency) }}</strong><small>{{ summaryNote }}</small></div>
      <div class="summary-card"><span>{{ summaryPrefix }}本月{{ summaryPrefix ? "净流量" : "结余" }}</span><strong :class="{ negative: summary.net < 0 }">{{ money(summary.net, currency) }}</strong><small>{{ summaryPrefix ? "结余是当月流量，余额见「管理」" : "收入 − 支出，转账不计入" }}</small></div>
    </section>

    <div class="tabs ledger-tabs" aria-label="记账分区">
      <button v-for="[id, label] in tabs" :key="id" :class="{ active: tab === id }" @click="tab = id">{{ label }}</button>
    </div>

    <EntryList
      v-if="tab === 'entries'"
      :entries="filterByAccount(bookEntries, accountFilter)"
      :accounts="accounts"
      :categories="categories"
      :payees="payees"
      :books="books"
      :show-book="bookFilter === null"
      :busy="busy"
      :account-filter="accountFilter"
      @edit="openEntry"
      @remove="removeEntry"
      @update:accountFilter="accountFilter = $event"
    />
    <BillPanel
      v-else-if="tab === 'bills'"
      :bills="bookBills"
      :books="books"
      :accounts="accounts"
      :categories="categories"
      :payees="payees"
      :stats="scopedStats"
      :today="today"
      :busy="busy"
      :default-book-id="bookFilter"
      @sync="syncBills"
      @error="emit('error', $event)"
      @notice="emit('notice', $event)"
    />
    <div v-else-if="tab === 'manage'" class="ledger-manage">
      <BookPanel :books="books" :busy="busy" @changed="reload()" @error="emit('error', $event)" @notice="emit('notice', $event)" @view-entries="viewBookEntries" />
      <AccountPanel :accounts="accounts" :busy="busy" @changed="reload()" @error="emit('error', $event)" @notice="emit('notice', $event)" @view-entries="viewAccountEntries" />
      <CategoryPanel :categories="categories" :busy="busy" @changed="reload()" @error="emit('error', $event)" @notice="emit('notice', $event)" />
      <PayeePanel :payees="payees" :busy="busy" @changed="reload()" @error="emit('error', $event)" @notice="emit('notice', $event)" />
    </div>
    <ReportPanel v-else :stats="scopedStats" :month="month" :book-name="selectedBook?.name ?? ''" />

    <EntryForm
      v-if="editing !== undefined"
      :key="editing?.id ?? 'new'"
      :item="editing || undefined"
      :books="books"
      :default-book-id="bookFilter"
      :accounts="accounts.filter((row) => !row.archived || row.id === editing?.account_id)"
      :categories="categories.filter((row) => !row.archived || row.id === editing?.category_id)"
      :payees="payees.filter((row) => !row.archived || row.id === editing?.payee_id)"
      :today="today"
      :busy="busy"
      :error="formError"
      @close="closeEntry"
      @save="saveEntry"
      @remove="removeEntry"
      @payees-changed="refreshPayees"
    />
    <p v-if="entries.length" class="page-footnote">账目清楚，心里就松一点。</p>
  </section>
</template>
