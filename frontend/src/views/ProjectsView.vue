<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { api, ApiError } from "../api";
import type { Project } from "../types";
import { labels } from "../domain";
import AppIcon from "../components/AppIcon.vue";
import EmptyState from "../components/EmptyState.vue";
import ModalDialog from "../components/ModalDialog.vue";

const props = defineProps<{
  projects: Project[];
  busy: boolean;
}>();
const emit = defineEmits<{
  save: [data: Record<string, unknown>, id?: number];
  remove: [item: Project];
  error: [error: unknown];
}>();
const mode = ref<"create" | "edit" | null>(null),
  selected = ref<Project | null>(null),
  error = ref("");
const form = reactive({ title: "", notes: "", status: "active" });
const tabs = [
  ["all", "全部"],
  ["active", "进行中"],
  ["paused", "暂缓"],
  ["done", "已完成"],
] as const;
const filter = ref("all");
const rows = computed(() =>
  props.projects
    .filter((item) => filter.value === "all" || item.status === filter.value)
    .sort(
      (a, b) =>
        Number(a.status === "active") * -1 - Number(b.status === "active") * -1 ||
        Number(a.status === "paused") * -1 - Number(b.status === "paused") * -1 ||
        b.id - a.id,
    ),
);
const activeCount = computed(
  () => props.projects.filter((item) => item.status === "active").length,
);
function openEditor(item?: Project) {
  error.value = "";
  selected.value = item ?? null;
  mode.value = item ? "edit" : "create";
  form.title = item ? item.title : "";
  form.notes = item ? item.notes : "";
  form.status = item ? item.status : "active";
}
function submit() {
  emit("save", { ...form }, selected.value?.id);
  mode.value = null;
}
function setStatus(item: Project, status: Project["status"]) {
  emit("save", { title: item.title, notes: item.notes, status }, item.id);
}
</script>
<template>
  <section class="page projects-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">WHAT YOU ARE BUILDING</span>
        <h1>在做<span class="title-period">.</span></h1>
        <p>正在推进的事，一个个看着它们完成。</p>
      </div>
      <button class="button primary" :disabled="busy" @click="openEditor()">
        <AppIcon name="plus" :size="18" />添加在做
      </button>
    </header>
    <div class="collection-toolbar">
      <div class="tabs" aria-label="状态筛选">
        <button
          v-for="[value, label] in tabs"
          :key="value"
          :class="{ active: filter === value }"
          @click="filter = value"
        >
          {{ label }}
        </button>
      </div>
      <span class="muted small"
        >{{ activeCount }} 个进行中 · {{ projects.length }} 个全部</span
      >
    </div>
    <EmptyState
      v-if="!rows.length"
      icon="projects"
      title="把正在做的事放进来"
      description="项目开发、装修、学一门手艺，进行中的事都值得一个位置。"
      action="添加第一个在做"
      @action="openEditor()"
    />
    <div v-else class="project-list">
      <article v-for="item in rows" :key="item.id" class="project-card">
        <div class="project-body">
          <div class="checkin-title-row">
            <h3>{{ item.title }}</h3>
            <span :class="['tag', item.status]">{{ labels[item.status] }}</span>
          </div>
          <p v-if="item.notes" class="record-notes">{{ item.notes }}</p>
          <p class="muted small">始于 {{ item.created_at.slice(0, 10) }}</p>
        </div>
        <div class="project-actions">
          <template v-if="item.status !== 'done'">
            <button
              v-if="item.status === 'active'"
              class="text-button"
              :disabled="busy"
              @click="setStatus(item, 'paused')"
            >
              暂缓</button
            ><button
              v-else
              class="text-button"
              :disabled="busy"
              @click="setStatus(item, 'active')"
            >
              继续</button
            ><button
              class="text-button"
              :disabled="busy"
              @click="setStatus(item, 'done')"
            >
              完成
            </button>
          </template>
          <button
            class="icon-button"
            :aria-label="`编辑 ${item.title}`"
            :disabled="busy"
            @click="openEditor(item)"
          >
            <AppIcon name="edit" :size="16" /></button
          ><button
            class="icon-button danger-hover"
            :aria-label="`删除 ${item.title}`"
            :disabled="busy"
            @click="emit('remove', item)"
          >
            <AppIcon name="delete" :size="16" />
          </button>
        </div>
      </article>
    </div>
    <ModalDialog
      v-if="mode"
      :title="mode === 'create' ? '添加在做' : '编辑在做'"
      subtitle="正在推进的事，慢慢来。"
      @close="mode = null"
    >
      <form class="record-form" @submit.prevent="submit">
        <label
          >名称<input
            v-model="form.title"
            required
            minlength="1"
            maxlength="120"
            placeholder="例如：项目开发"
        /></label>
        <label
          >说明 <span class="optional">选填</span
          ><textarea
            v-model="form.notes"
            rows="4"
            maxlength="4000"
            placeholder="目标、进度或下一步…"
          ></textarea>
        </label>
        <label
          >状态<select v-model="form.status">
            <option value="active">进行中</option>
            <option value="paused">暂缓</option>
            <option value="done">已完成</option>
          </select></label
        >
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <footer class="modal-actions">
          <button type="button" class="button secondary" @click="mode = null">
            取消</button
          ><button class="button primary" :disabled="busy">保存</button>
        </footer>
      </form>
    </ModalDialog>
  </section>
</template>
