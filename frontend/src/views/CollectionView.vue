<script setup lang="ts">
import { computed, ref } from "vue";
import type { Collection, Records, RecordItem, Task, Stats } from "../types";
import {
  labels,
  money,
  expenseSummary,
  countdown,
  daysBetween,
} from "../domain";
import { metricCurrencies, monthTrend, trendTotal } from "../stats";
import AppIcon from "../components/AppIcon.vue";
import EmptyState from "../components/EmptyState.vue";
import BarChart from "../components/BarChart.vue";
const props = defineProps<{
  collection: Collection;
  records: Records;
  stats: Stats | null;
  today: string;
  busy: boolean;
}>();
const emit = defineEmits<{
  create: [];
  edit: [item: RecordItem];
  remove: [item: RecordItem];
  action: [id: number, action: string, data?: unknown];
}>();
const search = ref(""),
  filter = ref("all");
const config = {
  tasks: {
    title: "待办清单",
    kicker: "ONE THING AT A TIME",
    description: "腾出脑海的空间，把想做的事慢慢完成。",
    add: "添加待办",
    empty: "从一件小事开始",
    hint: "记下今天想完成的事，不必一次安排整个生活。",
  },
  expenses: {
    title: "周期费用",
    kicker: "KNOW WHERE IT GOES",
    description: "每一笔持续的支出，都心中有数。",
    add: "添加费用",
    empty: "给固定支出一个位置",
    hint: "记录订阅、会员或房租，到期时手动确认付款。",
  },
  shows: {
    title: "追剧片单",
    kicker: "A GOOD STORY AWAITS",
    description: "收藏想看的故事，记住每一次看到哪里。",
    add: "添加作品",
    empty: "下一段好故事，等你开启",
    hint: "添加一部想看的电影、剧集或动漫，慢慢享受。",
  },
  milestones: {
    title: "重要日子",
    kicker: "MOMENTS THAT MATTER",
    description: "平凡的日期，也可以装着特别的意义。",
    add: "添加日子",
    empty: "总有一些日子值得记住",
    hint: "生日、周年、旅行出发日，把期待留在这里。",
  },
};
const current = computed(() => config[props.collection]);
const filtered = computed(() =>
  props.records[props.collection].filter(
    (item) =>
      item.title.toLowerCase().includes(search.value.toLowerCase()) &&
      (filter.value === "all" ||
        ("status" in item && item.status === filter.value)),
  ),
);
const summaries = computed(() =>
  expenseSummary(props.records.expenses, props.today),
);
const expenseCurrencies = computed(() =>
  props.stats ? metricCurrencies(props.stats.months, "expense_due") : [],
);
const statsCurrency = ref("");
const activeCurrency = computed(
  () => statsCurrency.value || expenseCurrencies.value[0] || "CNY",
);
const expenseTrend = computed(() =>
  props.stats && props.collection === "expenses" && expenseCurrencies.value.length
    ? monthTrend(
        props.stats,
        "expense_due",
        activeCurrency.value,
        (value, currency) => money(value, currency),
      )
    : [],
);
const expenseTrendTotal = computed(() => trendTotal(expenseTrend.value));
const tabs = computed(() =>
  props.collection === "tasks"
    ? ["all", "todo", "doing", "waiting", "done"]
    : props.collection === "shows"
      ? ["all", "watching", "planned", "completed", "paused"]
      : [],
);
const dueLabel = (date: string) => {
  const days = daysBetween(props.today, date);
  return days < 0
    ? `逾期 ${-days} 天`
    : days === 0
      ? "今天到期"
      : days === 1
        ? "明天到期"
        : date.replaceAll("-", ".");
};
</script>
<template>
  <section :key="collection" class="page collection-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">{{ current.kicker }}</span>
        <h1>
          {{ current.title
          }}<span class="heading-count">{{ records[collection].length }}</span>
        </h1>
        <p>{{ current.description }}</p>
      </div>
      <button class="button primary" @click="emit('create')">
        <AppIcon name="plus" :size="18" />{{ current.add }}
      </button>
    </header>
    <section v-if="collection === 'expenses'" class="expense-summary">
      <div v-if="!summaries.length" class="summary-card">
        <span>月均成本</span><strong>—</strong><small>添加费用后自动计算</small>
      </div>
      <div
        v-for="summary in summaries"
        :key="summary.currency"
        class="summary-card"
      >
        <span>{{ summary.currency }} · 月均成本</span
        ><strong>{{ money(summary.monthly, summary.currency) }}</strong
        ><small
          >本月应付 <b>{{ money(summary.due, summary.currency) }}</b></small
        >
      </div>
      <p class="summary-note">
        月均成本将每期金额按月摊分；本月应付按费用周期推算，分别统计各币种。确认已付只推进下次日期，不记录银行交易。
      </p>
    </section>
    <section
      v-if="collection === 'expenses' && expenseTrend.length"
      class="panel trend-panel"
      aria-label="近十二个月应付趋势"
    >
      <header class="panel-heading">
        <div>
          <span class="section-index">TREND</span>
          <h2>近 12 个月应付</h2>
        </div>
        <div class="trend-head-right">
          <strong class="trend-total"
            >{{ money(expenseTrendTotal, activeCurrency) }}<small>合计</small></strong
          >
          <div v-if="expenseCurrencies.length > 1" class="tabs" aria-label="币种筛选">
            <button
              v-for="currency in expenseCurrencies"
              :key="currency"
              :class="{ active: currency === activeCurrency }"
              @click="statsCurrency = currency"
            >
              {{ currency }}
            </button>
          </div>
        </div>
      </header>
      <div class="trend-body">
        <BarChart
          :points="expenseTrend"
          chart-title="近十二个月每月应付金额柱状图"
        />
        <p class="summary-note">
          按费用周期从下次应付日外推各月应付，未确认付款也会计入；停用的费用不计。
        </p>
      </div>
    </section>
    <section
      v-if="collection === 'shows' && stats && records.shows.length"
      class="shows-stats"
      aria-label="追剧统计"
    >
      <div
        v-for="[value, label] in [
          [stats.shows.watching, '在看'],
          [stats.shows.planned, '想看'],
          [stats.shows.completed, '已看完'],
          [stats.shows.paused, '暂搁'],
        ]"
        :key="label"
        class="summary-card"
      >
        <span>{{ label }}</span><strong>{{ value }}</strong>
      </div>
      <div class="summary-card">
        <span>累计看完</span
        ><strong>{{ stats.shows.episodes_watched }}<small>集</small></strong>
      </div>
    </section>
    <div class="collection-toolbar">
      <div v-if="tabs.length" class="tabs" aria-label="状态筛选">
        <button
          v-for="tab in tabs"
          :key="tab"
          :class="{ active: filter === tab }"
          @click="filter = tab"
        >
          {{ tab === "all" ? "全部" : labels[tab] }}
        </button>
      </div>
      <span v-else class="muted small"
        >{{ filtered.length }} 条记录 · 留意每一点日常</span
      ><label class="search-box"
        ><AppIcon name="search" :size="17" /><input
          v-model="search"
          aria-label="搜索记录"
          placeholder="搜索记录…"
      /></label>
    </div>
    <EmptyState
      v-if="!records[collection].length"
      :icon="collection"
      :title="current.empty"
      :description="current.hint"
      :action="current.add"
      @action="emit('create')"
    /><EmptyState
      v-else-if="!filtered.length"
      icon="search"
      title="没有找到对应记录"
      description="试试其他关键词，或切换状态筛选。"
    />
    <div
      v-else
      :class="[
        'record-list',
        {
          'card-grid': collection === 'shows' || collection === 'milestones',
          'has-shows': collection === 'shows',
        },
      ]"
    >
      <article
        v-for="item in filtered"
        :key="item.id"
        class="record-card"
        :class="{
          'is-done': 'status' in item && item.status === 'done',
          'show-card': collection === 'shows',
        }"
      >
        <template v-if="collection === 'tasks' && 'due_date' in item"
          ><button
            class="task-check"
            :class="{ checked: item.status === 'done' }"
            :aria-label="`${item.status === 'done' ? '重新打开' : '完成'} ${item.title}`"
            :disabled="busy"
            @click="
              emit('action', item.id, 'status', {
                status: item.status === 'done' ? 'todo' : 'done',
              })
            "
          >
            <AppIcon v-if="item.status === 'done'" name="check" :size="15" />
          </button>
          <div class="record-body">
            <h3>{{ item.title }}</h3>
            <p v-if="item.notes" class="record-notes">{{ item.notes }}</p>
            <div class="record-meta">
              <span :class="['tag', item.status]">{{
                labels[item.status]
              }}</span
              ><span
                v-if="item.priority !== 'normal'"
                :class="{ 'text-orange': item.priority === 'high' }"
                >{{ labels[item.priority] }}</span
              ><span
                v-if="item.due_date"
                :class="{
                  'text-orange':
                    item.due_date < today && item.status !== 'done',
                }"
                ><AppIcon name="calendar" :size="13" />{{
                  dueLabel(item.due_date)
                }}</span
              >
            </div>
          </div></template
        ><template v-if="collection === 'expenses' && 'amount_cents' in item"
          ><span class="record-symbol" :class="{ inactive: !item.active }"
            ><AppIcon name="expenses"
          /></span>
          <div class="record-body">
            <h3>
              {{ item.title
              }}<span v-if="!item.active" class="tag">已停用</span>
            </h3>
            <p class="record-notes">
              {{ item.notes || "给每一笔固定支出，留一份清楚的记录" }}
            </p>
            <div class="record-meta">
              <span
                :class="{ 'text-orange': item.next_due < today && item.active }"
                ><AppIcon name="calendar" :size="13" />{{
                  dueLabel(item.next_due)
                }}</span
              ><span>{{
                item.period_months === 1
                  ? "月付"
                  : item.period_months === 3
                    ? "季付"
                    : "年付"
              }}</span>
            </div>
          </div>
          <div class="expense-amount">
            <strong>{{ money(item.amount_cents, item.currency) }}</strong
            ><button
              v-if="item.active"
              class="text-button"
              :disabled="busy"
              @click="emit('action', item.id, 'pay')"
            >
              确认本期已付<AppIcon name="chevron" :size="14" />
            </button></div></template
        ><template v-if="collection === 'shows' && 'progress' in item"
          ><button
            type="button"
            class="show-cover"
            :class="item.media_type"
            :aria-label="`编辑 ${item.title}`"
            @click="emit('edit', item)"
          >
            <img
              v-if="item.poster_path"
              :src="`/api/shows/${item.id}/poster`"
              :alt="item.title"
              loading="lazy"
            /><AppIcon v-else name="shows" :size="30" /><span
              v-if="item.score"
              class="show-score"
              >★ {{ item.score }}</span
            >
          </button>
          <div class="record-body">
            <div class="record-meta">
              <span :class="['tag', item.status]">{{
                labels[item.status]
              }}</span
              ><span v-if="item.seasons">{{ item.seasons }} 季</span
              ><span v-if="item.air_status" :class="['tag', item.air_status]">{{
                labels[item.air_status]
              }}</span
              ><span v-if="item.update_weekday !== null"
                >{{
                  ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][
                    item.update_weekday
                  ]
                }}更新</span
              ><span class="show-kind">{{ labels[item.media_type] }}</span>
            </div>
            <h3>{{ item.title }}</h3>
            <p v-if="item.notes" class="record-notes">{{ item.notes }}</p>
            <div class="show-progress">
              <span
                >已看 {{ item.progress }}
                <span class="muted">/ {{ item.total ?? "—" }} 集</span></span
              ><button
                class="text-button"
                :disabled="
                  busy || (item.total !== null && item.progress >= item.total)
                "
                @click="emit('action', item.id, 'advance')"
              >
                <AppIcon name="plus" :size="15" />看完一集
              </button>
            </div>
            <div class="progress-track">
              <span
                :style="{
                  width: `${item.total ? (item.progress / item.total) * 100 : 0}%`,
                }"
              ></span>
            </div></div></template
        ><template
          v-if="collection === 'milestones' && 'repeats_yearly' in item"
          ><div class="milestone-top">
            <span class="record-symbol"><AppIcon name="milestones" /></span
            ><span class="tag">{{
              item.repeats_yearly ? "每年纪念" : "特别的一天"
            }}</span>
          </div>
          <div class="record-body">
            <h3>{{ item.title }}</h3>
            <div class="countdown-number">
              <strong>{{
                Math.abs(countdown(item.date, item.repeats_yearly, today))
              }}</strong
              ><span>{{
                countdown(item.date, item.repeats_yearly, today) < 0
                  ? "天已经过去"
                  : countdown(item.date, item.repeats_yearly, today) === 0
                    ? "就是今天"
                    : "天后到来"
              }}</span>
            </div>
            <p class="muted small">{{ item.date.replaceAll("-", ".") }}</p>
            <p v-if="item.notes" class="record-notes">{{ item.notes }}</p>
          </div></template
        >
        <div v-if="collection !== 'shows'" class="record-actions">
          <button
            class="icon-button"
            :aria-label="`编辑 ${item.title}`"
            @click="emit('edit', item)"
          >
            <AppIcon name="edit" :size="16" /></button
          ><button
            class="icon-button danger-hover"
            :aria-label="`删除 ${item.title}`"
            @click="emit('remove', item)"
          >
            <AppIcon name="delete" :size="16" />
          </button>
        </div>
      </article>
    </div>
    <p v-if="records[collection].length" class="page-footnote">
      一点一滴，都是生活的痕迹。
    </p>
  </section>
</template>
