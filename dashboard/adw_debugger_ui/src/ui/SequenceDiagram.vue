<script setup lang="ts">
// A Mermaid-style sequence diagram built from Vue components, no Mermaid:
//
//   ParticipantBox  a title box above and below each participant (a button)
//   Lifeline        the dashed line down from it, carrying an ActivationBar
//   ActivationBar   coloured by status while that participant is working
//   MessageArrow    one row per message: call (solid), return (dashed), self-call (loop)
//   TimeAxis        when each row happened, relative to the run's start
//
// Layout follows heichong/vue-sequence-diagram (MIT): participants across the
// top and bottom, lifelines between, one row per message, a time column on the
// left. Positions come from ./sequence/geometry.ts. All text is interpolated,
// never rendered as HTML.
import { computed, ref } from 'vue'
import type { DiagramColumn, DiagramModel } from '../contracts'
import Lifeline from './sequence/Lifeline.vue'
import MessageArrow from './sequence/MessageArrow.vue'
import ParticipantBox from './sequence/ParticipantBox.vue'
import TimeAxis from './sequence/TimeAxis.vue'
import { AXIS_WIDTH, bodyHeight, COLUMN_MIN_WIDTH, columnCentre } from './sequence/geometry'

const props = defineProps<{ model: DiagramModel }>()
const emit = defineEmits<{ 'phase-click': [instanceId: string]; 'runner-click': [] }>()

const zoom = ref(1)
const count = computed(() => Math.max(1, props.model.columns.length))
const rowCount = computed(() => props.model.rows.length)
const minWidth = computed(() => `${AXIS_WIDTH + count.value * COLUMN_MIN_WIDTH}px`)

function select(column: DiagramColumn): void {
  if (column.kind === 'runner') emit('runner-click')
  else emit('phase-click', column.instanceId)
}
</script>

<template>
  <div class="sd">
    <div class="sd-tools">
      <button type="button" class="sd-zoom" aria-label="Zoom out" @click="zoom = Math.max(0.4, zoom - 0.1)">-</button>
      <span class="sd-zoom-value">{{ Math.round(zoom * 100) }}%</span>
      <button type="button" class="sd-zoom" aria-label="Zoom in" @click="zoom = Math.min(2, zoom + 0.1)">+</button>
      <button type="button" class="sd-zoom" @click="zoom = 1">Reset</button>
      <span class="sd-hint">Click a phase box to filter the events below; click the ADW box for all events.</span>
    </div>
    <div class="sd-scroll">
      <div class="sd-canvas" :style="{ zoom, minWidth }">
        <div class="sd-titles sd-titles-top" :style="{ marginLeft: `${AXIS_WIDTH}px` }">
          <ParticipantBox v-for="column in model.columns" :key="column.instanceId" :column="column" edge="top"
                          @select="select" />
        </div>
        <div class="sd-body" :style="{ height: `${bodyHeight(rowCount)}px` }">
          <TimeAxis :rows="model.rows" />
          <div class="sd-plot" :style="{ left: `${AXIS_WIDTH}px` }">
            <Lifeline v-for="(column, index) in model.columns" :key="column.instanceId" :column="column"
                      :centre="columnCentre(index, count)" :rows="rowCount" />
            <MessageArrow v-for="(row, index) in model.rows" :key="row.id" :row="row" :index="index" :count="count" />
          </div>
        </div>
        <div class="sd-titles sd-titles-bottom" :style="{ marginLeft: `${AXIS_WIDTH}px` }">
          <ParticipantBox v-for="column in model.columns" :key="column.instanceId" :column="column" edge="bottom"
                          @select="select" />
        </div>
      </div>
    </div>
  </div>
</template>

