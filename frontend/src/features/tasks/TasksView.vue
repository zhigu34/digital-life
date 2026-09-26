<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import AppIcon from "../../components/AppIcon.vue";
import EmptyState from "../../components/EmptyState.vue";
import type { GroupItem, Task, TaskGroup } from "../../types";
import GroupCard from "./GroupCard.vue";
import GroupForm from "./GroupForm.vue";
import HistoryDialog from "./HistoryDialog.vue";
import ItemForm from "./ItemForm.vue";
import TaskCard from "./TaskCard.vue";
import { useGroups } from "./useGroups";
import type { GroupPayload } from "./api";
import "./tasks.css";

const props = defineProps<{
  tasks: Task[];
  today: string;
  busy: boolean;
  /** Bumped by the shell when the today overview asks for a form. */
  createRequest: { kind: "todo" | "group"; nonce: number } | null;
  /** Bumped by the today overview to check an item without leaving the page. */
  checkRequest: { groupId: number; itemId: number; nonce: number } | null;
}>();
const emit = defineEmits<{
  sync: [groups: TaskGroup[]];
  notice: [message: string];
  error: [error: unknown];
  create: [kind: "todo"];
  toggleTask: [task: Task];
  editTask: [task: Task];
  removeTask: [task: Task];
}>();

const store = useGroups((rows) => emit("sync", rows));
const { groups, loading, error } = store;
const working = computed(() => props.busy || store.busy.value);
const filter = ref<"all" | "once" | "group" | "done">("all");
const search = ref("");
const creating = ref(false);
const formError = ref("");
const editingGroup = ref<TaskGroup | null>(null);
const editingItem = ref<{ group: TaskGroup; item?: GroupItem } | null>(null);
/** Ids only: the dialog must follow the live item, which is replaced on check. */
const detail = ref<{ groupId: number; itemId: number } | null>(null);
const detailGroup = computed(() => groups.value.find((group) => group.id === detail.value?.groupId));
const detailItem = computed(() =>
  detailGroup.value?.items.find((item) => item.id === detail.value?.itemId),
);
const tabs = [
  ["all", "全部"],
  ["once", "待办"],
  ["group", "长期任务"],
  ["done", "已完成"],
] as const;

function matches(text: string): boolean {
  const keyword = search.value.trim().toLowerCase();
  return !keyword || text.toLowerCase().includes(keyword);
}
const visibleTasks = computed(() =>
  props.tasks.filter(
    (task) =>
      matches(`${task.title} ${task.notes}`) &&
      (filter.value === "all" ||
        filter.value === "once" ||
        (filter.value === "done" && task.status === "done")),
  ),
);
const visibleGroups = computed(() =>
  !["all", "group"].includes(filter.value)
    ? []
    : groups.value.filter((group) =>
        matches([group.title, group.notes, ...group.items.map((item) => item.title)].join(" ")),
      ),
);
const hasAnything = computed(() => props.tasks.length > 0 || groups.value.length > 0);
const doneCount = computed(() => props.tasks.filter((task) => task.status === "done").length);

/** The group a live item belongs to, so actions always carry both ids. */
function groupOf(item: GroupItem): TaskGroup | undefined {
  return groups.value.find((group) => group.items.some((row) => row.id === item.id));
}

async function toggle(item: GroupItem) {
  const group = groupOf(item);
  if (!group) return;
  try {
    if (item.recent_days.includes(props.today)) {
      if (!window.confirm(`撤销“${item.title}”今天的打卡？`)) return;
      await store.undo(group.id, item.id, props.today);
      emit("notice", "已撤销今天的打卡");
    } else {
      await store.check(group.id, item.id);
      emit("notice", `已打卡：${item.title}`);
    }
  } catch (e) {
    emit("error", e);
  }
}

async function reload() {
  try {
    await store.load();
  } catch (e) {
    emit("error", e);
  }
}

