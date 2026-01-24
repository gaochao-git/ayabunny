/**
 * 设置状态管理 - 与原项目配置一致
 */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// ASR 服务选项
export const ASR_SERVICES = [
  { id: 'funasr', name: 'FunASR', desc: '阿里达摩院，中文优化', port: 10095 },
  { id: 'whisper', name: 'Whisper', desc: 'OpenAI，多语言支持', port: 8017 },
] as const

export type ASRService = typeof ASR_SERVICES[number]['id']

// LLM 模型选项
export const LLM_MODELS = [
  { id: 'Qwen/Qwen3-30B-A3B-Instruct-2507', name: 'Qwen3-30B-A3B-Instruct', desc: '通义千问3 30B' },
  { id: 'deepseek-ai/DeepSeek-V3', name: 'DeepSeek-V3', desc: 'DeepSeek 最新模型' },
] as const

export type LLMModel = typeof LLM_MODELS[number]['id']

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

// VAD 类型选项
export const VAD_TYPES = [
  { id: 'simple', name: '简单音量检测', desc: '基于音量阈值，低延迟' },
  { id: 'webrtc', name: 'WebRTC VAD', desc: '频谱分析，轻量准确' },
  { id: 'silero', name: 'Silero VAD', desc: '前端AI模型' },
  { id: 'funasr', name: 'FunASR VAD', desc: '服务端AI模型，最准确' },
] as const

export type VADType = typeof VAD_TYPES[number]['id']

export const useSettingsStore = defineStore('settings', () => {
  // 从 localStorage 加载设置
  const stored = localStorage.getItem('voice-chat-settings')
  const initial = stored ? JSON.parse(stored) : {}

  // ========== ASR 语音识别 ==========
  const asrService = ref<ASRService>(initial.asrService ?? 'funasr') // ASR 服务
  const silenceThreshold = ref(initial.silenceThreshold ?? 30)      // 静音阈值 (0-255)
  const silenceDuration = ref(initial.silenceDuration ?? 1500)      // 静音时长 (ms)
  const autoSend = ref(initial.autoSend ?? true)                    // 静音自动发送

  // ========== LLM 大语言模型 ==========
  const llmModel = ref<LLMModel>(initial.llmModel ?? 'Qwen/Qwen3-30B-A3B-Instruct-2507')   // 模型选择
  const llmTemperature = ref(initial.llmTemperature ?? 0.7)         // 温度 (0-1.5)
  const llmMaxTokens = ref(initial.llmMaxTokens ?? 1500)            // 最大输出 (200-4000)
  const llmMaxHistory = ref(initial.llmMaxHistory ?? 20)            // 记忆轮数 (5-50)

  // ========== TTS 语音合成 ==========
  const ttsEnabled = ref(initial.ttsEnabled ?? true)                // 启用 TTS
  const ttsVoice = ref(initial.ttsVoice ?? 'alex')                  // 声音选择
  const ttsGain = ref(initial.ttsGain ?? 10)                        // 音量增益 (1-20x)

  // ========== VAD 打断检测 ==========
  const vadEnabled = ref(initial.vadEnabled ?? true)                // 启用 VAD
  const vadType = ref<VADType>(initial.vadType ?? 'simple')         // VAD 类型
  const vadThreshold = ref(initial.vadThreshold ?? 60)              // 打断阈值 (10-80)，仅简单模式
  const vadTriggerCount = ref(initial.vadTriggerCount ?? 5)         // 触发次数 (2-10)，仅简单模式
  const vadIgnoreTime = ref(initial.vadIgnoreTime ?? 800)           // 忽略时间 (ms)

  // 保存设置
  function save(): void {
    const settings = {
      // ASR
      asrService: asrService.value,
      silenceThreshold: silenceThreshold.value,
      silenceDuration: silenceDuration.value,
      autoSend: autoSend.value,
      // LLM
      llmModel: llmModel.value,
      llmTemperature: llmTemperature.value,
      llmMaxTokens: llmMaxTokens.value,
      llmMaxHistory: llmMaxHistory.value,
      // TTS
      ttsEnabled: ttsEnabled.value,
      ttsVoice: ttsVoice.value,
      ttsGain: ttsGain.value,
      // VAD
      vadEnabled: vadEnabled.value,
      vadType: vadType.value,
      vadThreshold: vadThreshold.value,
      vadTriggerCount: vadTriggerCount.value,
      vadIgnoreTime: vadIgnoreTime.value,
    }
    localStorage.setItem('voice-chat-settings', JSON.stringify(settings))
  }

  // 监听变化自动保存
  watch(
    [
      asrService, silenceThreshold, silenceDuration, autoSend,
      llmModel, llmTemperature, llmMaxTokens, llmMaxHistory,
      ttsEnabled, ttsVoice, ttsGain,
      vadEnabled, vadType, vadThreshold, vadTriggerCount, vadIgnoreTime,
    ],
    save,
    { deep: true }
  )

  return {
    // ASR
    asrService,
    silenceThreshold,
    silenceDuration,
    autoSend,
    // LLM
    llmModel,
    llmTemperature,
    llmMaxTokens,
    llmMaxHistory,
    // TTS
    ttsEnabled,
    ttsVoice,
    ttsGain,
    // VAD
    vadEnabled,
    vadType,
    vadThreshold,
    vadTriggerCount,
    vadIgnoreTime,
    // Methods
    save,
  }
})
