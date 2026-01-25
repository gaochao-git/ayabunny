<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useChat } from '@/composables/useChat'
import { useAudioRecorder } from '@/composables/useAudioRecorder'
import { useTTSPlayer } from '@/composables/useTTSPlayer'
import { useVAD } from '@/composables/useVAD'
import { useWebRTCVAD } from '@/composables/useWebRTCVAD'
import { useSileroVAD } from '@/composables/useSileroVAD'
import { useFunASRVAD } from '@/composables/useFunASRVAD'
import { useSettingsStore, BACKGROUNDS, AVATARS } from '@/stores/settings'
import { transcribe } from '@/api/asr'
import ChatArea from '@/components/ChatArea.vue'
import RightPanel from '@/components/RightPanel.vue'

const settings = useSettingsStore()
const chat = useChat()

// 用于前向引用的变量
let startCallRecording: () => Promise<void>
let ttsPlayer: ReturnType<typeof useTTSPlayer>

// 状态
const inputText = ref('')
const showSettings = ref(false)
const isInCall = ref(false)       // 是否在通话中
const isTranscribing = ref(false) // 是否正在语音转文字
const isProcessingCall = ref(false) // 是否正在处理通话（防止并发）

// 当前选择的背景和头像
const currentBackground = computed(() =>
  BACKGROUNDS.find(bg => bg.id === settings.background) || BACKGROUNDS[0]
)
const currentAvatar = computed(() =>
  AVATARS.find(av => av.id === settings.avatar) || AVATARS[0]
)

// 背景样式
const backgroundStyle = computed(() => ({
  background: `linear-gradient(135deg, ${currentBackground.value.colors[0]} 0%, ${currentBackground.value.colors[1]} 50%, ${currentBackground.value.colors[2]} 100%)`
}))

// TTS 播放器
ttsPlayer = useTTSPlayer({
  gain: () => settings.ttsGain,
  voice: () => settings.ttsVoice,
  customVoiceId: () => settings.ttsCustomVoiceId,
  speed: () => settings.ttsSpeed,
  onPlayStart: async () => {
    console.log('[TTS] 开始播放')
    // 通话中，播放时启动 VAD 检测打断
    if (settings.vadEnabled && isInCall.value) {
      try {
        await vad.start()
      } catch (error) {
        console.error('[VAD] 启动失败:', error)
      }
    }
  },
  onPlayEnd: () => {
    console.log('[TTS] 播放结束')
    // 播放结束后停止 VAD
    vad.stop()
    // 通话中自动继续录音（检查状态避免并发）
    if (isInCall.value && !callRecorder.isRecording.value && !isProcessingCall.value) {
      startCallRecording()
    }
  },
})

// 唤醒词 ASR 识别函数
async function transcribeForWakeWord(blob: Blob): Promise<string> {
  try {
    const result = await transcribe(blob)
    return result.success ? result.text : ''
  } catch {
    return ''
  }
}

// VAD 语音打断检测（仅通话中使用，支持唤醒词模式）
// 打断词/唤醒词列表（动态包含助手名字）
const getWakeWords = () => {
  const name = settings.assistantName || '小智'
  return [
    // 助手名字（用户设置的）
    name,
    // 打断词
    '等等', '等一下', '等会', '等会儿',
    '停', '停一下', '停停', '暂停',
    '不对', '不是', '不要', '不用',
    '好了', '可以了', '行了', '够了',
    '听我说', '我说', '我想说',
    '安静', '别说了', '闭嘴',
  ]
}

// 通用的打断处理函数
function handleVADSpeechStart() {
  console.log('[VAD] 检测到用户说话，打断 TTS')
  if (ttsPlayer.isPlaying.value) {
    // 停止 TTS 播放（会清空队列）
    ttsPlayer.stop()
    // 延迟一点再开始录音，避免捕获 TTS 尾音
    setTimeout(() => {
      if (isInCall.value && !callRecorder.isRecording.value && !isProcessingCall.value) {
        startCallRecording()
      }
    }, 200)
  }
}

