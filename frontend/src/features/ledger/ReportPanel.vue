<script setup lang="ts">
import { computed, ref } from "vue";
import type { Stats } from "../../types";
import { money } from "../../domain";
import { fullMonthLabel, monthTrend, trendTotal } from "../../stats";
import { categoryShares } from "./ledger";
import AppIcon from "../../components/AppIcon.vue";
import BarChart from "../../components/BarChart.vue";

const props = defineProps<{ stats: Stats | null; month: string; bookName: string }>();
const tabs = computed(() => {
  const found = new Set<string>();
  for (const entry of props.stats?.months ?? []) {
    for (const currency of Object.keys(entry.ledger_expense)) found.add(currency);
    for (const currency of Object.keys(entry.ledger_income)) found.add(currency);
  }
  return [...found].sort((a, b) => (a === "CNY" ? -1 : b === "CNY" ? 1 : a.localeCompare(b)));
});
const currency = ref("");
const activeCurrency = computed(() => currency.value || tabs.value[0] || "CNY");

const incomeTrend = computed(() =>
  props.stats ? monthTrend(props.stats, "ledger_income", activeCurrency.value, money) : [],
);
const expenseTrend = computed(() =>
  props.stats ? monthTrend(props.stats, "ledger_expense", activeCurrency.value, money) : [],
);
const incomeTotal = computed(() => trendTotal(incomeTrend.value));
const expenseTotal = computed(() => trendTotal(expenseTrend.value));
const monthRow = computed(
  () => props.stats?.months.find((row) => row.month === props.month) ?? null,
);
const monthIncome = computed(() => monthRow.value?.ledger_income[activeCurrency.value] ?? 0);
const monthExpense = computed(() => monthRow.value?.ledger_expense[activeCurrency.value] ?? 0);
const shares = computed(() =>
  categoryShares(props.stats?.ledger.categories ?? [], "expense", activeCurrency.value),
);
const payees = computed(() => props.stats?.ledger.payees ?? []);
</script>

<template>
  <section class="ledger-report">
    <div v-if="tabs.length > 1" class="tabs" aria-label="币种筛选">
      <button v-for="item in tabs" :key="item" :class="{ active: item === activeCurrency }" @click="currency = item">{{ item }}</button>
    </div>
    <p class="summary-note">{{ bookName ? `当前只看「${bookName}」的流水（转账不计入收支）；账户余额仍是所有账本的合计。` : "报表只统计真实发生的流水（转账不计入收支），并始终按全部账户计算，不受流水页的账户筛选影响。" }}</p>

    <section class="report-summary">
      <div class="summary-card"><span>{{ fullMonthLabel(month) }} · 收入</span><strong>{{ money(monthIncome, activeCurrency) }}</strong><small>近 12 个月 {{ money(incomeTotal, activeCurrency) }}</small></div>
      <div class="summary-card"><span>{{ fullMonthLabel(month) }} · 支出</span><strong>{{ money(monthExpense, activeCurrency) }}</strong><small>近 12 个月 {{ money(expenseTotal, activeCurrency) }}</small></div>
      <div class="summary-card"><span>{{ fullMonthLabel(month) }} · 结余</span><strong :class="{ negative: monthIncome - monthExpense < 0 }">{{ money(monthIncome - monthExpense, activeCurrency) }}</strong><small>当月收入 − 当月支出</small></div>
    </section>

    <div class="report-charts">
      <section class="panel trend-panel" aria-label="近十二个月收入趋势">
        <header class="panel-heading"><div><span class="section-index">INCOME</span><h2>近 12 个月收入</h2></div></header>
        <div class="trend-body"><BarChart :points="incomeTrend" chart-title="近十二个月每月收入柱状图" /></div>
      </section>
      <section class="panel trend-panel" aria-label="近十二个月支出趋势">
        <header class="panel-heading"><div><span class="section-index">EXPENSE</span><h2>近 12 个月支出</h2></div></header>
        <div class="trend-body"><BarChart :points="expenseTrend" chart-title="近十二个月每月支出柱状图" /></div>
      </section>
    </div>

    <section class="panel">
      <header class="panel-heading"><div><span class="section-index">SHARE</span><h2>当月分类占比</h2></div></header>
      <ul v-if="shares.length" class="share-list">
        <li v-for="row in shares" :key="row.id">
          <span class="share-name">{{ row.name }}</span>
          <span class="share-track"><span class="share-fill" :style="{ width: `${Math.round(row.share * 100)}%` }"></span></span>
          <span class="share-value">{{ Math.round(row.share * 100) }}%<small>{{ money(row.amount, activeCurrency) }}</small></span>
        </li>
      </ul>
      <p v-else class="muted small">本月还没有带分类的支出。</p>
    </section>

    <section class="panel">
      <header class="panel-heading"><div><span class="section-index">PAYEE</span><h2>当月商户 TOP</h2></div></header>
      <ul v-if="payees.length" class="payee-ranking">
        <li v-for="row in payees" :key="row.payee_id ?? 'unlabelled'">
          <AppIcon name="expenses" :size="15" />
          <span>{{ row.name }}</span>
          <strong>{{ money(row.totals[activeCurrency] ?? 0, activeCurrency) }}</strong>
        </li>
      </ul>
      <p v-else class="muted small">本月还没有支出流水。</p>
    </section>
  </section>
</template>
