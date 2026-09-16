<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { api, ApiError } from "../api";
import type { CheckInItem, CheckInLogEntry } from "../types";
import { currentStreak, countInRange, lastDays, weekdayLabel, daysSinceLastCheck } from "../checkin";
import AppIcon from "../components/AppIcon.vue";
import EmptyState from "../components/EmptyState.vue";
import ModalDialog from "../components/ModalDialog.vue";

const props = defineProps<{
  items: CheckInItem[];
  today: string;
  parentBusy: boolean;
}>();
const emit = defineEmits<{
  refresh: [];
  notice: [message: string];
  error: [error: unknown];
}>();
const mode = ref<"create" | "edit" | "manage" | null>(null),
  selected = ref<CheckInItem | null>(null),
  busy = ref(false),
  error = ref(""),
  filter = ref("all"),
  logs = ref<CheckInLogEntry[]>([]),
  logsLoading = ref(false);
const form = reactive({ title: "", notes: "", kind: "daily", active: true });
const makeup = reactive({ checked_on: props.today, note: "" });
const working = computed(() => busy.value || props.parentBusy);
const tabs = [
  ["all", "全部"],
  ["daily", "每日必做"],
  ["ongoing", "在做"],
  ["archived", "已归档"],
] as const;
const rows = computed(() =>
  props.items
    .filter(
      (item) =>
        filter.value === "all"
          ? item.active
          : filter.value === "archived"
            ? !item.active
            : item.active && item.kind === filter.value,
    )
    .sort((a, b) => Number(b.active) - Number(a.active) || b.id - a.id),
);
const week = computed(() => lastDays(props.today, 7));
const streakOf = (item: CheckInItem) => currentStreak(item.days, props.today);
const weekOf = (item: CheckInItem) => countInRange(item.days, week.value[0]!, props.today);
function openEditor(item?: CheckInItem) {
  error.value = "";
  selected.value = item ?? null;
  mode.value = item ? "edit" : "create";
  Object.assign(form, item ?? { title: "", notes: "", kind: "daily", active: true });
}
async function save() {
  if (working.value) return;
  busy.value = true;
  error.value = "";
  try {
    await api(
      `/checkins${selected.value ? `/${selected.value.id}` : ""}`,
      selected.value ? "PATCH" : "POST",
      { ...form },
    );
    mode.value = null;
    emit("refresh");
    emit("notice", selected.value ? "打卡项目已更新" : "打卡项目已添加");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) emit("error", e);
    else error.value = e instanceof Error ? e.message : "保存失败";
  } finally {
    busy.value = false;
  }
}
async function remove(item: CheckInItem) {
  if (working.value) return;
  if (!window.confirm(`确定删除“${item.title}”及全部打卡记录？删除后无法恢复。`)) return;
  busy.value = true;
  try {
    await api(`/checkins/${item.id}`, "DELETE");
    emit("refresh");
    emit("notice", "打卡项目已删除");
  } catch (e) {
    emit("error", e);
  } finally {
    busy.value = false;
  }
}
async function check(item: CheckInItem) {
  if (working.value) return;
  if (item.days.includes(props.today)) {
    if (!window.confirm(`撤销“${item.title}”今天的打卡？`)) return;
    busy.value = true;
    try {
      await api(`/checkins/${item.id}/check/${props.today}`, "DELETE");
      emit("refresh");
      emit("notice", "已撤销今天的打卡");
    } catch (e) {
      emit("error", e);
    } finally {
      busy.value = false;
    }
    return;
  }
  busy.value = true;
  try {
    await api(`/checkins/${item.id}/check`, "POST", {});
    emit("refresh");
    emit("notice", `已打卡：${item.title}`);
  } catch (e) {
    emit("error", e);
  } finally {
    busy.value = false;
  }
}
async function openManager(item: CheckInItem) {
  error.value = "";
  selected.value = item;
  mode.value = "manage";
  Object.assign(makeup, { checked_on: props.today, note: "" });
  logs.value = [];
  logsLoading.value = true;
  try {
    logs.value = await api<CheckInLogEntry[]>(`/checkins/${item.id}/logs`);
  } catch (e) {
    emit("error", e);
    mode.value = null;
  } finally {
    logsLoading.value = false;
  }
}
async function submitMakeup() {
  if (!selected.value || working.value) return;
  busy.value = true;
  error.value = "";
  try {
    await api(`/checkins/${selected.value.id}/check`, "POST", { ...makeup });
    Object.assign(makeup, { checked_on: props.today, note: "" });
    logs.value = await api<CheckInLogEntry[]>(`/checkins/${selected.value.id}/logs`);
    emit("refresh");
    emit("notice", "打卡记录已保存");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) emit("error", e);
    else error.value = e instanceof Error ? e.message : "保存失败";
  } finally {
    busy.value = false;
  }
}
async function removeLog(log: CheckInLogEntry) {
  if (!selected.value || working.value) return;
  busy.value = true;
  try {
    await api(`/checkins/${selected.value.id}/check/${log.checked_on}`, "DELETE");
    logs.value = await api<CheckInLogEntry[]>(`/checkins/${selected.value.id}/logs`);
    emit("refresh");
    emit("notice", "已删除该天记录");
  } catch (e) {
    emit("error", e);
  } finally {
    busy.value = false;
  }
}
const kindLabels: Record<string, string> = { daily: "每日必做", ongoing: "在做" };
</script>
<template>
  <section class="page checkins-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">SHOW UP EVERY DAY</span>
        <h1>打卡<span class="title-period">.</span></h1>
        <p>每天必做的事和正在推进的事，点一下就算数。</p>
      </div>
      <button class="button primary" :disabled="working" @click="openEditor()">
        <AppIcon name="plus" :size="18" />添加打卡
      </button>
    </header>
    <div class="collection-toolbar">
      <div class="tabs" aria-label="打卡类型筛选">
        <button
          v-for="[value, label] in tabs"
          :key="value"
          :class="{ active: filter === value }"
          @click="filter = value"
        >
          {{ label }}
        </button>
      </div>
      <span class="muted small">{{ rows.length }} 个项目</span>
    </div>
    <EmptyState
      v-if="!rows.length"
      icon="checkins"
      title="从一件小事开始坚持"
      description="每天健身一小时、读几页书，或者给正在做的项目打个卡。"
      action="添加第一个打卡"
      @action="openEditor()"
    />
    <div v-else class="checkin-list">
      <article v-for="item in rows" :key="item.id" class="checkin-card">
        <button
          class="checkin-hit"
          :class="{ done: item.days.includes(today), inactive: !item.active }"
          :aria-label="`${item.days.includes(today) ? '撤销今天打卡' : '打卡'} ${item.title}`"
          :disabled="working || !item.active"
          @click="check(item)"
        >
          <AppIcon v-if="item.days.includes(today)" name="check" :size="22" />
        </button>
        <div class="checkin-body">
          <div class="checkin-title-row">
            <h3>{{ item.title }}</h3>
            <span :class="['tag', item.kind]">{{ kindLabels[item.kind] }}</span>
          </div>
          <p v-if="item.notes" class="record-notes">{{ item.notes }}</p>
          <p class="checkin-stats">
            <template v-if="item.kind === 'daily'"
              ><strong>连续 {{ streakOf(item) }}</strong> 天 · 累计
              {{ item.total_count }} 天 · 本周 {{ weekOf(item) }} 天</template
            >
            <template v-else
              >累计 <strong>{{ item.total_count }}</strong> 天 · 本周
              {{ weekOf(item) }} 天 ·
              {{
                daysSinceLastCheck(item, today) === null
                  ? "还没打过卡"
                  : daysSinceLastCheck(item, today) === 0
                    ? "今天刚打过"
                    : `最近 ${daysSinceLastCheck(item, today)} 天前`
              }}</template
            >
          </p>
          <div v-if="item.kind === 'daily'" class="checkin-week" aria-label="最近七天">
            <span
              v-for="day in week"
              :key="day"
              :class="{
                hit: item.days.includes(day),
                today: day === today,
              }"
              ><i>{{ weekdayLabel(day) }}</i></span
            >
          </div>
        </div>
        <div class="record-actions">
          <button
            class="icon-button"
            :aria-label="`管理打卡记录 ${item.title}`"
            :disabled="working"
            @click="openManager(item)"
          >
            <AppIcon name="history" :size="16" /></button
          ><button
            class="icon-button"
            :aria-label="`编辑打卡 ${item.title}`"
            :disabled="working"
            @click="openEditor(item)"
          >
            <AppIcon name="edit" :size="16" /></button
          ><button
            class="icon-button danger-hover"
            :aria-label="`删除打卡 ${item.title}`"
            :disabled="working"
            @click="remove(item)"
          >
            <AppIcon name="delete" :size="16" />
          </button>
        </div>
      </article>
    </div>
    <ModalDialog
      v-if="mode === 'create' || mode === 'edit'"
      :title="mode === 'create' ? '添加打卡' : '编辑打卡'"
      subtitle="坚持的小事，也值得被记录。"
      @close="mode = null"
    >
      <form class="record-form" @submit.prevent="save">
        <label
          >名称<input
            v-model="form.title"
            required
            minlength="1"
            maxlength="120"
            placeholder="例如：健身1小时"
        /></label>
        <label
          >类型<select v-model="form.kind">
            <option value="daily">每日必做（连续天数）</option>
            <option value="ongoing">在做（累计天数）</option>
          </select></label
        >
        <label
          >备注 <span class="optional">选填</span
          ><textarea v-model="form.notes" rows="3" maxlength="4000"></textarea>
        </label>
        <label class="checkbox-label"
          ><input v-model="form.active" type="checkbox" />启用（归档后保留记录但不能打卡）</label
        >
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <footer class="modal-actions">
          <button type="button" class="button secondary" @click="mode = null">
            取消</button
          ><button class="button primary" :disabled="working">
            {{ working ? "保存中…" : "保存" }}
          </button>
        </footer>
      </form>
    </ModalDialog>
    <ModalDialog
      v-if="mode === 'manage' && selected"
      :title="`打卡记录 · ${selected.title}`"
      subtitle="补卡、检查和修正历史记录。"
      @close="mode = null"
    >
      <form class="record-form" @submit.prevent="submitMakeup">
        <div class="form-grid">
          <label
            >日期<input v-model="makeup.checked_on" type="date" required /></label
          >
        </div>
        <label
          >当天备注 <span class="optional">选填</span
          ><input v-model="makeup.note" maxlength="4000" placeholder="例如：练了背"
        /></label>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <footer class="modal-actions">
          <button type="button" class="button secondary" @click="mode = null">
            完成</button
          ><button class="button primary" :disabled="working">
            {{ working ? "保存中…" : "记一笔" }}
          </button>
        </footer>
      </form>
      <div class="checkin-log-list" aria-label="历史打卡">
        <p v-if="logsLoading" class="muted small">正在加载…</p>
        <p v-else-if="!logs.length" class="muted small">还没有任何记录。</p>
        <div v-for="log in logs" :key="log.id" class="checkin-log-row">
          <strong>{{ log.checked_on }}</strong>
          <span class="muted small">{{ log.note || "—" }}</span>
          <button
            class="icon-button danger-hover"
            :aria-label="`删除 ${log.checked_on} 的记录`"
            :disabled="working"
            @click="removeLog(log)"
          >
            <AppIcon name="delete" :size="15" />
          </button>
        </div>
      </div>
    </ModalDialog>
  </section>
</template>