async function saveGroup(payload: Record<string, unknown>) {
  formError.value = "";
  try {
    if (editingGroup.value) {
      await store.update(editingGroup.value.id, payload);
      editingGroup.value = null;
      emit("notice", "长期任务已更新");
      return;
    }
    await store.add(payload as unknown as GroupPayload);
    creating.value = false;
    emit("notice", "长期任务已添加");
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存失败";
    emit("error", e);
  }
}

function openGroupForm(group?: TaskGroup) {
  formError.value = "";
  if (group) editingGroup.value = group;
  else creating.value = true;
}

function openItemForm(group: TaskGroup, item?: GroupItem) {
  formError.value = "";
  editingItem.value = { group, item };
}

function closeForms() {
  creating.value = false;
  editingGroup.value = null;
  editingItem.value = null;
  formError.value = "";
}

function openHistory(group: TaskGroup, item: GroupItem) {
  detail.value = { groupId: group.id, itemId: item.id };
}

async function checkInPeriod(payload: { on: string; note: string }) {
  const target = detail.value;
  if (!target) return;
  try {
    await store.check(target.groupId, target.itemId, payload);
    emit("notice", "已记录这次打卡");
  } catch (e) {
    emit("error", e);
  }
}

async function undoInPeriod(on: string) {
  const target = detail.value;
  if (!target) return;
  try {
    await store.undo(target.groupId, target.itemId, on);
    emit("notice", "已删除该天记录");
  } catch (e) {
    emit("error", e);
  }
}

function editFromHistory() {
  const group = detailGroup.value;
  const item = detailItem.value;
  detail.value = null;
  if (group && item) openItemForm(group, item);
}

async function saveItem(payload: Record<string, unknown>) {
  formError.value = "";
  const target = editingItem.value;
  if (!target) return;
  try {
    const values = {
      title: payload.title,
      repeat_unit: payload.repeat_unit,
      start_date: payload.start_date,
    };
    if (target.item) await store.saveItem(target.group.id, target.item.id, values);
    else await store.addItem(target.group.id, values as { title: string; repeat_unit: "day" });
    editingItem.value = null;
    emit("notice", target.item ? "打卡项已更新" : "打卡项已添加");
  } catch (e) {
    formError.value = e instanceof Error ? e.message : "保存失败";
    emit("error", e);
  }
}

async function removeGroup(group: TaskGroup) {
  if (!window.confirm(`确定删除“${group.title}”及组内全部打卡记录？删除后无法恢复。`)) return;
  try {
    await store.remove(group.id);
    emit("notice", "长期任务已删除");
  } catch (e) {
    emit("error", e);
  }
}

async function removeItem(group: TaskGroup, item: GroupItem) {
  try {
    await store.removeItem(group.id, item.id);
    detail.value = null;
    emit("notice", "打卡项已删除");
  } catch (e) {
    emit("error", e);
  }
}

async function toggleArchive(group: TaskGroup) {
  const question = group.archived
    ? `恢复“${group.title}”？恢复后重新开始计算周期。`
    : `归档“${group.title}”？归档后不再期待新的周期，历史记录会保留。`;
  if (!window.confirm(question)) return;
  try {
    await store.update(group.id, { archived: !group.archived });
    emit("notice", group.archived ? "已恢复长期任务" : "已归档长期任务");
  } catch (e) {
    emit("error", e);
  }
}

async function checkFromRequest(groupId: number, itemId: number) {
  try {
    await store.check(groupId, itemId);
    emit("notice", "已打卡");
  } catch (e) {
    emit("error", e);
  }
}

onMounted(() => {
  void reload();
});

// Both run immediately: the shell may hand over a request in the same tick it
// navigates here, before this component has mounted.
watch(
  () => props.createRequest,
  (request) => {
    if (!request) return;
    if (request.kind === "todo") emit("create", "todo");
    else openGroupForm();
  },
  { immediate: true },
);
watch(
  () => props.checkRequest,
  (request) => {
    if (request) void checkFromRequest(request.groupId, request.itemId);
  },
  { immediate: true },
);
</script>

