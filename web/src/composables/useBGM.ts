/**
 * 背景音乐 Composable
 * 讲故事时播放轻柔的背景音乐
 * 支持 Media Session API，可通过手机控制中心控制
 */

import { ref, watch } from 'vue'

export interface BGMOptions {
  volume?: () => number
  enabled?: () => boolean
}

// 背景音乐列表 - FiftySounds 免费儿童音乐
const BGM_LIST = [
  { url: '/bgm/sweet-dreams.mp3', title: '甜蜜的梦' },
  { url: '/bgm/moon-and-sun.mp3', title: '月亮和太阳' },
  { url: '/bgm/cotton-clouds.mp3', title: '棉花云' },
  { url: '/bgm/twinkle-star.mp3', title: '小星星' },
  { url: '/bgm/candy-town.mp3', title: '糖果镇' },
  { url: '/bgm/a-day-to-remember.mp3', title: '值得纪念的一天' },
  { url: '/bgm/story-gentle.mp3', title: '轻柔故事' },
]

export function useBGM(options: BGMOptions = {}) {
  const isPlaying = ref(false)
  const isDucked = ref(false)  // 是否处于闪避状态（TTS 播放时降低音量）
  let currentAudio: HTMLAudioElement | null = null
  let unlockedAudio: HTMLAudioElement | null = null  // 预解锁的音频对象
  let pendingBgmId: string | null = null  // 等待播放的 BGM
  let currentTrack: typeof BGM_LIST[0] | null = null
  let fadeTimer: ReturnType<typeof setInterval> | null = null  // 淡入淡出定时器
  let normalVolume = 0.6  // 正常音量
  const DUCK_VOLUME = 0.15  // 闪避时的音量（TTS 播放时）

  /**
   * 设置 Media Session 元数据（让手机控制中心显示音乐信息）
   */
  function setupMediaSession(track: typeof BGM_LIST[0]): void {
    if (!('mediaSession' in navigator)) {
      console.log('[BGM] 浏览器不支持 Media Session API')
      return
    }

    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: track.title,
        artist: '故事背景音乐',
        album: '儿童故事',
        artwork: [
          { src: '/rabbit.svg', sizes: '512x512', type: 'image/svg+xml' },
        ],
      })

      // 设置媒体控制回调
      navigator.mediaSession.setActionHandler('play', () => {
        console.log('[BGM] Media Session: play')
        if (currentAudio && currentAudio.paused) {
          currentAudio.play()
          isPlaying.value = true
        }
      })

      navigator.mediaSession.setActionHandler('pause', () => {
        console.log('[BGM] Media Session: pause')
        if (currentAudio && !currentAudio.paused) {
          currentAudio.pause()
          isPlaying.value = false
        }
      })

      navigator.mediaSession.setActionHandler('stop', () => {
        console.log('[BGM] Media Session: stop')
        stop()
      })

      console.log('[BGM] Media Session 已设置:', track.title)
    } catch (e) {
      console.warn('[BGM] Media Session 设置失败:', e)
    }
  }

  /**
   * 清除 Media Session
   */
  function clearMediaSession(): void {
    if ('mediaSession' in navigator) {
      try {
        navigator.mediaSession.metadata = null
        navigator.mediaSession.setActionHandler('play', null)
        navigator.mediaSession.setActionHandler('pause', null)
        navigator.mediaSession.setActionHandler('stop', null)
      } catch (e) {
        // 忽略
      }
    }
  }

  /**
   * 在用户交互时解锁音频（移动端必须）
   * 使用静音音频解锁，不播放真实 BGM
   */
  function unlock(): void {
    if (unlockedAudio) {
      console.log('[BGM] 已经解锁过了')
      return
    }

    console.log('[BGM] 尝试解锁音频...')

    // 创建一个 Audio 对象用于解锁
    const audio = new Audio()
    audio.volume = 0
    audio.muted = true

    // 使用静音的 WAV 数据解锁（不播放真实 BGM）
    audio.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA'

    audio.play().then(() => {
      audio.pause()
      audio.muted = false
      // 保留这个已解锁的 audio 对象，后续播放时再设置真实 src
      unlockedAudio = audio
      console.log('[BGM] 音频已解锁')
      // 清除挂起的 BGM，不自动播放
      pendingBgmId = null
    }).catch(e => {
      console.warn('[BGM] 解锁失败:', e)
    })
  }

  /**
   * 播放背景音乐
   * @param bgmId 可选，指定要播放的 BGM 文件名（如 "sweet-dreams.mp3" 或 "custom/xxx.mp3"）
   */
  function play(bgmId?: string | null): void {
    console.log('[BGM] play() 被调用, bgmId:', bgmId, 'isPlaying:', isPlaying.value, 'unlocked:', !!unlockedAudio)

    if (options.enabled && !options.enabled()) {
      console.log('[BGM] 背景音乐已禁用')
      return
    }

    if (isPlaying.value) {
      console.log('[BGM] 已在播放中')
      return
    }

    // 如果还没有解锁，保存待播放的 BGM，等待解锁
    if (!unlockedAudio) {
      console.log('[BGM] 还未解锁，等待用户交互...')
      pendingBgmId = bgmId ?? ''
      return
    }

    // 如果指定了 bgmId，使用指定的 BGM；否则随机选择
    let track: typeof BGM_LIST[0]
    if (bgmId) {
      // 查找匹配的预设 BGM
      const preset = BGM_LIST.find(b => b.url === `/bgm/${bgmId}` || b.url.endsWith(`/${bgmId}`))
      if (preset) {
        track = preset
      } else {
        // 自定义 BGM
        track = {
          url: `/bgm/${bgmId}`,
          title: bgmId.split('/').pop()?.replace(/\.[^.]+$/, '') || '自定义音乐',
        }
      }
    } else {
      // 随机选择
      track = BGM_LIST[Math.floor(Math.random() * BGM_LIST.length)]
    }

    currentTrack = track
    console.log('[BGM] 准备播放:', track.title, track.url)

    // 复用已解锁的 audio 对象
    const audio = unlockedAudio!

    // 如果 URL 不同，需要更换
    if (audio.src !== new URL(track.url, location.origin).href) {
      audio.src = track.url
    }

    audio.loop = true
    audio.volume = 0
    audio.currentTime = 0

    // 尝试播放
    const playPromise = audio.play()

    if (playPromise !== undefined) {
      playPromise.then(() => {
        currentAudio = audio
        isPlaying.value = true
        fadeIn(audio, options.volume?.() ?? 0.6, 2000)
        setupMediaSession(track)
        console.log('[BGM] 播放成功:', track.title)
      }).catch(e => {
        console.warn('[BGM] 播放失败:', e.name, e.message)
        // 如果是自动播放策略阻止，保存待播放状态
        if (e.name === 'NotAllowedError') {
          console.log('[BGM] 需要用户交互才能播放，等待下次交互...')
          pendingBgmId = bgmId ?? ''
          unlockedAudio = null  // 重置，需要重新解锁
        }
      })
    }
  }

  /**
   * 停止背景音乐
   */
  function stop(): void {
    console.log('[BGM] stop() 被调用')

    if (currentAudio) {
      fadeOut(currentAudio, 1000, () => {
        if (currentAudio) {
          currentAudio.pause()
          currentAudio = null
        }
        isPlaying.value = false
        currentTrack = null
        clearMediaSession()
        console.log('[BGM] 已停止')
      })
    }
  }

  /**
   * 取消正在进行的淡入淡出动画
   */
  function cancelFade(): void {
    if (fadeTimer) {
      clearInterval(fadeTimer)
      fadeTimer = null
    }
  }

  /**
   * 设置音量（会取消淡入动画，防止覆盖用户调整）
   */
  function setVolume(volume: number): void {
    cancelFade()  // 用户手动调整时，取消淡入动画
    if (currentAudio) {
      currentAudio.volume = Math.max(0, Math.min(1, volume))
    }
  }

  /**
   * 渐入效果
   */
  function fadeIn(audio: HTMLAudioElement, targetVolume: number, duration: number): void {
    cancelFade()  // 先取消之前的动画

    const steps = 20
    const stepTime = duration / steps
    const volumeStep = targetVolume / steps
    let currentStep = 0

    fadeTimer = setInterval(() => {
      currentStep++
      if (audio) {
        audio.volume = Math.min(targetVolume, volumeStep * currentStep)
      }

      if (currentStep >= steps) {
        cancelFade()
        if (audio) audio.volume = targetVolume
      }
    }, stepTime)
  }

  /**
   * 渐出效果
   */
  function fadeOut(audio: HTMLAudioElement, duration: number, callback?: () => void): void {
    cancelFade()  // 先取消之前的动画

    const startVolume = audio.volume
    const steps = 20
    const stepTime = duration / steps
    const volumeStep = startVolume / steps
    let currentStep = 0

    fadeTimer = setInterval(() => {
      currentStep++
      if (audio) {
        audio.volume = Math.max(0, startVolume - volumeStep * currentStep)
      }

      if (currentStep >= steps) {
        cancelFade()
        if (audio) audio.volume = 0
        callback?.()
      }
    }, stepTime)
  }

  /**
   * 音频闪避 - TTS 播放时降低 BGM 音量
   */
  function duck(): void {
    if (!currentAudio || isDucked.value) return

    console.log('[BGM] 音频闪避: 降低音量')
    isDucked.value = true
    normalVolume = currentAudio.volume  // 保存当前音量

    // 快速淡出到闪避音量
    cancelFade()
    const startVolume = currentAudio.volume
    const steps = 10
    const stepTime = 200 / steps  // 200ms 内完成
    const volumeStep = (startVolume - DUCK_VOLUME) / steps
    let currentStep = 0

    fadeTimer = setInterval(() => {
      currentStep++
      if (currentAudio) {
        currentAudio.volume = Math.max(DUCK_VOLUME, startVolume - volumeStep * currentStep)
      }
      if (currentStep >= steps) {
        cancelFade()
        if (currentAudio) currentAudio.volume = DUCK_VOLUME
      }
    }, stepTime)
  }

  /**
   * 取消音频闪避 - TTS 停止时恢复 BGM 音量
   */
  function unduck(): void {
    if (!currentAudio || !isDucked.value) return

    console.log('[BGM] 取消闪避: 恢复音量')
    isDucked.value = false

    // 淡入恢复到正常音量
    cancelFade()
    const targetVolume = options.volume?.() ?? normalVolume
    const startVolume = currentAudio.volume
    const steps = 10
    const stepTime = 300 / steps  // 300ms 内完成
    const volumeStep = (targetVolume - startVolume) / steps
    let currentStep = 0

    fadeTimer = setInterval(() => {
      currentStep++
      if (currentAudio) {
        currentAudio.volume = Math.min(targetVolume, startVolume + volumeStep * currentStep)
      }
      if (currentStep >= steps) {
        cancelFade()
        if (currentAudio) currentAudio.volume = targetVolume
      }
    }, stepTime)
  }

  // 监听音量设置变化
  if (options.volume) {
    watch(options.volume, (newVolume) => {
      // 如果正在闪避状态，只更新保存的正常音量，不改变当前音量
      if (isDucked.value) {
        normalVolume = newVolume
      } else {
        setVolume(newVolume)
      }
    })
  }

  return {
    isPlaying,
    isDucked,
    play,
    stop,
    setVolume,
    duck,      // TTS 播放时调用
    unduck,    // TTS 停止时调用
    unlock,
    preload: unlock,  // 兼容
    tryResumePending: unlock,  // 兼容
  }
}
