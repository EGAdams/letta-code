<script setup lang="ts">
// The debugger's own terminal pane: white on black like the stream below it.
// It follows the newest line until the reader scrolls up, and resumes when
// they scroll back to the bottom -- the existing terminal's pause behaviour.
import { nextTick, ref, watch } from 'vue'
import type { LogLine } from '../domain/state'

const props = defineProps<{ lines: LogLine[]; label: string; tall: boolean }>()
const host = ref<HTMLElement | null>(null)
const following = ref(true)

function onScroll(): void {
  const node = host.value
  if (node) following.value = node.scrollHeight - node.scrollTop - node.clientHeight <= 8
}

watch(() => props.lines.length, async () => {
  if (!following.value) return
  await nextTick()
  if (host.value) host.value.scrollTop = host.value.scrollHeight
}, { immediate: true })
</script>

<template>
  <div class="adwdbg-log">
    <div class="adwdbg-log-head">
      <span class="adwdbg-log-label">{{ label }}</span>
      <span>{{ lines.length }} line{{ lines.length === 1 ? '' : 's' }}{{ following ? '' : ' · paused (scroll to bottom to follow)' }}</span>
    </div>
    <div ref="host" class="adwdbg-log-lines" :class="{ 'adwdbg-log-tall': tall }" role="log" @scroll="onScroll">
      <div v-if="lines.length === 0" class="adwdbg-log-empty">No ADW events to show.</div>
      <div v-for="line in lines" :key="line.eventId" class="adwdbg-log-line" :data-kind="line.kind"
           :data-run="line.runId">{{ line.text }}</div>
    </div>
  </div>
</template>

<style>
.adwdbg-log { margin-top: 8px; background: #000; color: #fff; }
.adwdbg-log-head { display: flex; justify-content: space-between; gap: 12px; padding: 4px 12px;
  border-bottom: 1px solid #333; font: 12px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; color: #cfd6df; }
.adwdbg-log-label { font-weight: 700; color: #fff; }
.adwdbg-log-lines { box-sizing: border-box; height: 24vh; min-height: 140px; overflow-y: auto; padding: 8px 12px;
  font: 13px/1.5 ui-monospace, SFMono-Regular, Consolas, "Courier New", monospace; }
.adwdbg-log-lines.adwdbg-log-tall { height: 60vh; }
.adwdbg-log-line { white-space: pre-wrap; overflow-wrap: anywhere; }
.adwdbg-log-empty { color: #888; }
</style>
