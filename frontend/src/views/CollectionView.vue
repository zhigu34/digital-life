<script setup lang="ts">
import { computed, ref } from "vue";
import type { Records, RecordItem } from "../types";
import { labels, countdown, daysBetween } from "../domain";
import AppIcon from "../components/AppIcon.vue";
import EmptyState from "../components/EmptyState.vue";

const props = defineProps<{
  collection: "tasks" | "milestones";
  records: Records;
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
  milestones: {
    title: "重要日子",
    kicker: "MOMENTS THAT MATTER",
    description: "平凡的日期，也可以装着特别的意义。",
    add: "添加日子",
    empty: "总有一些日子值得记住",
    hint: "生日、周年、旅行出发日，把期待留在这里。",
  },
};
const current = computed(
  () => config[props.collection as keyof typeof config],
);
const filtered = computed(() =>
  props.records[props.collection].filter(
    (item) =>
      item.title.toLowerCase().includes(search.value.toLowerCase()) &&
      (filter.value === "all" ||
        ("status" in item && item.status === filter.value)),
  ),
);
const tabs = computed(() =>
  props.collection === "tasks"
    ? ["all", "todo", "doing", "waiting", "done"]
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
      :class="['record-list', { 'card-grid': collection === 'milestones' }]"
    >
      <article
        v-for="item in filtered"
        :key="item.id"
        class="record-card"
        :class="{ 'is-done': 'status' in item && item.status === 'done' }"
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
        <div class="record-actions">
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
