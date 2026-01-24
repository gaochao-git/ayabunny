/**
 * TTS 播放器 Composable
 *
 * 支持动态配置音量增益和声音
 */

import { ref, onUnmounted } from 'vue'
import { synthesize } from '@/api/tts'

export interface TTSPlayerOptions {
  gain?: number | (() => number)      // 音量增益 (1-20x)
  voice?: string | (() => string)     // TTS 声音
  onPlayStart?: () => void
  onPlayEnd?: () => void
}

// 获取选项值（支持函数或直接值）
function getOptionValue<T>(option: T | (() => T) | undefined, defaultValue: T): T {
  if (option === undefined) return defaultValue
  if (typeof option === 'function') return (option as () => T)()
  return option
}

export function useTTSPlayer(options: TTSPlayerOptions = {}) {
  const { onPlayStart, onPlayEnd } = options

  // 动态获取配置值
  const getGain = () => getOptionValue(options.gain, 10)
  const getVoice = () => getOptionValue(options.voice, 'alex')

  const isPlaying = ref(false)
  const isPending = ref(false)

  let audioContext: AudioContext | null = null
  let currentSource: AudioBufferSourceNode | null = null
  let gainNode: GainNode | null = null

  // 播放队列
  const queue: string[] = []
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
   * 播放文本
   */
  async function speak(text: string): Promise<void> {
    // 如果被停止了，重置状态
    if (isStopped) {
      isStopped = false
    }
    queue.push(text)
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
      const text = queue.shift()!

      try {
        // 合成语音（使用当前配置的声音）
        const voice = getVoice()
        console.log(`[TTS] Synthesizing with voice: ${voice}`)
        const audioData = await synthesize({ text, voice })

        // 如果在合成期间被停止，不播放
        if (isStopped) break

        // 播放音频
        await playAudioBuffer(audioData)
      } catch (error) {
        console.error('TTS error:', error)
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

    // 清空队列
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
