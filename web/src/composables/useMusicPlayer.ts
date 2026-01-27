/**
 * 音乐播放器 Composable
 * 用于播放儿歌，支持语音控制
 */

import { ref, computed } from 'vue'
import { getSongs, getSongAudioUrl, type Song } from '@/api/songs'

export interface MusicPlayerOptions {
  volume?: number
  onSongEnd?: () => void
}

// 全局状态（单例模式）
const songs = ref<Song[]>([])
const currentSong = ref<Song | null>(null)
const isPlaying = ref(false)
const isPaused = ref(false)
const isDucked = ref(false)  // 语音检测时降低音量

let audio: HTMLAudioElement | null = null
let normalVolume = 0.8
const DUCK_VOLUME = 0.2  // 语音检测时的音量

/**
 * 加载歌曲列表
 */
async function loadSongs(): Promise<void> {
  if (songs.value.length > 0) return
  try {
    songs.value = await getSongs()
    console.log('[Music] 已加载', songs.value.length, '首歌曲')
  } catch (e) {
    console.error('[Music] 加载歌曲列表失败:', e)
  }
}

/**
 * 根据关键词查找歌曲
 */
function findSong(keyword: string): Song | null {
  const kw = keyword.toLowerCase()

  for (const song of songs.value) {
    // 精确匹配标题
    if (song.title === keyword || song.title_en.toLowerCase() === kw) {
      return song
    }
    // 关键词匹配
    for (const k of song.keywords) {
      if (kw.includes(k.toLowerCase()) || k.toLowerCase().includes(kw)) {
        return song
      }
    }
  }

  return null
}

/**
 * 随机获取一首歌曲
 */
function getRandomSong(): Song | null {
  if (songs.value.length === 0) return null
  const index = Math.floor(Math.random() * songs.value.length)
  return songs.value[index]
}

export function useMusicPlayer(options: MusicPlayerOptions = {}) {

  /**
   * 播放指定歌曲
   */
  function play(song: Song): void {
    console.log('[Music] 播放:', song.title)

    // 停止当前播放
    if (audio) {
      audio.pause()
      audio.src = ''
    }

    currentSong.value = song
    audio = new Audio(getSongAudioUrl(song.file))
    audio.volume = options.volume ?? normalVolume

    audio.onended = () => {
      console.log('[Music] 播放结束:', song.title)
      isPlaying.value = false
      isPaused.value = false
      currentSong.value = null
      options.onSongEnd?.()
    }

    audio.onerror = (e) => {
      console.error('[Music] 播放错误:', e)
      isPlaying.value = false
      isPaused.value = false
      currentSong.value = null
    }

    audio.play().then(() => {
      isPlaying.value = true
      isPaused.value = false
      setupMediaSession(song)
    }).catch(e => {
      console.error('[Music] 播放失败:', e)
    })
  }

  /**
   * 播放歌曲（按名称或随机）
   */
  async function playSong(name?: string): Promise<Song | null> {
    await loadSongs()

    let song: Song | null = null

    if (name) {
      song = findSong(name)
      if (!song) {
        console.log('[Music] 未找到歌曲:', name, '，随机播放')
        song = getRandomSong()
      }
    } else {
      song = getRandomSong()
    }

    if (song) {
      play(song)
      return song
    }

    console.warn('[Music] 没有可播放的歌曲')
    return null
  }

  /**
   * 暂停
   */
  function pause(): void {
    if (audio && isPlaying.value && !isPaused.value) {
      audio.pause()
      isPaused.value = true
      console.log('[Music] 已暂停')
    }
  }

  /**
   * 继续播放
   */
  function resume(): void {
    if (audio && isPaused.value) {
      audio.play()
      isPaused.value = false
      console.log('[Music] 继续播放')
    }
  }

  /**
   * 停止
   */
  function stop(): void {
    if (audio) {
      audio.pause()
      audio.src = ''
      audio = null
    }
    isPlaying.value = false
    isPaused.value = false
    currentSong.value = null
    clearMediaSession()
    console.log('[Music] 已停止')
  }

  /**
   * 下一首
   */
  async function next(): Promise<Song | null> {
    stop()
    return playSong()
  }

  /**
   * 设置音量
   */
  function setVolume(volume: number): void {
    normalVolume = Math.max(0, Math.min(1, volume))
    if (audio && !isDucked.value) {
      audio.volume = normalVolume
    }
  }

  /**
   * 语音检测时降低音量
   */
  function duck(): void {
    if (!audio || isDucked.value) return
    console.log('[Music] 音量闪避')
    isDucked.value = true
    audio.volume = DUCK_VOLUME
  }

  /**
   * 恢复正常音量
   */
  function unduck(): void {
    if (!audio || !isDucked.value) return
    console.log('[Music] 恢复音量')
    isDucked.value = false
    audio.volume = normalVolume
  }

  /**
   * 设置 Media Session
   */
  function setupMediaSession(song: Song): void {
    if (!('mediaSession' in navigator)) return

    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: song.title,
        artist: song.title_en,
        album: '儿歌',
        artwork: [
          { src: '/rabbit.svg', sizes: '512x512', type: 'image/svg+xml' },
        ],
      })

      navigator.mediaSession.setActionHandler('play', resume)
      navigator.mediaSession.setActionHandler('pause', pause)
      navigator.mediaSession.setActionHandler('stop', stop)
      navigator.mediaSession.setActionHandler('nexttrack', () => next())

    } catch (e) {
      console.warn('[Music] Media Session 设置失败:', e)
    }
  }

  /**
   * 清除 Media Session
   */
  function clearMediaSession(): void {
    if (!('mediaSession' in navigator)) return

    try {
      navigator.mediaSession.metadata = null
      navigator.mediaSession.setActionHandler('play', null)
      navigator.mediaSession.setActionHandler('pause', null)
      navigator.mediaSession.setActionHandler('stop', null)
      navigator.mediaSession.setActionHandler('nexttrack', null)
    } catch (e) {
      // 忽略
    }
  }

  return {
    // 状态
    songs,
    currentSong,
    isPlaying,
    isPaused,
    isDucked,

    // 方法
    loadSongs,
    playSong,
    pause,
    resume,
    stop,
    next,
    setVolume,
    duck,
    unduck,
  }
}
