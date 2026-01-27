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
  let currentAudio: HTMLAudioElement | null = null
  let readyToPlay = false  // 音频是否已解锁
  let currentTrack: typeof BGM_LIST[0] | null = null
  let fadeTimer: ReturnType<typeof setInterval> | null = null  // 淡入淡出定时器

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
   */
  function unlock(): void {
    if (readyToPlay) return

    console.log('[BGM] 尝试解锁音频...')

    // 创建一个短音频来解锁
    const audio = new Audio()
    audio.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA='
    audio.volume = 0.001

    audio.play().then(() => {
      audio.pause()
      readyToPlay = true
      console.log('[BGM] 音频已解锁')
    }).catch(e => {
      console.warn('[BGM] 解锁失败:', e)
    })
  }

  /**
   * 播放背景音乐
   * @param bgmId 可选，指定要播放的 BGM 文件名（如 "sweet-dreams.mp3" 或 "custom/xxx.mp3"）
   */
  function play(bgmId?: string | null): void {
    console.log('[BGM] play() 被调用, bgmId:', bgmId, 'isPlaying:', isPlaying.value)

    if (options.enabled && !options.enabled()) {
      console.log('[BGM] 背景音乐已禁用')
      return
    }

    if (isPlaying.value) {
      console.log('[BGM] 已在播放中')
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

    const audio = new Audio(track.url)
    audio.loop = true
    audio.volume = 0

    // 监听加载事件
    audio.addEventListener('canplaythrough', () => {
      console.log('[BGM] 音频已加载完成')
    })

    audio.addEventListener('error', (e) => {
      console.error('[BGM] 音频加载错误:', e)
    })

    // 尝试播放
    const playPromise = audio.play()

    if (playPromise !== undefined) {
      playPromise.then(() => {
        currentAudio = audio
        isPlaying.value = true
        readyToPlay = true  // 成功播放说明已解锁
        fadeIn(audio, options.volume?.() ?? 0.6, 2000)
        setupMediaSession(track)
        console.log('[BGM] 播放成功')
      }).catch(e => {
        console.warn('[BGM] 播放失败:', e.name, e.message)
        // 如果是自动播放策略阻止，等待用户下次交互
        if (e.name === 'NotAllowedError') {
          console.log('[BGM] 需要用户交互才能播放，等待下次交互...')
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

  // 监听音量设置变化
  if (options.volume) {
    watch(options.volume, (newVolume) => {
      setVolume(newVolume)
    })
  }

  return {
    isPlaying,
    play,
    stop,
    setVolume,
    unlock,
    preload: unlock,  // 兼容
    tryResumePending: unlock,  // 兼容
  }
}
