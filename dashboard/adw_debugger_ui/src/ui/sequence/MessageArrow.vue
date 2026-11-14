<script setup lang="ts">
// One message row: a labelled arrow between two lifelines, or a loop back to
// the same lifeline for a self-call. Solid = a call or a note; dashed = a
// return. The label is the whole recorded text, rendered only as text.
import { computed } from 'vue'
import type { DiagramRow } from '../../contracts'
import { columnCentre, columnShare, direction, ROW_HEIGHT, rowY } from './geometry'

const props = defineProps<{ row: DiagramRow; index: number; count: number }>()

const way = computed(() => direction(props.row.from, props.row.to))

const style = computed(() => {
  const top = `${rowY(props.index) - ROW_HEIGHT * 0.62}px`
  const height = `${ROW_HEIGHT}px`
  const from = columnCentre(props.row.from, props.count)
  if (way.value === 'self') {
    // A self-call keeps to the right of its own lifeline; the last column has only half a column there.
    const room = props.row.from === props.count - 1 ? 0.46 : 0.92
    return { top, height, left: `${from}%`, width: `${columnShare(props.count) * room}%` }
  }
  const to = columnCentre(props.row.to, props.count)
  return { top, height, left: `${Math.min(from, to)}%`, width: `${Math.abs(to - from)}%` }
})
</script>

<template>
  <div class="sd-message" :class="[`sd-${way}`, { 'sd-dashed': row.dashed }]" :data-kind="row.kind"
       :data-row="index" :style="style">
    <div class="sd-label" :title="row.text"><span class="sd-label-text">{{ row.text }}</span></div>
    <div class="sd-line"><span class="sd-head" /></div>
  </div>
</template>