<template>
  <section class="page collection-page tasks-page">
    <div v-if="error" class="global-error" role="alert">
      <span>{{ error }}</span><button class="text-button" @click="reload">重新加载</button>
    </div>
    <div v-if="loading" class="loading-line" role="status" aria-label="正在同步任务"></div>
    <header class="page-heading">
      <div>
        <span class="eyebrow">ONE OFF, OR EVERY DAY</span>
        <h1>任务<span class="title-period">.</span><span class="heading-count">{{ tasks.length + groups.length }}</span></h1>
        <p>一次就能做完的记成待办；想长期坚持的，放进分组里按周期打卡。</p>
      </div>
      <div class="heading-actions">
        <button class="button secondary" :disabled="working" @click="openGroupForm()">
          <AppIcon name="plus" :size="18" />添加长期任务
        </button>
        <button class="button primary" :disabled="working" @click="emit('create', 'todo')">
          <AppIcon name="plus" :size="18" />添加待办
        </button>
      </div>
    </header>

    <div class="collection-toolbar">
      <div class="tabs" aria-label="任务筛选">
        <button
          v-for="[value, label] in tabs"
          :key="value"
          :class="{ active: filter === value }"
          @click="filter = value"
        >
          {{ label }}
        </button>
      </div>
      <span class="muted small">
        {{ tasks.length - doneCount }} 件待办 · {{ groups.length }} 个长期任务
      </span>
      <label class="search-box"
        ><AppIcon name="search" :size="17" /><input
          v-model="search"
          aria-label="搜索任务"
          placeholder="搜索任务…"
      /></label>
    </div>

    <EmptyState
      v-if="!loading && !hasAnything"
      icon="tasks"
      title="从一件小事开始"
      description="记下今天想完成的事，或者把想坚持的事放进一个长期任务里。"
      action="添加第一件待办"
      @action="emit('create', 'todo')"
    />
    <EmptyState
      v-else-if="!visibleTasks.length && !visibleGroups.length"
      icon="search"
      title="没有找到对应任务"
      description="试试其他关键词，或切换筛选。"
    />

    <div v-else class="record-list">
      <TaskCard
        v-for="task in visibleTasks"
        :key="`task-${task.id}`"
        :task="task"
        :today="today"
        :busy="working"
        @toggle="emit('toggleTask', task)"
        @edit="emit('editTask', task)"
        @remove="emit('removeTask', task)"
      />
      <GroupCard
        v-for="group in visibleGroups"
        :key="`group-${group.id}`"
        :group="group"
        :today="today"
        :busy="working"
        @toggle="toggle"
        @open="(item) => openHistory(group, item)"
        @add-item="openItemForm(group)"
        @edit="openGroupForm(group)"
        @archive="toggleArchive(group)"
        @remove-item="(item) => removeItem(group, item)"
        @remove="removeGroup(group)"
      />
    </div>

    <div v-if="visibleGroups.length" class="period-legend">
      <span><i class="done"></i>周期内已达标</span>
      <span><i class="missed"></i>周期结束仍未达标</span>
      <span><i class="pending"></i>当前周期进行中</span>
      <span><i class="before"></i>开始日期之前或已归档</span>
      <span>角标 = 该周期完成次数</span>
    </div>

    <p v-if="hasAnything" class="page-footnote">一点一滴，都是生活的痕迹。</p>

    <GroupForm
      v-if="creating || editingGroup"
      :group="editingGroup ?? undefined"
      :busy="working"
      :error="formError"
      @close="closeForms"
      @save="saveGroup"
    />
    <ItemForm
      v-if="editingItem"
      :item="editingItem.item"
      :group-title="editingItem.group.title"
      :today="today"
      :busy="working"
      :error="formError"
      @close="closeForms"
      @save="saveItem"
    />
    <HistoryDialog
      v-if="detail && detailGroup && detailItem"
      :group="detailGroup"
      :item="detailItem"
      :today="today"
      :busy="working"
      :error="formError"
      @close="detail = null"
      @check="checkInPeriod"
      @undo="undoInPeriod"
      @edit="editFromHistory"
      @remove="removeItem(detailGroup, detailItem)"
      @error="emit('error', $event)"
    />
  </section>
</template>
