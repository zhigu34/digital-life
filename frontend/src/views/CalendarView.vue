<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { Records, Page } from "../types";
import {
  buildCalendarEvents,
  monthGrid,
  kindLabels,
  kindPages,
  type CalendarEvent,
  type CalendarKind,
} from "../calendar";
import AppIcon from "../components/AppIcon.vue";

const props = defineProps<{ records: Records; today: string }>();
const emit = defineEmits<{ navigate: [page: Page] }>();

const [initialYear, initialMonth] = props.today.split("-").map(Number);
const year = ref(initialYear!),
  month = ref(initialMonth!),
  selected = ref(props.today);
const grid = computed(() => monthGrid(year.value, month.value));
const events = computed(() =>
  buildCalendarEvents(props.records, year.value, month.value, props.today),
);
const monthTitle = computed(() =>
  new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year.value, month.value - 1, 15))),
);
const selectedEvents = computed(() => events.value.get(selected.value) ?? []);
const selectedLabel = computed(() =>
  new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
    timeZone: "UTC",
  }).format(new Date(`${selected.value}T12:00:00Z`)),
);
const monthCounts = computed(() => {
  const counts: Record<CalendarKind, number> = {
    task: 0,
    expense: 0,
    milestone: 0,
    maintenance: 0,
  };
  for (const list of events.value.values())
    for (const event of list) counts[event.kind]++;
  return counts;
});
function shift(delta: number) {
  const total = year.value * 12 + month.value - 1 + delta;
  year.value = Math.floor(total / 12);
  month.value = (total % 12) + 1;
}
watch([year, month], () => {
  const prefix = `${year.value}-${String(month.value).padStart(2, "0")}-`;
  if (!selected.value.startsWith(prefix))
    selected.value = `${prefix}01`;
});
function backToToday() {
  year.value = initialYear!;
  month.value = initialMonth!;
  selected.value = props.today;
}
const kindIcons: Record<CalendarKind, string> = {
  task: "tasks",
  expense: "expenses",
  milestone: "milestones",
  maintenance: "maintenance",
};
const cellEvents = (date: string): CalendarEvent[] =>
  events.value.get(date) ?? [];
</script>
<template>
  <section class="page calendar-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">DAYS, SIDE BY SIDE</span>
        <h1>所有日子，一张日历<span class="title-period">.</span></h1>
        <p>
          待办截止、周期扣费、维护到期和值得纪念的日子，在同一格里看见。
        </p>
      </div>
    </header>
    <section class="panel calendar-card" aria-label="月历">
      <header class="calendar-head">
        <div>
          <strong>{{ monthTitle }}</strong>
          <span class="calendar-month-count"
            >{{ monthCounts.maintenance + monthCounts.expense }} 项安排</span
          >
        </div>
        <div class="calendar-controls">
          <button
            class="icon-button icon-flip"
            aria-label="上一个月"
            @click="shift(-1)"
          >
            <AppIcon name="chevron" :size="17" />
          </button>
          <button class="calendar-today-button" @click="backToToday">
            今天
          </button>
          <button class="icon-button" aria-label="下一个月" @click="shift(1)">
            <AppIcon name="chevron" :size="17" />
          </button>
        </div>
      </header>
      <div class="calendar-weekdays" aria-hidden="true">
        <span v-for="weekday in ['一', '二', '三', '四', '五', '六', '日']" :key="weekday">{{ weekday }}</span>
      </div>
      <div class="calendar-grid">
        <div
          v-for="cell in grid"
          :key="cell.date"
          :class="['calendar-cell', { outside: !cell.inMonth }]"
        >
          <button
            v-if="cell.inMonth"
            :class="[
              'cell-hit',
              {
                today: cell.date === today,
                selected: cell.date === selected,
                'has-events': cellEvents(cell.date).length > 0,
              },
            ]"
            :aria-label="`查看 ${cell.date} 的安排`"
            @click="selected = cell.date"
          >
            <span class="cell-day">{{ cell.day }}</span>
            <span
              v-for="event in cellEvents(cell.date).slice(0, 2)"
              :key="`${event.kind}-${event.id}`"
              :class="['cal-chip', event.kind, { overdue: event.overdue }]"
              >{{ event.title }}</span
            >
            <span v-if="cellEvents(cell.date).length > 2" class="cell-more"
              >还有 {{ cellEvents(cell.date).length - 2 }} 项</span
            >
          </button>
          <span v-else class="cell-day">{{ cell.day }}</span>
        </div>
      </div>
      <footer class="calendar-legend">
        <span
          v-for="(label, kind) in kindLabels"
          :key="kind"
          :class="['legend-chip', kind]"
          >{{ label }} {{ monthCounts[kind] }}</span
        >
      </footer>
    </section>
    <section class="panel calendar-day-panel" aria-label="当日安排">
      <header class="panel-heading">
        <div>
          <span class="section-index">{{
            selected === today ? "TODAY" : "SELECTED"
          }}</span>
          <h2>{{ selectedLabel }}</h2>
        </div>
      </header>
      <div v-if="selectedEvents.length" class="compact-list">
        <button
          v-for="event in selectedEvents"
          :key="`${event.kind}-${event.id}`"
          class="compact-row calendar-event-row"
          :aria-label="`查看${kindLabels[event.kind]}：${event.title}`"
          @click="emit('navigate', kindPages[event.kind])"
        >
          <span :class="['mini-symbol', event.kind]"
            ><AppIcon :name="kindIcons[event.kind]" :size="18"
          /></span>
          <div>
            <h3>{{ event.title }}</h3>
            <p>
              {{ event.overdue ? "已逾期 · " : "" }}{{ event.detail }}
            </p>
          </div>
          <span :class="['tag', event.kind]">{{ kindLabels[event.kind] }}</span>
        </button>
      </div>
      <div v-else class="calendar-day-empty">
        <AppIcon name="leaf" :size="22" />
        <p>这一天暂无安排，留白也是一种安排。</p>
      </div>
    </section>
  </section>
</template>
