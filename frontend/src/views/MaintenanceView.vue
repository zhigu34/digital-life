<script setup lang="ts">
import { computed, onUnmounted, reactive, ref } from "vue";
import { api, ApiError } from "../api";
import { money } from "../domain";
import { maintenanceTiming, nextMaintenanceDate } from "../maintenance";
import type { Maintenance, MaintenanceLog } from "../types";
import AppIcon from "../components/AppIcon.vue";
import EmptyState from "../components/EmptyState.vue";
import ModalDialog from "../components/ModalDialog.vue";

const props = defineProps<{
  items: Maintenance[];
  today: string;
  parentBusy: boolean;
}>();
const emit = defineEmits<{
  refresh: [];
  error: [error: unknown];
  notice: [message: string];
  remove: [item: Maintenance];
}>();
const mode = ref<"create" | "edit" | "complete" | "history" | "correct" | null>(
  null,
);
const selected = ref<Maintenance | null>(null),
  selectedLog = ref<MaintenanceLog | null>(null);
const history = ref<MaintenanceLog[]>([]),
  busy = ref(false),
  historyLoading = ref(false),
  error = ref("");
const search = ref(""),
  filter = ref("all");
const working = computed(() => busy.value || props.parentBusy);
const config = reactive({
  title: "",
  notes: "",
  period_value: 1,
  period_unit: "months" as "days" | "months",
  remind_days: 7,
  active: true,
  last_completed: props.today,
});
const completion = reactive({
  completed_on: props.today,
  cost: "",
  currency: "CNY",
  notes: "",
});
let disposed = false;
onUnmounted(() => {
  disposed = true;
});
const rows = computed(() =>
  props.items
    .filter(
      (item) =>
        item.title.toLowerCase().includes(search.value.toLowerCase()) &&
        (filter.value === "all" ||
          (filter.value === "active" && item.active) ||
          (filter.value === "due" &&
            maintenanceTiming(item, props.today).remind) ||
          (filter.value === "inactive" && !item.active)),
    )
    .sort(
      (a, b) =>
        Number(b.active) - Number(a.active) ||
        a.next_due.localeCompare(b.next_due),
    ),
);
const reminderCount = computed(
  () =>
    props.items.filter((item) => maintenanceTiming(item, props.today).remind)
      .length,
);
const preview = computed(() => {
  try {
    return nextMaintenanceDate(
      config.last_completed,
      Number(config.period_value),
      config.period_unit,
    );
  } catch {
    return "";
  }
});
const modalTitle = computed(() =>
  mode.value === "create"
    ? "添加维护"
    : mode.value === "edit"
      ? "编辑维护"
      : mode.value === "complete"
        ? "记录完成"
        : mode.value === "correct"
          ? "修正记录"
          : "完成历史",
);
function close() {
  if (busy.value) return;
  mode.value = null;
  error.value = "";
  history.value = [];
  selected.value = null;
  selectedLog.value = null;
}
function showConfig(item?: Maintenance) {
  error.value = "";
  selected.value = item ?? null;
  mode.value = item ? "edit" : "create";
  Object.assign(
    config,
    item
      ? {
          title: item.title,
          notes: item.notes,
          period_value: item.period_value,
          period_unit: item.period_unit,
          remind_days: item.remind_days,
          active: item.active,
          last_completed: item.last_completed,
        }
      : {
          title: "",
          notes: "",
          period_value: 1,
          period_unit: "months",
          remind_days: 7,
          active: true,
          last_completed: props.today,
        },
  );
}
function showCompletion(item: Maintenance) {
  error.value = "";
  selected.value = item;
  selectedLog.value = null;
  mode.value = "complete";
  Object.assign(completion, {
    completed_on: props.today,
    cost: "",
    currency: "CNY",
    notes: "",
  });
}
function showCorrection(log: MaintenanceLog) {
  error.value = "";
  selectedLog.value = log;
  mode.value = "correct";
  Object.assign(completion, {
    completed_on: log.completed_on,
    cost: log.cost_cents === null ? "" : (log.cost_cents / 100).toFixed(2),
    currency: log.currency,
    notes: log.notes,
  });
}
function fail(e: unknown) {
  if (disposed) return;
  if (e instanceof ApiError && e.status === 401) {
    emit("error", e);
    return;
  }
  error.value = e instanceof Error ? e.message : "操作失败，请重试";
}
async function saveConfig() {
  busy.value = true;
  error.value = "";
  try {
    const data: {
      title: string;
      notes: string;
      period_value: number;
      period_unit: "days" | "months";
      remind_days: number;
      active: boolean;
      last_completed?: string;
    } = {
      title: config.title,
      notes: config.notes,
      period_value: Number(config.period_value),
      period_unit: config.period_unit,
      remind_days: Number(config.remind_days),
      active: config.active,
    };
    if (mode.value === "create") data.last_completed = config.last_completed;
    await api(
      `/maintenance${mode.value === "edit" ? `/${selected.value!.id}` : ""}`,
      mode.value === "edit" ? "PATCH" : "POST",
      data,
    );
    if (disposed) return;
    mode.value = null;
    emit("refresh");
    emit("notice", "维护事项已保存");
  } catch (e) {
    fail(e);
  } finally {
    busy.value = false;
  }
}
async function saveCompletion() {
  if (!selected.value) return;
  busy.value = true;
  error.value = "";
  try {
    const cost =
      completion.cost === "" ? null : Math.round(Number(completion.cost) * 100);
    const data = {
      completed_on: completion.completed_on,
      cost_cents: cost,
      currency: completion.currency,
      notes: completion.notes,
    };
    const correcting = mode.value === "correct";
    const item = await api<Maintenance>(
      `/maintenance/${selected.value.id}/${correcting ? `history/${selectedLog.value!.id}` : "complete"}`,
      correcting ? "PATCH" : "POST",
      data,
    );
    if (disposed) return;
    selected.value = item;
    emit("refresh");
    emit(
      "notice",
      correcting
        ? "完成记录已修正，到期日期已重新计算"
        : "完成已记录，下次到期日期已更新",
    );
    if (correcting) {
      mode.value = "history";
      await fetchHistory();
    } else mode.value = null;
  } catch (e) {
    fail(e);
  } finally {
    busy.value = false;
  }
}
async function fetchHistory() {
  if (!selected.value) return;
  historyLoading.value = true;
  error.value = "";
  const id = selected.value.id;
  try {
    const logs = await api<MaintenanceLog[]>(`/maintenance/${id}/history`);
    if (!disposed && selected.value?.id === id) history.value = logs;
  } catch (e) {
    fail(e);
  } finally {
    historyLoading.value = false;
  }
}
async function showHistory(item: Maintenance) {
  selected.value = item;
  history.value = [];
  mode.value = "history";
  await fetchHistory();
}
function remove(item: Maintenance) {
  emit("remove", item);
}
</script>

