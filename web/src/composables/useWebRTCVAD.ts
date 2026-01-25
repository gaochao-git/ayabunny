/**
 * WebRTC VAD Composable
 * 基于频谱分析的语音活动检测，模拟 WebRTC VAD 算法
 * 比简单音量检测更准确，比 Silero VAD 更轻量
 */

import { ref, onUnmounted } from 'vue'

export interface WebRTCVADOptions {
  /** 语音开始回调（如果配置了中断词，只有匹配时才触发） */
  onSpeechStart?: () => void
  /** 语音结束回调 */
  onSpeechEnd?: () => void
  /** 语音检测阈值 (0-1)，值越小越灵敏 */
  threshold?: number | (() => number)
  /** 语音能量在频谱中的最小占比 */
  speechFreqRatio?: number
  /** 启动后忽略检测的时间 (ms) */
  ignoreTime?: number | (() => number)
  /** 连续检测到语音的帧数才触发 */
  speechFrames?: number
  /** 连续检测到静音的帧数才结束 */
  silenceFrames?: number
  /** 中断词列表（支持数组或返回数组的函数） */
  wakeWords?: string[] | (() => string[])
  /** ASR 识别函数（用于中断词验证） */
  transcribeFn?: (blob: Blob) => Promise<string>
  /** 中断词检测到时的回调 */
  onWakeWordDetected?: (word: string) => void
}

