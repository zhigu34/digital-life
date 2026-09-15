<script setup lang="ts">
import { ref } from "vue";
import AppIcon from "../components/AppIcon.vue";
defineProps<{ busy: boolean; error: string }>();
const emit = defineEmits<{ login: [username: string, password: string] }>();
const username = ref(""),
  password = ref("");
</script>
<template>
  <main class="login-page">
    <section class="login-story">
      <a class="brand" href="#"
        ><span class="brand-mark"><AppIcon name="leaf" :size="24" /></span
        >digital life<span class="brand-dot">.</span></a
      >
      <div class="login-message">
        <span class="eyebrow">A LITTLE SPACE FOR YOUR EVERYDAY</span>
        <h1>让日常有序，<br />让生活可见<span>。</span></h1>
        <p>
          待办、订阅、追剧和重要日子。<br />把生活里的小事，安放在自己的空间。
        </p>
        <div class="orbit-art" aria-hidden="true">
          <div class="orbit-ring ring-1"></div>
          <div class="orbit-ring ring-2"></div>
          <span class="orbit-core"><AppIcon name="leaf" :size="70" /></span
          ><span class="orbit-chip chip-1"
            ><AppIcon name="check" />小事，慢慢完成</span
          ><span class="orbit-chip chip-2"
            ><AppIcon name="sun" />生活，正在发生</span
          >
        </div>
      </div>
      <span class="login-footer">LESS NOISE. MORE LIFE.</span>
    </section>
    <section class="login-form-side">
      <form
        class="login-form"
        @submit.prevent="emit('login', username, password)"
      >
        <span class="eyebrow">WELCOME BACK</span>
        <h2>回到你的日常</h2>
        <p class="muted">登录，继续记录生活的每一个小进展。</p>
        <label
          >用户名<input
            v-model="username"
            name="username"
            autocomplete="username"
            required
            autofocus
            placeholder="输入你的用户名"
            maxlength="32" /></label
        ><label
          >密码<input
            v-model="password"
            name="password"
            type="password"
            autocomplete="current-password"
            required
            placeholder="输入密码"
            maxlength="128"
        /></label>
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <button class="button primary login-submit" :disabled="busy">
          {{ busy ? "正在登录…" : "进入我的空间"
          }}<AppIcon
            :name="busy ? 'loading' : 'arrow'"
            :class="{ spin: busy }"
          />
        </button>
        <div class="login-hint">
          <AppIcon name="leaf" :size="16" /><span
            >私人空间 · 账户由管理员创建</span
          >
        </div>
      </form>
      <p class="login-bottom">把注意力，留给值得的生活。</p>
    </section>
  </main>
</template>
