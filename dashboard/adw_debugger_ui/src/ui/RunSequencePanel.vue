<script setup lang="ts">
// One ADW run's sequence diagram, for a page that embeds it (the object
// debugger). Each phase is a column. Clicking a phase opens a pop-up black
// terminal with that phase's console output; clicking the same phase again
// closes it, clicking another phase switches to that one. The ADW box does the
// same for every event of the run.
import { onBeforeUnmount, onErrorCaptured, ref, shallowRef } from 'vue'
import type { DebuggerController } from '../controller'
import type { DebuggerView } from '../domain/view'
import LogPane from './LogPane.vue'
import SequenceDiagram from './SequenceDiagram.vue'

const ALL = '@all'
const props = defineProps<{ controller: DebuggerController }>()
const view = shallowRef<DebuggerView | null>(null)
const open = ref<string | null>(null)
const unsubscribe = props.controller.subscribe(next => { view.value = next })
onBeforeUnmount(unsubscribe)
onErrorCaptured(error => {
  props.controller.reportRenderError(error instanceof Error ? error.message : String(error))
  return false
})

function toggle(id: string): void {
  if (open.value === id) {
    open.value = null
    props.controller.allEvents()
    return
  }
  open.value = id
  if (id === ALL) props.controller.allEvents()
  else props.controller.selectPhase(id)
}

function close(): void {
  if (open.value) toggle(open.value)
}
</script>

<template>
  <section v-if="view" class="adwseq" aria-label="ADW run sequence diagram">
    <header class="adwseq-head">
      <strong data-field="headline">{{ view.headline }}</strong>
      <span v-if="view.runStatus" class="adwdbg-chip" :data-run-status="view.runStatus" data-field="status">{{ view.runStatus }}</span>
    </header>
    <p v-if="view.connection.status === 'disconnected'" class="adwdbg-warn" data-warning="connection" role="status">
      Event feed disconnected (attempt {{ view.connection.attempts }}): {{ view.connection.reason }}.
      Showing the last events received.
    </p>
    <p v-else-if="view.connection.status === 'degraded'" class="adwdbg-warn" data-warning="feed" role="status">
      The ADW trace cannot be read: {{ view.connection.reason }}
    </p>
    <p v-if="view.renderError" class="adwdbg-warn" data-warning="render" role="alert">
      Diagram could not be redrawn ({{ view.renderError }}). Showing the last good diagram.
    </p>

    <div class="adwseq-stage">
      <SequenceDiagram v-if="view.diagram.columns.length" :model="view.diagram"
                       hint="Click a phase to open its console; click it again to close."
                       @phase-click="toggle($event)" @runner-click="toggle(ALL)" />
      <p v-else class="adwdbg-idle" data-field="idle">
        {{ view.connection.status === 'connecting' ? 'Loading the run…' : 'This run has not started a step yet.' }}
      </p>
      <div v-if="open" class="adwseq-popup" data-field="popup" role="dialog" :aria-label="view.filterLabel">
        <button type="button" class="adwseq-close" aria-label="Close console" @click="close()">×</button>
        <LogPane :lines="view.lines" :label="view.filterLabel" :tall="false" />
      </div>
    </div>
  </section>
</template>

<style>
.adwseq { margin: 6px 0; font-family: system-ui, sans-serif; }
.adwseq-head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 6px; font-size: .9rem; }
.adwseq-stage { position: relative; }
.adwseq-popup { position: absolute; left: 4%; right: 4%; top: calc(100% - 12px); z-index: 50;
  border: 1px solid #444; border-radius: 6px; background: #000; box-shadow: 0 8px 28px rgba(0, 0, 0, .55); }
.adwseq-popup .adwdbg-log { margin-top: 0; border-radius: 6px; }
.adwseq-popup .adwdbg-log-lines { height: 40vh; }
.adwseq-close { position: absolute; top: 1px; right: 6px; z-index: 1; border: 0; background: transparent;
  color: #fff; font-size: 16px; cursor: pointer; }
.adwseq-popup .adwdbg-log-head { padding-right: 32px; }
.adwseq .adwdbg-chip { padding: 1px 8px; border: 1px solid #8a93a0; border-radius: 10px; font-size: .8rem; }
.adwseq .adwdbg-chip[data-run-status="fail"], .adwseq .adwdbg-chip[data-run-status="interrupted"] {
  border-color: #d32f2f; color: #b71c1c; font-weight: 700; }
.adwseq .adwdbg-warn { margin: 6px 0; padding: 6px 10px; border-left: 4px solid #ef6c00; background: #fff3e0; color: #4e2a00; }
.adwseq .adwdbg-idle { margin: 6px 0; padding: 14px; border: 1px dashed #b6bcc6; border-radius: 6px; color: #555; }
</style>
