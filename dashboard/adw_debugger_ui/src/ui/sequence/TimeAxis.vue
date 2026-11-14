<script setup lang="ts">
// The left-hand time axis: when each message row was recorded, relative to the run's start.
import type { DiagramRow } from '../../contracts'
import { AXIS_WIDTH, rowY } from './geometry'

defineProps<{ rows: DiagramRow[] }>()
</script>

<template>
  <div class="sd-axis" :style="{ width: `${AXIS_WIDTH}px` }" aria-hidden="true">
    <span v-for="(row, index) in rows" :key="row.id" class="sd-tick" :style="{ top: `${rowY(index)}px` }">
      {{ row.elapsed }}
    </span>
  </div>
</template>
