<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { api } from "../../api";
import type {
  Expense,
  LedgerAccount,
  LedgerCategory,
  LedgerPayee,
  Stats,
} from "../../types";
import { money, expenseSummary } from "../../domain";
import { metricCurrencies, monthTrend, trendTotal } from "../../stats";
import { payExpense } from "./api";
import AppIcon from "../../components/AppIcon.vue";
import EmptyState from "../../components/EmptyState.vue";
import BarChart from "../../components/BarChart.vue";
import ModalDialog from "../../components/ModalDialog.vue";

const props = defineProps<{
  bills: Expense[];
  accounts: LedgerAccount[];
  categories: LedgerCategory[];
  payees: LedgerPayee[];
  stats: Stats | null;
  today: string;
  busy: boolean;
}>();
const emit = defineEmits<{
  sync: [bills: Expense[]];
  error: [error: unknown];
  notice: [message: string];
}>();

const currencies = ["CNY", "USD", "EUR", "JPY", "HKD"];
const summaries = computed(() => expenseSummary(props.bills, props.today));
const dueCurrencies = computed(() =>
  props.stats ? metricCurrencies(props.stats.months, "expense_due") : [],
);
const statsCurrency = ref("");
const activeCurrency = computed(
  () => statsCurrency.value || dueCurrencies.value[0] || "CNY",
);
const trend = computed(() =>
  props.stats && dueCurrencies.value.length
    ? monthTrend(props.stats, "expense_due", activeCurrency.value, money)
    : [],
);
const trendSum = computed(() => trendTotal(trend.value));
const expenseCategories = computed(() =>
  props.categories.filter((row) => row.kind === "expense"),
);

const editing = ref<Expense | null | undefined>(undefined);
const formError = ref("");
const form = reactive({
  title: "",
  amount: "",
  currency: "CNY",
  period_months: 1,
  next_due: props.today,
  anchor_day: Number(props.today.slice(-2)),
  active: true,
  account_id: null as number | null,
  category_id: null as number | null,
  payee_id: null as number | null,
  notes: "",
});

function open(item?: Expense) {
  formError.value = "";
  editing.value = item ?? null;
  form.title = item?.title ?? "";
  form.amount = item ? (item.amount_cents / 100).toFixed(2) : "";
  form.currency = item?.currency ?? "CNY";
  form.period_months = item?.period_months ?? 1;
  form.next_due = item?.next_due ?? props.today;
  form.anchor_day = item?.anchor_day ?? Number(props.today.slice(-2));
  form.active = item?.active ?? true;
  form.account_id = item?.account_id ?? null;
  form.category_id = item?.category_id ?? null;
  form.payee_id = item?.payee_id ?? null;
  form.notes = item?.notes ?? "";
}
function close() {
  editing.value = undefined;
  formError.value = "";
}
async function refresh(message: string) {
  const bills = await api<Expense[]>("/expenses");
  emit("sync", bills);
  emit("notice", message);
}
async function save() {
  if (!editing.value) return;
  formError.value = "";
  const cents = Math.round(Number(form.amount) * 100);
  if (!Number.isFinite(cents) || cents < 1) {
    formError.value = "请填写大于 0 的金额";
    return;
  }
  const payload = {
    title: form.title,
    amount_cents: cents,
    currency: form.currency,
    period_months: Number(form.period_months),
    next_due: form.next_due,
    anchor_day: Number(form.anchor_day),
    active: form.active,
    account_id: form.account_id,
    category_id: form.category_id,
    payee_id: form.payee_id,
    notes: form.notes,
  };
  try {
    const item = editing.value;
    await api(`/expenses${item ? `/${item.id}` : ""}`, item ? "PATCH" : "POST", payload);
    close();
    await refresh(item ? "账单已更新" : "账单已添加");
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存失败";
  }
}
async function remove(item: Expense) {
  if (!window.confirm(`确定删除“${item.title}”？删除后无法恢复。`)) return;
  try {
    await api(`/expenses/${item.id}`, "DELETE");
    close();
    await refresh("账单已删除");
  } catch (e) {
    emit("error", e);
  }
}
async function toggleActive(item: Expense) {
  try {
    await api(`/expenses/${item.id}`, "PATCH", { active: !item.active });
    await refresh(item.active ? "账单已停用" : "账单已重新启用");
  } catch (e) {
    emit("error", e);
  }
}
function dueLabel(date: string) {
  return date < props.today ? `逾期 · ${date.replaceAll("-", ".")}` : date.replaceAll("-", ".");
}
async function pay(item: Expense) {
  const account = props.accounts.find((row) => row.id === item.account_id);
  const message = account
    ? `确认本期已付？将同时记一笔 ${money(item.amount_cents, item.currency)} 的流水到「${account.name}」。`
    : "确认本期已经支付？下次应付日期将向后推进一个周期。";
  if (!window.confirm(message)) return;
  try {
    const result = await payExpense(item.id);
    await refresh(
      result.entry_id ? "本期已付，并已记一笔流水" : "本期已付，下次日期已更新",
    );
  } catch (e) {
    emit("error", e);
  }
}
</script>

