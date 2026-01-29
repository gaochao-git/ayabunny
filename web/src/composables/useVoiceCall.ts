/**
 * 语音通话状态机
 *
 * 统一管理通话状态，替代 ChatView.vue 中分散的状态逻辑
 *
 * 状态流转：
 * IDLE → LISTENING → RECORDING → PROCESSING → SPEAKING → LISTENING → ...
 *
 * 支持：
 * - VAD 启用/禁用
 * - TTS 启用/禁用
 * - 用户打断
 * - 视频通话（捕获帧）
 */

import { ref, computed } from 'vue'

// 状态枚举
export enum CallState {
  IDLE = 'idle',           // 空闲（非通话）
  LISTENING = 'listening', // VAD 监听中（等待用户说话）
  RECORDING = 'recording', // 录音中
  PROCESSING = 'processing', // ASR 识别 + LLM 思考中
  SPEAKING = 'speaking',   // TTS 播放中
}

// 事件类型
export type CallEvent =
  | { type: 'START_CALL' }
  | { type: 'END_CALL' }
  | { type: 'VOICE_DETECTED' }
  | { type: 'SILENCE_DETECTED' }
  | { type: 'ASR_COMPLETE'; text: string }
  | { type: 'ASR_EMPTY' }
  | { type: 'LLM_COMPLETE' }
  | { type: 'TTS_STARTED' }
  | { type: 'TTS_ENDED' }
  | { type: 'INTERRUPTED' }

// VAD 接口
export interface VADService {
  start: () => Promise<void>
  stop: () => void
  isActive: { value: boolean }
}

// 录音器接口
export interface RecorderService {
  startRecording: () => Promise<void>
  stopRecording: () => Promise<Blob>
  isRecording: { value: boolean }
}

// TTS 接口
export interface TTSService {
  speak: (text: string) => void
  stop: () => void
  unlock: () => Promise<void>
  isPlaying: { value: boolean }
  isPending: { value: boolean }
}

// Chat 接口
export interface ChatService {
  send: (text: string, onSentence?: (s: string) => void, image?: string) => Promise<string>
  abort: () => void
  isLoading: { value: boolean }
}

export interface VoiceCallOptions {
  // 依赖的服务
  vad: VADService
  recorder: RecorderService
  tts: TTSService
  chat: ChatService

  // ASR 转写函数
  transcribe: (blob: Blob) => Promise<{ success: boolean; text: string }>

  // 配置（返回函数，支持响应式）
  vadEnabled: () => boolean
  ttsEnabled: () => boolean

  // 可选：视频帧捕获
  captureFrame?: () => string | null

  // 可选：音频解锁（移动端需要）
  unlockAudio?: () => Promise<void>
}