// 简单 VAD（基于音量阈值）
const simpleVAD = useVAD({
  threshold: () => settings.vadThreshold,
  triggerCount: () => settings.vadTriggerCount,
  ignoreTime: () => settings.vadIgnoreTime,
  wakeWords: getWakeWords,
  wakeWordTimeout: 1500,
  transcribeFn: transcribeForWakeWord,
  onWakeWordDetected: () => {
    console.log('[SimpleVAD] 唤醒词检测到！')
  },
  onSpeechStart: handleVADSpeechStart,
})

// WebRTC VAD（基于频谱分析）
const webrtcVAD = useWebRTCVAD({
  ignoreTime: () => settings.vadIgnoreTime,
  wakeWords: getWakeWords,
  transcribeFn: transcribeForWakeWord,
  onWakeWordDetected: (word) => {
    console.log(`[WebRTC VAD] 中断词匹配: "${word}"`)
  },
  onSpeechStart: handleVADSpeechStart,
})

// Silero VAD（基于后端 AI 模型 + 中断词验证）
const sileroVAD = useSileroVAD({
  wsUrl: 'ws://127.0.0.1:10097',  // Silero VAD 服务 WebSocket 地址
  wakeWords: getWakeWords,  // 中断词列表（动态获取，包含助手名字）
  transcribeFn: transcribeForWakeWord,  // ASR 识别函数
  ignoreTime: () => settings.vadIgnoreTime,
  onWakeWordDetected: (word, text) => {
    console.log(`[Silero VAD] 中断词匹配: "${word}" (原文: "${text}")`)
  },
  onSpeechStart: handleVADSpeechStart,
})

// FunASR VAD（基于服务端 AI 模型 + 中断词验证）
const funasrVAD = useFunASRVAD({
  wsUrl: 'ws://127.0.0.1:10096',  // FunASR 流式服务 WebSocket 地址
  ignoreTime: () => settings.vadIgnoreTime,
  wakeWords: getWakeWords,  // 中断词列表（动态获取，包含助手名字）
  transcribeFn: transcribeForWakeWord,  // ASR 识别函数
  onSpeechStart: handleVADSpeechStart,
  onWakeWordDetected: (word, text) => {
    console.log(`[FunASR VAD] 中断词匹配: "${word}" (原文: "${text}")`)
  },
})

// 统一 VAD 接口
const vad = {
  start: async () => {
    if (settings.vadType === 'funasr') {
      await funasrVAD.start()
    } else if (settings.vadType === 'silero') {
      await sileroVAD.start()
    } else if (settings.vadType === 'webrtc') {
      await webrtcVAD.start()
    } else {
      simpleVAD.start()
    }
  },
  stop: () => {
    simpleVAD.stop()
    webrtcVAD.stop()
    sileroVAD.stop()
    funasrVAD.stop()
  },
  get isActive() {
    if (settings.vadType === 'funasr') return funasrVAD.isActive
    if (settings.vadType === 'silero') return sileroVAD.isActive
    if (settings.vadType === 'webrtc') return webrtcVAD.isActive
    return simpleVAD.isActive
  },
  get isSpeaking() {
    if (settings.vadType === 'funasr') return funasrVAD.isSpeaking
    if (settings.vadType === 'silero') return sileroVAD.isSpeaking
    if (settings.vadType === 'webrtc') return webrtcVAD.isSpeaking
    return simpleVAD.isSpeaking
  },
  get isLoading() {
    return sileroVAD.isLoading || funasrVAD.isConnecting
  },
}

// 监听 VAD 类型变化，切换时停止当前 VAD
watch(() => settings.vadType, (newType, oldType) => {
  if (newType !== oldType) {
    console.log(`[VAD] 切换类型: ${oldType} -> ${newType}`)
    // 停止所有 VAD
    simpleVAD.stop()
    webrtcVAD.stop()
    sileroVAD.stop()
    funasrVAD.stop()
  }
})

// 通话录音器（带静音检测自动停止）
const callRecorder = useAudioRecorder({
  silenceThreshold: () => settings.silenceThreshold,
  silenceDuration: () => settings.silenceDuration,
  onSilenceDetected: async () => {
    console.log('[Call] 检测到静音，自动停止录音...')
    // 防止并发：检查是否正在处理、是否在通话中、是否还在录音
    if (settings.autoSend && callRecorder.isRecording.value && isInCall.value && !isProcessingCall.value) {
      await handleCallRecordingStop()
    }
  },
})

// 语音转文字录音器（不自动停止，手动控制）
const transcribeRecorder = useAudioRecorder({})

