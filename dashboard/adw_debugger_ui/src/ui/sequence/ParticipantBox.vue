<script setup lang="ts">
// One participant's title box. Drawn twice per column -- above and below the
// lifelines, as in a Mermaid sequence diagram -- and each copy is a button.
import type { DiagramColumn } from '../../contracts'

const props = defineProps<{ column: DiagramColumn; edge: 'top' | 'bottom' }>()
const emit = defineEmits<{ select: [column: DiagramColumn] }>()

function tooltip(): string {
  return [props.column.purpose, props.column.detail, props.column.instanceId].filter(Boolean).join('\n')
}
</script>

<template>
  <button type="button" class="sd-box" :class="{ 'sd-selected': column.selected, 'sd-runner': column.kind === 'runner' }"
          :data-status="column.status" :data-instance="column.instanceId" :data-edge="edge"
          :data-participant="column.kind ?? 'phase'" :title="tooltip()" :aria-pressed="column.selected"
          @click="emit('select', column)">
    <span class="sd-name">{{ column.name }}<template v-if="column.attempt && column.attempt > 1"> · attempt {{ column.attempt }}</template></span>
    <span class="sd-status">{{ column.statusLabel }}<template v-if="column.detail"> · {{ column.detail }}</template></span>
  </button>
</template>
