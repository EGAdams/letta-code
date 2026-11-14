<script setup lang="ts">
// Presentation only: draws the controller's view and forwards five actions.
import { onBeforeUnmount, onErrorCaptured, shallowRef } from 'vue'
import type { DebuggerController } from '../controller'
import type { DebuggerView } from '../domain/view'
import LogPane from './LogPane.vue'
import SequenceDiagram from './SequenceDiagram.vue'

const props = defineProps<{ controller: DebuggerController }>()
const view = shallowRef<DebuggerView | null>(null)
const unsubscribe = props.controller.subscribe(next => { view.value = next })
onBeforeUnmount(unsubscribe)
onErrorCaptured(error => {
  props.controller.reportRenderError(error instanceof Error ? error.message : String(error))
  return false
})

const LEGEND = [
  ['waiting', 'Waiting'], ['running', 'Running'], ['stalled', 'Stalled'], ['fail', 'Fail'], ['pass', 'Pass'],
] as const
</script>

<template>
  <section v-if="view" class="adwdbg" aria-label="Live ADW sequence debugger">
    <header class="adwdbg-head">
      <strong class="adwdbg-title">ADW sequence</strong>
      <template v-if="view.runId">
        <span data-field="adw">{{ view.adwName }}</span>
        <span data-field="run">run {{ view.runId }}</span>
        <span class="adwdbg-chip" :data-run-status="view.runStatus" data-field="status">{{ view.runStatus }}</span>
      </template>
      <span class="adwdbg-chip" :data-mode="view.mode" data-field="mode">{{ view.modeLabel }}</span>
      <span class="adwdbg-legend" aria-label="Status colours">
        <span v-for="[status, label] in LEGEND" :key="status" class="adwdbg-key" :data-status="status">{{ label }}</span>
        <span class="adwdbg-key adwdbg-key-selected">Selected</span>
      </span>
    </header>

    <p v-if="view.connection.status === 'disconnected'" class="adwdbg-warn" data-warning="connection" role="status">
      Event feed disconnected (attempt {{ view.connection.attempts }}): {{ view.connection.reason }}.
      The diagram shows the last events received; this is a connection problem, not an ADW failure.
    </p>
    <p v-else-if="view.connection.status === 'degraded'" class="adwdbg-warn" data-warning="feed" role="status">
      The dashboard cannot read the ADW trace: {{ view.connection.reason }}
    </p>
    <p v-if="view.renderError" class="adwdbg-warn" data-warning="render" role="alert">
      Diagram could not be redrawn ({{ view.renderError }}). Showing the last good diagram; the terminal is unaffected.
    </p>

    <SequenceDiagram v-if="view.diagram.columns.length" :model="view.diagram"
                     @phase-click="props.controller.selectPhase($event)" />
    <p v-else class="adwdbg-idle" data-field="idle">
      {{ view.runId ? 'This run has not constructed a phase yet.' : 'No pilot ADW run has been recorded yet.' }}
    </p>

    <div class="adwdbg-bar">
      <button type="button" class="am-btn" data-action="follow-live" @click="props.controller.followLive()">Follow live</button>
      <button type="button" class="am-btn" data-action="all-events" :disabled="!view.phaseSelected"
              @click="props.controller.allEvents()">All events</button>
      <button type="button" class="am-btn" data-action="clear-run" :disabled="!!view.clearDisabledReason"
              :title="view.clearDisabledReason" @click="props.controller.clearSelectedRun()">{{ view.clearLabel }}</button>
      <span v-if="view.clearDisabledReason" class="adwdbg-note">{{ view.clearDisabledReason }}</span>
      <span class="adwdbg-note" data-field="timing">
        stall timeout {{ view.stallTimeoutSeconds }}s<template v-if="view.lastDelayMs !== null"> · last event shown
        {{ view.lastDelayMs }} ms after it was recorded</template>
      </span>
    </div>

    <LogPane :lines="view.lines" :label="`ADW events — ${view.filterLabel}`" :tall="view.phaseSelected" />
  </section>
</template>

<style>
.adwdbg { margin: 8px 0 10px; }
.adwdbg-head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 6px; font-size: .9rem; }
.adwdbg-chip { padding: 1px 8px; border: 1px solid #8a93a0; border-radius: 10px; font-size: .8rem; }
.adwdbg-chip[data-mode="pinned"], .adwdbg-chip[data-run-status="fail"],
.adwdbg-chip[data-run-status="interrupted"] { border-color: #d32f2f; color: #b71c1c; font-weight: 700; }
.adwdbg-chip[data-mode="live"] { border-color: #2e7d32; color: #1b5e20; font-weight: 700; }
.adwdbg-legend { display: flex; flex-wrap: wrap; gap: 4px; margin-left: auto; }
.adwdbg-key { padding: 1px 7px; border: 1px solid rgba(0, 0, 0, .35); border-radius: 3px; font-size: .74rem; }
.adwdbg-key[data-status="waiting"] { background: #9e9e9e; color: #111; }
.adwdbg-key[data-status="running"] { background: #ffd54f; color: #111; }
.adwdbg-key[data-status="stalled"] { background: #ff9800; color: #111; }
.adwdbg-key[data-status="fail"] { background: #d32f2f; color: #fff; }
.adwdbg-key[data-status="pass"] { background: #2e7d32; color: #fff; }
.adwdbg-key-selected { outline: 3px solid #1565c0; outline-offset: -1px; }
.adwdbg-warn { margin: 6px 0; padding: 6px 10px; border-left: 4px solid #ef6c00; background: #fff3e0; color: #4e2a00; }
.adwdbg-idle { margin: 6px 0; padding: 14px; border: 1px dashed #b6bcc6; border-radius: 6px; color: #555; }
.adwdbg-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px; }
.adwdbg-note { font-size: .8rem; color: #555; }
</style>