// 计算属性
const canSend = computed(() => inputText.value.trim() && !chat.isLoading.value)

// 状态文字（通话中显示）
const statusText = computed(() => {
  if (sileroVAD.isLoading.value || funasrVAD.isConnecting.value) return '加载VAD模型...'
  if (callRecorder.isRecording.value) return '正在听...'
  // TTS 播放时，检查 VAD 状态
  if (ttsPlayer.isPlaying.value || ttsPlayer.isPending.value) {
    // 正在验证中断词
    if (funasrVAD.isCheckingWakeWord.value) {
      return '验证中断词...'
    }
    // VAD 检测到语音
    if (funasrVAD.isSpeaking.value || sileroVAD.isSpeaking.value || webrtcVAD.isSpeaking.value || simpleVAD.isSpeaking.value) {
      return '检测到语音...'
    }
    return '正在说...'
  }
  if (chat.isLoading.value) return '思考中...'
  if (isProcessingCall.value) return '处理中...'
  return '等待说话...'
})

// ============ 文字模式 ============

// 发送文字消息（不播放语音）
async function handleSend() {
  if (!canSend.value) return

  const text = inputText.value.trim()
  inputText.value = ''

  // 文字模式不播放语音
  await chat.send(text)
}

// 语音转文字（填充到输入框）
async function toggleTranscribe() {
  if (transcribeRecorder.isRecording.value) {
    // 停止录音，进行识别
    isTranscribing.value = true
    try {
      const audioBlob = await transcribeRecorder.stopRecording()
      const result = await transcribe(audioBlob)
      if (result.success && result.text) {
        // 将识别结果填充到输入框
        inputText.value = (inputText.value + ' ' + result.text).trim()
      }
    } catch (error) {
      console.error('Transcribe error:', error)
    } finally {
      isTranscribing.value = false
    }
  } else {
    // 开始录音
    try {
      await transcribeRecorder.startRecording()
    } catch (error) {
      console.error('Failed to start transcribe recording:', error)
    }
  }
}

// ============ 通话模式 ============

// 开始/结束通话
function toggleCall() {
  if (isInCall.value) {
    endCall()
  } else {
    startCall()
  }
}

// 开始语音通话
async function startCall() {
  // 移动端需要在用户交互时解锁音频
  await ttsPlayer.unlock()
  isInCall.value = true
  await startCallRecording()
}

// 结束语音通话
function endCall() {
  console.log('[Call] 结束通话')
  isInCall.value = false
  isProcessingCall.value = false  // 重置处理状态

  // 停止所有活动
  chat.abort()  // 取消 LLM 请求
  if (callRecorder.isRecording.value) {
    callRecorder.stopRecording()
  }
  ttsPlayer.stop()  // 会清空 TTS 队列
  vad.stop()
}

// 开始通话录音
startCallRecording = async function() {
  // 防止重复开始录音
  if (callRecorder.isRecording.value) {
    console.log('[Call] 已在录音中，跳过')
    return
  }
  // 防止在处理中开始录音
  if (isProcessingCall.value) {
    console.log('[Call] 正在处理中，跳过录音')
    return
  }
  // 防止 TTS 播放时开始录音（避免录到 TTS 声音）
  if (ttsPlayer.isPlaying.value) {
    console.log('[Call] TTS 正在播放，跳过录音')
    return
  }

  try {
    console.log('[Call] 开始录音...')
    await callRecorder.startRecording()
  } catch (error) {
    console.error('[Call] 开始录音失败:', error)
  }
}

