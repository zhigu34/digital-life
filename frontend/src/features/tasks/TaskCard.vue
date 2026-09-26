<script setup lang="ts">
import AppIcon from "../../components/AppIcon.vue";
import { daysBetween, labels } from "../../domain";
import type { Task } from "../../types";

defineProps<{ task: Task; today: string; busy: boolean }>();
const emit = defineEmits<{ toggle: []; edit: []; remove: [] }>();

function dueLabel(date: string, today: string): string {
  const days = daysBetween(today, date);
  if (days < 0) return `逾期 ${-days} 天`;
  if (days === 0) return "今天到期";
  if (days === 1) return "明天到期";
  return date.replaceAll("-", ".");
}

function completedLabel(date: string): string {
  const [, month, day] = date.split("-").map(Number) as [number, number, number];
  return `已于 ${month} 月 ${day} 日完成`;
}
</script>

<template>
  <article class="record-card" :class="{ 'is-done': task.status === 'done' }">
    <button
      class="task-check"
      :class="{ checked: task.status === 'done' }"
      :aria-label="`${task.status === 'done' ? '重新打开' : '完成'} ${task.title}`"
      :disabled="busy"
      @click="emit('toggle')"
    >
      <AppIcon v-if="task.status === 'done'" name="check" :size="15" />
    </button>
    <div class="record-body">
      <h3>{{ task.title }}</h3>
      <p v-if="task.notes" class="record-notes">{{ task.notes }}</p>
      <div class="record-meta">
        <span :class="['tag', task.status]">{{ labels[task.status] }}</span>
        <span v-if="task.priority !== 'normal'" :class="{ 'text-orange': task.priority === 'high' }">
          {{ labels[task.priority] }}
        </span>
        <span v-if="task.completed_on">{{ completedLabel(task.completed_on) }}</span>
        <span
          v-else-if="task.due_date"
          :class="{ 'text-orange': task.due_date < today }"
        >
          <AppIcon name="calendar" :size="13" />{{ dueLabel(task.due_date, today) }}
        </span>
        <span v-else>不设期限</span>
      </div>
    </div>
    <div class="record-actions">
      <button class="icon-button" :aria-label="`编辑 ${task.title}`" :disabled="busy" @click="emit('edit')">
        <AppIcon name="edit" :size="16" />
      </button>
      <button
        class="icon-button danger-hover"
        :aria-label="`删除 ${task.title}`"
        :disabled="busy"
        @click="emit('remove')"
      >
        <AppIcon name="delete" :size="16" />
      </button>
    </div>
  </article>
</template>
