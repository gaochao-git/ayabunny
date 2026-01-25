/**
 * TTS 播放器 Composable
 *
 * 支持动态配置音量增益和声音
 * 优化：并行预合成，在播放当前句子时同时合成后续句子
 */

import { ref, onUnmounted } from 'vue'
import { synthesize } from '@/api/tts'

export interface TTSPlayerOptions {
  gain?: number | (() => number)      // 音量增益 (1-20x)
  voice?: string | (() => string)     // TTS 声音
  customVoiceId?: string | null | (() => string | null)  // 自定义音色 ID（优先级高于 voice）
  speed?: number | (() => number)     // 语速 (0.5-2.0)
  onPlayStart?: () => void
  onPlayEnd?: () => void
}

// 获取选项值（支持函数或直接值）
function getOptionValue<T>(option: T | (() => T) | undefined, defaultValue: T): T {
  if (option === undefined) return defaultValue
  if (typeof option === 'function') return (option as () => T)()
  return option
}

// 队列项：文本 + 预合成的音频
interface QueueItem {
  text: string
  audioPromise: Promise<ArrayBuffer>  // 预合成 Promise
  audio?: ArrayBuffer                  // 合成完成的音频
}

export function useTTSPlayer(options: TTSPlayerOptions = {}) {
  const { onPlayStart, onPlayEnd } = options

  // 动态获取配置值
  const getGain = () => getOptionValue(options.gain, 10)
  const getVoice = () => getOptionValue(options.voice, 'alex')
  const getCustomVoiceId = () => getOptionValue(options.customVoiceId, null)
  const getSpeed = () => getOptionValue(options.speed, 1.0)

  const isPlaying = ref(false)
  const isPending = ref(false)

  let audioContext: AudioContext | null = null
  let currentSource: AudioBufferSourceNode | null = null
  let gainNode: GainNode | null = null

  // 播放队列（带预合成）
  const queue: QueueItem[] = []
  let isProcessing = false
  let isStopped = false  // 是否被手动停止（用于区分正常结束和打断）

  /**
   * 初始化音频上下文
   */
  function initAudioContext() {
    if (!audioContext) {
      audioContext = new AudioContext()
      gainNode = audioContext.createGain()
      gainNode.connect(audioContext.destination)
    }
    // 移动端需要在用户交互后恢复 AudioContext
    if (audioContext.state === 'suspended') {
      audioContext.resume()
    }
    // 更新增益值
    if (gainNode) {
      gainNode.gain.value = getGain()
    }
  }

  /**
   * 解锁音频（移动端需要在用户点击时调用）
   */
  async function unlock(): Promise<void> {
    initAudioContext()
    if (audioContext && audioContext.state === 'suspended') {
      await audioContext.resume()
    }
    console.log('[TTS] Audio unlocked, state:', audioContext?.state)
  }

  /**
   * 开始合成（立即返回 Promise，不阻塞）
   */
  function startSynthesis(text: string): Promise<ArrayBuffer> {
    const voice = getVoice()
    const customVoiceId = getCustomVoiceId()
    const speed = getSpeed()
    console.log(`[TTS] 开始预合成: "${text.slice(0, 20)}..." voice=${voice}, speed=${speed}`)
    return synthesize({ text, voice, customVoiceId: customVoiceId || undefined, speed })
  }

  /**
   * 播放文本（立即开始预合成）
   */
  async function speak(text: string): Promise<void> {
    // 如果被停止了，重置状态
    if (isStopped) {
      isStopped = false
    }

    // 立即开始预合成（不等待）
    const audioPromise = startSynthesis(text)

    // 加入队列
    queue.push({ text, audioPromise })

    // 启动播放处理（如果没在处理中）
    if (!isProcessing) {
      processQueue()
    }
  }

  /**
   * 处理播放队列
   */
  async function processQueue(): Promise<void> {
    if (isProcessing || queue.length === 0) return

    isProcessing = true
    isPending.value = true
    isStopped = false

    while (queue.length > 0 && !isStopped) {
      const item = queue.shift()!

      try {
        // 等待预合成完成（通常已经在合成中或已完成）
        console.log(`[TTS] 等待合成完成: "${item.text.slice(0, 20)}..."`)
        const audioData = await item.audioPromise

        // 如果在合成期间被停止，不播放
        if (isStopped) break

        // 播放音频
        await playAudioBuffer(audioData)
      } catch (error) {
        console.error('[TTS] 合成/播放错误:', error)
      }
    }

    isProcessing = false
    isPending.value = false

    // 只有在正常结束（非打断）且队列为空时才触发 onPlayEnd
    if (!isStopped && queue.length === 0) {
      console.log('[TTS] 队列播放完成')
      onPlayEnd?.()
    }
  }

  /**
   * 播放音频 Buffer
   */
  async function playAudioBuffer(audioData: ArrayBuffer): Promise<void> {
    return new Promise(async (resolve, reject) => {
      try {
        initAudioContext()
        if (!audioContext || !gainNode) {
          reject(new Error('Audio context not initialized'))
          return
        }

        const audioBuffer = await audioContext.decodeAudioData(audioData)

        currentSource = audioContext.createBufferSource()
        currentSource.buffer = audioBuffer
        currentSource.connect(gainNode)

        currentSource.onended = () => {
          isPlaying.value = false
          currentSource = null
          // 注意：不在这里调用 onPlayEnd，由 processQueue 统一管理
          resolve()
        }

        isPlaying.value = true
        onPlayStart?.()
        currentSource.start()
        console.log(`[TTS] 开始播放，时长: ${audioBuffer.duration.toFixed(1)}s`)
      } catch (error) {
        isPlaying.value = false
        reject(error)
      }
    })
  }

  /**
   * 停止播放（打断）
   */
  function stop(): void {
    console.log('[TTS] 停止播放，清空队列')

    // 标记为手动停止
    isStopped = true

    // 清空队列（预合成的 Promise 会自然完成，但结果不会被使用）
    queue.length = 0

    // 停止当前播放
    if (currentSource) {
      try {
        currentSource.stop()
      } catch {
        // 忽略已停止的错误
      }
      currentSource = null
    }

    isPlaying.value = false
    isPending.value = false
    isProcessing = false
  }

  /**
   * 设置音量增益
   */
  function setGain(newGain: number): void {
    if (gainNode) {
      gainNode.gain.value = Math.max(1, Math.min(20, newGain))
    }
  }

  /**
   * 清理资源
   */
  function cleanup(): void {
    stop()
    if (audioContext) {
      audioContext.close()
      audioContext = null
    }
    gainNode = null
  }

  onUnmounted(cleanup)

  return {
    isPlaying,
    isPending,
    speak,
    stop,
    setGain,
    unlock,  // 移动端需要在用户交互时调用
  }
}
