/**
 * Silero VAD Composable
 * 使用 Silero VAD 模型进行语音活动检测
 * 比简单音量检测更准确，能区分人声和噪音
 */

import { ref, onUnmounted } from 'vue'
import { MicVAD } from '@ricky0123/vad-web'

export interface SileroVADOptions {
  /** 语音开始回调 */
  onSpeechStart?: () => void
  /** 语音结束回调，返回音频数据 */
  onSpeechEnd?: (audio: Float32Array) => void
  /** 唤醒词列表（支持数组或返回数组的函数） */
  wakeWords?: string[] | (() => string[])
  /** ASR 识别函数（用于唤醒词检测） */
  transcribeFn?: (blob: Blob) => Promise<string>
  /** 唤醒词检测到时回调 */
  onWakeWordDetected?: () => void
  /** 启动后忽略检测的时间 (ms)，防止检测到 TTS 声音 */
  ignoreTime?: number | (() => number)
}

export function useSileroVAD(options: SileroVADOptions = {}) {
  const { onSpeechStart, onSpeechEnd, wakeWords, transcribeFn, onWakeWordDetected, ignoreTime } = options

  const isActive = ref(false)
  const isSpeaking = ref(false)
  const isLoading = ref(false)
  const isCheckingWakeWord = ref(false)

  let vadInstance: MicVAD | null = null
  let ignoreUntil = 0  // 忽略检测直到此时间戳

  // 获取 ignoreTime 值（支持函数或固定值）
  function getIgnoreTime(): number {
    if (typeof ignoreTime === 'function') return ignoreTime()
    return ignoreTime ?? 800
  }

  // 获取唤醒词列表（支持函数或固定值）
  function getWakeWords(): string[] {
    if (typeof wakeWords === 'function') return wakeWords()
    return wakeWords ?? []
  }

  /**
   * 将 Float32Array 转换为 WAV Blob
   */
  function float32ToWavBlob(audioData: Float32Array, sampleRate: number = 16000): Blob {
    const numChannels = 1
    const bitsPerSample = 16
    const bytesPerSample = bitsPerSample / 8
    const blockAlign = numChannels * bytesPerSample
    const byteRate = sampleRate * blockAlign
    const dataSize = audioData.length * bytesPerSample
    const buffer = new ArrayBuffer(44 + dataSize)
    const view = new DataView(buffer)

    // WAV header
    const writeString = (offset: number, str: string) => {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i))
      }
    }

    writeString(0, 'RIFF')
    view.setUint32(4, 36 + dataSize, true)
    writeString(8, 'WAVE')
    writeString(12, 'fmt ')
    view.setUint32(16, 16, true)
    view.setUint16(20, 1, true)
    view.setUint16(22, numChannels, true)
    view.setUint32(24, sampleRate, true)
    view.setUint32(28, byteRate, true)
    view.setUint16(32, blockAlign, true)
    view.setUint16(34, bitsPerSample, true)
    writeString(36, 'data')
    view.setUint32(40, dataSize, true)

    // Audio data
    let offset = 44
    for (let i = 0; i < audioData.length; i++) {
      const sample = Math.max(-1, Math.min(1, audioData[i]))
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true)
      offset += 2
    }

    return new Blob([buffer], { type: 'audio/wav' })
  }

  /**
   * 检测唤醒词
   */
  async function checkWakeWord(audioData: Float32Array): Promise<boolean> {
    const words = getWakeWords()
    if (!words.length || !transcribeFn) return true // 没有唤醒词要求，直接通过

    isCheckingWakeWord.value = true
    try {
      const wavBlob = float32ToWavBlob(audioData)
      console.log('[SileroVAD] 检测唤醒词，音频大小:', wavBlob.size)

      const text = await transcribeFn(wavBlob)
      console.log('[SileroVAD] ASR 结果:', text)

      const detected = words.some(word => text?.includes(word))
      if (detected) {
        console.log('[SileroVAD] 检测到唤醒词')
        onWakeWordDetected?.()
      }
      return detected
    } catch (error) {
      console.error('[SileroVAD] 唤醒词检测失败:', error)
      return false
    } finally {
      isCheckingWakeWord.value = false
    }
  }

  /**
   * 启动 VAD
   */
  async function start(): Promise<void> {
    if (isActive.value) return

    isLoading.value = true
    console.log('[SileroVAD] 正在加载模型...')

    // 设置忽略时间
    ignoreUntil = Date.now() + getIgnoreTime()

    try {
      vadInstance = await MicVAD.new({
        onSpeechStart: () => {
          // 检查是否在忽略期内
          if (Date.now() < ignoreUntil) {
            console.log('[SileroVAD] 忽略期内，跳过语音检测')
            return
          }

          console.log('[SileroVAD] 检测到语音开始')
          isSpeaking.value = true
          // 如果没有唤醒词要求，直接触发回调
          if (!getWakeWords().length) {
            onSpeechStart?.()
          }
        },
        onSpeechEnd: async (audio: Float32Array) => {
          // 检查是否在忽略期内
          if (Date.now() < ignoreUntil) {
            console.log('[SileroVAD] 忽略期内，跳过语音结束处理')
            return
          }

          console.log('[SileroVAD] 检测到语音结束，样本数:', audio.length)
          isSpeaking.value = false

          // 如果有唤醒词要求，先检测
          if (getWakeWords().length && transcribeFn) {
            const hasWakeWord = await checkWakeWord(audio)
            if (hasWakeWord) {
              onSpeechStart?.() // 唤醒词匹配，触发开始
            }
          }

          onSpeechEnd?.(audio)
        },
        positiveSpeechThreshold: 0.8,  // 语音检测阈值
        negativeSpeechThreshold: 0.3,  // 非语音检测阈值
        minSpeechFrames: 3,            // 最小语音帧数
        preSpeechPadFrames: 10,        // 语音前填充帧数
        redemptionFrames: 8,           // 语音结束前的缓冲帧数
      })

      vadInstance.start()
      isActive.value = true
      console.log('[SileroVAD] 已启动')
    } catch (error) {
      console.error('[SileroVAD] 启动失败:', error)
      throw error
    } finally {
      isLoading.value = false
    }
  }

  /**
   * 停止 VAD
   */
  function stop(): void {
    if (vadInstance) {
      vadInstance.pause()
      vadInstance.destroy()
      vadInstance = null
    }
    isActive.value = false
    isSpeaking.value = false
    isCheckingWakeWord.value = false
    console.log('[SileroVAD] 已停止')
  }

  /**
   * 暂停 VAD
   */
  function pause(): void {
    if (vadInstance) {
      vadInstance.pause()
      console.log('[SileroVAD] 已暂停')
    }
  }

  /**
   * 恢复 VAD
   */
  function resume(): void {
    if (vadInstance) {
      vadInstance.start()
      console.log('[SileroVAD] 已恢复')
    }
  }

  onUnmounted(stop)

  return {
    isActive,
    isSpeaking,
    isLoading,
    isCheckingWakeWord,
    start,
    stop,
    pause,
    resume,
  }
}
