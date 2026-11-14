<script setup lang="ts">
// A participant's dashed lifeline, with its activation bar when it has one.
import type { DiagramColumn } from '../../contracts'
import ActivationBar from './ActivationBar.vue'

defineProps<{ column: DiagramColumn; centre: number; rows: number }>()
</script>

<template>
  <div class="sd-lifeline-track" :data-lifeline="column.instanceId" :style="{ left: `${centre}%` }">
    <span class="sd-lifeline" />
    <ActivationBar v-if="column.activeFrom !== null && column.activeFrom !== undefined"
                   :from="column.activeFrom" :to="column.activeTo ?? null" :rows="rows" :status="column.status" />
  </div>
</template>
