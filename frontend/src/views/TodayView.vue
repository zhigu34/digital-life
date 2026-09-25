<script setup lang="ts">
import { computed } from "vue";
import type { User, Records, Page, Collection } from "../types";
import {
  browserTimezone,
  daysBetween,
  countdown,
  expenseSummary,
  money,
  labels,
} from "../domain";
import { maintenanceReminders, maintenanceTiming } from "../maintenance";
import AppIcon from "../components/AppIcon.vue";
import EmptyState from "../components/EmptyState.vue";
import type { LedgerTab } from "../features/ledger/ledger";
const props = defineProps<{
  user: User;
  records: Records;
  today: string;
  busy: boolean;
}>();
const emit = defineEmits<{
  navigate: [page: Page, ledgerTab?: LedgerTab];
  create: [collection: Collection];
  complete: [id: number];
  checkin: [id: number];
}>();
const tasks = computed(() =>
  props.records.tasks
    .filter((t) => t.status !== "done")
    .sort((a, b) => (a.due_date ?? "9999").localeCompare(b.due_date ?? "9999"))
    .slice(0, 4),
);
const completed = computed(
  () => props.records.tasks.filter((t) => t.status === "done").length,
);
const costs = computed(() =>
  expenseSummary(props.records.expenses, props.today),
);
const expenses = computed(() =>
  props.records.expenses
    .filter((e) => e.active)
    .sort((a, b) => a.next_due.localeCompare(b.next_due))
    .slice(0, 3),
);
const moments = computed(() =>
  props.records.milestones
    .map((m) => ({
      ...m,
      days: countdown(m.date, m.repeats_yearly, props.today),
    }))
    .filter((m) => m.days >= 0)
    .sort((a, b) => a.days - b.days)
    .slice(0, 3),
);
const shows = computed(() =>
  props.records.shows.filter((s) => s.status === "watching").slice(0, 3),
);
const dateLabel = computed(() =>
  new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
    timeZone: "UTC",
  }).format(new Date(`${props.today}T12:00:00Z`)),
);
const maintenanceDue = computed(() =>
  maintenanceReminders(props.records.maintenance, props.today),
);
const alive = computed(() =>
  props.user.birthday ? daysBetween(props.user.birthday, props.today) : null,
);
const dueCheckins = computed(() =>
  props.records.checkins
    .filter((item) => item.active && item.kind === "daily" && !item.days.includes(props.today))
    .slice(0, 3),
);
</script>
<template>
  <section class="page today-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">YOUR EVERYDAY, AT A GLANCE</span>
        <h1>今天，也好好生活<span class="title-period">.</span></h1>
        <p>
          {{ dateLabel }} <span class="dot-separator">·</span> 欢迎回来，{{
            user.display_name
          }}
        </p>
      </div>
      <button class="button primary" @click="emit('create', 'tasks')">
        <AppIcon name="plus" :size="18" />记一件事
      </button>
    </header>
    <section class="life-banner">
      <div class="life-banner-copy">
        <span class="banner-kicker"
          ><span class="live-dot"></span> LIFE IS HAPPENING</span
        >
        <h2 v-if="alive !== null">
          这是你与世界相遇的<br /><span
            >第 {{ Math.max(0, alive).toLocaleString() }} 天。</span
          >
        </h2>
        <h2 v-else>日子慢慢过，<br /><span>把美好一件件记下。</span></h2>
        <p>
          {{
            alive !== null
              ? "每个平凡的今天，都值得认真收藏。"
              : "留一点空间给自己，也给正在发生的生活。"
          }}
        </p>
        <button
          v-if="alive === null"
          class="banner-link"
          @click="emit('navigate', 'profile')"
        >
          设置生日，看看你的人生刻度<AppIcon name="arrow" :size="16" /></button
        ><span v-else class="banner-small"
          >以你的时区 {{ user.timezone }} 计算</span
        >
      </div>
      <div class="banner-art" aria-hidden="true">
        <span class="art-circle circle-a"></span
        ><span class="art-circle circle-b"></span
        ><span class="art-circle circle-c"></span>
        <div class="art-plant">
          <AppIcon name="leaf" :size="116" :stroke-width="0.8" />
        </div>
        <span class="art-caption">MAKE ROOM<br />FOR LIFE.</span>
      </div>
    </section>
    <section class="stats-grid">
      <button class="stat-card" @click="emit('navigate', 'tasks')">
        <span class="stat-top"><span>待完成</span><AppIcon name="tasks" /></span
        ><strong>{{ records.tasks.length - completed }}<small>件</small></strong
        ><span class="stat-bottom"
          >已完成 {{ completed }} 件<AppIcon name="up" :size="17"
        /></span></button
      ><button class="stat-card" @click="emit('navigate', 'expenses', 'bills')">
        <span class="stat-top"
          ><span>账单月均</span><AppIcon name="expenses" /></span
        ><strong class="stat-money">{{
          costs.length ? money(costs[0]!.monthly, costs[0]!.currency) : "—"
        }}</strong
        ><span class="stat-bottom"
          >{{
            costs.length > 1
              ? `另有 ${costs.length - 1} 种币种，点击查看`
              : `${records.expenses.filter((e) => e.active).length} 项使用中的账单`
          }}<AppIcon name="up" :size="17"
        /></span></button
      ><button class="stat-card" @click="emit('navigate', 'shows')">
        <span class="stat-top"><span>正在追</span><AppIcon name="shows" /></span
        ><strong
          >{{ records.shows.filter((s) => s.status === "watching").length
          }}<small>部</small></strong
        ><span class="stat-bottom"
          >给自己一点放松的时间<AppIcon name="up" :size="17"
        /></span></button
      ><button class="stat-card" @click="emit('navigate', 'milestones')">
        <span class="stat-top"
          ><span>值得期待</span><AppIcon name="milestones" /></span
        ><strong
          >{{ moments.length ? moments[0]!.days : "—"
          }}<small v-if="moments.length">天</small></strong
        ><span class="stat-bottom truncate"
          >{{ moments[0]?.title || "记录下一个特别的日子"
          }}<AppIcon name="up" :size="17"
        /></span>
      </button>
    </section>
    <section
      v-if="maintenanceDue.length"
      class="maintenance-reminder-panel"
      aria-label="维护提醒"
    >
      <header>
        <div>
          <span class="mini-symbol"
            ><AppIcon name="maintenance" :size="18"
          /></span>
          <div>
            <h2>该照料一下这些了</h2>
            <p>{{ maintenanceDue.length }} 项周期维护进入提醒时间</p>
          </div>
        </div>
        <button class="text-button" @click="emit('navigate', 'maintenance')">
          查看维护<AppIcon name="chevron" :size="15" />
        </button>
      </header>
      <button
        v-for="item in maintenanceDue.slice(0, 3)"
        :key="item.id"
        class="maintenance-reminder-row"
        :aria-label="`查看维护 ${item.title}`"
        @click="emit('navigate', 'maintenance')"
      >
        <span>{{ item.title }}</span
        ><span
          :class="{
            'text-orange': maintenanceTiming(item, today).remaining < 0,
          }"
          >{{ maintenanceTiming(item, today).label }}</span
        ><AppIcon name="chevron" :size="14" />
      </button>
    </section>
    <section v-if="dueCheckins.length" class="maintenance-reminder-panel" aria-label="今日打卡">
      <header>
        <div>
          <span class="mini-symbol sky"><AppIcon name="checkins" :size="18" /></span>
          <div>
            <h2>今天还没打卡</h2>
            <p>{{ dueCheckins.length }} 项每日必做在等你</p>
          </div>
        </div>
        <button class="text-button" @click="emit('navigate', 'checkins')">
          全部打卡<AppIcon name="chevron" :size="15" />
        </button>
      </header>
      <button
        v-for="item in dueCheckins"
        :key="item.id"
        class="maintenance-reminder-row"
        :aria-label="`打卡 ${item.title}`"
        :disabled="busy"
        @click="emit('checkin', item.id)"
      >
        <span>{{ item.title }}</span
        ><span>点我打卡</span
        ><AppIcon name="chevron" :size="14" />
      </button>
    </section>
    <div class="dashboard-grid">
      <section class="panel focus-panel">
        <header class="panel-heading">
          <div>
            <span class="section-index">01</span>
            <h2>接下来，做这些</h2>
          </div>
          <button class="text-button" @click="emit('navigate', 'tasks')">
            全部待办<AppIcon name="chevron" :size="15" />
          </button>
        </header>
        <div v-if="tasks.length" class="dashboard-tasks">
          <div v-for="task in tasks" :key="task.id" class="dashboard-task">
            <button
              class="task-check"
              :aria-label="`完成 ${task.title}`"
              :disabled="busy"
              @click="emit('complete', task.id)"
            ></button>
            <div>
              <h3>{{ task.title }}</h3>
              <span class="small muted">{{
                task.due_date
                  ? (task.due_date < today
                      ? "已逾期 · "
                      : task.due_date === today
                        ? "今天 · "
                        : "") + task.due_date
                  : "不设期限，按自己的节奏"
              }}</span>
            </div>
            <span :class="['tag', task.status]">{{ labels[task.status] }}</span>
          </div>
        </div>
        <EmptyState
          v-else
          icon="tasks"
          title="今天，从容一点"
          description="还没有待办。记下一件想做的小事，就很好。"
          action="添加第一件事"
          @action="emit('create', 'tasks')"
        /><button
          v-if="tasks.length"
          class="panel-add"
          @click="emit('create', 'tasks')"
        >
          <AppIcon name="plus" :size="17" />添加一件想做的事
        </button>
      </section>
      <section class="panel">
        <header class="panel-heading">
          <div>
            <span class="section-index">02</span>
            <h2>账单到期</h2>
          </div>
          <button
            class="icon-button"
            aria-label="查看全部账单"
            @click="emit('navigate', 'expenses', 'bills')"
          >
            <AppIcon name="up" :size="18" />
          </button>
        </header>
        <div v-if="expenses.length" class="compact-list">
          <div
            v-for="expense in expenses"
            :key="expense.id"
            class="compact-row"
          >
            <span class="mini-symbol"
              ><AppIcon name="expenses" :size="18"
            /></span>
            <div>
              <h3>{{ expense.title }}</h3>
              <p>
                {{ expense.next_due < today ? "已逾期 · " : ""
                }}{{ expense.next_due }}
              </p>
            </div>
            <strong>{{ money(expense.amount_cents, expense.currency) }}</strong>
          </div>
        </div>
        <EmptyState
          v-else
          icon="expenses"
          title="钱去哪了，记下来就清楚"
          description="先记一笔开销，或添加一条周期性账单。"
          action="去记账"
          @action="emit('create', 'expenses')"
        />
      </section>
      <section class="panel">
        <header class="panel-heading">
          <div>
            <span class="section-index">03</span>
            <h2>留一点时间给故事</h2>
          </div>
          <button class="text-button" @click="emit('navigate', 'shows')">
            我的片单<AppIcon name="chevron" :size="15" />
          </button>
        </header>
        <div v-if="shows.length" class="compact-list">
          <div v-for="show in shows" :key="show.id" class="compact-row">
            <span class="mini-symbol lavender"
              ><AppIcon name="shows" :size="18"
            /></span>
            <div>
              <h3>{{ show.title }}</h3>
              <p>已看 {{ show.progress }} / {{ show.total ?? "—" }} 集</p>
            </div>
            <span class="tag watching">在看</span>
          </div>
        </div>
        <EmptyState
          v-else
          icon="shows"
          title="给自己一场好故事"
          description="把想看的作品放进片单，下次就知道看什么。"
          action="添加作品"
          @action="emit('create', 'shows')"
        />
      </section>
      <section class="panel moments-panel">
        <header class="panel-heading">
          <div>
            <span class="section-index">04</span>
            <h2>生活里的小期待</h2>
          </div>
          <button
            class="icon-button"
            aria-label="查看全部重要日子"
            @click="emit('navigate', 'milestones')"
          >
            <AppIcon name="up" :size="18" />
          </button>
        </header>
        <div v-if="moments.length" class="compact-list">
          <div v-for="moment in moments" :key="moment.id" class="compact-row">
            <span class="mini-symbol peach"
              ><AppIcon name="milestones" :size="18"
            /></span>
            <div>
              <h3>{{ moment.title }}</h3>
              <p>
                {{ moment.repeats_yearly ? "每年都值得纪念" : moment.date }}
              </p>
            </div>
            <strong class="days-pill"
              >{{ moment.days }}<small> 天</small></strong
            >
          </div>
        </div>
        <EmptyState
          v-else
          icon="milestones"
          title="让期待有一个日期"
          description="生日、旅行、纪念日，每一种期待都算数。"
          action="添加重要日子"
          @action="emit('create', 'milestones')"
        />
      </section>
    </div>
    <footer class="dashboard-footer">
      <AppIcon name="leaf" :size="15" /> 日常有序，自在生活。<span
        >DIGITAL LIFE</span
      >
    </footer>
  </section>
</template>