// 处理通话录音停止（识别并发送，带TTS）
async function handleCallRecordingStop() {
  // 防止并发
  if (isProcessingCall.value) {
    console.log('[Call] 已在处理中，跳过')
    return
  }

  isProcessingCall.value = true
  console.log('[Call] 开始处理录音...')

  try {
    const audioBlob = await callRecorder.stopRecording()
    const result = await transcribe(audioBlob)

    if (result.success && result.text) {
      console.log('[Call] ASR 识别结果:', result.text)

      // 通话模式：流式 TTS
      const onSentence = settings.ttsEnabled
        ? (sentence: string) => {
            // 检查是否已取消（用户打断或挂断）
            if (!isInCall.value) return
            console.log('[Call] 流式 TTS 句子:', sentence)
            ttsPlayer.speak(sentence)
          }
        : undefined

      await chat.send(result.text, onSentence)

      // chat.send 完成后，检查是否需要启动录音
      // 条件：TTS 没有启用，或 TTS 没有在播放/待播放
      if (isInCall.value) {
        if (!settings.ttsEnabled) {
          // TTS 未启用，直接继续录音
          console.log('[Call] TTS 未启用，继续录音')
          startCallRecording()
        } else if (!ttsPlayer.isPlaying.value && !ttsPlayer.isPending.value) {
          // TTS 启用但没有内容在播放，可能是内容被过滤了，直接继续录音
          console.log('[Call] TTS 无待播放内容，继续录音')
          startCallRecording()
        }
        // 如果 TTS 正在播放/待播放，会在 onPlayEnd 回调中继续录音
      }
    } else if (isInCall.value) {
      // 识别失败或无内容，继续录音
      console.log('[Call] ASR 无结果，继续录音')
      startCallRecording()
    }
  } catch (error) {
    console.error('[Call] 处理录音错误:', error)
    if (isInCall.value) {
      startCallRecording()
    }
  } finally {
    isProcessingCall.value = false
  }
}

// 键盘事件
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// 清空对话
function clearChat() {
  chat.clear()
}
</script>

