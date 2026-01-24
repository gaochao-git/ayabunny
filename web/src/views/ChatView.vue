<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useChat } from '@/composables/useChat'
import { useAudioRecorder } from '@/composables/useAudioRecorder'
import { useTTSPlayer } from '@/composables/useTTSPlayer'
import { useVAD } from '@/composables/useVAD'
import { useWebRTCVAD } from '@/composables/useWebRTCVAD'
import { useSileroVAD } from '@/composables/useSileroVAD'
import { useFunASRVAD } from '@/composables/useFunASRVAD'
import { useSettingsStore } from '@/stores/settings'
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

// TTS 播放器
ttsPlayer = useTTSPlayer({
  gain: () => settings.ttsGain,
  voice: () => settings.ttsVoice,
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
// 唤醒词支持同音字：小智、小志、小知、乔治等
const wakeWords = ['小智', '小志', '小知', '小之', '乔治']

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
  wakeWords: wakeWords,
  wakeWordTimeout: 1500,
  transcribeFn: transcribeForWakeWord,
  onWakeWordDetected: () => {
    console.log('[SimpleVAD] 唤醒词"小智"检测到！')
  },
  onSpeechStart: handleVADSpeechStart,
})

// WebRTC VAD（基于频谱分析）
const webrtcVAD = useWebRTCVAD({
  ignoreTime: () => settings.vadIgnoreTime,
  onSpeechStart: handleVADSpeechStart,
})

// Silero VAD（基于前端 AI 模型）
const sileroVAD = useSileroVAD({
  wakeWords: wakeWords,
  transcribeFn: transcribeForWakeWord,
  ignoreTime: () => settings.vadIgnoreTime,
  onWakeWordDetected: () => {
    console.log('[SileroVAD] 唤醒词"小智"检测到！')
  },
  onSpeechStart: handleVADSpeechStart,
})