<template>
  <section class="ledger-bills">
    <header class="bill-heading">
      <div>
        <h2>固定账单</h2>
        <p class="summary-note">「推算应付」按下次应付日外推，未确认付款也计入；「实际发生」只有确认付款并记账后才有。</p>
      </div>
      <button class="button primary" @click="open()"><AppIcon name="plus" :size="18" />添加账单</button>
    </header>

    <section class="expense-summary">
      <div v-if="!summaries.length" class="summary-card">
        <span>月均成本</span><strong>—</strong><small>添加账单后自动计算</small>
      </div>
      <div v-for="summary in summaries" :key="summary.currency" class="summary-card">
        <span>{{ summary.currency }} · 月均成本</span><strong>{{ money(summary.monthly, summary.currency) }}</strong><small>本月应付 <b>{{ money(summary.due, summary.currency) }}</b></small>
      </div>
    </section>

    <section v-if="trend.length" class="panel trend-panel" aria-label="近十二个月应付趋势">
      <header class="panel-heading">
        <div><span class="section-index">TREND</span><h2>近 12 个月应付</h2></div>
        <div class="trend-head-right">
          <strong class="trend-total">{{ money(trendSum, activeCurrency) }}<small>合计</small></strong>
          <div v-if="dueCurrencies.length > 1" class="tabs" aria-label="币种筛选">
            <button v-for="currency in dueCurrencies" :key="currency" :class="{ active: currency === activeCurrency }" @click="statsCurrency = currency">{{ currency }}</button>
          </div>
        </div>
      </header>
      <div class="trend-body">
        <BarChart :points="trend" chart-title="近十二个月每月应付金额柱状图" />
      </div>
    </section>

    <EmptyState v-if="!bills.length" icon="expenses" title="给固定支出一个位置" description="记录订阅、会员或房租，到期时手动确认付款；绑定账户后确认付款会同时记一笔流水。" action="添加账单" @action="open()" />
    <ul v-else class="bill-list">
      <li v-for="item in bills" :key="item.id" class="bill-row" :class="{ inactive: !item.active }">
        <span class="record-symbol" :class="{ inactive: !item.active }"><AppIcon name="expenses" /></span>
        <div class="bill-main">
          <h3>{{ item.title }}<span v-if="!item.active" class="tag">已停用</span></h3>
          <p class="ledger-meta">
            <span :class="{ 'text-orange': item.next_due < today && item.active }"><AppIcon name="calendar" :size="13" />{{ dueLabel(item.next_due) }}</span>
            <span>{{ item.period_months === 1 ? "月付" : item.period_months === 3 ? "季付" : item.period_months === 12 ? "年付" : `${item.period_months} 个月` }}</span>
            <span v-if="accounts.find((row) => row.id === item.account_id)" class="muted small">扣款：{{ accounts.find((row) => row.id === item.account_id)!.name }}</span>
            <span v-else class="muted small">未绑定账户，确认付款只推进日期</span>
          </p>
          <p v-if="item.notes" class="record-notes">{{ item.notes }}</p>
        </div>
        <strong class="bill-amount">{{ money(item.amount_cents, item.currency) }}</strong>
        <div class="bill-actions">
          <button v-if="item.active" class="text-button" :disabled="busy" @click="pay(item)">确认本期已付<AppIcon name="chevron" :size="14" /></button>
          <button v-else class="text-button" :disabled="busy" @click="toggleActive(item)">重新启用<AppIcon name="chevron" :size="14" /></button>
          <button class="icon-button" :aria-label="`编辑 ${item.title}`" @click="open(item)"><AppIcon name="edit" :size="16" /></button>
          <button class="icon-button danger-hover" :aria-label="`删除 ${item.title}`" @click="remove(item)"><AppIcon name="delete" :size="16" /></button>
        </div>
      </li>
    </ul>

    <ModalDialog v-if="editing !== undefined" :title="`${editing ? '编辑' : '添加'}账单`" subtitle="固定扣费日遇到短月会自动取月底。" @close="close">
      <form class="record-form" @submit.prevent="save">
        <label>名称<input v-model="form.title" required maxlength="120" autofocus placeholder="例如：云存储订阅" /></label>
        <div class="form-grid">
          <label>每期金额<input v-model="form.amount" type="number" inputmode="decimal" required min="0.01" max="1000000" step="0.01" placeholder="0.00" /></label>
          <label>币种<select v-model="form.currency"><option v-for="currency in currencies" :key="currency">{{ currency }}</option></select></label>
          <label>付费周期<select v-model="form.period_months"><option :value="1">每月</option><option :value="3">每季度</option><option :value="12">每年</option></select></label>
          <label>下次应付<input v-model="form.next_due" type="date" required @change="form.anchor_day = Number(form.next_due.slice(-2))" /></label>
        </div>
        <label>固定扣费日 <span class="optional">短月自动取月底</span><input v-model="form.anchor_day" type="number" min="1" max="31" required /></label>
        <label class="checkbox-label"><input v-model="form.active" type="checkbox" />正在使用（计入应付统计）</label>
        <div class="form-grid">
          <label>扣款账户 <span class="optional">绑定后确认付款会自动记一笔</span><select v-model="form.account_id"><option :value="null">不绑定</option><option v-for="row in accounts" :key="row.id" :value="row.id">{{ row.name }}（{{ row.currency }}）</option></select></label>
          <label>默认分类 <span class="optional">选填</span><select v-model="form.category_id"><option :value="null">不指定</option><option v-for="row in expenseCategories" :key="row.id" :value="row.id">{{ row.name }}</option></select></label>
        </div>
        <label>供应方 <span class="optional">选填，计入商户汇总</span><select v-model="form.payee_id"><option :value="null">不指定</option><option v-for="row in payees" :key="row.id" :value="row.id">{{ row.name }}</option></select></label>
        <label>备注 <span class="optional">选填</span><textarea v-model="form.notes" rows="3" maxlength="4000" placeholder="一些想记住的小细节…"></textarea></label>
        <p v-if="formError" role="alert" class="form-error">{{ formError }}</p>
        <footer class="modal-actions">
          <button type="button" class="button secondary" :disabled="busy" @click="close">取消</button>
          <button class="button primary" :disabled="busy">{{ busy ? "保存中…" : "保存账单" }}</button>
        </footer>
      </form>
    </ModalDialog>
  </section>
</template>
