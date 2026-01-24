/**
 * 麦克风录音 Composable
 *
 * 静音检测逻辑与原项目一致：
 * - 使用整数音量 (0-255)
 * - 音量 > 阈值 = 说话
 * - 音量 <= 阈值 且已说过话 = 静音
 * - 静音持续指定时间 = 自动停止
 */

import { ref, onUnmounted } from 'vue'

export interface AudioRecorderOptions {
  silenceThreshold?: number | (() => number)  // 静音阈值 (0-255)，默认 30
  silenceDuration?: number | (() => number)   // 静音持续时间 ms，默认 1500
  onSilenceDetected?: () => void
}

// 获取选项值（支持函数或直接值）
function getOptionValue<T>(option: T | (() => T) | undefined, defaultValue: T): T {
  if (option === undefined) return defaultValue
  if (typeof option === 'function') return (option as () => T)()
  return option
}

export function useAudioRecorder(options: AudioRecorderOptions = {}) {
  const { onSilenceDetected } = options

  // 动态获取配置值
  const getSilenceThreshold = () => getOptionValue(options.silenceThreshold, 30)
  const getSilenceDuration = () => getOptionValue(options.silenceDuration, 1500)

  const isRecording = ref(false)
  const audioLevel = ref(0)      // 整数音量 (0-255)
  const normalizedLevel = ref(0) // 归一化音量 (0-1)，用于 UI 显示

  let mediaRecorder: MediaRecorder | null = null
  let audioContext: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let audioChunks: Blob[] = []
  let silenceStart: number | null = null  // 静音开始时间
  let animationFrame: number | null = null
  let hasSpoken = false  // 记录是否已开始说话

  /**
   * 开始录音
   */
  async function startRecording(): Promise<void> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // 设置音频分析
      audioContext = new AudioContext()
      analyser = audioContext.createAnalyser()
      analyser.fftSize = 256
      const source = audioContext.createMediaStreamSource(stream)
      source.connect(analyser)

      // 设置 MediaRecorder
      mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      })

      audioChunks = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data)
        }
      }

      mediaRecorder.start(100) // 每 100ms 收集一次数据
      isRecording.value = true
      hasSpoken = false         // 重置说话状态
      silenceStart = null       // 重置静音计时

      console.log('[AudioRecorder] Recording started')
      // 开始监测音量
      monitorAudioLevel()
    } catch (error) {
      console.error('Failed to start recording:', error)
      throw error
    }
  }

  /**
   * 停止录音
   */
  async function stopRecording(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        reject(new Error('Not recording'))
        return
      }

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
        cleanup()
        resolve(audioBlob)
      }

      mediaRecorder.stop()
      mediaRecorder.stream.getTracks().forEach((track) => track.stop())
    })
  }

  // 用于节流日志输出
  let lastLogTime = 0

  /**
   * 监测音量级别（与原项目逻辑一致）
   *
   * - 音量 > 阈值：说话，重置静音计时
   * - 音量 <= 阈值 且已说过话：开始静音计时
   * - 静音持续指定时间：触发回调
   */
  function monitorAudioLevel() {
    if (!analyser || !isRecording.value) return

    const dataArray = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteFrequencyData(dataArray)

    // 计算平均音量（整数 0-255）
    const average = Math.round(dataArray.reduce((a, b) => a + b, 0) / dataArray.length)
    audioLevel.value = average
    normalizedLevel.value = average / 255  // 归一化给 UI 使用

    // 获取当前配置值
    const threshold = getSilenceThreshold()
    const duration = getSilenceDuration()

    // 每秒输出一次调试日志
    const now = Date.now()
    if (now - lastLogTime > 1000) {
      console.log(`[AudioRecorder] 音量: ${average}, 阈值: ${threshold}, 已说话: ${hasSpoken}, 静音开始: ${silenceStart ? Math.round((now - silenceStart) / 100) / 10 + 's' : 'null'}`)
      lastLogTime = now
    }

    // 音量高于阈值 = 说话
    if (average > threshold) {
      if (!hasSpoken) {
        console.log('[AudioRecorder] 检测到说话开始')
      }
      hasSpoken = true
      silenceStart = null  // 重置静音计时
    }
    // 音量低于等于阈值 且 已说过话 = 静音
    else if (hasSpoken) {
      if (!silenceStart) {
        silenceStart = now
        console.log('[AudioRecorder] 开始静音计时...')
      } else if (now - silenceStart > duration) {
        // 静音持续超过阈值，触发回调
        console.log('[AudioRecorder] 检测到说话结束，触发回调')
        if (onSilenceDetected) {
          onSilenceDetected()
        }
        return  // 不再继续监测
      }
    }

    animationFrame = requestAnimationFrame(monitorAudioLevel)
  }

  /**
   * 清理资源
   */
  function cleanup() {
    isRecording.value = false
    audioLevel.value = 0
    normalizedLevel.value = 0

    if (animationFrame) {
      cancelAnimationFrame(animationFrame)
      animationFrame = null
    }

    silenceStart = null
    hasSpoken = false

    if (audioContext) {
      audioContext.close()
      audioContext = null
    }

    analyser = null
    mediaRecorder = null
  }

  onUnmounted(cleanup)

  return {
    isRecording,
    audioLevel,         // 整数 (0-255)，用于静音检测调试
    normalizedLevel,    // 归一化 (0-1)，用于 UI 显示
    startRecording,
    stopRecording,
  }
}