export function useVoiceCall(options: VoiceCallOptions) {
  const {
    vad,
    recorder,
    tts,
    chat,
    transcribe,
    vadEnabled,
    ttsEnabled,
    captureFrame,
    unlockAudio,
  } = options

  // 状态
  const state = ref<CallState>(CallState.IDLE)
  const error = ref<string | null>(null)
  let llmCompleted = false  // 标记 LLM 是否已完成（用于 SPEAKING 状态判断）

  // 计算属性
  const isInCall = computed(() => state.value !== CallState.IDLE)
  const isListening = computed(() => state.value === CallState.LISTENING)
  const isRecording = computed(() => state.value === CallState.RECORDING)
  const isProcessing = computed(() => state.value === CallState.PROCESSING)
  const isSpeaking = computed(() => state.value === CallState.SPEAKING)

  // 状态文字
  const statusText = computed(() => {
    switch (state.value) {
      case CallState.IDLE:
        return ''
      case CallState.LISTENING:
        return '等待说话...'
      case CallState.RECORDING:
        return '正在听...'
      case CallState.PROCESSING:
        return '思考中...'
      case CallState.SPEAKING:
        return '正在说...'
      default:
        return ''
    }
  })

  // 防止并发处理
  let isTransitioning = false

  /**
   * 状态机核心：处理事件
   */
  async function dispatch(event: CallEvent): Promise<void> {
    // 防止并发
    if (isTransitioning && event.type !== 'END_CALL') {
      console.log(`[VoiceCall] 忽略事件 ${event.type}（正在转换中）`)
      return
    }

    const prevState = state.value
    console.log(`[VoiceCall] ${prevState} + ${event.type}`)

    try {
      isTransitioning = true

      switch (state.value) {
        case CallState.IDLE:
          if (event.type === 'START_CALL') {
            await enterListening()
          }
          break

        case CallState.LISTENING:
          if (event.type === 'VOICE_DETECTED') {
            await enterRecording()
          } else if (event.type === 'END_CALL') {
            await enterIdle()
          }
          break

        case CallState.RECORDING:
          if (event.type === 'SILENCE_DETECTED') {
            await enterProcessing()
          } else if (event.type === 'END_CALL') {
            await enterIdle()
          }
          break

        case CallState.PROCESSING:
          if (event.type === 'TTS_STARTED') {
            state.value = CallState.SPEAKING
          } else if (event.type === 'LLM_COMPLETE') {
            llmCompleted = true
            // LLM 完成但没有 TTS，回到监听
            if (!tts.isPlaying.value && !tts.isPending.value) {
              await enterListening()
            }
          } else if (event.type === 'END_CALL') {
            await enterIdle()
          }
          break

        case CallState.SPEAKING:
          if (event.type === 'LLM_COMPLETE') {
            // 记录 LLM 已完成，等 TTS 结束再回到 LISTENING
            llmCompleted = true
          } else if (event.type === 'TTS_ENDED') {
            // 只有 LLM 完成后才回到监听
            if (llmCompleted) {
              await enterListening()
            }
            // 否则继续等待 LLM 输出更多内容
          } else if (event.type === 'INTERRUPTED') {
            tts.stop()
            chat.abort()
            // 延迟一点再录音，避免录到 TTS 尾音
            await sleep(200)
            await enterRecording()
          } else if (event.type === 'END_CALL') {
            await enterIdle()
          }
          break
      }

      console.log(`[VoiceCall] → ${state.value}`)
    } finally {
      isTransitioning = false
    }
  }

  // ============ 状态进入动作 ============

  async function enterIdle(): Promise<void> {
    state.value = CallState.IDLE
    error.value = null

    // 清理所有资源
    vad.stop()
    tts.stop()
    chat.abort()

    if (recorder.isRecording.value) {
      try {
        await recorder.stopRecording()
      } catch {
        // 忽略
      }
    }
  }

  async function enterListening(): Promise<void> {
    state.value = CallState.LISTENING
    error.value = null

    if (vadEnabled()) {
      try {
        await vad.start()
      } catch (e) {
        console.error('[VoiceCall] VAD 启动失败:', e)
        error.value = 'VAD 启动失败'
        // VAD 失败时直接进入录音模式
        await enterRecording()
      }
    } else {
      // VAD 未启用，直接进入录音
      await enterRecording()
    }
  }

  async function enterRecording(): Promise<void> {
    // 防止 TTS 播放时录音
    if (tts.isPlaying.value) {
      console.log('[VoiceCall] TTS 正在播放，跳过录音')
      return
    }

    state.value = CallState.RECORDING
    error.value = null

    try {
      await recorder.startRecording()
    } catch (e) {
      console.error('[VoiceCall] 录音启动失败:', e)
      error.value = '录音启动失败'
      await enterListening()
    }
  }

  async function enterProcessing(): Promise<void> {
    state.value = CallState.PROCESSING
    error.value = null
    llmCompleted = false  // 重置 LLM 完成标记

    try {
      // 1. 停止录音获取音频
      const audioBlob = await recorder.stopRecording()

      // 2. ASR 转写
      const result = await transcribe(audioBlob)

      if (!result.success || !result.text) {
        console.log('[VoiceCall] ASR 无结果，继续监听')
        if (state.value === CallState.PROCESSING) {
          await enterListening()
        }
        return
      }

      console.log('[VoiceCall] ASR 结果:', result.text)

      // 3. 捕获视频帧（如果有）
      const frameImage = captureFrame?.()
      const image = frameImage ? `data:image/jpeg;base64,${frameImage}` : undefined

      // 4. 发送给 LLM（流式 TTS）
      const onSentence = ttsEnabled()
        ? (sentence: string) => {
            // 检查是否仍在通话中
            if (state.value === CallState.IDLE) return
            tts.speak(sentence)
            // 首次播放时切换到 SPEAKING 状态
            if (state.value === CallState.PROCESSING) {
              dispatch({ type: 'TTS_STARTED' })
            }
          }
        : undefined

      await chat.send(result.text, onSentence, image)

      // 5. LLM 完成
      if (state.value !== CallState.IDLE) {
        dispatch({ type: 'LLM_COMPLETE' })
      }

    } catch (e) {
      console.error('[VoiceCall] 处理失败:', e)
      error.value = String(e)
      if (state.value === CallState.PROCESSING) {
        await enterListening()
      }
    }
  }

  // ============ 公开 API ============

  /**
   * 开始通话
   */
  async function startCall(): Promise<void> {
    // 解锁音频（移动端需要）
    await tts.unlock()
    await unlockAudio?.()

    dispatch({ type: 'START_CALL' })
  }

  /**
   * 结束通话
   */
  function endCall(): void {
    dispatch({ type: 'END_CALL' })
  }

  /**
   * VAD 检测到语音开始
   */
  function onVoiceDetected(): void {
    if (state.value === CallState.SPEAKING) {
      // 打断 TTS
      dispatch({ type: 'INTERRUPTED' })
    } else if (state.value === CallState.LISTENING) {
      dispatch({ type: 'VOICE_DETECTED' })
    }
  }

  /**
   * 静音检测触发
   */
  function onSilenceDetected(): void {
    if (state.value === CallState.RECORDING) {
      dispatch({ type: 'SILENCE_DETECTED' })
    }
  }

  /**
   * TTS 播放结束
   */
  function onTtsEnded(): void {
    if (state.value === CallState.SPEAKING) {
      dispatch({ type: 'TTS_ENDED' })
    }
  }

  /**
   * 用户打断（手动触发）
   */
  function interrupt(): void {
    if (state.value === CallState.SPEAKING) {
      dispatch({ type: 'INTERRUPTED' })
    }
  }

  return {
    // 状态
    state,
    error,
    statusText,

    // 计算属性
    isInCall,
    isListening,
    isRecording,
    isProcessing,
    isSpeaking,

    // 公开 API
    startCall,
    endCall,
    interrupt,

    // 事件处理（供外部回调调用）
    onVoiceDetected,
    onSilenceDetected,
    onTtsEnded,
  }
}

// 工具函数
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}
