<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { browserTimezone } from "../domain";
import type { User } from "../types";
import AppIcon from "../components/AppIcon.vue";
import ModalDialog from "../components/ModalDialog.vue";
const props = defineProps<{ user: User; busy: boolean }>();
const emit = defineEmits<{
  profile: [data: unknown];
  password: [data: unknown];
  export: [];
  import: [data: unknown];
  logout: [];
}>();
const profile = reactive({
  display_name: props.user.display_name,
  birthday: props.user.birthday ?? "",
  timezone: props.user.timezone,
  theme: props.user.theme,
});
const profileError = ref("");
function saveProfile() {
  profileError.value = "";
  if (browserTimezone(profile.timezone) !== profile.timezone) {
    profileError.value = "请选择当前浏览器支持的时区，例如 Asia/Shanghai 或 UTC";
    return;
  }
  emit("profile", { ...profile, birthday: profile.birthday || null });
}
const password = reactive({ current_password: "", new_password: "" });
const pendingImport = ref<Record<string, unknown> | null>(null);
const importError = ref("");
const fileInput = ref<HTMLInputElement>();
const importSummary = computed(() => {
  const data = pendingImport.value;
  if (!data) return "";
  const parts = [
    ["待办", "tasks"],
    ["长期任务", "task_groups"],
    ["费用", "expenses"],
    ["追剧", "shows"],
    ["日子", "milestones"],
    ["维护", "maintenance"],
  ].map(
    ([label, key]) =>
      `${label} ${(Array.isArray(data[key]) ? data[key].length : 0) as number}`,
  );
  return parts.join(" · ");
});
async function pickImportFile(event: Event) {
  importError.value = "";
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text());
    if (typeof parsed !== "object" || parsed === null || !("user" in parsed))
      throw new Error("请选择 digital-life 导出的 JSON 文件");
    pendingImport.value = parsed as Record<string, unknown>;
  } catch (error) {
    importError.value =
      error instanceof SyntaxError ? "文件不是有效的 JSON" : (error as Error).message;
  }
}
function confirmImport() {
  if (!pendingImport.value) return;
  emit("import", pendingImport.value);
  pendingImport.value = null;
}
</script>
<template>
  <section class="page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">MAKE YOURSELF AT HOME</span>
        <h1>个人设置</h1>
        <p>按照你的节奏，打理这个小小的空间。</p>
      </div>
    </header>
    <div class="settings-layout">
      <section class="panel settings-panel">
        <header>
          <span class="section-index">01</span>
          <h2>关于你</h2>
        </header>
        <form
          @submit.prevent="saveProfile"
        >
          <label>用户名<input :value="user.username" disabled /></label
          ><label
            >显示名称<input
              v-model="profile.display_name"
              required
              minlength="1"
              maxlength="60"
          /></label>
          <div class="form-grid">
            <label
              >生日 <span class="optional">选填</span
              ><input v-model="profile.birthday" type="date" /></label
            ><label
              >主题<select v-model="profile.theme">
                <option value="light">明亮</option>
                <option value="dark">深色</option>
                <option value="system">跟随系统</option>
              </select></label
            >
          </div>
          <label
            >时区<input
              v-model="profile.timezone"
              list="timezones"
              required
              placeholder="Asia/Shanghai"
            /><datalist id="timezones">
              <option>Asia/Shanghai</option>
              <option>Asia/Hong_Kong</option>
              <option>Asia/Tokyo</option>
              <option>Europe/London</option>
              <option>America/New_York</option>
              <option>America/Los_Angeles</option>
              <option>UTC</option>
            </datalist></label
          >
          <p class="field-hint">日期、人生天数与倒计时都按你的时区计算。</p>
          <p v-if="profileError" class="form-error" role="alert">{{ profileError }}</p>
          <p v-if="browserTimezone(user.timezone) !== user.timezone" class="field-hint">已保存的时区不受当前浏览器支持，日期暂按 UTC 显示。请重新设置时区。</p>
          <button class="button primary" :disabled="busy">保存个人资料</button>
        </form>
      </section>
      <div class="settings-secondary">
        <section class="panel settings-panel">
          <header>
            <span class="section-index">02</span>
            <h2>账户安全</h2>
          </header>
          <form @submit.prevent="emit('password', { ...password })">
            <label
              >当前密码<input
                v-model="password.current_password"
                type="password"
                required
                autocomplete="current-password"
                maxlength="128" /></label
            ><label
              >新密码<input
                v-model="password.new_password"
                type="password"
                required
                minlength="12"
                maxlength="128"
                autocomplete="new-password"
                placeholder="至少 12 个字符"
            /></label>
            <p class="field-hint">修改后所有设备需重新登录。</p>
            <button class="button secondary" :disabled="busy">更新密码</button>
          </form>
        </section>
        <section class="panel settings-panel">
          <header>
            <span class="section-index">03</span>
            <h2>你的数据，自己掌握</h2>
          </header>
          <p class="muted">
            将个人资料和全部生活记录导出为 JSON 文件，妥善留存属于你的日常。
          </p>
          <div class="data-actions">
            <button
              class="button secondary"
              :disabled="busy"
              @click="emit('export')"
            >
              <AppIcon name="download" :size="17" />导出我的数据
            </button>
            <button
              class="button secondary"
              :disabled="busy"
              @click="fileInput?.click()"
            >
              <AppIcon name="up" :size="17" />导入数据
            </button>
            <input
              ref="fileInput"
              type="file"
              accept="application/json,.json"
              class="visually-hidden"
              aria-label="选择要导入的 JSON 文件"
              @change="pickImportFile"
            />
          </div>
          <p v-if="importError" class="form-error" role="alert">{{ importError }}</p>
          <p class="field-hint">
            导入会把文件里的生活记录替换本账号当前的全部记录；登录和个人设置不受影响。
          </p>
        </section>
        <button
          class="button logout-button"
          :disabled="busy"
          @click="emit('logout')"
        >
          <AppIcon name="logout" :size="17" />退出登录
        </button>
      </div>
    </div>
    <ModalDialog
      v-if="pendingImport"
      title="确认导入这份文件？"
      subtitle="导入会先清空再恢复，请确认文件来自你的导出。"
      @close="pendingImport = null"
    >
      <p class="muted">{{ importSummary }}</p>
      <p class="field-hint">
        本账号当前的全部生活记录（待办、长期任务及其打卡、费用、追剧、重要日子、维护及其历史）将被替换；登录、密码和个人设置保持不变。
      </p>
      <div class="modal-actions">
        <button class="button secondary" @click="pendingImport = null">
          取消
        </button>
        <button class="button danger" @click="confirmImport">
          替换并导入
        </button>
      </div>
    </ModalDialog>
  </section>
</template>
