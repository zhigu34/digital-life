<script setup lang="ts">
import { computed, ref } from "vue";
import type { LedgerAccount, LedgerCategory, LedgerEntry, LedgerPayee } from "../../types";
import { money } from "../../domain";
import {
  ENTRY_LIMIT,
  entryAccountLabel,
  entryKindLabels,
  groupEntriesByDay,
  monthsOf,
  signedAmount,
} from "./ledger";
import AppIcon from "../../components/AppIcon.vue";
import EmptyState from "../../components/EmptyState.vue";

const props = defineProps<{
  entries: LedgerEntry[];
  accounts: LedgerAccount[];
  categories: LedgerCategory[];
  payees: LedgerPayee[];
  accountFilter: number | null;
  busy: boolean;
}>();
const emit = defineEmits<{
  edit: [entry: LedgerEntry];
  remove: [entry: LedgerEntry];
  "update:accountFilter": [id: number | null];
}>();

const kinds = ["all", "expense", "income", "transfer"] as const;
const kind = ref<(typeof kinds)[number]>("all");
const month = ref("all");
const search = ref("");
const filteredAccount = computed(
  () => props.accounts.find((row) => row.id === props.accountFilter) ?? null,
);
const monthOptions = computed(() => monthsOf(props.entries));

const visible = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  return props.entries.filter((entry) => {
    if (kind.value !== "all" && entry.kind !== kind.value) return false;
    if (month.value !== "all" && !entry.occurred_on.startsWith(month.value)) return false;
    if (!keyword) return true;
    return [
      entry.note,
      categoryName(entry.category_id),
      payeeName(entry.payee_id),
      entryAccountLabel(entry, props.accounts),
      money(entry.amount_cents, entry.currency),
    ]
      .join(" ")
      .toLowerCase()
      .includes(keyword);
  });
});
const groups = computed(() => groupEntriesByDay(visible.value));
const truncated = computed(() => props.entries.length >= ENTRY_LIMIT);

function categoryName(id: number | null) {
  return props.categories.find((row) => row.id === id)?.name ?? "";
}
function payeeName(id: number | null) {
  return props.payees.find((row) => row.id === id)?.name ?? "";
}
function title(entry: LedgerEntry) {
  return categoryName(entry.category_id) || entryKindLabels[entry.kind];
}
const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
function dayLabel(date: string) {
  const parsed = new Date(`${date}T00:00:00Z`);
  return `${parsed.getUTCMonth() + 1}月${parsed.getUTCDate()}日 ${weekdays[parsed.getUTCDay()]}`;
}
function totalsText(totals: Record<string, number>) {
  return Object.entries(totals)
    .map(([currency, cents]) => money(cents, currency))
    .join(" · ");
}
</script>

<template>
  <section class="ledger-entries">
    <div class="collection-toolbar ledger-toolbar">
      <div class="tabs" aria-label="类型筛选">
        <button
          v-for="option in kinds"
          :key="option"
          :class="{ active: kind === option }"
          @click="kind = option"
        >
          {{ option === "all" ? "全部" : entryKindLabels[option] }}
        </button>
      </div>
      <div class="ledger-filters">
        <label class="select-field"><span>账户</span><select :value="accountFilter ?? ''" @change="emit('update:accountFilter', Number(($event.target as HTMLSelectElement).value) || null)"><option value="">全部账户</option><option v-for="row in accounts" :key="row.id" :value="row.id">{{ row.name }}</option></select></label>
        <label class="select-field"><span>月份</span><select v-model="month"><option value="all">全部月份</option><option v-for="value in monthOptions" :key="value" :value="value">{{ value.replace('-', ' 年 ') }} 月</option></select></label>
        <label class="search-box"><AppIcon name="search" :size="17" /><input v-model="search" aria-label="搜索流水" placeholder="搜索备注、商户、分类…" /></label>
      </div>
    </div>

    <p v-if="filteredAccount" class="filter-chip">
      <span>已筛选：{{ filteredAccount.name }}</span>
      <button class="text-button" @click="emit('update:accountFilter', null)"><AppIcon name="close" :size="14" />清除</button>
    </p>
    <p v-if="truncated" class="summary-note">
      仅显示最近 {{ ENTRY_LIMIT }} 笔流水，账户口径统计可能不完整；请缩窄月份后再看汇总。
    </p>

    <EmptyState
      v-if="!entries.length"
      icon="expenses"
      title="还没有一笔流水"
      description="记下第一笔支出或收入，这个月的钱就看得见了。"
    />
    <EmptyState
      v-else-if="!visible.length"
      icon="search"
      title="没有找到对应流水"
      description="试试其他关键词，或切换类型与月份。"
    />

    <div v-else class="ledger-groups">
      <section v-for="group in groups" :key="group.date" class="ledger-group">
        <header class="ledger-group-heading">
          <h3>{{ dayLabel(group.date) }}</h3>
          <span v-if="Object.keys(group.income).length" class="income-text">收 {{ totalsText(group.income) }}</span>
          <span v-if="Object.keys(group.expense).length" class="expense-text">支 {{ totalsText(group.expense) }}</span>
        </header>
        <ul class="ledger-rows">
          <li v-for="entry in group.entries" :key="entry.id" class="ledger-row">
            <span class="ledger-symbol" :class="entry.kind"><AppIcon :name="entry.kind === 'transfer' ? 'arrow' : 'expenses'" :size="17" /></span>
            <div class="ledger-main">
              <h4>{{ title(entry) }}<span v-if="entry.expense_id" class="tag bill-tag">账单</span></h4>
              <p class="ledger-meta">
                <span v-if="payeeName(entry.payee_id)" class="payee">{{ payeeName(entry.payee_id) }}</span>
                <span v-if="entry.note" class="ledger-note">{{ entry.note }}</span>
                <span v-if="entry.kind === 'transfer'" class="muted small">不计收支</span>
              </p>
            </div>
            <span class="account-chip" :class="{ archived: accounts.find((row) => row.id === (entry.account_id ?? entry.from_account_id))?.archived }">{{ entryAccountLabel(entry, accounts) }}</span>
            <strong class="ledger-amount" :class="entry.kind">{{ signedAmount(entry.amount_cents, entry.currency, entry.kind, money) }}</strong>
            <div class="record-actions">
              <button class="icon-button" :aria-label="`编辑 ${title(entry)}`" :disabled="busy" @click="emit('edit', entry)"><AppIcon name="edit" :size="16" /></button>
              <button class="icon-button danger-hover" :aria-label="`删除 ${title(entry)}`" :disabled="busy" @click="emit('remove', entry)"><AppIcon name="delete" :size="16" /></button>
            </div>
          </li>
        </ul>
      </section>
    </div>
  </section>
</template>
