<script setup lang="ts">
// The coloured block on a lifeline while that participant is doing work.
import { computed } from 'vue'
import type { PhaseStatus } from '../../contracts'
import { barSpan } from './geometry'

const props = defineProps<{ from: number; to: number | null; rows: number; status: PhaseStatus }>()
const span = computed(() => barSpan(props.from, props.to, props.rows))
</script>

<template>
  <span class="sd-bar" :class="{ 'sd-bar-open': to === null }" :data-status="status"
        :style="{ top: `${span.top}px`, height: `${span.height}px` }" />
</template>
