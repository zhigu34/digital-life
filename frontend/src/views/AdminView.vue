<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import type { User } from "../types";
import { api } from "../api";
import AppIcon from "../components/AppIcon.vue";
import ModalDialog from "../components/ModalDialog.vue";
const props = defineProps<{ user: User }>();
const emit = defineEmits<{
  error: [error: unknown];
  notice: [message: string];
}>();
const users = ref<User[]>([]),
  busy = ref(false),
  loading = ref(true),
  mode = ref<"create" | "reset" | null>(null),
  target = ref<User | null>(null),
  error = ref("");
const form = reactive({ username: "", display_name: "", password: "" });
async function load() {
  try {
    users.value = await api<User[]>("/admin/users");
  } catch (e) {
    emit("error", e);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
function open(user?: User) {
  target.value = user ?? null;
  mode.value = user ? "reset" : "create";
  Object.assign(form, { username: "", display_name: "", password: "" });
  error.value = "";
}
async function save() {
  busy.value = true;
  error.value = "";
  try {
    if (mode.value === "create") await api("/admin/users", "POST", { ...form });
    else
      await api(`/admin/users/${target.value!.id}`, "PATCH", {
        password: form.password,
      });
    mode.value = null;
    await load();
    emit("notice", "账户已更新");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "操作失败";
  } finally {
    busy.value = false;
  }
}
async function toggle(user: User) {
  if (
    !window.confirm(
      `确认${user.is_active ? "停用" : "启用"}“${user.display_name}”？${user.is_active ? "该账户将退出所有设备。" : ""}`,
    )
  )
    return;
  busy.value = true;
  try {
    await api(`/admin/users/${user.id}`, "PATCH", {
      is_active: !user.is_active,
    });
    await load();
    emit("notice", "账户状态已更新");
  } catch (e) {
    emit("error", e);
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <section class="page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">A SPACE FOR EVERYONE</span>
        <h1>账户管理</h1>
        <p>创建独立的个人空间，每个账户拥有自己的生活记录。</p>
      </div>
      <button class="button primary" @click="open()">
        <AppIcon name="plus" :size="17" />创建账户
      </button>
    </header>
    <p v-if="loading" class="muted">正在加载账户…</p>
    <div v-else class="record-list">
      <article v-for="person in users" :key="person.id" class="record-card">
        <span class="avatar">{{ person.display_name.slice(0, 1) }}</span>
        <div class="record-body">
          <h3>
            {{ person.display_name
            }}<span class="tag">{{
              person.is_admin ? "管理员" : "普通账户"
            }}</span>
          </h3>
          <p class="record-notes">
            @{{ person.username }} ·
            {{ person.is_active ? "使用中" : "已停用" }}
          </p>
        </div>
        <div class="admin-actions">
          <button
            class="button secondary compact"
            :disabled="busy"
            @click="open(person)"
          >
            重置密码</button
          ><button
            v-if="person.id !== props.user.id"
            class="text-button"
            :disabled="busy"
            @click="toggle(person)"
          >
            {{ person.is_active ? "停用" : "启用" }}
          </button>
        </div>
      </article>
    </div>
    <ModalDialog
      v-if="mode"
      :title="
        mode === 'create' ? '创建账户' : `重置 ${target?.display_name} 的密码`
      "
      @close="mode = null"
      ><form @submit.prevent="save">
        <template v-if="mode === 'create'"
          ><label
            >用户名<input
              v-model="form.username"
              required
              minlength="3"
              maxlength="32"
              pattern="[A-Za-z0-9_-]+"
              autocomplete="off"
              placeholder="3–32 位字母、数字、下划线或短横线" /></label
          ><label
            >显示名称<input
              v-model="form.display_name"
              required
              maxlength="60" /></label></template
        ><label
          >{{ mode === "create" ? "初始密码" : "新密码"
          }}<input
            v-model="form.password"
            type="password"
            required
            minlength="12"
            maxlength="128"
            autocomplete="new-password"
            placeholder="至少 12 个字符"
        /></label>
        <p v-if="mode === 'reset'" class="field-hint">
          重置后，该账户所有设备需重新登录。
        </p>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <footer class="modal-actions">
          <button type="button" class="button secondary" @click="mode = null">
            取消</button
          ><button class="button primary" :disabled="busy">
            {{ busy ? "保存中…" : "确认保存" }}
          </button>
        </footer>
      </form></ModalDialog
    >
  </section>
</template>
