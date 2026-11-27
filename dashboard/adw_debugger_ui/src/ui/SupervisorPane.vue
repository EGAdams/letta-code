<script setup lang="ts">
// The supervisors' records for one machine, beside the run's own events:
// awake or asleep, heartbeats, wake reasons, handoffs and todos, held mail,
// failure timers, recovery attempts and what blocked them. Read-only -- there
// is no clear or resend here, and clearing a run's terminal does not touch it.
import type { SupervisorView } from '../domain/supervisor'

defineProps<{ supervisor: SupervisorView }>()
const emit = defineEmits<{
  machine: [name: string]
  agent: [name: string]
  correlate: []
}>()

function pick(event: Event, name: 'machine' | 'agent'): void {
  const value = (event.target as HTMLSelectElement).value
  if (name === 'machine') emit('machine', value)
  else emit('agent', value)
}
</script>

<template>
  <section class="adwsup" aria-label="Supervisor activity" data-field="supervisor">
    <div class="adwsup-bar">
      <strong>Supervisors</strong>
      <label class="adwdbg-note">Machine
        <select data-field="supervisor-machine" :value="supervisor.machine" @change="pick($event, 'machine')">
          <option v-for="name in supervisor.machines" :key="name" :value="name">{{ name || 'This machine' }}</option>
        </select>
      </label>
      <label class="adwdbg-note">Agent
        <select data-field="supervisor-agent" :value="supervisor.agent" @change="pick($event, 'agent')">
          <option value="">All agents</option>
          <option v-for="name in supervisor.agents" :key="name" :value="name">{{ name }}</option>
        </select>
      </label>
      <button type="button" class="am-btn" data-action="supervisor-correlate" :aria-pressed="supervisor.correlate"
              @click="emit('correlate')">{{ supervisor.correlateLabel }}</button>
      <span v-if="supervisor.awake" class="adwdbg-chip" data-field="supervisor-state"
            :data-supervisor-state="supervisor.awake">{{ supervisor.awake }}</span>
      <span class="adwdbg-note">{{ supervisor.lines.length }} of {{ supervisor.total }} records</span>
    </div>
    <p v-if="supervisor.error" class="adwdbg-warn" data-warning="supervisor" role="status">
      Supervisor records could not be read: {{ supervisor.error }}. This is a connection problem, not a supervisor failure.
    </p>
    <p v-for="gap in supervisor.gaps" :key="gap" class="adwdbg-note" data-field="supervisor-gap">Not shown: {{ gap }}</p>
    <div class="adwdbg-log">
      <div class="adwdbg-log-lines adwsup-lines" role="log" aria-label="Supervisor records">
        <p v-if="!supervisor.lines.length" class="adwsup-empty" data-field="supervisor-empty">
          {{ supervisor.total ? 'No supervisor record matches this filter.' : 'No supervisor record has been read yet.' }}
        </p>
        <div v-for="line in supervisor.lines" :key="line.key" class="adwsup-line" :data-kind="line.kind"
             :data-state="line.state">
          <span class="adwsup-at">{{ line.at }}</span>
          <span class="adwsup-who">{{ line.machine }}/{{ line.agent }}</span>
          <span class="adwsup-kind">{{ line.kind }}<template v-if="line.state"> · {{ line.state }}</template></span>
          <span class="adwsup-text">{{ line.text }}</span>
          <span v-if="line.ids" class="adwsup-ids">{{ line.ids }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style>
.adwsup { margin: 10px 0; }
.adwsup-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 6px; }
.adwsup-lines { height: 220px; overflow: auto; padding: 4px 8px; }
.adwsup-line { display: flex; flex-wrap: wrap; gap: 8px; font: 12px/1.45 ui-monospace, monospace; color: #e6e6e6; }
.adwsup-at, .adwsup-ids { color: #9aa4b2; }
.adwsup-who { color: #8ab4f8; }
.adwsup-kind { color: #ffd54f; }
.adwsup-line[data-state="failed"] .adwsup-kind, .adwsup-line[data-state="not fixed"] .adwsup-kind,
.adwsup-line[data-state="stale"] .adwsup-kind, .adwsup-line[data-state="failing"] .adwsup-kind { color: #ff8a80; }
.adwsup-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.adwsup-empty { color: #9aa4b2; margin: 6px 0; }
.adwdbg-chip[data-supervisor-state="awake"] { border-color: #2e7d32; color: #1b5e20; font-weight: 700; }
.adwdbg-chip[data-supervisor-state="asleep"] { border-color: #8a93a0; }
</style>
