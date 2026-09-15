<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import AppIcon from "./AppIcon.vue";
defineProps<{ title: string; subtitle?: string }>();
const emit = defineEmits<{ close: [] }>();
const dialog = ref<HTMLDialogElement>();
let previouslyFocused: Element | null = null;
onMounted(() => {
  previouslyFocused = document.activeElement;
  dialog.value?.showModal();
  document.body.style.overflow = "hidden";
});
onUnmounted(() => {
  document.body.style.overflow = "";
  if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
});
</script>
<template>
  <dialog
    ref="dialog"
    class="modal"
    aria-labelledby="dialog-title"
    @cancel.prevent="emit('close')"
    @click="
      (event) => {
        if (event.target === dialog) emit('close');
      }
    "
  >
    <div class="modal-content">
      <header class="modal-head">
        <div>
          <span class="eyebrow">YOUR LIFE, WELL ORGANIZED</span>
          <h2 id="dialog-title">{{ title }}</h2>
          <p v-if="subtitle">{{ subtitle }}</p>
        </div>
        <button
          type="button"
          class="icon-button"
          aria-label="关闭"
          @click="emit('close')"
        >
          <AppIcon name="close" />
        </button>
      </header>
      <slot />
    </div>
  </dialog>
</template>