<template>
  <!-- 移动端：全屏布局 / 桌面端：居中卡片 -->
  <div class="fixed inset-0 md:relative md:inset-auto md:min-h-screen md:flex md:items-center md:justify-center md:p-4" :style="backgroundStyle">
    <!-- 装饰性元素（仅桌面端） -->
    <div class="hidden md:block fixed inset-0 pointer-events-none overflow-hidden" :style="backgroundStyle">
      <div class="star" style="top: 15%; left: 15%; animation-delay: 0s;"></div>
      <div class="star" style="top: 25%; right: 20%; animation-delay: 1s;"></div>
      <div class="star" style="top: 70%; left: 10%; animation-delay: 2s;"></div>
      <div class="star" style="top: 80%; right: 15%; animation-delay: 0.5s;"></div>
      <div class="heart" style="top: 30%; left: 8%;"></div>
      <div class="heart" style="top: 65%; right: 12%;"></div>
    </div>

    <!-- 主容器 -->
    <div class="h-full w-full md:h-[85vh] md:max-h-[800px] md:w-auto bg-white md:rounded-3xl md:shadow-2xl flex relative z-10 overflow-hidden">
      <!-- 聊天区域 -->
      <div
        class="flex-1 flex flex-col w-full md:w-[420px] md:flex-none"
        :class="{ 'hidden md:flex': showSettings }"
      >
        <!-- 头部 -->
        <header class="flex-shrink-0 bg-gradient-to-r from-pink-400 via-pink-500 to-orange-400 px-4 h-14 flex items-center justify-between safe-top">
          <div class="flex items-center gap-2">
            <span class="text-white text-lg font-semibold">{{ settings.assistantName || '小智' }}</span>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="clearChat"
              class="px-3 py-1.5 bg-white/20 hover:bg-white/30 text-white text-sm rounded-lg transition-colors"
            >
              清空
            </button>
            <button
              @click="showSettings = !showSettings"
              :class="[
                'p-1.5 rounded-lg transition-colors',
                showSettings ? 'bg-white/40' : 'bg-white/20 hover:bg-white/30'
              ]"
              title="设置/故事"
            >
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </header>

      <!-- 主内容区 - 根据模式显示不同内容 -->
      <div class="flex-1 min-h-0 flex flex-col">
        <!-- 通话中：显示角色头像 -->
        <template v-if="isInCall">
          <div class="flex-1 flex flex-col items-center justify-center pb-16 bg-gradient-to-b from-white/50 to-white">
            <!-- 角色头像区域 -->
            <div class="relative">
              <!-- 说话时的声波动效 -->
              <div
                v-if="ttsPlayer.isPlaying.value"
                class="absolute inset-0 flex items-center justify-center"
              >
                <div class="absolute w-48 h-48 rounded-full bg-pink-200/30 animate-pulse"></div>
                <div class="absolute w-40 h-40 rounded-full bg-pink-300/40 animate-ping-slow"></div>
                <div class="absolute w-32 h-32 rounded-full bg-pink-400/30 animate-ping-slow animation-delay-200"></div>
              </div>

              <!-- 录音时的波纹 -->
              <div
                v-if="callRecorder.isRecording.value"
                class="absolute inset-0 flex items-center justify-center"
              >
                <div class="absolute w-44 h-44 rounded-full border-4 border-green-300/50 animate-ping-slow"></div>
                <div class="absolute w-36 h-36 rounded-full border-4 border-green-400/60 animate-ping-slow animation-delay-200"></div>
              </div>

              <!-- 头像 -->
              <div
                class="relative w-36 h-36 md:w-44 md:h-44 rounded-full bg-gradient-to-br from-pink-50 to-orange-50 flex items-center justify-center cursor-pointer transition-all duration-300 overflow-hidden border-4 border-white shadow-xl scale-105"
                :class="{ 'animate-bounce-slow': ttsPlayer.isPlaying.value }"
                @click="toggleCall"
              >
                <img
                  :src="currentAvatar.file"
                  :alt="currentAvatar.name"
                  class="w-full h-full object-cover"
                />
              </div>

              <!-- 通话中红点 -->
              <div class="absolute top-0 right-0 w-5 h-5 bg-red-500 rounded-full border-2 border-white animate-pulse"></div>
            </div>

            <!-- 状态文字 -->
            <p class="mt-6 text-lg font-medium text-pink-600">
              {{ statusText }}
            </p>

            <!-- 状态指示 -->
            <div class="flex gap-2 mt-3">
              <span class="w-2.5 h-2.5 rounded-full bg-green-400" title="已连接"></span>
              <span
                class="w-2.5 h-2.5 rounded-full transition-colors"
                :class="callRecorder.isRecording.value ? 'bg-pink-400 animate-pulse' : 'bg-gray-300'"
                title="录音状态"
              ></span>
              <span
                class="w-2.5 h-2.5 rounded-full transition-colors"
                :class="ttsPlayer.isPlaying.value ? 'bg-orange-400 animate-pulse' : 'bg-gray-300'"
                title="播放状态"
              ></span>
              <span
                class="w-2.5 h-2.5 rounded-full transition-colors"
                :class="(funasrVAD.isActive.value || sileroVAD.isActive.value) ? 'bg-blue-400 animate-pulse' : 'bg-gray-300'"
                title="VAD检测"
              ></span>
            </div>

            <!-- 音量显示（通话中） -->
            <div class="mt-4 text-xs text-gray-400">
              音量: {{ callRecorder.audioLevel.value }}
            </div>
          </div>
        </template>

        <!-- 非通话时：显示聊天消息或欢迎界面 -->
        <template v-else>
          <!-- 有消息时显示聊天区域 -->
          <ChatArea
            v-if="chat.messages.value.length > 0 || chat.isLoading.value"
            :messages="chat.messages.value"
            :streaming-content="chat.streamingContent.value"
            :is-loading="chat.isLoading.value"
            :current-skill="chat.currentSkill.value"
            :tool-calls="chat.toolCalls.value"
            class="flex-1 min-h-0"
          />
          <!-- 无消息时显示欢迎界面 -->
          <div v-else class="flex-1 flex flex-col items-center justify-center text-center px-8">
            <div class="text-6xl mb-4">{{ currentAvatar.icon }}</div>
            <h2 class="text-xl font-semibold text-gray-700 mb-2">你好，我是{{ settings.assistantName || '小智' }}</h2>
            <p class="text-gray-500 text-sm mb-6">点击电话按钮开始语音对话，或直接输入文字</p>
          </div>
        </template>
      </div>

      <!-- 底部输入区 -->
      <footer class="flex-shrink-0 px-4 py-3 md:pb-4 bg-white safe-bottom">
        <!-- 提示文字 -->
        <div v-if="isInCall" class="text-center text-xs text-gray-400 mb-3">
          说完自动识别 | 点击头像挂断
        </div>

        <!-- 输入框（按钮在内部） -->
        <div class="relative flex items-center bg-gray-50 border border-gray-200 rounded-full px-4 py-2 focus-within:ring-2 focus-within:ring-pink-400 focus-within:border-transparent">
          <input
            v-model="inputText"
            @keydown="handleKeydown"
            :disabled="chat.isLoading.value"
            placeholder="输入消息..."
            class="flex-1 bg-transparent border-none outline-none text-base text-gray-700 placeholder-gray-400 disabled:text-gray-400"
            inputmode="text"
            autocomplete="off"
          />

          <!-- 按钮组 -->
          <div class="flex items-center gap-1 ml-2">
            <!-- 语音转文字按钮 -->
            <button
              @click="toggleTranscribe"
              :disabled="isTranscribing"
              :class="[
                'w-9 h-9 rounded-full flex items-center justify-center transition-colors',
                transcribeRecorder.isRecording.value
                  ? 'bg-red-500 text-white animate-pulse'
                  : 'bg-pink-500 hover:bg-pink-600 text-white'
              ]"
              :title="transcribeRecorder.isRecording.value ? '停止录音' : '语音输入'"
            >
              <svg v-if="isTranscribing" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </button>

            <!-- 电话按钮 -->
            <button
              @click="toggleCall"
              :class="[
                'w-9 h-9 rounded-full flex items-center justify-center transition-colors',
                isInCall
                  ? 'bg-red-500 hover:bg-red-600 text-white'
                  : 'bg-gray-200 hover:bg-gray-300 text-gray-500'
              ]"
              :title="isInCall ? '挂断电话' : '开始通话'"
            >
              <svg v-if="isInCall" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3a2 2 0 00-2 2v1c0 8.284 6.716 15 15 15h1a2 2 0 002-2v-3.28a1 1 0 00-.684-.948l-4.493-1.498a1 1 0 00-1.21.502l-1.13 2.257a11.042 11.042 0 01-5.516-5.517l2.257-1.128a1 1 0 00.502-1.21L9.228 3.683A1 1 0 008.279 3H5z" />
              </svg>
              <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
              </svg>
            </button>

            <!-- 发送按钮 -->
            <button
              @click="handleSend"
              :disabled="!canSend"
              :class="[
                'w-9 h-9 rounded-full flex items-center justify-center transition-colors',
                canSend
                  ? 'bg-orange-400 hover:bg-orange-500 text-white'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              ]"
              title="发送"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </div>
      </footer>
      </div>

      <!-- 右侧：设置/故事面板 -->
      <RightPanel
        :show="showSettings"
        @close="showSettings = false"
      />
    </div>
  </div>