<template>
  <section class="page maintenance-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">CARE FOR WHAT CARRIES YOU</span>
        <h1>
          周期维护<span class="heading-count">{{ items.length }}</span>
        </h1>
        <p>滤芯、清洗、保养。把定期照料的事，安心记在这里。</p>
      </div>
      <button class="button primary" :disabled="working" @click="showConfig()">
        <AppIcon name="plus" :size="18" />添加维护
      </button>
    </header>
    <div class="maintenance-intro">
      <span class="record-symbol"><AppIcon name="maintenance" /></span>
      <div>
        <strong>{{
          reminderCount
            ? "有 " + reminderCount + " 项维护需要留意"
            : "照料日常，也照料安心"
        }}</strong>
        <p>每次实际完成后，重新计算下一次到期。费用和细节会留在完成历史里。</p>
      </div>
    </div>
    <div class="collection-toolbar">
      <div class="tabs" aria-label="维护状态筛选">
        <button
          v-for="[value, label] in [
            ['all', '全部'],
            ['due', '待留意'],
            ['active', '使用中'],
            ['inactive', '已停用'],
          ]"
          :key="value"
          :class="{ active: filter === value }"
          @click="filter = value!"
        >
          {{ label }}
        </button>
      </div>
      <label class="search-box"
        ><AppIcon name="search" :size="17" /><input
          v-model="search"
          aria-label="搜索维护"
          placeholder="搜索维护…"
      /></label>
    </div>
    <EmptyState
      v-if="!items.length"
      icon="maintenance"
      title="把定期照料，交给日历"
      description="从更换滤芯、清洗空调或一次保养开始，记下上次完成的日期。"
      action="添加第一项维护"
      @action="showConfig()"
    />
    <EmptyState
      v-else-if="!rows.length"
      icon="search"
      title="这里暂时没有对应事项"
      description="试试其他关键词，或切换维护状态。"
    />
    <div v-else class="maintenance-grid">
      <article
        v-for="item in rows"
        :key="item.id"
        class="maintenance-card"
        :class="{
          'maintenance-inactive': !item.active,
          'maintenance-alert': maintenanceTiming(item, today).remind,
        }"
      >
        <header>
          <span class="record-symbol"><AppIcon name="maintenance" /></span
          ><span
            class="tag"
            :class="{
              'maintenance-due-tag': maintenanceTiming(item, today).remind,
            }"
            >{{ maintenanceTiming(item, today).label }}</span
          >
          <div class="record-actions">
            <button
              class="icon-button"
              :aria-label="`编辑维护 ${item.title}`"
              :disabled="working"
              @click="showConfig(item)"
            >
              <AppIcon name="edit" :size="16" /></button
            ><button
              class="icon-button danger-hover"
              :aria-label="`删除维护 ${item.title}`"
              :disabled="working"
              @click="remove(item)"
            >
              <AppIcon name="delete" :size="16" />
            </button>
          </div>
        </header>
        <h2>{{ item.title }}</h2>
        <p v-if="item.notes" class="record-notes">{{ item.notes }}</p>
        <div class="maintenance-elapsed">
          <span>距离上次完成</span
          ><strong
            >{{ maintenanceTiming(item, today).elapsed
            }}<small>天</small></strong
          ><span>已过 {{ maintenanceTiming(item, today).elapsed }} 天</span>
        </div>
        <dl class="maintenance-dates">
          <div>
            <dt>上次完成</dt>
            <dd>{{ item.last_completed }}</dd>
          </div>
          <div>
            <dt>下次到期</dt>
            <dd>{{ item.next_due }}</dd>
          </div>
        </dl>
        <p class="maintenance-cycle">
          每 {{ item.period_value }}
          {{
            item.period_unit === "days" ? "天" : "个月"
          }}一次<span>·</span>提前 {{ item.remind_days }} 天提醒
        </p>
        <footer>
          <button
            class="button secondary compact"
            :disabled="working"
            @click="showHistory(item)"
          >
            <AppIcon name="history" :size="15" />查看历史</button
          ><button
            class="button primary compact"
            :disabled="working || !item.active"
            @click="showCompletion(item)"
          >
            <AppIcon name="check" :size="15" />记录完成
          </button>
        </footer>
      </article>
    </div>
    <p v-if="items.length" class="page-footnote">
      好好照料的日常，会回赠你长久的安心。
    </p>

    <ModalDialog
      v-if="mode"
      :title="modalTitle"
      :subtitle="selected?.title ?? '记下实际完成日期，从这里开始照料。'"
      @close="close"
    >
      <form
        v-if="mode === 'create' || mode === 'edit'"
        @submit.prevent="saveConfig"
      >
        <label
          >名称<input
            v-model="config.title"
            required
            maxlength="120"
            autofocus
            placeholder="例如：更换净水器滤芯"
        /></label>
        <label v-if="mode === 'create'"
          >上次完成日期<input
            v-model="config.last_completed"
            type="date"
            required
            min="0001-01-01"
            :max="today"
        /></label>
        <p v-else class="field-hint maintenance-hint">
          上次完成
          {{
            config.last_completed
          }}。如需修改实际日期，请在完成历史中修正记录。
        </p>
        <div class="form-grid">
          <label
            >周期数值<input
              v-model.number="config.period_value"
              type="number"
              min="1"
              :max="config.period_unit === 'months' ? 120 : 3650"
              step="1"
              required /></label
          ><label
            >周期单位<select v-model="config.period_unit">
              <option value="days">天</option>
              <option value="months">月</option>
            </select></label
          >
        </div>
        <label
          >提前提醒天数<input
            v-model.number="config.remind_days"
            type="number"
            min="0"
            max="365"
            step="1"
            required
        /></label>
        <p class="field-hint">
          {{
            preview
              ? "按当前设置，下次到期 " + preview
              : "请选择有效的完成日期和周期。"
          }}<br />按月周期以实际完成日计算，遇到短月取月底。
        </p>
        <label class="checkbox-label"
          ><input v-model="config.active" type="checkbox" />正在使用</label
        ><label
          >维护备注 <span class="optional">选填</span
          ><textarea
            v-model="config.notes"
            rows="3"
            maxlength="4000"
            placeholder="型号、规格或需要留意的细节…"
          ></textarea>
        </label>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <footer class="modal-actions">
          <button
            type="button"
            class="button secondary"
            :disabled="working"
            @click="close"
          >
            取消</button
          ><button class="button primary" :disabled="working || !preview">
            {{ busy ? "保存中…" : "保存维护" }}
          </button>
        </footer>
      </form>
      <form
        v-else-if="mode === 'complete' || mode === 'correct'"
        @submit.prevent="saveCompletion"
      >
        <label
          >完成日期<input
            v-model="completion.completed_on"
            type="date"
            required
            min="0001-01-01"
            :max="today"
            autofocus
        /></label>
        <div class="form-grid">
          <label
            >费用 <span class="optional">选填</span
            ><input
              v-model="completion.cost"
              type="number"
              min="0"
              max="1000000"
              step="0.01"
              placeholder="未记录" /></label
          ><label
            >币种<select v-model="completion.currency">
              <option
                v-for="currency in ['CNY', 'USD', 'EUR', 'JPY', 'HKD']"
                :key="currency"
              >
                {{ currency }}
              </option>
            </select></label
          >
        </div>
        <label
          >完成备注 <span class="optional">选填</span
          ><textarea
            v-model="completion.notes"
            rows="3"
            maxlength="4000"
            placeholder="这次换了什么，或做了哪些保养…"
          ></textarea>
        </label>
        <p class="field-hint">
          可以补录过去的日期，同一天只保留一条完成记录。下次到期始终按最新完成日期计算。
        </p>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <footer class="modal-actions">
          <button
            type="button"
            class="button secondary"
            :disabled="working"
            @click="
              mode === 'correct' ? ((mode = 'history'), (error = '')) : close()
            "
          >
            {{ mode === "correct" ? "返回历史" : "取消" }}</button
          ><button class="button primary" :disabled="working">
            {{
              busy ? "保存中…" : mode === "correct" ? "保存修正" : "确认完成"
            }}
          </button>
        </footer>
      </form>
      <div v-else class="maintenance-history">
        <div v-if="selected" class="history-current">
          <span
            >当前上次完成 <b>{{ selected.last_completed }}</b></span
          ><span
            >下次到期 <b>{{ selected.next_due }}</b></span
          >
        </div>
        <p v-if="historyLoading" role="status" class="muted small">
          正在读取完成历史…
        </p>
        <div v-else-if="error" class="form-error" role="alert">
          {{ error
          }}<button class="text-button" @click="fetchHistory">重新加载</button>
        </div>
        <article v-for="log in history" :key="log.id" class="history-entry">
          <div class="history-entry-heading">
            <span class="mini-symbol"><AppIcon name="check" :size="16" /></span>
            <div>
              <h3>{{ log.completed_on }}</h3>
              <span class="small muted">{{
                log.cost_cents === null
                  ? "未记录费用"
                  : money(log.cost_cents, log.currency)
              }}</span>
            </div>
            <button
              class="text-button"
              :disabled="working"
              @click="showCorrection(log)"
            >
              修正记录<AppIcon name="edit" :size="13" />
            </button>
          </div>
          <p v-if="log.notes">{{ log.notes }}</p>
        </article>
        <p class="field-hint maintenance-hint">
          记录按实际完成日期排序。修正日期后，会重新计算上次完成与下次到期。
        </p>
        <footer class="modal-actions">
          <button class="button secondary" :disabled="working" @click="close">
            关闭历史
          </button>
        </footer>
      </div>
    </ModalDialog>
  </section>
</template>