export function useWebRTCVAD(options: WebRTCVADOptions = {}) {
  const {
    onSpeechStart,
    onSpeechEnd,
    threshold = 0.3,
    speechFreqRatio = 0.4,
    ignoreTime = 800,
    speechFrames = 3,
    silenceFrames = 30,  // 增加到 30 帧（约 500ms 静音才结束）
    wakeWords,
    transcribeFn,
    onWakeWordDetected,
  } = options

  const isActive = ref(false)
  const isSpeaking = ref(false)
  const isCheckingWakeWord = ref(false)

  let audioContext: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let mediaStream: MediaStream | null = null
  let animationId: number | null = null
  let ignoreUntil = 0
  let speechFrameCount = 0
  let silenceFrameCount = 0

  // 音频录制相关
  let mediaRecorder: MediaRecorder | null = null
  let audioChunks: Blob[] = []

  // 获取配置值
  function getThreshold(): number {
    return typeof threshold === 'function' ? threshold() : threshold
  }

  function getIgnoreTime(): number {
    return typeof ignoreTime === 'function' ? ignoreTime() : ignoreTime
  }

  function getWakeWords(): string[] {
    if (typeof wakeWords === 'function') return wakeWords()
    return wakeWords ?? []
  }

  /**
   * 开始录音（用于中断词检测）
   */
  function startRecording() {
    if (!mediaStream || mediaRecorder?.state === 'recording') {
      console.log('[WebRTC VAD] 录音已在进行中或无媒体流')
      return
    }

    audioChunks = []
    mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm;codecs=opus' })

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        audioChunks.push(e.data)
        console.log(`[WebRTC VAD] 录音数据: ${e.data.size} bytes, 总 chunks: ${audioChunks.length}`)
      }
    }

    mediaRecorder.start(100)  // 每 100ms 收集一次数据
    console.log('[WebRTC VAD] 开始录音')
  }

  /**
   * 停止录音并返回音频 Blob
   */
  function stopRecording(): Promise<Blob> {
    return new Promise((resolve) => {
      if (!mediaRecorder || mediaRecorder.state !== 'recording') {
        resolve(new Blob(audioChunks, { type: 'audio/webm' }))
        return
      }

      mediaRecorder.onstop = () => {
        resolve(new Blob(audioChunks, { type: 'audio/webm' }))
      }

      mediaRecorder.stop()
    })
  }

  /**
   * 验证中断词
   */
  async function verifyWakeWord(): Promise<boolean> {
    if (!transcribeFn || audioChunks.length === 0) return false

    isCheckingWakeWord.value = true
    try {
      const audioBlob = await stopRecording()
      console.log(`[WebRTC VAD] 发送 ASR 验证，音频大小: ${audioBlob.size} bytes`)

      const text = await transcribeFn(audioBlob)
      console.log(`[WebRTC VAD] ASR 识别结果: "${text}"`)

      const words = getWakeWords()
      const matchedWord = words.find(word => text?.toLowerCase().includes(word.toLowerCase()))

      if (matchedWord) {
        console.log(`[WebRTC VAD] 匹配到中断词: "${matchedWord}"`)
        onWakeWordDetected?.(matchedWord)
        return true
      } else {
        console.log(`[WebRTC VAD] 未匹配到中断词`)
        return false
      }
    } catch (error) {
      console.error('[WebRTC VAD] ASR 验证失败:', error)
      return false
    } finally {
      isCheckingWakeWord.value = false
      audioChunks = []
    }
  }

  /**
   * 分析频谱判断是否为语音
   * WebRTC VAD 使用频谱特征而非简单音量
   */
  function analyzeSpectrum(frequencyData: Uint8Array): boolean {
    const length = frequencyData.length

    // 人声主要在 85Hz - 3000Hz 范围
    // 假设采样率 48000Hz，FFT size 2048
    // 每个 bin 约 23.4Hz
    const speechStartBin = Math.floor(85 / 23.4)   // ~4
    const speechEndBin = Math.floor(3000 / 23.4)   // ~128

    let totalEnergy = 0
    let speechEnergy = 0

    for (let i = 0; i < length; i++) {
      const energy = frequencyData[i] / 255
      totalEnergy += energy

      if (i >= speechStartBin && i <= speechEndBin) {
        speechEnergy += energy
      }
    }

    if (totalEnergy === 0) return false

    // 计算语音频段能量占比
    const ratio = speechEnergy / totalEnergy

    // 计算语音频段平均能量
    const avgSpeechEnergy = speechEnergy / (speechEndBin - speechStartBin + 1)

    // 同时满足：语音频段占比高 + 能量超过阈值
    return ratio > speechFreqRatio && avgSpeechEnergy > getThreshold()
  }

  /**
   * 检测循环
   */
  function detectLoop() {
    if (!analyser || !isActive.value) return

    const frequencyData = new Uint8Array(analyser.frequencyBinCount)
    analyser.getByteFrequencyData(frequencyData)

    // 忽略期内不检测
    if (Date.now() < ignoreUntil) {
      animationId = requestAnimationFrame(detectLoop)
      return
    }

    const isSpeech = analyzeSpectrum(frequencyData)

    if (isSpeech) {
      speechFrameCount++
      silenceFrameCount = 0

      // 连续检测到语音，触发开始
      if (!isSpeaking.value && speechFrameCount >= speechFrames) {
        const words = getWakeWords()
        console.log('[WebRTC VAD] 检测到语音开始, 中断词:', words)
        isSpeaking.value = true

        // 如果配置了中断词，开始录音
        if (words.length > 0 && transcribeFn) {
          startRecording()
        } else {
          // 没有中断词要求，直接触发回调
          onSpeechStart?.()
        }
      }
    } else {
      silenceFrameCount++
      speechFrameCount = 0

      // 连续检测到静音，触发结束
      if (isSpeaking.value && silenceFrameCount >= silenceFrames) {
        console.log('[WebRTC VAD] 检测到语音结束')
        isSpeaking.value = false

        // 如果配置了中断词，进行验证
        const words = getWakeWords()
        if (words.length > 0 && transcribeFn) {
          // 异步验证中断词
          verifyWakeWord().then((matched) => {
            if (matched) {
              onSpeechStart?.()  // 匹配到中断词才触发打断
            }
          })
        }

        onSpeechEnd?.()
      }
    }

    animationId = requestAnimationFrame(detectLoop)
  }

  /**
   * 启动 VAD
   */
  async function start(): Promise<void> {
    if (isActive.value) return

    console.log('[WebRTC VAD] 启动中...')

    try {
      // 获取麦克风（关闭降噪以提高检测灵敏度）
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,   // 保留回声消除，过滤 TTS 声音
          noiseSuppression: false,  // 关闭降噪，提高检测灵敏度
          autoGainControl: true,
        }
      })

      // 创建音频分析器
      audioContext = new AudioContext()
      analyser = audioContext.createAnalyser()
      analyser.fftSize = 2048
      analyser.smoothingTimeConstant = 0.5

      const source = audioContext.createMediaStreamSource(mediaStream)
      source.connect(analyser)

      // 设置忽略时间
      ignoreUntil = Date.now() + getIgnoreTime()
      speechFrameCount = 0
      silenceFrameCount = 0

      isActive.value = true

      // 开始检测
      detectLoop()

      console.log('[WebRTC VAD] 已启动')
    } catch (error) {
      console.error('[WebRTC VAD] 启动失败:', error)
      throw error
    }
  }

  /**
   * 停止 VAD
   */
  function stop(): void {
    if (animationId) {
      cancelAnimationFrame(animationId)
      animationId = null
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop())
      mediaStream = null
    }

    if (audioContext) {
      audioContext.close()
      audioContext = null
    }

    analyser = null
    isActive.value = false
    isSpeaking.value = false
    speechFrameCount = 0
    silenceFrameCount = 0

    console.log('[WebRTC VAD] 已停止')
  }

  onUnmounted(stop)

  return {
    isActive,
    isSpeaking,
    isCheckingWakeWord,
    start,
    stop,
  }
}
