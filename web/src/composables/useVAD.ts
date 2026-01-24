/**
 * VAD (Voice Activity Detection) Composable
 * 用于检测用户语音打断 TTS 播放
 *
 * 与原项目逻辑一致：
 * - threshold: 打断阈值 (10-80)，音量超过此值才可能触发打断
 * - triggerCount: 触发次数 (2-10)，连续检测到多少次才真正打断
 * - ignoreTime: 忽略时间 (ms)，TTS 开始后忽略麦克风输入的时间
 */

import { ref, onUnmounted } from 'vue'

export interface VADOptions {
  threshold?: number | (() => number)      // 打断阈值 (0-255)
  triggerCount?: number | (() => number)   // 触发次数
  ignoreTime?: number | (() => number)     // 忽略时间 (ms)
  onSpeechStart?: () => void
  onSpeechEnd?: () => void
}

// 获取选项值（支持函数或直接值）
function getOptionValue<T>(option: T | (() => T) | undefined, defaultValue: T): T {
  if (option === undefined) return defaultValue
  if (typeof option === 'function') return (option as () => T)()
  return option
}

export function useVAD(options: VADOptions = {}) {
  const { onSpeechStart, onSpeechEnd } = options

  // 动态获取配置值
  const getThreshold = () => getOptionValue(options.threshold, 60)
  const getTriggerCount = () => getOptionValue(options.triggerCount, 5)
  const getIgnoreTime = () => getOptionValue(options.ignoreTime, 800)

  const isActive = ref(false)
  const isSpeaking = ref(false)
  const audioLevel = ref(0)

  let audioContext: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let mediaStream: MediaStream | null = null
  let animationFrame: number | null = null

  // 打断检测状态
  let startTime: number | null = null  // VAD 启动时间
  let consecutiveCount = 0              // 连续检测到超过阈值的次数

  /**
   * 启动 VAD
   */
  async function start(): Promise<void> {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })

      audioContext = new AudioContext()
      analyser = audioContext.createAnalyser()
      analyser.fftSize = 256

      const source = audioContext.createMediaStreamSource(mediaStream)
      source.connect(analyser)

      isActive.value = true
      startTime = Date.now()
      consecutiveCount = 0

      console.log('[VAD] Started, ignoring input for', getIgnoreTime(), 'ms')
      monitor()
    } catch (error) {
      console.error('Failed to start VAD:', error)
      throw error
    }
  }

  /**
   * 停止 VAD
   */
  function stop(): void {
    if (animationFrame) {
      cancelAnimationFrame(animationFrame)
      animationFrame = null
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop())
      mediaStream = null
    }

    if (audioContext) {
      audioContext.close()
      audioContext = null
    }

    analyser = null
    isActive.value = false
    isSpeaking.value = false
    audioLevel.value = 0
    startTime = null
    consecutiveCount = 0
  }

  /**
   * 监测音频活动
   */
  function monitor(): void {
    if (!analyser || !isActive.value) return

    const dataArray = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteFrequencyData(dataArray)

    // 计算平均音量（整数 0-255）
    const average = Math.round(dataArray.reduce((a, b) => a + b, 0) / dataArray.length)
    audioLevel.value = average

    const now = Date.now()
    const threshold = getThreshold()
    const triggerCount = getTriggerCount()
    const ignoreTime = getIgnoreTime()

    // 忽略时间内不检测
    if (startTime && now - startTime < ignoreTime) {
      animationFrame = requestAnimationFrame(monitor)
      return
    }

    // 语音活动检测
    if (average > threshold) {
      consecutiveCount++

      // 连续检测到足够次数才触发打断
      if (consecutiveCount >= triggerCount && !isSpeaking.value) {
        console.log(`[VAD] Speech detected! level=${average}, threshold=${threshold}, count=${consecutiveCount}`)
        isSpeaking.value = true
        onSpeechStart?.()
      }
    } else {
      // 音量低于阈值，重置计数
      if (consecutiveCount > 0) {
        consecutiveCount = 0
      }

      if (isSpeaking.value) {
        isSpeaking.value = false
        onSpeechEnd?.()
      }
    }

    animationFrame = requestAnimationFrame(monitor)
  }

  onUnmounted(stop)

  return {
    isActive,
    isSpeaking,
    audioLevel,
    start,
    stop,
  }
}