</template>

<style scoped>
/* 动画基础 */

@keyframes ping-slow {
  0% {
    transform: scale(1);
    opacity: 0.8;
  }
  100% {
    transform: scale(1.8);
    opacity: 0;
  }
}

.animate-ping-slow {
  animation: ping-slow 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
}

.animation-delay-200 {
  animation-delay: 0.2s;
}

/* 说话时的轻微弹跳动画 */
@keyframes bounce-slow {
  0%, 100% {
    transform: translateY(0) scale(1.05);
  }
  50% {
    transform: translateY(-8px) scale(1.08);
  }
}

.animate-bounce-slow {
  animation: bounce-slow 0.6s ease-in-out infinite;
}

/* 星星装饰 */
.star {
  position: absolute;
  width: 20px;
  height: 20px;
  background: #FFD700;
  clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
  animation: twinkle 2s ease-in-out infinite;
  opacity: 0.8;
}

@keyframes twinkle {
  0%, 100% {
    transform: scale(1) rotate(0deg);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.2) rotate(15deg);
    opacity: 1;
  }
}

/* 爱心装饰 */
.heart {
  position: absolute;
  width: 20px;
  height: 20px;
  background: #FF69B4;
  transform: rotate(-45deg);
  animation: heartbeat 1.5s ease-in-out infinite;
  opacity: 0.7;
}

.heart::before,
.heart::after {
  content: '';
  position: absolute;
  width: 20px;
  height: 20px;
  background: #FF69B4;
  border-radius: 50%;
}

.heart::before {
  top: -10px;
  left: 0;
}

.heart::after {
  top: 0;
  left: 10px;
}

@keyframes heartbeat {
  0%, 100% {
    transform: rotate(-45deg) scale(1);
  }
  50% {
    transform: rotate(-45deg) scale(1.1);
  }
}

/* 圆点装饰 */
.dot {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  opacity: 0.6;
  animation: bounce-dot 3s ease-in-out infinite;
}

@keyframes bounce-dot {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}
</style>
