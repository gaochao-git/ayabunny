/**
 * FunASR VAD Composable
 * 使用 FunASR 服务端的 FSMN-VAD 模型进行语音活动检测
 * 通过 WebSocket 流式传输音频，接收 VAD 事件
 * 支持中断词验证：检测到语音后，通过 ASR 识别内容，匹配中断词才触发打断
 */

import { ref, onUnmounted } from 'vue'
import { FUNASR_WS_URL } from '@/api/config'

export interface FunASRVADOptions {
  /** FunASR WebSocket 地址 */
  wsUrl?: string
  /** 语音开始回调（如果配置了中断词，只有匹配时才触发） */
  onSpeechStart?: () => void
  /** 语音结束回调 */
  onSpeechEnd?: () => void
  /** 中断词检测到时的回调 */
  onWakeWordDetected?: (word: string, text: string) => void
  /** 启动后忽略检测的时间 (ms) */
  ignoreTime?: number | (() => number)
  /** 中断词列表（支持数组或返回数组的函数） */
  wakeWords?: string[] | (() => string[])
  /** ASR 识别函数（用于中断词验证） */
  transcribeFn?: (blob: Blob) => Promise<string>
}

export function useFunASRVAD(options: FunASRVADOptions = {}) {
  const {
    wsUrl = FUNASR_WS_URL,
    onSpeechStart,
    onSpeechEnd,
    onWakeWordDetected,
    ignoreTime = 800,
    wakeWords = [],
    transcribeFn,
  } = options

  const isActive = ref(false)
  const isSpeaking = ref(false)
  const isConnecting = ref(false)
  const isCheckingWakeWord = ref(false)  // 正在检查中断词

  let ws: WebSocket | null = null
  let mediaStream: MediaStream | null = null
  let audioContext: AudioContext | null = null
  let processor: ScriptProcessorNode | null = null
  let ignoreUntil = 0

  // 音频缓冲区（用于中断词识别）
  let audioChunks: Int16Array[] = []
  let speechStartTime = 0

  // 获取忽略时间
  function getIgnoreTime(): number {
    return typeof ignoreTime === 'function' ? ignoreTime() : ignoreTime
  }

  // 获取中断词列表
  function getWakeWords(): string[] {
    return typeof wakeWords === 'function' ? wakeWords() : wakeWords
  }

  /**
   * 将 Float32Array 转换为 Int16Array (PCM)
   */
  function float32ToInt16(float32: Float32Array): Int16Array {
    const int16 = new Int16Array(float32.length)
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]))
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
    }
    return int16
  }

  /**
   * 重采样到 16kHz
   */
  function resample(audioData: Float32Array, fromSampleRate: number, toSampleRate: number): Float32Array {
    if (fromSampleRate === toSampleRate) {
      return audioData
    }
    const ratio = fromSampleRate / toSampleRate
    const newLength = Math.round(audioData.length / ratio)
    const result = new Float32Array(newLength)
    for (let i = 0; i < newLength; i++) {
      const index = Math.floor(i * ratio)
      result[i] = audioData[index]
    }
    return result
  }

  /**
   * 将 PCM 数据转换为 WAV Blob
   */
  function pcmToWavBlob(chunks: Int16Array[], sampleRate: number = 16000): Blob {
    // 合并所有 chunks
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
    const pcmData = new Int16Array(totalLength)
    let offset = 0
    for (const chunk of chunks) {
      pcmData.set(chunk, offset)
      offset += chunk.length
    }

    // 创建 WAV 头
    const wavHeader = new ArrayBuffer(44)
    const view = new DataView(wavHeader)
    const numChannels = 1
    const bitsPerSample = 16
    const byteRate = sampleRate * numChannels * bitsPerSample / 8
    const blockAlign = numChannels * bitsPerSample / 8
    const dataSize = pcmData.length * 2

    // RIFF header
    view.setUint32(0, 0x52494646, false) // "RIFF"
    view.setUint32(4, 36 + dataSize, true)
    view.setUint32(8, 0x57415645, false) // "WAVE"
    // fmt chunk
    view.setUint32(12, 0x666d7420, false) // "fmt "
    view.setUint32(16, 16, true)
    view.setUint16(20, 1, true) // PCM
    view.setUint16(22, numChannels, true)
    view.setUint32(24, sampleRate, true)
    view.setUint32(28, byteRate, true)
    view.setUint16(32, blockAlign, true)
    view.setUint16(34, bitsPerSample, true)
    // data chunk
    view.setUint32(36, 0x64617461, false) // "data"
    view.setUint32(40, dataSize, true)

    return new Blob([wavHeader, pcmData.buffer], { type: 'audio/wav' })
  }

  /**
   * 检查文本是否包含中断词
   */
  function checkWakeWords(text: string): string | null {
    const words = getWakeWords()
    if (!text || words.length === 0) return null
    const lowerText = text.toLowerCase()
    for (const word of words) {
      if (lowerText.includes(word.toLowerCase())) {
        return word
      }
    }
    return null
  }

  /**
   * 验证中断词
   */
  async function verifyWakeWord(): Promise<boolean> {
    if (!transcribeFn || audioChunks.length === 0) {
      console.log('[FunASR VAD] 无法验证中断词：缺少 transcribeFn 或音频数据')
      return false
    }

    isCheckingWakeWord.value = true
    try {
      // 转换为 WAV
      const wavBlob = pcmToWavBlob(audioChunks)
      console.log(`[FunASR VAD] 发送 ASR 验证，音频大小: ${wavBlob.size} bytes`)

      // ASR 识别
      const text = await transcribeFn(wavBlob)
      console.log(`[FunASR VAD] ASR 识别结果: "${text}"`)

      // 检查中断词
      const matchedWord = checkWakeWords(text)
      if (matchedWord) {
        console.log(`[FunASR VAD] 匹配到中断词: "${matchedWord}"`)
        onWakeWordDetected?.(matchedWord, text)
        return true
      } else {
        console.log(`[FunASR VAD] 未匹配到中断词`)
        return false
      }
    } catch (error) {
      console.error('[FunASR VAD] ASR 验证失败:', error)
      return false
    } finally {
      isCheckingWakeWord.value = false
      audioChunks = []  // 清空缓冲区
    }
  }

  /**
   * 启动 VAD
   */
  async function start(): Promise<void> {
    if (isActive.value || isConnecting.value) return

    isConnecting.value = true
    console.log('[FunASR VAD] 启动中...')

    try {
      // 获取麦克风（关闭降噪以提高语音检测灵敏度）
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,   // 保留回声消除，过滤 TTS 声音
          noiseSuppression: false,  // 关闭降噪，提高检测灵敏度
          autoGainControl: true,
          sampleRate: 16000,
        }
      })

      // 创建音频处理
      audioContext = new AudioContext({ sampleRate: 16000 })
      const source = audioContext.createMediaStreamSource(mediaStream)

      // 使用 ScriptProcessor（虽然已废弃，但兼容性好）
      processor = audioContext.createScriptProcessor(4096, 1, 1)

      // 连接 WebSocket
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('[FunASR VAD] WebSocket 已连接')

        // 发送配置
        const config = {
          mode: 'online',
          chunk_size: [5, 10, 5],
          wav_name: 'vad',
          is_speaking: true,
          chunk_interval: 10,
          itn: false,
          wav_format: 'pcm',
        }
        ws?.send(JSON.stringify(config))

        // 设置忽略时间
        const ignoreMs = getIgnoreTime()
        ignoreUntil = Date.now() + ignoreMs
        isActive.value = true
        isConnecting.value = false
        console.log(`[FunASR VAD] 启动完成, 忽略时间: ${ignoreMs}ms, 中断词:`, getWakeWords())

        // 开始处理音频
        processor!.onaudioprocess = (e) => {
          if (!ws || ws.readyState !== WebSocket.OPEN) return

          const inputData = e.inputBuffer.getChannelData(0)
          // 重采样到 16kHz
          const resampled = resample(inputData, audioContext!.sampleRate, 16000)
          const pcmData = float32ToInt16(resampled)

          // 发送到 VAD 服务
          ws.send(pcmData.buffer)

          // 始终缓存音频用于中断词识别（环形缓冲区，保留最近 3 秒）
          if (getWakeWords().length > 0 && transcribeFn) {
            audioChunks.push(pcmData)
            // 限制缓冲区大小（最多 3 秒）
            const maxChunks = Math.ceil(16000 * 3 / 4096)
            while (audioChunks.length > maxChunks) {
              audioChunks.shift()
            }
          }
        }

        source.connect(processor)
        processor!.connect(audioContext!.destination)
      }

      ws.onmessage = async (event) => {
        // 忽略期内不处理
        if (Date.now() < ignoreUntil) {
          console.log('[FunASR VAD] 忽略期内，跳过消息')
          return
        }

        try {
          const data = JSON.parse(event.data)
          console.log('[FunASR VAD] 收到消息:', JSON.stringify(data).slice(0, 100))

          // 检测到语音开始
          if (data.text && data.text.length > 0) {
            if (!isSpeaking.value) {
              console.log('[FunASR VAD] 检测到语音开始, text:', data.text)
              isSpeaking.value = true
              speechStartTime = Date.now()
              // 不清空缓冲区，保留之前缓存的音频（可能包含中断词的开头）

              // 如果没有配置中断词，直接触发回调
              if (getWakeWords().length === 0 || !transcribeFn) {
                onSpeechStart?.()
              }
            }
          }

          // 检测到语音结束
          if (data.is_final || (data.text === '' && isSpeaking.value)) {
            if (isSpeaking.value) {
              console.log('[FunASR VAD] 检测到语音结束, is_final:', data.is_final, ', audioChunks:', audioChunks.length)
              isSpeaking.value = false

              // 如果配置了中断词，进行验证
              if (getWakeWords().length > 0 && transcribeFn) {
                const speechDuration = Date.now() - speechStartTime
                console.log(`[FunASR VAD] 语音时长: ${speechDuration}ms`)

                // 只有语音足够长才验证（避免太短的误触发）
                if (speechDuration >= 300 && audioChunks.length > 0) {
                  const isWakeWord = await verifyWakeWord()
                  if (isWakeWord) {
                    onSpeechStart?.()  // 匹配到中断词才触发
                  }
                } else {
                  console.log('[FunASR VAD] 语音太短，跳过验证')
                  audioChunks = []
                }
              }

              onSpeechEnd?.()
            }
          }
        } catch (e) {
          // 忽略解析错误
        }
      }

      ws.onerror = (error) => {
        console.error('[FunASR VAD] WebSocket 错误:', error)
        isConnecting.value = false
      }

      ws.onclose = () => {
        console.log('[FunASR VAD] WebSocket 已关闭')
        isActive.value = false
        isConnecting.value = false
      }

    } catch (error) {
      console.error('[FunASR VAD] 启动失败:', error)
      isConnecting.value = false
      throw error
    }
  }

  /**
   * 停止 VAD
   */
  function stop(): void {
    if (processor) {
      processor.disconnect()
      processor = null
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop())
      mediaStream = null
    }

    if (audioContext) {
      audioContext.close()
      audioContext = null
    }

    if (ws) {
      // 发送结束信号
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ is_speaking: false }))
      }
      ws.close()
      ws = null
    }

    isActive.value = false
    isSpeaking.value = false
    isConnecting.value = false
    isCheckingWakeWord.value = false
    audioChunks = []

    console.log('[FunASR VAD] 已停止')
  }

  onUnmounted(stop)

  return {
    isActive,
    isSpeaking,
    isConnecting,
    isCheckingWakeWord,
    start,
    stop,
  }
}
