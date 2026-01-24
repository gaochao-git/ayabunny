/**
 * VAD (Voice Activity Detection) Composable
 * 用于检测用户语音打断 TTS 播放
 *
 * 支持两种模式：
 * 1. 直接打断模式：检测到声音就打断（默认）
 * 2. 唤醒词模式：检测到声音后录音识别，包含唤醒词才打断
 */

import { ref, onUnmounted } from 'vue'

export interface VADOptions {
  threshold?: number | (() => number)      // 打断阈值 (0-255)
  triggerCount?: number | (() => number)   // 触发次数
  ignoreTime?: number | (() => number)     // 忽略时间 (ms)
  wakeWord?: string                        // 唤醒词（如 "小智"），设置后启用唤醒词模式
  wakeWords?: string[]                     // 唤醒词列表（支持多个同音字）
  wakeWordTimeout?: number                 // 唤醒词录音时长 (ms)，默认 1500
  transcribeFn?: (blob: Blob) => Promise<string>  // ASR 识别函数
  onSpeechStart?: () => void
  onSpeechEnd?: () => void
  onWakeWordDetected?: () => void          // 唤醒词检测到时回调
}

// 获取选项值（支持函数或直接值）
function getOptionValue<T>(option: T | (() => T) | undefined, defaultValue: T): T {
  if (option === undefined) return defaultValue
  if (typeof option === 'function') return (option as () => T)()
  return option
}

export function useVAD(options: VADOptions = {}) {
  const { onSpeechStart, onSpeechEnd, onWakeWordDetected, wakeWord, wakeWords, transcribeFn } = options

  // 合并单个唤醒词和唤醒词列表
  const allWakeWords = wakeWords || (wakeWord ? [wakeWord] : [])

  // 动态获取配置值
  const getThreshold = () => getOptionValue(options.threshold, 60)
  const getTriggerCount = () => getOptionValue(options.triggerCount, 5)
  const getIgnoreTime = () => getOptionValue(options.ignoreTime, 800)
  const wakeWordTimeout = options.wakeWordTimeout || 1500

  const isActive = ref(false)
  const isSpeaking = ref(false)
  const audioLevel = ref(0)
  const isCheckingWakeWord = ref(false)  // 是否正在检测唤醒词

  let audioContext: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let mediaStream: MediaStream | null = null       // 用于 VAD 监听
  let recordStream: MediaStream | null = null      // 用于唤醒词录音（独立流，启动时创建）
  let animationFrame: number | null = null

  // 打断检测状态
  let startTime: number | null = null  // VAD 启动时间
  let consecutiveCount = 0              // 连续检测到超过阈值的次数

  // 唤醒词录音相关
  let wakeWordRecorder: MediaRecorder | null = null
  let wakeWordChunks: Blob[] = []

  /**
   * 启动 VAD
   */
  async function start(): Promise<void> {
    try {
      // 获取两个独立的 MediaStream：一个用于监听，一个用于录音
      // 这样录音时不会影响监听，也不会在录音时请求新权限导致音频中断
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // 如果启用了唤醒词模式，预先创建录音用的 MediaStream
      if (allWakeWords.length > 0 && transcribeFn) {
        recordStream = await navigator.mediaDevices.getUserMedia({ audio: true })
        console.log('[VAD] Record stream ready for wake word detection')
      }

      audioContext = new AudioContext()
      analyser = audioContext.createAnalyser()
      analyser.fftSize = 256

      const source = audioContext.createMediaStreamSource(mediaStream)
      source.connect(analyser)

      isActive.value = true
      startTime = Date.now()
      consecutiveCount = 0

      console.log('[VAD] Started, ignoring input for', getIgnoreTime(), 'ms')
      if (allWakeWords.length > 0) {
        console.log('[VAD] Wake word mode enabled:', allWakeWords.join(', '))
      }
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

    if (wakeWordRecorder && wakeWordRecorder.state !== 'inactive') {
      wakeWordRecorder.stop()
      wakeWordRecorder = null
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop())
      mediaStream = null
    }

    if (recordStream) {
      recordStream.getTracks().forEach((track) => track.stop())
      recordStream = null
    }

    if (audioContext) {
      audioContext.close()
      audioContext = null
    }

    analyser = null
    isActive.value = false
    isSpeaking.value = false
    isCheckingWakeWord.value = false
    audioLevel.value = 0
    startTime = null
    consecutiveCount = 0
  }

  /**
   * 开始唤醒词录音检测（使用预先创建的 recordStream，不请求新权限）
   */
  async function startWakeWordDetection(): Promise<void> {
    if (!transcribeFn || !recordStream || isCheckingWakeWord.value) return

    isCheckingWakeWord.value = true
    wakeWordChunks = []
    console.log('[VAD] Starting wake word detection...')

    try {
      // 使用预先创建的 recordStream，不请求新权限，避免音频中断
      wakeWordRecorder = new MediaRecorder(recordStream, {
        mimeType: 'audio/webm;codecs=opus',
      })

      wakeWordRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          wakeWordChunks.push(event.data)
        }
      }

      wakeWordRecorder.onstop = () => {
        if (wakeWordChunks.length === 0) {
          isCheckingWakeWord.value = false
          return
        }

        const audioBlob = new Blob(wakeWordChunks, { type: 'audio/webm' })
        console.log('[VAD] Wake word audio recorded:', audioBlob.size, 'bytes')

        // 异步处理 ASR，不阻塞主线程
        setTimeout(async () => {
          try {
            const text = await transcribeFn(audioBlob)
            console.log('[VAD] Wake word ASR result:', text)

            // 检查是否包含任意一个唤醒词
            const detectedWord = allWakeWords.find(word => text && text.includes(word))
            if (detectedWord) {
              console.log('[VAD] Wake word detected:', detectedWord)
              onWakeWordDetected?.()
              onSpeechStart?.()
            } else {
              console.log('[VAD] Wake word not found in:', text)
            }
          } catch (error) {
            console.error('[VAD] Wake word ASR error:', error)
          } finally {
            isCheckingWakeWord.value = false
            wakeWordRecorder = null
          }
        }, 0)
      }

      // 开始录音
      wakeWordRecorder.start(100)

      // 设置超时停止录音
      setTimeout(() => {
        if (wakeWordRecorder && wakeWordRecorder.state === 'recording') {
          wakeWordRecorder.stop()
        }
      }, wakeWordTimeout)

    } catch (error) {
      console.error('[VAD] Failed to start wake word detection:', error)
      isCheckingWakeWord.value = false
    }
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

    // 如果正在检测唤醒词，跳过
    if (isCheckingWakeWord.value) {
      animationFrame = requestAnimationFrame(monitor)
      return
    }

    // 语音活动检测
    if (average > threshold) {
      consecutiveCount++

      // 连续检测到足够次数才触发
      if (consecutiveCount >= triggerCount && !isSpeaking.value) {
        console.log(`[VAD] Speech detected! level=${average}, threshold=${threshold}, count=${consecutiveCount}`)

        // 唤醒词模式：录音识别
        if (allWakeWords.length > 0 && transcribeFn) {
          startWakeWordDetection()
        } else {
          // 直接打断模式
          isSpeaking.value = true
          onSpeechStart?.()
        }

        consecutiveCount = 0  // 重置计数
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
    isCheckingWakeWord,
    audioLevel,
    start,
    stop,
  }
}
