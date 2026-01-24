<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  isRecording: boolean
  isPlaying: boolean
  audioLevel: number
}>()

const emit = defineEmits<{
  (e: 'hangup'): void
}>()

const statusText = computed(() => {
  if (props.isRecording) return '正在聆听...'
  if (props.isPlaying) return '正在播放...'
  return '通话中'
})

const pulseScale = computed(() => {
  return 1 + props.audioLevel * 0.5
})
</script>

<template>
  <div class="fixed inset-0 bg-gradient-to-b from-primary-600 to-primary-800 flex flex-col items-center justify-center z-50">
    <!-- 头像和动画 -->
    <div class="relative mb-8">
      <!-- 脉冲动画 -->
      <div
        v-if="isRecording || isPlaying"
        class="absolute inset-0 rounded-full bg-white/20 pulse-ring"
        :style="{ transform: `scale(${pulseScale})` }"
      ></div>
      <div
        v-if="isRecording || isPlaying"
        class="absolute inset-0 rounded-full bg-white/10 pulse-ring"
        style="animation-delay: 0.5s"
        :style="{ transform: `scale(${pulseScale * 1.2})` }"
      ></div>

      <!-- 头像 -->
      <div class="w-32 h-32 rounded-full bg-white/20 flex items-center justify-center relative z-10">
        <svg class="w-16 h-16 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      </div>
    </div>

    <!-- 状态文字 -->
    <p class="text-white text-xl mb-2">语音助手</p>
    <p class="text-white/70 text-sm mb-12">{{ statusText }}</p>

    <!-- 音量指示器 -->
    <div v-if="isRecording" class="flex space-x-1 mb-8">
      <div
        v-for="i in 5"
        :key="i"
        class="w-1 bg-white/50 rounded-full transition-all duration-100"
        :style="{
          height: `${Math.max(8, audioLevel * 100 * (0.5 + i * 0.1))}px`
        }"
      ></div>
    </div>

    <!-- 挂断按钮 -->
    <button
      @click="emit('hangup')"
      class="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 transition-colors flex items-center justify-center shadow-lg"
    >
      <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3a2 2 0 00-2 2v1c0 8.284 6.716 15 15 15h1a2 2 0 002-2v-3.28a1 1 0 00-.684-.948l-4.493-1.498a1 1 0 00-1.21.502l-1.13 2.257a11.042 11.042 0 01-5.516-5.517l2.257-1.128a1 1 0 00.502-1.21L9.228 3.683A1 1 0 008.279 3H5z" />
      </svg>
    </button>
  </div>
</template>