<style>
.sd { border: 1px solid #c9ced6; border-radius: 8px; background: #fff; color: #1b1f24; }
.sd-tools { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 4px 8px;
  border-bottom: 1px solid #e3e6ea; font-size: .8rem; }
.sd-zoom { min-width: 28px; padding: 2px 8px; border: 1px solid #b6bcc6; border-radius: 4px; background: #f5f6f8; cursor: pointer; }
.sd-zoom-value { min-width: 3.2em; text-align: center; }
.sd-hint { margin-left: auto; color: #5b6470; }
.sd-scroll { overflow: auto; max-height: 56vh; }
.sd-canvas { padding: 10px 12px 10px 0; }

/* Participant boxes: rounded, raised, the status colour under a soft sheen. */
.sd-titles { display: flex; }
.sd-box { flex: 1 1 0; min-width: 0; margin: 0 10px; padding: 6px 8px; border: 1px solid rgba(0, 0, 0, .28);
  border-radius: 7px; display: flex; flex-direction: column; gap: 1px; align-items: center; cursor: pointer;
  font: inherit; text-align: center; overflow-wrap: anywhere; box-shadow: 2px 3px 5px rgba(0, 0, 0, .22);
  background-image: linear-gradient(to bottom, rgba(255, 255, 255, .42), rgba(255, 255, 255, 0) 55%, rgba(0, 0, 0, .08)); }
.sd-box:hover { filter: brightness(1.05); }
.sd-name { font-weight: 700; font-size: .86rem; }
.sd-status { font-size: .72rem; letter-spacing: .03em; }
.sd-box[data-status="waiting"] { background-color: #9e9e9e; color: #111; }
.sd-box[data-status="running"] { background-color: #ffd54f; color: #111; }
.sd-box[data-status="stalled"] { background-color: #ff9800; color: #111; }
.sd-box[data-status="fail"] { background-color: #d32f2f; color: #fff; }
.sd-box[data-status="pass"] { background-color: #2e7d32; color: #fff; }
.sd-box.sd-runner { border-style: double; border-width: 3px; }
.sd-box.sd-selected { outline: 4px solid #1565c0; outline-offset: 2px; }
.sd-box:focus-visible { outline: 3px dashed #1565c0; outline-offset: 2px; }

/* Body: time axis on the left, lifelines and messages in the plot. */
.sd-body { position: relative; }
.sd-axis { position: absolute; left: 0; top: 0; bottom: 0; border-right: 1px solid #eef0f3; }
.sd-tick { position: absolute; right: 8px; transform: translateY(-50%); font: 11px/1 ui-monospace, SFMono-Regular, Consolas, monospace;
  color: #3b4a6b; white-space: nowrap; }
.sd-plot { position: absolute; top: 0; right: 0; bottom: 0; }
.sd-lifeline-track { position: absolute; top: 0; bottom: 0; width: 0; }
.sd-lifeline { position: absolute; top: 0; bottom: 0; left: -1px; border-left: 1.5px dashed #59606b; }
.sd-bar { position: absolute; left: -6px; width: 12px; border: 1px solid rgba(0, 0, 0, .25); border-radius: 2px;
  box-shadow: 2px 2px 4px rgba(0, 0, 0, .25); }
.sd-bar[data-status="waiting"] { background: #9e9e9e; }
.sd-bar[data-status="running"] { background: #ffd54f; }
.sd-bar[data-status="stalled"] { background: #ff9800; }
.sd-bar[data-status="fail"] { background: #d32f2f; }
.sd-bar[data-status="pass"] { background: #43a047; }
.sd-bar-open { border-bottom-style: dashed; animation: sd-pulse 1.6s ease-in-out infinite; }
@keyframes sd-pulse { 50% { opacity: .6; } }

/* Messages. The line sits at 62% of the row; the label sits on it. */
.sd-message { position: absolute; box-sizing: border-box; pointer-events: none; }
.sd-label { position: absolute; left: 0; right: 0; bottom: calc(38% + 2px); padding: 0 12px; text-align: center;
  font: 12px/1.3 system-ui, "Segoe UI", sans-serif; color: #2b2f36; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; pointer-events: auto; }
.sd-label-text { position: relative; z-index: 1; padding: 0 3px; background: #fff; border-radius: 3px; }
.sd-line { position: absolute; left: 6px; right: 6px; top: 62%; border-top: 1.5px solid #1b1f24; }
.sd-dashed .sd-line { border-top-style: dashed; }
.sd-head { position: absolute; top: -5.5px; width: 0; height: 0; border: 5px solid transparent; }
.sd-right .sd-head { right: -1px; border-left: 8px solid #1b1f24; border-right-width: 0; }
.sd-left .sd-head { left: -1px; border-right: 8px solid #1b1f24; border-left-width: 0; }
/* Self-call: a small loop out to the right and back, label beside it. */
.sd-self .sd-line { left: 6px; right: auto; width: 22px; top: 40%; height: 22%; border: 1.5px solid #1b1f24; border-left: 0; }
.sd-self.sd-dashed .sd-line { border-style: dashed; border-left: 0; }
.sd-self .sd-head { left: -2px; top: auto; bottom: -6px; border-right: 8px solid #1b1f24; border-left-width: 0; }
.sd-self .sd-label { left: 34px; right: 0; bottom: auto; top: 50%; transform: translateY(-50%); padding: 0 4px; text-align: left; }
</style>
