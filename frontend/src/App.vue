<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { api, ApiError, setCsrf } from "./api";
import { calendarDate } from "./domain";
import type {
  User,
  Records,
  Collection,
  Page,
  RecordItem,
  Maintenance,
  Stats,
} from "./types";
import AppIcon from "./components/AppIcon.vue";
import RecordForm from "./components/RecordForm.vue";
import LoginView from "./views/LoginView.vue";
import TodayView from "./views/TodayView.vue";
import CalendarView from "./views/CalendarView.vue";
import CollectionView from "./views/CollectionView.vue";
import ProfileView from "./views/ProfileView.vue";
import AdminView from "./views/AdminView.vue";
import MaintenanceView from "./views/MaintenanceView.vue";
import NotesView from "./views/NotesView.vue";
const user = ref<User | null>(null),
  initializing = ref(true),
  loading = ref(false),
  busy = ref(false),
  error = ref(""),
  loginError = ref(""),
  notice = ref("");
const records = reactive<Records>({
  tasks: [],
  expenses: [],
  shows: [],
  milestones: [],
  maintenance: [],
  notes: [],
});
const stats = ref<Stats | null>(null);
const page = ref<Page>("today"),
  editing = ref<{ collection: Collection; item?: RecordItem } | null>(null),
  formError = ref("");
const now = ref(new Date()),
  today = computed(() =>
    calendarDate(user.value?.timezone ?? "Asia/Shanghai", now.value),
  );
const navigation: [Page, string, string][] = [
  ["today", "今日概览", "你的生活，此刻"],
  ["calendar", "日历", ""],
  ["tasks", "待办清单", ""],
  ["expenses", "周期费用", ""],
  ["shows", "追剧片单", ""],
  ["milestones", "重要日子", ""],
  ["maintenance", "周期维护", ""],
  ["notes", "文字随记", ""],
];
const pageLabels: Record<Page, string> = {
  today: "今日概览",
  calendar: "日历",
  tasks: "待办清单",
  expenses: "周期费用",
  shows: "追剧片单",
  milestones: "重要日子",
  maintenance: "周期维护",
  notes: "文字随记",
  profile: "个人设置",
  admin: "账户管理",
};
const mobileNavLabels: Record<string, string> = {
  today: "今日",
  calendar: "日历",
  tasks: "待办",
  expenses: "费用",
  shows: "追剧",
  milestones: "日子",
  maintenance: "维护",
  notes: "随记",
};
let noticeTimer: ReturnType<typeof setTimeout>,
  clockTimer: ReturnType<typeof setInterval>;
