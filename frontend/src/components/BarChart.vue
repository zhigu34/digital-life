<script setup lang="ts">
import { computed } from "vue";
import type { TrendPoint } from "../stats";

const props = defineProps<{
  points: TrendPoint[];
  chartTitle: string;
}>();
const max = computed(() =>
  Math.max(...props.points.map((point) => point.value), 1),
);
</script>
<template>
  <div class="bar-chart" role="img" :aria-label="chartTitle">
    <div v-for="(point, index) in points" :key="index" class="bar-col">
      <span class="bar-track" :title="point.title">
        <span
          class="bar-fill"
          :class="{ zero: point.value === 0 }"
          :style="{ height: `${Math.max((point.value / max) * 100, 0)}%` }"
        ></span>
      </span>
      <span class="bar-label">{{ point.label }}</span>
    </div>
  </div>
</template>
