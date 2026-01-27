/**
 * 设置状态管理 - 与原项目配置一致
 */

import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// ASR 服务选项
export const ASR_SERVICES = [
  { id: 'sensevoice', name: 'SenseVoice', desc: '云端，免费，中文优秀（默认）' },
  { id: 'whisper', name: 'Whisper', desc: '本地，需配置 WHISPER_ENABLED=true' },
  { id: 'funasr', name: 'FunASR', desc: '本地，需配置 FUNASR_ENABLED=true' },
] as const

export type ASRService = typeof ASR_SERVICES[number]['id']

// LLM 模型选项
export const LLM_MODELS = [
  { id: 'Qwen/Qwen3-30B-A3B-Instruct-2507', name: 'Qwen3-30B-A3B-Instruct', desc: '通义千问3 30B' },
  { id: 'deepseek-ai/DeepSeek-V3', name: 'DeepSeek-V3', desc: 'DeepSeek 最新模型' },
] as const

export type LLMModel = typeof LLM_MODELS[number]['id']

// TTS 模型选项
export const TTS_MODELS = [
  { id: 'IndexTeam/IndexTTS-2', name: 'IndexTTS-2', desc: '多音色，支持克隆（默认）' },
  { id: 'FunAudioLLM/CosyVoice2-0.5B', name: 'CosyVoice 2', desc: '阿里开源，中文效果好' },
] as const

export type TTSModel = typeof TTS_MODELS[number]['id']

// TTS 音色选项（按模型分组）
export const TTS_VOICES = {
  'IndexTeam/IndexTTS-2': [
    { id: 'alex', name: 'Alex (男·稳重)' },
    { id: 'benjamin', name: 'Benjamin (男·低沉)' },
    { id: 'charles', name: 'Charles (男·磁性)' },
    { id: 'david', name: 'David (男·开朗)' },
    { id: 'anna', name: 'Anna (女·稳重)' },
    { id: 'bella', name: 'Bella (女·热情)' },
    { id: 'claire', name: 'Claire (女·温柔)' },
    { id: 'diana', name: 'Diana (女·开朗)' },
  ],
  'FunAudioLLM/CosyVoice2-0.5B': [
    { id: '中文女', name: '中文女' },
    { id: '中文男', name: '中文男' },
    { id: '英文女', name: '英文女' },
    { id: '英文男', name: '英文男' },
    { id: '日语男', name: '日语男' },
    { id: '粤语女', name: '粤语女' },
    { id: '韩语女', name: '韩语女' },
  ],
} as const

// 默认音色（兼容旧代码）
export const DEFAULT_TTS_VOICES = TTS_VOICES['IndexTeam/IndexTTS-2']

// VAD 类型选项
export const VAD_TYPES = [
  { id: 'ten', name: 'TEN VAD', desc: '后端，超轻量(1.3MB)，低延迟' },
  { id: 'webrtc', name: 'WebRTC VAD', desc: '前端频谱分析，超轻量' },
  { id: 'silero', name: 'Silero VAD', desc: '后端ONNX模型，准确(50MB)' },
  { id: 'funasr', name: 'FunASR VAD', desc: '后端AI模型，待实现' },
] as const

export type VADType = typeof VAD_TYPES[number]['id']

// 背景选项
export const BACKGROUNDS = [
  { id: 'sunset', name: '日落橙', colors: ['#ffecd2', '#fcb69f', '#ffeaa7'] },
  { id: 'ocean', name: '海洋蓝', colors: ['#a8edea', '#fed6e3', '#d299c2'] },
  { id: 'forest', name: '森林绿', colors: ['#d4fc79', '#96e6a1', '#dfe6e9'] },
  { id: 'lavender', name: '薰衣草', colors: ['#e0c3fc', '#8ec5fc', '#f093fb'] },
  { id: 'candy', name: '糖果粉', colors: ['#ffecd2', '#fcb69f', '#ff9a9e'] },
] as const

export type BackgroundType = typeof BACKGROUNDS[number]['id']

// 角色选项（暂时都用 rabbit.svg，后续可添加更多角色图片）
export const AVATARS = [
  { id: 'rabbit-girl', name: '小兔妹妹', icon: '🐰', file: '/rabbit.svg' },
  { id: 'rabbit-boy', name: '小兔弟弟', icon: '🐇', file: '/rabbit.svg' },
  { id: 'cat-girl', name: '小猫姐姐', icon: '🐱', file: '/rabbit.svg' },
  { id: 'bear-boy', name: '小熊哥哥', icon: '🐻', file: '/rabbit.svg' },
] as const

