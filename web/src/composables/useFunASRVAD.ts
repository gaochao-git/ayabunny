/**
 * FunASR VAD Composable
 * 使用 FunASR 服务端的 FSMN-VAD 模型进行语音活动检测
 * 通过 WebSocket 流式传输音频，接收 VAD 事件
 */

import { ref, onUnmounted } from 'vue'

export interface FunASRVADOptions {
  /** FunASR WebSocket 地址 */
  wsUrl?: string
  /** 语音开始回调 */
  onSpeechStart?: () => void
  /** 语音结束回调 */
  onSpeechEnd?: () => void
  /** 启动后忽略检测的时间 (ms) */
  ignoreTime?: number | (() => number)
}

export function useFunASRVAD(options: FunASRVADOptions = {}) {
  const {
    wsUrl = 'ws://127.0.0.1:10096',
    onSpeechStart,
    onSpeechEnd,
    ignoreTime = 800,
  } = options

  const isActive = ref(false)
  const isSpeaking = ref(false)
  const isConnecting = ref(false)

  let ws: WebSocket | null = null
  let mediaStream: MediaStream | null = null
  let audioContext: AudioContext | null = null
  let processor: ScriptProcessorNode | null = null
  let ignoreUntil = 0

  // 获取忽略时间
  function getIgnoreTime(): number {
    return typeof ignoreTime === 'function' ? ignoreTime() : ignoreTime
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
   * 启动 VAD
   */
  async function start(): Promise<void> {
    if (isActive.value || isConnecting.value) return

    isConnecting.value = true
    console.log('[FunASR VAD] 启动中...')

    try {
      // 获取麦克风
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
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
        ignoreUntil = Date.now() + getIgnoreTime()
        isActive.value = true
        isConnecting.value = false

        // 开始处理音频
        processor!.onaudioprocess = (e) => {
          if (!ws || ws.readyState !== WebSocket.OPEN) return

          const inputData = e.inputBuffer.getChannelData(0)
          // 重采样到 16kHz
          const resampled = resample(inputData, audioContext!.sampleRate, 16000)
          const pcmData = float32ToInt16(resampled)
          ws.send(pcmData.buffer)
        }

        source.connect(processor)
        processor!.connect(audioContext!.destination)
      }

      ws.onmessage = (event) => {
        // 忽略期内不处理
        if (Date.now() < ignoreUntil) return

        try {
          const data = JSON.parse(event.data)

          // FunASR 返回的 VAD 信息
          // 检查是否有语音活动
          if (data.text && data.text.length > 0) {
            if (!isSpeaking.value) {
              console.log('[FunASR VAD] 检测到语音开始')
              isSpeaking.value = true
              onSpeechStart?.()
            }
          }

          // 检查是否语音结束（is_final 或静音）
          if (data.is_final || (data.text === '' && isSpeaking.value)) {
            if (isSpeaking.value) {
              console.log('[FunASR VAD] 检测到语音结束')
              isSpeaking.value = false
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

    console.log('[FunASR VAD] 已停止')
  }

  onUnmounted(stop)

  return {
    isActive,
    isSpeaking,
    isConnecting,
    start,
    stop,
  }
}
