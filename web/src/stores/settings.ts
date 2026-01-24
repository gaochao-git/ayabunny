/**
 * 设置状态管理 - 与原项目配置一致
 */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// TTS 音色选项
export const TTS_VOICES = [
  { id: 'alex', name: 'Alex (男·稳重)' },
  { id: 'benjamin', name: 'Benjamin (男·低沉)' },
  { id: 'charles', name: 'Charles (男·磁性)' },
  { id: 'david', name: 'David (男·开朗)' },
  { id: 'anna', name: 'Anna (女·稳重)' },
  { id: 'bella', name: 'Bella (女·热情)' },
  { id: 'claire', name: 'Claire (女·温柔)' },
  { id: 'diana', name: 'Diana (女·开朗)' },
]

export const useSettingsStore = defineStore('settings', () => {
  // 从 localStorage 加载设置
  const stored = localStorage.getItem('voice-chat-settings')
  const initial = stored ? JSON.parse(stored) : {}

  // ========== ASR 语音识别 ==========
  const silenceThreshold = ref(initial.silenceThreshold ?? 30)      // 静音阈值 (0-255)
  const silenceDuration = ref(initial.silenceDuration ?? 1500)      // 静音时长 (ms)
  const autoSend = ref(initial.autoSend ?? true)                    // 静音自动发送

  // ========== LLM 大语言模型 ==========
  const llmTemperature = ref(initial.llmTemperature ?? 0.7)         // 温度 (0-1.5)
  const llmMaxTokens = ref(initial.llmMaxTokens ?? 1500)            // 最大输出 (200-4000)
  const llmMaxHistory = ref(initial.llmMaxHistory ?? 20)            // 记忆轮数 (5-50)

  // ========== TTS 语音合成 ==========
  const ttsEnabled = ref(initial.ttsEnabled ?? true)                // 启用 TTS
  const ttsVoice = ref(initial.ttsVoice ?? 'alex')                  // 声音选择
  const ttsGain = ref(initial.ttsGain ?? 10)                        // 音量增益 (1-20x)

  // ========== VAD 打断检测 ==========
  const vadEnabled = ref(initial.vadEnabled ?? true)                // 启用 VAD
  const vadThreshold = ref(initial.vadThreshold ?? 60)              // 打断阈值 (10-80)
  const vadTriggerCount = ref(initial.vadTriggerCount ?? 5)         // 触发次数 (2-10)
  const vadIgnoreTime = ref(initial.vadIgnoreTime ?? 800)           // 忽略时间 (ms)

  // 保存设置
  function save(): void {
    const settings = {
      // ASR
      silenceThreshold: silenceThreshold.value,
      silenceDuration: silenceDuration.value,
      autoSend: autoSend.value,
      // LLM
      llmTemperature: llmTemperature.value,
      llmMaxTokens: llmMaxTokens.value,
      llmMaxHistory: llmMaxHistory.value,
      // TTS
      ttsEnabled: ttsEnabled.value,
      ttsVoice: ttsVoice.value,
      ttsGain: ttsGain.value,
      // VAD
      vadEnabled: vadEnabled.value,
      vadThreshold: vadThreshold.value,
      vadTriggerCount: vadTriggerCount.value,
      vadIgnoreTime: vadIgnoreTime.value,
    }
    localStorage.setItem('voice-chat-settings', JSON.stringify(settings))
  }

  // 监听变化自动保存
  watch(
    [
      silenceThreshold, silenceDuration, autoSend,
      llmTemperature, llmMaxTokens, llmMaxHistory,
      ttsEnabled, ttsVoice, ttsGain,
      vadEnabled, vadThreshold, vadTriggerCount, vadIgnoreTime,
    ],
    save,
    { deep: true }
  )

  return {
    // ASR
    silenceThreshold,
    silenceDuration,
    autoSend,
    // LLM
    llmTemperature,
    llmMaxTokens,
    llmMaxHistory,
    // TTS
    ttsEnabled,
    ttsVoice,
    ttsGain,
    // VAD
    vadEnabled,
    vadThreshold,
    vadTriggerCount,
    vadIgnoreTime,
    // Methods
    save,
  }
})
