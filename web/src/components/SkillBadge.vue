<script setup lang="ts">
defineProps<{
  name: string
  status?: 'pending' | 'running' | 'done'
}>()
</script>

<template>
  <div
    class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm transition-all"
    :class="{
      'bg-yellow-100 text-yellow-700': status === 'pending',
      'bg-green-100 text-green-700': status === 'running',
      'bg-gray-100 text-gray-600': status === 'done' || !status
    }"
  >
    <!-- 状态图标 -->
    <span v-if="status === 'running'" class="relative flex h-2 w-2">
      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
      <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
    </span>
    <svg v-else-if="status === 'done'" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
    </svg>
    <svg v-else class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>

    <!-- 技能名称 -->
    <span class="font-medium">{{ name }}</span>
  </div>
</template>