export type AvatarType = typeof AVATARS[number]['id']

export const useSettingsStore = defineStore('settings', () => {
  // 从 localStorage 加载设置
  const stored = localStorage.getItem('voice-chat-settings')
  const initial = stored ? JSON.parse(stored) : {}

  // ========== ASR 语音识别 ==========
  const asrService = ref<ASRService>(initial.asrService ?? 'sensevoice') // ASR 服务
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
  const ttsModel = ref<TTSModel>(initial.ttsModel ?? 'IndexTeam/IndexTTS-2')  // TTS 模型
  const ttsVoice = ref(initial.ttsVoice ?? 'alex')                  // 声音选择
  const ttsCustomVoiceId = ref<string | null>(initial.ttsCustomVoiceId ?? null)  // 自定义音色 ID
  const ttsSpeed = ref(initial.ttsSpeed ?? 1.0)                     // 语速 (0.5-2.0)
  const ttsGain = ref(initial.ttsGain ?? 10)                        // 音量增益 (1-20x)

  // ========== VAD 打断检测 ==========
  const vadEnabled = ref(initial.vadEnabled ?? true)                // 启用 VAD
  // VAD 类型（兼容旧值 'simple'/'ten' 迁移到 'webrtc'）
  const savedVadType = (initial.vadType === 'simple' || initial.vadType === 'ten') ? 'webrtc' : initial.vadType
  const vadType = ref<VADType>(savedVadType ?? 'webrtc')
  const vadThreshold = ref(initial.vadThreshold ?? 60)              // 打断阈值 (10-80)，仅简单模式
  const vadTriggerCount = ref(initial.vadTriggerCount ?? 5)         // 触发次数 (2-10)，仅简单模式
  const vadIgnoreTime = ref(initial.vadIgnoreTime ?? 800)           // 忽略时间 (ms)

  // ========== 外观设置 ==========
  const background = ref<BackgroundType>(initial.background ?? 'sunset')  // 背景主题
  const avatar = ref<AvatarType>(initial.avatar ?? 'rabbit-girl')         // 角色形象
  const assistantName = ref(initial.assistantName ?? '小智')              // 助手名字
  const assistantAliases = ref<string[]>(initial.assistantAliases ?? ['小知', '小志'])  // 同音词/别名

  // ========== 背景音乐 ==========
  const bgmEnabled = ref(initial.bgmEnabled ?? true)                      // 启用背景音乐
  const bgmVolume = ref(initial.bgmVolume ?? 0.6)                         // 背景音乐音量 (0-1)

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
      ttsModel: ttsModel.value,
      ttsVoice: ttsVoice.value,
      ttsCustomVoiceId: ttsCustomVoiceId.value,
      ttsSpeed: ttsSpeed.value,
      ttsGain: ttsGain.value,
      // VAD
      vadEnabled: vadEnabled.value,
      vadType: vadType.value,
      vadThreshold: vadThreshold.value,
      vadTriggerCount: vadTriggerCount.value,
      vadIgnoreTime: vadIgnoreTime.value,
      // 外观
      background: background.value,
      avatar: avatar.value,
      assistantName: assistantName.value,
      assistantAliases: assistantAliases.value,
      // BGM
      bgmEnabled: bgmEnabled.value,
      bgmVolume: bgmVolume.value,
    }
    localStorage.setItem('voice-chat-settings', JSON.stringify(settings))
  }

  // 监听变化自动保存
  watch(
    [
      asrService, silenceThreshold, silenceDuration, autoSend,
      llmModel, llmTemperature, llmMaxTokens, llmMaxHistory,
      ttsEnabled, ttsModel, ttsVoice, ttsCustomVoiceId, ttsSpeed, ttsGain,
      vadEnabled, vadType, vadThreshold, vadTriggerCount, vadIgnoreTime,
      background, avatar, assistantName, assistantAliases,
      bgmEnabled, bgmVolume,
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
    ttsModel,
    ttsVoice,
    ttsCustomVoiceId,
    ttsSpeed,
    ttsGain,
    // VAD
    vadEnabled,
    vadType,
    vadThreshold,
    vadTriggerCount,
    vadIgnoreTime,
    // 外观
    background,
    avatar,
    assistantName,
    assistantAliases,
    // BGM
    bgmEnabled,
    bgmVolume,
    // Methods
    save,
  }
})