// FunASR VAD（基于服务端 AI 模型）
const funasrVAD = useFunASRVAD({
  wsUrl: 'ws://127.0.0.1:10096',  // FunASR 流式服务 WebSocket 地址
  ignoreTime: () => settings.vadIgnoreTime,
  onSpeechStart: handleVADSpeechStart,
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

// 状态文字
const statusText = computed(() => {
  if (isInCall.value) {
    if (sileroVAD.isLoading.value) return '加载VAD模型...'
    if (callRecorder.isRecording.value) return '正在听...'
    if (ttsPlayer.isPlaying.value || ttsPlayer.isPending.value) return '正在说...'
    if (chat.isLoading.value) return '思考中...'
    if (isProcessingCall.value) return '处理中...'
    return '等待说话...'
  }
  return '点击开始对话'
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

      // 如果不播放 TTS，直接继续录音
      if (!settings.ttsEnabled && isInCall.value) {
        startCallRecording()
      }
      // 如果播放 TTS，会在 onPlayEnd 回调中继续录音
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
  <div class="min-h-screen cute-background flex items-center justify-center p-0 md:p-4 relative overflow-hidden">
    <!-- 装饰性元素（手机端隐藏） -->
    <div class="hidden md:block absolute inset-0 pointer-events-none overflow-hidden">
      <!-- 星星 -->
      <div class="star" style="top: 15%; left: 15%; animation-delay: 0s;"></div>
      <div class="star" style="top: 25%; right: 20%; animation-delay: 1s;"></div>
      <div class="star" style="top: 70%; left: 10%; animation-delay: 2s;"></div>
      <div class="star" style="top: 80%; right: 15%; animation-delay: 0.5s;"></div>
      <div class="star" style="top: 45%; left: 8%; animation-delay: 1.5s;"></div>
      <div class="star" style="top: 60%; right: 8%; animation-delay: 2.5s;"></div>
      <!-- 爱心 -->
      <div class="heart" style="top: 30%; left: 8%;"></div>
      <div class="heart" style="top: 65%; right: 12%;"></div>
      <!-- 圆点 -->
      <div class="dot" style="top: 40%; left: 5%; background: #FFB6C1;"></div>
      <div class="dot" style="top: 50%; right: 6%; background: #87CEEB;"></div>
      <div class="dot" style="top: 85%; left: 20%; background: #98FB98;"></div>
    </div>

    <!-- 主卡片容器 -->
    <div
      class="bg-white md:rounded-3xl shadow-2xl flex relative z-10 overflow-hidden transition-all duration-300 w-full md:w-auto h-screen md:h-[85vh] md:max-h-[800px]"
    >
      <!-- 左侧：聊天区域 -->
      <div
        class="flex flex-col flex-shrink-0 w-full md:w-[420px]"
        :class="{ 'hidden md:flex': showSettings }"
      >
        <!-- 头部 -->
        <header class="bg-gradient-to-r from-pink-400 via-pink-500 to-orange-400 px-5 h-16 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-white text-lg font-semibold">小智</span>
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

      <!-- 聊天区域 -->
      <ChatArea
        :messages="chat.messages.value"
        :streaming-content="chat.streamingContent.value"
        :is-loading="chat.isLoading.value"
        class="flex-1 min-h-0"
      />

      <!-- 头像区域 -->
      <div class="py-6 flex flex-col items-center bg-gradient-to-b from-pink-50 to-white">
        <!-- 同心圆波纹 + 头像 -->
        <div class="relative">
          <!-- 外圈波纹（通话中显示） -->
          <div
            v-if="isInCall"
            class="absolute inset-0 rounded-full border-2 border-pink-200"
            :class="{ 'animate-ping-slow': callRecorder.isRecording.value || ttsPlayer.isPlaying.value }"
            :style="{ transform: 'scale(1.6)', opacity: 0.3 }"
          ></div>
          <div
            v-if="isInCall"
            class="absolute inset-0 rounded-full border-2 border-pink-300"
            :class="{ 'animate-ping-slow animation-delay-200': callRecorder.isRecording.value || ttsPlayer.isPlaying.value }"
            :style="{ transform: 'scale(1.3)', opacity: 0.5 }"
          ></div>

          <!-- 头像容器 -->
          <div
            class="w-28 h-28 rounded-full bg-gradient-to-br from-pink-50 to-orange-50 flex items-center justify-center cursor-pointer hover:scale-105 transition-transform overflow-hidden border-4 border-white shadow-lg"
            @click="toggleCall"
          >
            <img
              src="/rabbit.svg"
              alt="小智"
              class="w-full h-full object-cover"
            />
          </div>

          <!-- 通话中红点 -->
          <div
            v-if="isInCall"
            class="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full border-2 border-white animate-pulse"
          ></div>
        </div>

        <!-- 状态文字 -->
        <p class="mt-4 text-pink-500 text-sm font-medium">{{ statusText }}</p>

        <!-- 状态指示点 -->
        <div class="flex gap-1.5 mt-2">
          <span
            class="w-2 h-2 rounded-full transition-colors"
            :class="isInCall ? 'bg-green-400' : 'bg-gray-300'"
          ></span>
          <span
            class="w-2 h-2 rounded-full transition-colors"
            :class="callRecorder.isRecording.value ? 'bg-pink-400 animate-pulse' : 'bg-gray-300'"
          ></span>
          <span
            class="w-2 h-2 rounded-full transition-colors"
            :class="ttsPlayer.isPlaying.value ? 'bg-orange-400 animate-pulse' : 'bg-gray-300'"
          ></span>
        </div>
      </div>

      <!-- 底部输入区 -->
      <footer class="px-4 pb-4">
        <!-- 提示文字 -->
        <div class="text-center text-xs text-gray-400 mb-3">
          <span v-if="isInCall">
            音量: {{ callRecorder.audioLevel.value }} | 说完自动识别
          </span>
          <span v-else>点击头像开始语音对话</span>
        </div>

        <!-- 输入框（按钮在内部） -->
        <div class="relative flex items-center bg-gray-50 border border-gray-200 rounded-full px-4 py-2 focus-within:ring-2 focus-within:ring-pink-400 focus-within:border-transparent">
          <input
            v-model="inputText"
            @keydown="handleKeydown"
            :disabled="chat.isLoading.value"
            placeholder="输入消息..."
            class="flex-1 bg-transparent border-none outline-none text-sm text-gray-700 placeholder-gray-400 disabled:text-gray-400"
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
        :audio-level="isInCall ? callRecorder.audioLevel.value : transcribeRecorder.audioLevel.value"
        @close="showSettings = false"
      />
    </div>
  </div>
</template>

<style scoped>
/* 可爱的渐变背景 */
.cute-background {
  background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 50%, #ffeaa7 100%);
  position: relative;
}

/* 装饰性云朵 */
.cute-background::before {
  content: '';
  position: absolute;
  top: 10%;
  left: 5%;
  width: 120px;
  height: 60px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 60px;
  box-shadow:
    40px 20px 0 rgba(255, 255, 255, 0.5),
    -30px 10px 0 rgba(255, 255, 255, 0.4);
  animation: float 6s ease-in-out infinite;
}

.cute-background::after {
  content: '';
  position: absolute;
  top: 20%;
  right: 10%;
  width: 80px;
  height: 40px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 40px;
  box-shadow:
    25px 15px 0 rgba(255, 255, 255, 0.4),
    -20px 8px 0 rgba(255, 255, 255, 0.3);
  animation: float 8s ease-in-out infinite reverse;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0) translateX(0);
  }
  50% {
    transform: translateY(-15px) translateX(10px);
  }
}

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
