<script setup lang="ts">
import AppIcon from "./AppIcon.vue";
defineProps<{
  icon: string;
  title: string;
  description: string;
  action?: string;
}>();
defineEmits<{ action: [] }>();
</script>
<template>
  <div class="empty-state">
    <span class="empty-icon"><AppIcon :name="icon" :size="28" /></span>
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <button v-if="action" class="button secondary" @click="$emit('action')">
      <AppIcon name="plus" :size="16" />{{ action }}
    </button>
  </div>
</template>
