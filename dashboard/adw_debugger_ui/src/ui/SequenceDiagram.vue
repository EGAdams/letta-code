<script setup lang="ts">
// Vue 3 / TypeScript port of vue-sequence-diagram's SequenceDiagram.vue
// (MIT, (c) heichong -- https://github.com/heichong/vue-sequence-diagram).
// Same idea as the original: one coordinated diagram drawn from ordinary
// elements -- a title box above and below each column, a lifeline between
// them, and one row per message. What changed: positions are percentages of
// the column grid instead of measured pixels, each title box is a button that
// carries its phase's status and identity, and message text is shown whole.
// All text is rendered by interpolation, never as HTML.
import { computed, ref } from 'vue'
import type { DiagramColumn, DiagramModel, DiagramRow } from '../contracts'

const props = defineProps<{ model: DiagramModel }>()
const emit = defineEmits<{ 'phase-click': [instanceId: string] }>()

const zoom = ref(1)
const count = computed(() => Math.max(1, props.model.columns.length))
const share = computed(() => 100 / count.value)

function lifelineStyle(index: number) {
  return { left: `${(index + 0.5) * share.value}%` }
}

function messageStyle(row: DiagramRow) {
  if (row.from === row.to) {
    // A self-call gets most of a column for its text; the last column only has half of one to its right.
    const room = row.from === count.value - 1 ? 0.48 : 0.94
    return { marginLeft: `${(row.from + 0.5) * share.value}%`, width: `${share.value * room}%` }
  }
  const left = Math.min(row.from, row.to)
  return { marginLeft: `${(left + 0.5) * share.value}%`, width: `${Math.abs(row.to - row.from) * share.value}%` }
}

function direction(row: DiagramRow): string {
  return row.from === row.to ? 'self' : row.from < row.to ? 'right' : 'left'
}

function title(column: DiagramColumn): string {
  return [column.purpose, column.instanceId].filter(Boolean).join('\n')
}
</script>

<template>
  <div class="sd">
    <div class="sd-tools">
      <button type="button" class="sd-zoom" aria-label="Zoom out" @click="zoom = Math.max(0.4, zoom - 0.1)">-</button>
      <span class="sd-zoom-value">{{ Math.round(zoom * 100) }}%</span>
      <button type="button" class="sd-zoom" aria-label="Zoom in" @click="zoom = Math.min(2, zoom + 0.1)">+</button>
      <button type="button" class="sd-zoom" @click="zoom = 1">Reset</button>
    </div>
    <div class="sd-scroll">
      <div class="sd-canvas" :style="{ zoom, minWidth: `${count * 260}px` }">
        <div v-for="edge in ['top', 'bottom']" :key="edge" class="sd-titles" :class="`sd-titles-${edge}`"
             :style="{ order: edge === 'top' ? 0 : 2 }">
          <button v-for="column in model.columns" :key="column.instanceId" type="button" class="sd-box"
                  :class="{ 'sd-selected': column.selected }" :data-status="column.status"
                  :data-instance="column.instanceId" :data-edge="edge" :title="title(column)"
                  :aria-pressed="column.selected" @click="emit('phase-click', column.instanceId)">
            <span class="sd-name">{{ column.name }}<template v-if="column.attempt"> · attempt {{ column.attempt }}</template></span>
            <span class="sd-status">{{ column.statusLabel }}</span>
            <span v-if="column.detail" class="sd-detail">{{ column.detail }}</span>
          </button>
        </div>
        <div class="sd-body" style="order: 1">
          <div v-if="model.rows.length === 0" class="sd-row sd-row-empty">
            <span v-for="(column, index) in model.columns" :key="column.instanceId" class="sd-lifeline"
                  :style="lifelineStyle(index)" />
          </div>
          <div v-for="row in model.rows" :key="row.id" class="sd-row">
            <span v-for="(column, index) in model.columns" :key="column.instanceId" class="sd-lifeline"
                  :style="lifelineStyle(index)" />
            <div class="sd-message" :class="[`sd-${direction(row)}`, { 'sd-dashed': row.dashed }]"
                 :data-kind="row.kind" :style="messageStyle(row)">
              <div class="sd-label">{{ row.text }}</div>
              <div class="sd-line"><span class="sd-head" /></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.sd { border: 1px solid #c9ced6; border-radius: 6px; background: #fff; color: #1b1f24; }
.sd-tools { display: flex; align-items: center; gap: 6px; padding: 4px 8px; border-bottom: 1px solid #e3e6ea; font-size: .8rem; }
.sd-zoom { min-width: 28px; padding: 2px 8px; border: 1px solid #b6bcc6; border-radius: 4px; background: #f5f6f8; cursor: pointer; }
.sd-zoom-value { min-width: 3.2em; text-align: center; }
.sd-scroll { overflow: auto; max-height: 46vh; }
.sd-canvas { display: flex; flex-direction: column; padding: 8px 0; }
.sd-titles { display: flex; }
.sd-box { flex: 1 1 0; min-width: 0; margin: 0 10px; padding: 6px 8px; border: 1px solid rgba(0, 0, 0, .35);
  border-radius: 4px; display: flex; flex-direction: column; gap: 2px; align-items: center; cursor: pointer;
  font: inherit; text-align: center; overflow-wrap: anywhere; }
.sd-name { font-weight: 700; }
.sd-status { font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }
.sd-detail { font-size: .76rem; }
.sd-box[data-status="waiting"] { background: #9e9e9e; color: #111; }
.sd-box[data-status="running"] { background: #ffd54f; color: #111; }
.sd-box[data-status="stalled"] { background: #ff9800; color: #111; }
.sd-box[data-status="fail"] { background: #d32f2f; color: #fff; }
.sd-box[data-status="pass"] { background: #2e7d32; color: #fff; }
.sd-box.sd-selected { outline: 4px solid #1565c0; outline-offset: 2px; }
.sd-box:focus-visible { outline: 3px dashed #1565c0; outline-offset: 2px; }
.sd-body { display: flex; flex-direction: column; }
.sd-row { position: relative; padding: 8px 0; }
.sd-row-empty { min-height: 28px; }
.sd-lifeline { position: absolute; top: 0; bottom: 0; width: 0; border-left: 2px solid #9aa3af; }
.sd-message { position: relative; box-sizing: border-box; }
.sd-label { padding: 0 12px 3px; font: 12px/1.4 ui-monospace, SFMono-Regular, Consolas, monospace;
  white-space: pre-wrap; overflow-wrap: anywhere; background: rgba(255, 255, 255, .88); }
.sd-line { position: relative; border-top: 2px solid #1b1f24; }
.sd-dashed .sd-line { border-top-style: dashed; }
.sd-head { position: absolute; top: -6px; width: 0; height: 0; border: 5px solid transparent; }
.sd-right .sd-head { right: 0; border-left-color: #1b1f24; border-right-width: 0; }
.sd-left .sd-head { left: 0; border-right-color: #1b1f24; border-left-width: 0; }
.sd-self .sd-line { height: 14px; border: 2px solid #1b1f24; border-left: 0; }
.sd-self.sd-dashed .sd-line { border-style: dashed; border-left: 0; }
.sd-self .sd-head { left: 0; top: auto; bottom: -6px; border-right-color: #1b1f24; border-left-width: 0; }
</style>