let accountVersion = 0;
function clear() {
  accountVersion++;
  user.value = null;
  setCsrf("");
  Object.assign(records, {
    tasks: [],
    expenses: [],
    shows: [],
    milestones: [],
    maintenance: [],
    notes: [],
  });
  stats.value = null;
  editing.value = null;
  page.value = "today";
  error.value = "";
  notice.value = "";
  document.documentElement.dataset.theme = "light";
}
function notify(message: string) {
  notice.value = message;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => (notice.value = ""), 4200);
}
function handleError(e: unknown) {
  if (e instanceof ApiError && e.status === 401) {
    clear();
    loginError.value = "登录已过期，请重新登录";
    return;
  }
  error.value = e instanceof Error ? e.message : "连接失败，请检查网络后重试";
}
async function load() {
  const version = accountVersion;
  loading.value = true;
  error.value = "";
  try {
    const [tasks, expenses, shows, milestones, maintenance, notes, statsData] =
      await Promise.all([
        api<Records["tasks"]>("/tasks"),
        api<Records["expenses"]>("/expenses"),
        api<Records["shows"]>("/shows"),
        api<Records["milestones"]>("/milestones"),
        api<Records["maintenance"]>("/maintenance"),
        api<Records["notes"]>("/notes"),
        api<Stats>(`/stats?end_month=${today.value.slice(0, 7)}`),
      ]);
    if (version === accountVersion) {
      Object.assign(records, {
        tasks,
        expenses,
        shows,
        milestones,
        maintenance,
        notes,
      });
      stats.value = statsData;
    }
  } catch (e) {
    if (version === accountVersion) handleError(e);
  } finally {
    if (version === accountVersion) loading.value = false;
  }
}
async function login(username: string, password: string) {
  busy.value = true;
  loginError.value = "";
  try {
    clear();
    const session = await api<{ user: User; csrf_token: string }>(
      "/auth/login",
      "POST",
      { username, password },
    );
    user.value = session.user;
    setCsrf(session.csrf_token);
    await load();
  } catch (e) {
    loginError.value = e instanceof Error ? e.message : "登录失败，请重试";
  } finally {
    busy.value = false;
  }
}
async function logout() {
  busy.value = true;
  try {
    await api("/auth/logout", "POST");
    clear();
  } catch (e) {
    handleError(e);
  } finally {
    busy.value = false;
  }
}
function navigate(destination: Page) {
  page.value = destination;
  editing.value = null;
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function open(collection: Collection, item?: RecordItem) {
  formError.value = "";
  editing.value = { collection, item };
}
async function save(data: Record<string, unknown>) {
  if (!editing.value) return;
  busy.value = true;
  formError.value = "";
  const { collection, item } = editing.value;
  try {
    await api(
      `/${collection}${item ? `/${item.id}` : ""}`,
      item ? "PATCH" : "POST",
      data,
    );
    editing.value = null;
    await load();
    notify(item ? "记录已更新" : "已添入你的日常");
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) handleError(e);
    else formError.value = e instanceof Error ? e.message : "保存失败";
  } finally {
    busy.value = false;
  }
}
async function remove(collection: Collection, item: RecordItem) {
  if (!window.confirm(`确定删除“${item.title}”？删除后无法恢复。`)) return;
  await mutate(`/${collection}/${item.id}`, "DELETE", undefined, "记录已删除");
}
async function mutate(
  path: string,
  method: string,
  data?: unknown,
  message = "已更新",
) {
  busy.value = true;
  error.value = "";
  try {
    await api(path, method, data);
    await load();
    notify(message);
  } catch (e) {
    handleError(e);
  } finally {
    busy.value = false;
  }
}
async function removeMaintenance(item: Maintenance) {
  if (
    !window.confirm(`确定删除“${item.title}”及其全部完成历史？删除后无法恢复。`)
  )
    return;
  await mutate(
    `/maintenance/${item.id}`,
    "DELETE",
    undefined,
    "维护事项及历史已删除",
  );
}
function action(
  collection: Collection,
  id: number,
  kind: string,
  data?: unknown,
) {
  if (
    kind === "pay" &&
    !window.confirm("确认本期已经支付？下次应付日期将向后推进一个周期。")
  )
    return;
  return mutate(
    `/${collection}/${id}${kind === "status" ? "" : `/${kind}`}`,
    kind === "status" ? "PATCH" : "POST",
    data,
    kind === "pay"
      ? "本期已付，下次日期已更新"
      : kind === "advance"
        ? "又看完一集，进度已更新"
        : "状态已更新",
  );
}
async function profile(data: unknown) {
  busy.value = true;
  try {
    user.value = await api<User>("/auth/profile", "PATCH", data);
    notify("个人资料已保存");
  } catch (e) {
    handleError(e);
  } finally {
    busy.value = false;
  }
}
async function password(data: unknown) {
  busy.value = true;
  try {
    await api("/auth/password", "POST", data);
    clear();
    loginError.value = "密码已更新，请使用新密码登录";
  } catch (e) {
    handleError(e);
  } finally {
    busy.value = false;
  }
}
async function exportData() {
  busy.value = true;
  try {
    const data = await api("/export");
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `digital-life-${today.value}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify("你的数据已导出");
  } catch (e) {
    handleError(e);
  } finally {
    busy.value = false;
  }
}
async function importData(data: unknown) {
  busy.value = true;
  error.value = "";
  try {
    const result = await api<{ imported: Record<string, number> }>(
      "/import",
      "POST",
      data,
    );
    await load();
    notify(`已导入 ${Object.values(result.imported).reduce((a, b) => a + b, 0)} 条记录`);
  } catch (e) {
    handleError(e);
  } finally {
    busy.value = false;
  }
}
const media = window.matchMedia("(prefers-color-scheme: dark)");
function theme() {
  document.documentElement.dataset.theme =
    user.value?.theme === "dark" ||
    (user.value?.theme === "system" && media.matches)
      ? "dark"
      : "light";
}
watch(() => user.value?.theme, theme);
onMounted(async () => {
  media.addEventListener("change", theme);
  clockTimer = setInterval(() => (now.value = new Date()), 60000);
  try {
    const session = await api<{ user: User; csrf_token: string }>(
      "/auth/session",
    );
    user.value = session.user;
    setCsrf(session.csrf_token);
    await load();
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 401))
      loginError.value = e instanceof Error ? e.message : "无法连接服务器";
  } finally {
    initializing.value = false;
  }
});
onUnmounted(() => {
  media.removeEventListener("change", theme);
  clearInterval(clockTimer);
  clearTimeout(noticeTimer);
});
</script>
<template>
  <div v-if="initializing" class="initial-loading">
    <span class="brand-mark"><AppIcon name="leaf" :size="30" /></span>
    <p>正在打开你的生活空间…</p>
    <AppIcon name="loading" class="spin" />
  </div>
  <LoginView
    v-else-if="!user"
    :busy="busy"
    :error="loginError"
    @login="login"
  />
  <div v-else class="app-shell">
    <aside class="sidebar">
      <button class="brand" @click="navigate('today')">
        <span class="brand-mark"><AppIcon name="leaf" :size="23" /></span
        >digital life<span class="brand-dot">.</span></button
      ><span class="sidebar-label">我的生活空间</span>
      <nav class="main-nav" aria-label="主导航">
        <button
          v-for="[id, label] in navigation"
          :key="id"
          :aria-label="id === 'today' ? '今日总览' : label"
          :class="{ active: page === id }"
          @click="navigate(id)"
        >
          <AppIcon :name="id" /><span>{{ label }}</span
          ><span
            v-if="
              id === 'tasks' && records.tasks.some((t) => t.status !== 'done')
            "
            class="nav-count"
            >{{ records.tasks.filter((t) => t.status !== "done").length }}</span
          ><span v-if="page === id" class="nav-active-dot"></span>
        </button>
      </nav>
      <div class="sidebar-bottom">
        <div class="sidebar-note">
          <AppIcon name="sun" :size="24" />
          <p>小事有条理，<br />生活有余地。</p>
          <span>MAKE ROOM FOR LIFE</span>
        </div>
        <button
          v-if="user.is_admin"
          aria-label="账号管理"
          :class="['sidebar-option', { active: page === 'admin' }]"
          @click="navigate('admin')"
        >
          <AppIcon name="admin" :size="18" />账户管理</button
        ><button
          :class="['sidebar-option', { active: page === 'profile' }]"
          @click="navigate('profile')"
        >
          <AppIcon name="profile" :size="18" />个人设置
        </button>
        <div class="sidebar-user">
          <span class="avatar">{{ user.display_name.slice(0, 1) }}</span
          ><button @click="navigate('profile')">
            <strong>{{ user.display_name }}</strong
            ><small>我的私人空间</small></button
          ><button
            class="icon-button"
            aria-label="退出登录"
            :disabled="busy"
            @click="logout"
          >
            <AppIcon name="logout" :size="17" />
          </button>
        </div>
      </div>
    </aside>
    <main class="main-shell">
      <header class="topbar">
        <div class="breadcrumb">
          <span>我的空间</span><AppIcon name="chevron" :size="13" /><strong>{{
            pageLabels[page]
          }}</strong>
        </div>
        <div class="topbar-right">
          <span class="privacy-dot"></span><span>只属于你的日常</span
          ><button
            v-if="user.is_admin"
            class="mobile-admin icon-button"
            aria-label="账号管理"
            @click="navigate('admin')"
          >
            <AppIcon name="admin" :size="18" /></button
          ><button
            class="mobile-avatar avatar"
            aria-label="个人设置"
            @click="navigate('profile')"
          >
            {{ user.display_name.slice(0, 1) }}
          </button>
        </div>
      </header>
      <div v-if="error" class="global-error" role="alert">
        <span>{{ error }}</span
        ><button class="text-button" @click="load">重新加载</button
        ><button
          class="icon-button"
          aria-label="关闭错误提示"
          @click="error = ''"
        >
          <AppIcon name="close" :size="16" />
        </button>
      </div>
      <div
        v-if="loading"
        class="loading-line"
        role="status"
        aria-label="正在同步记录"
      ></div>
      <TodayView
        v-if="page === 'today'"
        :user="user"
        :records="records"
        :today="today"
        :busy="busy"
        @navigate="navigate"
        @create="open"
        @complete="(id) => action('tasks', id, 'status', { status: 'done' })"
      /><CalendarView
        v-else-if="page === 'calendar'"
        :records="records"
        :today="today"
        @navigate="navigate"
      /><CollectionView
        v-else-if="['tasks', 'expenses', 'shows', 'milestones'].includes(page)"
        :key="page"
        :collection="page as Collection"
        :records="records"
        :stats="stats"
        :today="today"
        :busy="busy"
        @create="open(page as Collection)"
        @edit="(item) => open(page as Collection, item)"
        @remove="(item) => remove(page as Collection, item)"
        @action="(id, kind, data) => action(page as Collection, id, kind, data)"
      /><MaintenanceView
        v-else-if="page === 'maintenance'"
        :key="user.id"
        :items="records.maintenance"
        :stats="stats"
        :today="today"
        :parent-busy="busy"
        @refresh="load"
        @error="handleError"
        @notice="notify"
        @remove="removeMaintenance"
      /><NotesView
        v-else-if="page === 'notes'"
        :key="user.id"
        :items="records.notes"
        :today="today"
        :parent-busy="busy"
        @refresh="load"
        @error="handleError"
        @notice="notify"
      /><ProfileView
        v-else-if="page === 'profile'"
        :user="user"
        :busy="busy"
        @profile="profile"
        @password="password"
        @export="exportData"
        @import="importData"
        @logout="logout"
      /><AdminView
        v-else-if="page === 'admin' && user.is_admin"
        :user="user"
        @error="handleError"
        @notice="notify"
      />
    </main>
    <nav class="mobile-nav" aria-label="移动端导航">
      <button
        v-for="[id, label] in navigation"
        :key="id"
        :aria-label="id === 'today' ? '今日总览' : label"
        :class="{ active: page === id }"
        @click="navigate(id)"
      >
        <AppIcon :name="id" :size="21" /><span>{{ mobileNavLabels[id] }}</span>
      </button>
    </nav>
    <RecordForm
      v-if="editing"
      :key="`${editing.collection}-${editing.item?.id ?? 'new'}`"
      :collection="editing.collection"
      :item="editing.item"
      :today="today"
      :busy="busy"
      :error="formError"
      @close="editing = null"
      @save="save"
    /><Transition name="toast"
      ><div v-if="notice" class="toast" role="status">
        <AppIcon name="check" :size="18" />{{ notice }}
      </div></Transition
    >
  </div>
</template>
