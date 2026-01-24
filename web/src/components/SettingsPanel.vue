<script setup lang="ts">
import { computed } from 'vue'
import { useSettingsStore, TTS_VOICES } from '@/stores/settings'

const settings = useSettingsStore()

const props = defineProps<{
  show: boolean
  audioLevel?: number  // 从父组件传入的当前音量
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

// 格式化静音时长显示
const silenceDurationDisplay = computed(() => {
  return (settings.silenceDuration / 1000).toFixed(1) + 's'
})

// 格式化忽略时间显示
const vadIgnoreTimeDisplay = computed(() => {
  return settings.vadIgnoreTime + 'ms'
})

// 参数说明
const tooltips = {
  // ASR
  silenceThreshold: '当麦克风音量低于此值时判定为静音。值越小越灵敏，但容易误触发；值越大需要更安静的环境才能停止录音。建议根据当前音量调整。',
  silenceDuration: '静音持续多长时间后自动停止录音并发送。值越小响应越快，但可能在说话停顿时误触发；值越大等待越久。',

  // LLM
  llmTemperature: '控制AI回复的随机性和创造性。0=确定性强，回复稳定；1.5=随机性高，回复更有创意但可能不连贯。讲故事建议0.7-1.0。',
  llmMaxTokens: '限制AI单次回复的最大长度（约等于字数的1.5倍）。值越大回复越长，但响应时间也越长。',
  llmMaxHistory: '保留多少轮对话历史作为上下文。值越大AI记忆越长，但消耗更多资源。讲故事建议10-20轮。',

  // TTS
  ttsVoice: '选择语音合成的声音角色。不同声音有不同的音色和风格特点。',
  ttsGain: '放大语音播放的音量。如果听不清楚可以调大；如果太吵可以调小。1x为原始音量，20x为最大放大。',

  // VAD
  vadEnabled: '开启后，当AI说话时如果检测到你在说话，会自动停止播放，让你可以打断AI。',
  vadThreshold: '打断检测的音量阈值。你的声音需要超过此值才会触发打断。值越小越灵敏，但可能被背景噪音误触发。',
  vadTriggerCount: '连续检测到多少次超过阈值才真正触发打断。值越大越不容易误触发，但打断响应变慢。',
  vadIgnoreTime: 'AI开始说话后忽略麦克风输入的时间。防止AI的声音通过麦克风回传导致自己打断自己。',
}
</script>

<template>
  <Transition name="slide">
    <div
      v-if="show"
      class="fixed inset-y-0 right-0 w-96 bg-white shadow-xl z-50 flex flex-col"
    >
      <!-- 头部 -->
      <div class="flex items-center justify-between p-4 border-b bg-gradient-to-r from-pink-400 via-pink-500 to-orange-400">
        <h2 class="text-lg font-semibold text-white">参数设置</h2>
        <button
          @click="emit('close')"
          class="p-2 hover:bg-white/20 rounded-lg transition-colors"
        >
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- 当前音量显示 -->
      <div class="bg-gradient-to-r from-pink-400 to-orange-400 px-4 py-3 text-center" title="当前麦克风检测到的音量值（0-255），用于参考设置静音阈值和打断阈值">
        <span class="text-white/80 text-sm">当前音量: </span>
        <span class="text-white text-2xl font-bold">{{ props.audioLevel ?? 0 }}</span>
      </div>

      <!-- 设置内容 -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        <!-- ASR 语音识别 -->
        <section class="space-y-3">
          <div class="inline-block px-3 py-1 rounded text-xs font-semibold bg-blue-100 text-blue-600" title="语音识别相关参数，控制何时停止录音">
            ① ASR 语音识别
          </div>

          <div class="grid grid-cols-2 gap-3">
            <!-- 静音阈值 -->
            <div class="bg-white border rounded-lg p-3 cursor-help" :title="tooltips.silenceThreshold">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  静音阈值
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <span class="text-sm font-medium">{{ settings.silenceThreshold }}</span>
              </div>
              <input
                type="range"
                v-model.number="settings.silenceThreshold"
                min="5"
                max="50"
                class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>

            <!-- 静音时长 -->
            <div class="bg-white border rounded-lg p-3 cursor-help" :title="tooltips.silenceDuration">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  静音时长
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <span class="text-sm font-medium">{{ silenceDurationDisplay }}</span>
              </div>
              <input
                type="range"
                v-model.number="settings.silenceDuration"
                min="500"
                max="3000"
                step="100"
                class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500"
              />
            </div>
          </div>
        </section>

        <!-- LLM 大语言模型 -->
        <section class="space-y-3">
          <div class="inline-block px-3 py-1 rounded text-xs font-semibold bg-green-100 text-green-600" title="大语言模型参数，控制AI回复的风格和长度">
            ② LLM 大语言模型
          </div>

          <div class="grid grid-cols-2 gap-3">
            <!-- 温度 -->
            <div class="bg-white border rounded-lg p-3 cursor-help" :title="tooltips.llmTemperature">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  温度
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <span class="text-sm font-medium">{{ settings.llmTemperature }}</span>
              </div>
              <input
                type="range"
                v-model.number="settings.llmTemperature"
                min="0"
                max="1.5"
                step="0.1"
                class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500"
              />
            </div>

            <!-- 最大输出 -->
            <div class="bg-white border rounded-lg p-3 cursor-help" :title="tooltips.llmMaxTokens">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  最大输出
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <span class="text-sm font-medium">{{ settings.llmMaxTokens }}</span>
              </div>
              <input
                type="range"
                v-model.number="settings.llmMaxTokens"
                min="200"
                max="4000"
                step="100"
                class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500"
              />
            </div>

            <!-- 记忆轮数 -->
            <div class="bg-white border rounded-lg p-3 cursor-help" :title="tooltips.llmMaxHistory">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  记忆轮数
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <span class="text-sm font-medium">{{ settings.llmMaxHistory }}</span>
              </div>
              <input
                type="range"
                v-model.number="settings.llmMaxHistory"
                min="5"
                max="50"
                class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500"
              />
            </div>
          </div>
        </section>

        <!-- TTS 语音合成 -->
        <section class="space-y-3">
          <div class="inline-block px-3 py-1 rounded text-xs font-semibold bg-yellow-100 text-yellow-600" title="语音合成参数，控制AI说话的声音">
            ③ TTS 语音合成
          </div>

          <div class="grid grid-cols-2 gap-3">
            <!-- 声音选择 -->
            <div class="bg-white border rounded-lg p-3 col-span-2 cursor-help" :title="tooltips.ttsVoice">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  声音
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
              </div>
              <select
                v-model="settings.ttsVoice"
                class="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500"
              >
                <option v-for="voice in TTS_VOICES" :key="voice.id" :value="voice.id">
                  {{ voice.name }}
                </option>
              </select>
            </div>

            <!-- 音量增益 -->
            <div class="bg-white border rounded-lg p-3 col-span-2 cursor-help" :title="tooltips.ttsGain">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  音量增益
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <span class="text-sm font-medium">{{ settings.ttsGain }}x</span>
              </div>
              <input
                type="range"
                v-model.number="settings.ttsGain"
                min="1"
                max="20"
                class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-yellow-500"
              />
            </div>
          </div>
        </section>

        <!-- VAD 打断检测 -->
        <section class="space-y-3">
          <div class="inline-block px-3 py-1 rounded text-xs font-semibold bg-red-100 text-red-600" title="语音活动检测参数，用于检测用户说话并打断AI">
            ④ VAD 打断检测
          </div>

          <div class="grid grid-cols-2 gap-3">
            <!-- 启用 VAD -->
            <div class="bg-white border rounded-lg p-3 col-span-2 cursor-help" :title="tooltips.vadEnabled">
              <label class="flex items-center justify-between cursor-pointer">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  启用语音打断
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <input
                  type="checkbox"
                  v-model="settings.vadEnabled"
                  class="w-5 h-5 rounded text-red-500 focus:ring-red-500"
                />
              </label>
            </div>

            <!-- 打断阈值 -->
            <div class="bg-white border rounded-lg p-3 cursor-help" :title="tooltips.vadThreshold">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  打断阈值
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <span class="text-sm font-medium">{{ settings.vadThreshold }}</span>
              </div>
              <input
                type="range"
                v-model.number="settings.vadThreshold"
                min="10"
                max="80"
                class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-500"
              />
            </div>

            <!-- 触发次数 -->
            <div class="bg-white border rounded-lg p-3 cursor-help" :title="tooltips.vadTriggerCount">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  触发次数
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <span class="text-sm font-medium">{{ settings.vadTriggerCount }}</span>
              </div>
              <input
                type="range"
                v-model.number="settings.vadTriggerCount"
                min="2"
                max="10"
                class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-500"
              />
            </div>

            <!-- 忽略时间 -->
            <div class="bg-white border rounded-lg p-3 col-span-2 cursor-help" :title="tooltips.vadIgnoreTime">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600 flex items-center gap-1">
                  忽略时间
                  <svg class="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </span>
                <span class="text-sm font-medium">{{ vadIgnoreTimeDisplay }}</span>
              </div>
              <input
                type="range"
                v-model.number="settings.vadIgnoreTime"
                min="300"
                max="1500"
                step="100"
                class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-500"
              />
            </div>
          </div>
        </section>
      </div>
    </div>
  </Transition>

  <!-- 遮罩 -->
  <Transition name="fade">
    <div
      v-if="show"
      @click="emit('close')"
      class="fixed inset-0 bg-black/30 z-40"
    ></div>
  </Transition>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
