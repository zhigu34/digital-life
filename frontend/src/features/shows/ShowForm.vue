<script setup lang="ts">
import type { Show } from "../../types";
import LegacyShowForm from "../../components/ShowForm.vue";

defineProps<{ item?: Show; busy: boolean; error: string }>();
const emit = defineEmits<{ close: []; save: [data: Record<string, unknown>]; remove: [item: Show] }>();
</script>

<template>
  <LegacyShowForm :item="item" :busy="busy" :error="error" @close="emit('close')" @save="emit('save', $event)" @remove="emit('remove', $event)" />
</template>
