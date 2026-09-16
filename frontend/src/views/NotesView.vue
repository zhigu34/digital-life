<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { api, ApiError } from "../api";
import type { Note } from "../types";
import AppIcon from "../components/AppIcon.vue";
import EmptyState from "../components/EmptyState.vue";
import ModalDialog from "../components/ModalDialog.vue";

const props = defineProps<{
  items: Note[];
  today: string;
  parentBusy: boolean;
}>();
const emit = defineEmits<{
  refresh: [];
  notice: [message: string];
  error: [error: unknown];
}>();
const mode = ref<"create" | "edit" | null>(null),
  selected = ref<Note | null>(null),
  busy = ref(false),
  error = ref(""),
  search = ref("");
const form = reactive({ content: "", entry_date: props.today });
const working = computed(() => busy.value || props.parentBusy);
const groups = computed(() => {
  const keyword = search.value.trim().toLowerCase();
  const rows = props.items
    .filter((item) => item.content.toLowerCase().includes(keyword))
    .sort((a, b) => b.entry_date.localeCompare(a.entry_date) || b.id - a.id);
  const grouped: { date: string; label: string; entries: Note[] }[] = [];
  for (const item of rows) {
    const last = grouped.at(-1);
    if (last && last.date === item.entry_date) last.entries.push(item);
    else
      grouped.push({
        date: item.entry_date,
        label: dayLabel(item.entry_date),
        entries: [item],
      });
  }
  return grouped;
});
function dayLabel(date: string) {
  const formatted = new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
    timeZone: "UTC",
  }).format(new Date(`${date}T12:00:00Z`));
  return date === props.today ? `今天 · ${formatted}` : formatted;
}
function openEditor(item?: Note) {
  error.value = "";
  selected.value = item ?? null;
  mode.value = item ? "edit" : "create";
  form.content = item ? item.content : "";
  form.entry_date = item ? item.entry_date : props.today;
}
async function save() {
  if (working.value) return;
  busy.value = true;
  error.value = "";
  try {
    await api(
      `/notes${selected.value ? `/${selected.value.id}` : ""}`,
      selected.value ? "PATCH" : "POST",
      { ...form },
    );
    mode.value = null;
    emit("refresh");
    emit("notice", selected.value ? "随记已更新" : "已记下这一刻");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) emit("error", e);
    else error.value = e instanceof Error ? e.message : "保存失败";
  } finally {
    busy.value = false;
  }
}
async function remove(item: Note) {
  if (working.value) return;
  const preview =
    item.content.length > 20 ? `${item.content.slice(0, 20)}…` : item.content;
  if (!window.confirm(`确定删除“${preview}”？删除后无法恢复。`)) return;
  busy.value = true;
  try {
    await api(`/notes/${item.id}`, "DELETE");
    emit("refresh");
    emit("notice", "随记已删除");
  } catch (e) {
    emit("error", e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section class="page notes-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">SMALL MOMENTS, KEPT</span>
        <h1>文字随记<span class="title-period">.</span></h1>
        <p>一段话、一个念头，都值得被自己看见。</p>
      </div>
      <button class="button primary" :disabled="working" @click="openEditor()">
        <AppIcon name="plus" :size="18" />写一条
      </button>
    </header>
    <div class="collection-toolbar">
      <span class="muted small"
        >{{ items.length }} 条随记 · 按记录日期倒序</span
      ><label class="search-box"
        ><AppIcon name="search" :size="17" /><input
          v-model="search"
          aria-label="搜索随记"
          placeholder="搜索内容…"
      /></label>
    </div>
    <EmptyState
      v-if="!items.length"
      icon="notes"
      title="把此刻写下来"
      description="一句话也行。今天的心情、突然的想法，都留在这里。"
      action="写第一条"
      @action="openEditor()"
    /><EmptyState
      v-else-if="!groups.length"
      icon="search"
      title="没有找到相关随记"
      description="试试其他关键词。"
    />
    <div v-else class="notes-list">
      <section
        v-for="group in groups"
        :key="group.date"
        class="notes-group"
        :aria-label="group.label"
      >
        <h2>{{ group.label }}</h2>
        <article v-for="item in group.entries" :key="item.id" class="note-card">
          <p class="note-content">{{ item.content }}</p>
          <div class="note-actions">
            <span class="muted small">{{
              item.created_at.slice(0, 10) === item.entry_date
                ? "当天记下"
                : `记于 ${item.created_at.slice(0, 10)}`
            }}</span>
            <button
              class="icon-button"
              :aria-label="`编辑随记`"
              :disabled="working"
              @click="openEditor(item)"
            >
              <AppIcon name="edit" :size="16" /></button
            ><button
              class="icon-button danger-hover"
              :aria-label="`删除随记`"
              :disabled="working"
              @click="remove(item)"
            >
              <AppIcon name="delete" :size="16" />
            </button>
          </div>
        </article>
      </section>
    </div>
    <ModalDialog
      v-if="mode"
      :title="mode === 'create' ? '写一条随记' : '编辑随记'"
      subtitle="只属于你的私人记录。"
      @close="mode = null"
    >
      <form class="note-form" @submit.prevent="save">
        <label
          >内容<textarea
            v-model="form.content"
            required
            minlength="1"
            maxlength="4000"
            rows="6"
            placeholder="今天发生了什么，或者想到了什么…"
          ></textarea
        ></label>
        <label
          >记录日期<input v-model="form.entry_date" type="date" required />
        </label>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="modal-actions">
          <button type="button" class="button secondary" @click="mode = null">
            取消
          </button>
          <button class="button primary" :disabled="working">
            {{ mode === "create" ? "记下这一刻" : "保存修改" }}
          </button>
        </div>
      </form>
    </ModalDialog>
  </section>
</template>
