<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useChat } from '@/composables/useChat'
import { useAudioRecorder } from '@/composables/useAudioRecorder'
import { useTTSPlayer } from '@/composables/useTTSPlayer'
import { useWebRTCVAD } from '@/composables/useWebRTCVAD'
import { useSileroVAD } from '@/composables/useSileroVAD'
import { useFunASRVAD } from '@/composables/useFunASRVAD'
import { useBGM } from '@/composables/useBGM'
import { useMusicPlayer } from '@/composables/useMusicPlayer'
import { useVideoCapture } from '@/composables/useVideoCapture'
import { useVoiceCall, CallState } from '@/composables/useVoiceCall'
import { useSettingsStore, BACKGROUNDS, AVATARS, type AvatarType } from '@/stores/settings'
import { transcribe } from '@/api/asr'
import { analyzeVideo } from '@/api/video'
import { FUNASR_WS_URL } from '@/api/config'
import ChatArea from '@/components/ChatArea.vue'
import RightPanel from '@/components/RightPanel.vue'
import Avatar3D from '@/components/Avatar3D.vue'

const settings = useSettingsStore()
const chat = useChat()

// 儿歌播放器
const musicPlayer = useMusicPlayer({
  volume: 0.8,
  onSongEnd: () => {
    console.log('[Music] 歌曲播放结束')
  },
})

// 背景音乐播放器
const bgm = useBGM({
  volume: () => settings.bgmVolume,
  enabled: () => settings.bgmEnabled,
})

// 页面关闭时停止背景音乐和儿歌
const handleBeforeUnload = () => {
  bgm.stop()
  musicPlayer.stop()
}

onMounted(() => {
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onUnmounted(() => {
  bgm.stop()
  musicPlayer.stop()
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

// 状态
const inputText = ref('')
const showSettings = ref(false)
const isTranscribing = ref(false) // 是否正在语音转文字
// 附件状态（图片或视频）
const pendingMedia = ref<{ type: 'image' | 'video'; data: string; blob?: Blob } | null>(null)
const mediaInputRef = ref<HTMLInputElement | null>(null)

// 摄像头状态（独立开关）
const isCameraOn = ref(false)
const cameraPreviewRef = ref<HTMLVideoElement | null>(null)
const isAvatarMain = ref(true)  // AI角色是否为主画面（true=AI主/摄像头辅，false=摄像头主/AI辅）
const isCameraMinimized = ref(false)  // 非通话时摄像头是否最小化到右上角
const isAnalyzingMedia = ref(false)  // 是否正在分析媒体
const isMuted = ref(false)  // 是否静音（通话中）

// 视频捕获
const videoCapture = useVideoCapture({
  maxDuration: 60,
  frameInterval: 3000,  // 实时模式 3 秒采样一次
  resolution: { width: 640, height: 480 }
})

// 当前选择的背景和头像
const currentBackground = computed(() =>
  BACKGROUNDS.find(bg => bg.id === settings.background) || BACKGROUNDS[0]
)
const currentAvatar = computed(() =>
  AVATARS.find(av => av.id === settings.avatar) || AVATARS[0]
)

// 将 avatar ID 映射到 3D 宠物类型
const mascotType = computed(() => {
  const avatarId = settings.avatar as string
  if (avatarId === 'cat') return 'cat'
  if (avatarId === 'bear') return 'bear'
  if (avatarId === 'dino') return 'dino'
  if (avatarId === 'panda') return 'panda'
  return 'rabbit' // 默认兔子
})

// 背景样式
const backgroundStyle = computed(() => ({
  background: `linear-gradient(135deg, ${currentBackground.value.colors[0]} 0%, ${currentBackground.value.colors[1]} 50%, ${currentBackground.value.colors[2]} 100%)`
}))

// 唤醒词 ASR 识别函数（用于关键词打断模式）
async function transcribeForWakeWord(blob: Blob): Promise<string> {
  try {
    const result = await transcribe(blob)
    return result.success ? result.text : ''
  } catch {
    return ''
  }
}

// 打断词列表（只有 TTS 播放时才需要唤醒词验证）
const getWakeWords = (): string[] => {
  // 只有 TTS 播放中才需要唤醒词（用于打断）
  // 正常对话时返回空数组，VAD 检测到语音就直接触发
  if (!ttsPlayer?.isPlaying?.value) {
    return []
  }

  // 实时打断模式：不需要关键词，检测到语音就打断
  if (settings.vadInstantInterrupt) {
    return []
  }

  // 关键词打断模式：需要说唤醒词才能打断 TTS
  const name = settings.assistantName || '小智'
  const aliases = settings.assistantAliases || []
  return [
    name,
    ...aliases,
    '等等', '等一下', '等会', '等会儿',
    '停', '停一下', '停停', '暂停',
    '不对', '不是', '不要', '不用',
    '好了', '可以了', '行了', '够了',
    '听我说', '我说', '我想说',
    '安静', '别说了', '闭嘴',
  ]
}

// VAD 语音检测回调（由 voiceCall 状态机处理）
// 注意：voiceCall 稍后初始化，这里用函数引用
let voiceCall: ReturnType<typeof useVoiceCall>

function handleVADSpeechStart() {
  console.log('[VAD] 检测到用户说话')

  // 静音时忽略语音检测
  if (isMuted.value) {
    console.log('[VAD] 已静音，忽略')
    return
  }

  // 儿歌播放中降低音量
  if (musicPlayer.isPlaying.value) {
    musicPlayer.duck()
  }
  // 通知状态机
  voiceCall?.onVoiceDetected()
}

function handleVADSpeechEnd() {
  console.log('[VAD] 检测到语音结束')
  // VAD 的 onSpeechEnd 不直接触发发送
  // 由 useAudioRecorder 的静音检测来判断（用户可配置 silenceDuration）
}

// WebRTC VAD（基于频谱分析）
const webrtcVAD = useWebRTCVAD({
  ignoreTime: () => settings.vadIgnoreTime,
  wakeWordTimeout: () => settings.vadWakeWordTimeout,
  wakeWords: getWakeWords,
  transcribeFn: transcribeForWakeWord,
  onWakeWordDetected: (word) => console.log(`[WebRTC VAD] 中断词: "${word}"`),
  onSpeechStart: handleVADSpeechStart,
  onSpeechEnd: handleVADSpeechEnd,
})

// Silero VAD（内置后端，通过 /ws/vad 访问）
const getVadWsUrl = () => {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/ws/vad`
}
const sileroVAD = useSileroVAD({
  wsUrl: getVadWsUrl(),
  backend: () => settings.vadType,
  wakeWords: getWakeWords,
  transcribeFn: transcribeForWakeWord,
  ignoreTime: () => settings.vadIgnoreTime,
  onWakeWordDetected: (word, text) => console.log(`[Silero VAD] 中断词: "${word}"`),
  onSpeechStart: handleVADSpeechStart,
  onSpeechEnd: handleVADSpeechEnd,
})

// FunASR VAD（基于服务端 AI 模型）
const funasrVAD = useFunASRVAD({
  wsUrl: FUNASR_WS_URL,
  ignoreTime: () => settings.vadIgnoreTime,
  wakeWords: getWakeWords,
  transcribeFn: transcribeForWakeWord,
  onSpeechStart: handleVADSpeechStart,
  onSpeechEnd: handleVADSpeechEnd,
  onWakeWordDetected: (word, text) => console.log(`[FunASR VAD] 中断词: "${word}"`),
})

// 统一 VAD 接口
// - ten/silero/funasr: 连接后端 /ws/vad WebSocket（后端根据配置选择 VAD 后端）
// - webrtc: 前端频谱分析
const vad = {
  start: async () => {
    if (settings.vadType === 'funasr') {
      await funasrVAD.start()
    } else if (settings.vadType === 'silero' || settings.vadType === 'ten') {
      // ten 和 silero 都连接后端 /ws/vad
      await sileroVAD.start()
    } else if (settings.vadType === 'webrtc') {
      await webrtcVAD.start()
    }
  },
  stop: () => {
    webrtcVAD.stop()
    sileroVAD.stop()
    funasrVAD.stop()
  },
  get isActive() {
    if (settings.vadType === 'funasr') return funasrVAD.isActive
    if (settings.vadType === 'silero' || settings.vadType === 'ten') return sileroVAD.isActive
    if (settings.vadType === 'webrtc') return webrtcVAD.isActive
    return { value: false }
  },
  get isSpeaking() {
    if (settings.vadType === 'funasr') return funasrVAD.isSpeaking
    if (settings.vadType === 'silero' || settings.vadType === 'ten') return sileroVAD.isSpeaking
    if (settings.vadType === 'webrtc') return webrtcVAD.isSpeaking
    return { value: false }
  },
  get isLoading() {
    return sileroVAD.isLoading || funasrVAD.isConnecting
  },
}

// 监听 VAD 类型变化，切换时停止当前 VAD
watch(() => settings.vadType, (newType, oldType) => {
  if (newType !== oldType) {
    console.log(`[VAD] 切换类型: ${oldType} -> ${newType}`)
    // 停止所有 VAD
    webrtcVAD.stop()
    sileroVAD.stop()
    funasrVAD.stop()
  }
})

// 通话录音器（带静音检测自动停止）
const callRecorder = useAudioRecorder({
  silenceThreshold: () => settings.silenceThreshold,
  silenceDuration: () => settings.silenceDuration,
  onSilenceDetected: () => {
    console.log('[Call] 检测到静音')
    if (settings.autoSend) {
      voiceCall?.onSilenceDetected()
    }
  },
})

// 监听录音状态，录音时降低儿歌音量
watch(() => callRecorder.isRecording.value, (recording) => {
  if (musicPlayer.isPlaying.value) {
    recording ? musicPlayer.duck() : musicPlayer.unduck()
  }
})

// 语音转文字录音器（不自动停止，手动控制）
const transcribeRecorder = useAudioRecorder({})

// TTS 播放器
const ttsPlayer = useTTSPlayer({
  gain: () => settings.ttsGain,
  model: () => settings.ttsModel,
  voice: () => settings.ttsVoice,
  customVoiceId: () => settings.ttsCustomVoiceId,
  speed: () => settings.ttsSpeed,
  onPlayStart: async () => {
    console.log('[TTS] 开始播放')
    // 通话中启动 VAD 检测打断
    if (settings.vadEnabled && voiceCall?.isInCall.value) {
      try {
        await vad.start()
      } catch (error) {
        console.error('[VAD] 启动失败:', error)
      }
    }
  },
  onPlayEnd: () => {
    console.log('[TTS] 播放结束')
    // 只有在 LLM 处理完成后才触发 TTS_ENDED
    // 否则可能是 TTS 队列暂时为空，LLM 还在输出新句子
    if (!chat.isLoading.value) {
      voiceCall?.onTtsEnded()
    }
  },
})

// ============ 语音通话状态机 ============
voiceCall = useVoiceCall({
  vad,
  recorder: callRecorder,
  tts: ttsPlayer,
  chat,
  transcribe,
  vadEnabled: () => settings.vadEnabled,
  ttsEnabled: () => settings.ttsEnabled,
  captureFrame: () => {
    if (isCameraOn.value && videoCapture.isPreviewActive.value) {
      return videoCapture.captureFrame()
    }
    return null
  },
  unlockAudio: async () => {
    bgm.unlock()
    musicPlayer.unlock()
  },
})

// 监听 TTS 播放状态，实现音频闪避（TTS 播放时降低 BGM 和儿歌音量）
watch(() => ttsPlayer.isPlaying.value, (playing) => {
  if (bgm.isPlaying.value) {
    if (playing) {
      bgm.duck()  // TTS 开始播放，降低 BGM 音量
    } else {
      bgm.unduck()  // TTS 停止播放，恢复 BGM 音量
    }
  }
  // 儿歌音量闪避
  if (musicPlayer.isPlaying.value) {
    if (playing) {
      musicPlayer.duck()
    } else {
      musicPlayer.unduck()
    }
  }
})

// 监听儿歌播放状态变化
watch(() => musicPlayer.isPlaying.value, (playing) => {
  if (!voiceCall.isInCall.value) return

  if (playing) {
    // 儿歌开始播放，停止当前录音，启用 VAD 监听
    if (callRecorder.isRecording.value) {
      console.log('[Call] 儿歌开始，停止录音，启用 VAD')
      callRecorder.stopRecording()
    }
    vad.start()
  } else {
    // 儿歌停止
    console.log('[Call] 儿歌停止')
    vad.stop()
  }
})

// 监听音乐控制动作（来自 LLM）
watch(() => chat.musicAction.value, async (action) => {
  if (!action) return

  console.log('[Music] 收到控制动作:', action)

  switch (action.type) {
    case 'play':
      if (action.song) {
        // 播放指定歌曲
        await musicPlayer.loadSongs()
        const song = musicPlayer.songs.value.find(s => s.id === action.song!.id)
        if (song) {
          musicPlayer.playSong(song.title)
        } else {
          // 如果找不到，尝试随机播放
          musicPlayer.playSong()
        }
      } else {
        musicPlayer.playSong()
      }
      break
    case 'pause':
      musicPlayer.pause()
      break
    case 'resume':
      musicPlayer.resume()
      break
    case 'stop':
      musicPlayer.stop()
      break
    case 'next':
      if (action.song) {
        await musicPlayer.loadSongs()
        musicPlayer.playSong(action.song.title)
      } else {
        musicPlayer.next()
      }
      break
  }

  // 清除动作，避免重复处理
  chat.clearMusicAction()
})

// 计算属性
const canSend = computed(() => (inputText.value.trim() || pendingMedia.value) && !chat.isLoading.value && !isAnalyzingMedia.value)

// 状态文字（通话中显示）- 使用状态机的状态
const statusText = computed(() => {
  if (sileroVAD.isLoading.value || funasrVAD.isConnecting.value) return '加载VAD模型...'

  switch (voiceCall.state.value) {
    case CallState.LISTENING:
      if (funasrVAD.isSpeaking.value || sileroVAD.isSpeaking.value || webrtcVAD.isSpeaking.value) {
        return '检测到语音...'
      }
      return '等待说话...'
    case CallState.RECORDING:
      return '正在听...'
    case CallState.PROCESSING:
      return '思考中...'
    case CallState.SPEAKING:
      if (funasrVAD.isCheckingWakeWord.value || webrtcVAD.isCheckingWakeWord.value) {
        return '验证中断词...'
      }
      if (funasrVAD.isSpeaking.value || sileroVAD.isSpeaking.value || webrtcVAD.isSpeaking.value) {
        return '检测到语音...'
      }
      return '正在说...'
    default:
      return ''
  }
})

// ============ 文字模式 ============

// 发送文字消息（不播放语音）
async function handleSend() {
  if (!canSend.value) return

  const text = inputText.value.trim()
  const media = pendingMedia.value
  inputText.value = ''
  clearPendingMedia()

  // 用户交互时预加载 BGM（移动端需要在点击时预加载）
  bgm.preload()

  // 根据媒体类型处理
  if (media?.type === 'video' && media.blob) {
    // 视频：调用视频分析 API
    isAnalyzingMedia.value = true
    chat.addUserMessage(text)
    try {
      let response = ''
      for await (const event of analyzeVideo(media.blob, text)) {
        if (event.type === 'token' && event.content) {
          response += event.content
          chat.streamingContent.value = response
        }
      }
      chat.addAssistantMessage(response)
      chat.streamingContent.value = ''
    } finally {
      isAnalyzingMedia.value = false
    }
  } else if (media?.type === 'image') {
    // 图片：走 chat API
    await chat.send(text, undefined, media.data)
  } else if (isCameraOn.value && videoCapture.isPreviewActive.value) {
    // 摄像头开启：捕获当前帧
    const frame = videoCapture.captureFrame()
    const frameImage = frame ? `data:image/jpeg;base64,${frame}` : undefined
    await chat.send(text, undefined, frameImage)
  } else {
    // 纯文字
    await chat.send(text)
  }
}

// 处理媒体选择（图片或视频）
function handleMediaSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const isVideo = file.type.startsWith('video/')
  const isImage = file.type.startsWith('image/')

  if (isVideo) {
    // 视频：保存 blob 用于上传
    const url = URL.createObjectURL(file)
    pendingMedia.value = {
      type: 'video',
      data: url,
      blob: file
    }
    // 如果输入框为空，添加默认提示
    if (!inputText.value.trim()) {
      inputText.value = '分析这段视频'
    }
  } else if (isImage) {
    // 图片：压缩并转 base64
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        // 压缩图片（最大 800px）
        const maxSize = 800
        let { width, height } = img
        if (width > maxSize || height > maxSize) {
          if (width > height) {
            height = (height / width) * maxSize
            width = maxSize
          } else {
            width = (width / height) * maxSize
            height = maxSize
          }
        }

        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')!
        ctx.drawImage(img, 0, 0, width, height)

        // 转为 base64（JPEG 格式，质量 0.8）
        const base64 = canvas.toDataURL('image/jpeg', 0.8)
        pendingMedia.value = {
          type: 'image',
          data: base64
        }

        // 如果输入框为空，添加默认提示
        if (!inputText.value.trim()) {
          inputText.value = '这是什么？'
        }
      }
      img.src = e.target?.result as string
    }
    reader.readAsDataURL(file)
  }

  // 重置 input
  input.value = ''
}

// 清除待发送媒体
function clearPendingMedia() {
  if (pendingMedia.value?.type === 'video' && pendingMedia.value.data) {
    URL.revokeObjectURL(pendingMedia.value.data)
  }
  pendingMedia.value = null
}

// 触发媒体选择
function triggerMediaSelect() {
  mediaInputRef.value?.click()
}

// 语音转文字（填充到输入框）
async function toggleTranscribe() {
  if (transcribeRecorder.isRecording.value) {
    // 停止录音，进行识别
    isTranscribing.value = true
    try {
      const audioBlob = await transcribeRecorder.stopRecording()
      const result = await transcribe(audioBlob)
      if (result.success && result.text) {
        // 将识别结果填充到输入框
        inputText.value = (inputText.value + ' ' + result.text).trim()
      }
    } catch (error) {
      console.error('Transcribe error:', error)
    } finally {
      isTranscribing.value = false
    }
  } else {
    // 开始录音
    try {
      await transcribeRecorder.startRecording()
    } catch (error) {
      console.error('Failed to start transcribe recording:', error)
    }
  }
}

// ============ 通话模式（使用状态机） ============

function toggleCall() {
  if (voiceCall.isInCall.value) {
    voiceCall.endCall()
    isMuted.value = false  // 挂断时重置静音状态
  } else {
    voiceCall.startCall()
  }
}

// 切换静音（通话中）
function toggleMute() {
  isMuted.value = !isMuted.value
  console.log('[Call] 静音:', isMuted.value)
}

// 键盘事件
function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// 切换背景音乐
function toggleBGM() {
  // 用户交互时解锁音频（移动端需要）
  bgm.unlock()

  if (bgm.isPlaying.value) {
    bgm.stop()
  } else {
    bgm.play()
  }
}

// 清空对话
function clearChat() {
  chat.clear()
}

// ============ 摄像头控制 ============

// 切换摄像头
async function toggleCamera() {
  if (isCameraOn.value) {
    // 关闭摄像头
    videoCapture.stopPreview()
    isCameraOn.value = false
    console.log('[Camera] Stopped')
  } else {
    // 开启摄像头：先设置状态，等元素渲染后再启动预览
    isCameraOn.value = true
    console.log('[Camera] Turning on...')
    // 预览会在 watch(cameraPreviewRef) 中自动启动
  }
}

// 监听摄像头预览元素变化
watch(cameraPreviewRef, async (el, oldEl) => {
  if (el && isCameraOn.value) {
    // 如果预览未启动，启动预览
    if (!videoCapture.isPreviewActive.value) {
      try {
        await videoCapture.startPreview(el)
      } catch (error) {
        console.error('[Camera] Auto start failed:', error)
        isCameraOn.value = false
      }
    } else if (el !== oldEl) {
      // 如果预览已启动但元素变了（切换了位置），重新连接流
      console.log('[Camera] Video element changed, reconnecting stream...')
      videoCapture.stopPreview()
      try {
        await videoCapture.startPreview(el)
      } catch (error) {
        console.error('[Camera] Reconnect failed:', error)
        isCameraOn.value = false
      }
    }
  }
})
</script>

<template>
  <!-- 移动端：全屏布局 / 桌面端：居中卡片 -->
  <div class="fixed inset-0 md:relative md:inset-auto md:min-h-screen md:flex md:items-center md:justify-center md:p-4" :style="backgroundStyle">
    <!-- 装饰性元素（仅桌面端） -->
    <div class="hidden md:block fixed inset-0 pointer-events-none overflow-hidden" :style="backgroundStyle">
      <div class="star" style="top: 15%; left: 15%; animation-delay: 0s;"></div>
      <div class="star" style="top: 25%; right: 20%; animation-delay: 1s;"></div>
      <div class="star" style="top: 70%; left: 10%; animation-delay: 2s;"></div>
      <div class="star" style="top: 80%; right: 15%; animation-delay: 0.5s;"></div>
      <div class="heart" style="top: 30%; left: 8%;"></div>
      <div class="heart" style="top: 65%; right: 12%;"></div>
    </div>

    <!-- 主容器 -->
    <div class="h-full w-full md:h-[85vh] md:max-h-[800px] md:w-auto bg-white md:rounded-3xl md:shadow-2xl flex relative z-10 overflow-hidden">
      <!-- 聊天区域 -->
      <div
        class="flex-1 flex flex-col w-full md:w-[420px] md:flex-none"
        :class="{ 'hidden md:flex': showSettings }"
      >
        <!-- 头部 -->
        <header class="flex-shrink-0 bg-gradient-to-r from-pink-300 via-rose-300 to-orange-300 px-4 py-3 flex items-center justify-between safe-top">
          <div class="flex items-center gap-2">
            <span class="text-white text-lg font-semibold">{{ settings.assistantName || '小智' }}</span>
          </div>
          <div class="flex items-center gap-2">
            <!-- BGM 开关按钮 -->
            <button
              @click="toggleBGM"
              :class="[
                'p-1.5 rounded-lg transition-colors',
                bgm.isPlaying.value ? 'bg-white/40' : 'bg-white/20 hover:bg-white/30'
              ]"
              :title="bgm.isPlaying.value ? '关闭背景音乐' : '开启背景音乐'"
            >
              <svg v-if="bgm.isPlaying.value" class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>
              </svg>
              <svg v-else class="w-5 h-5 text-white/60" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>
                <path d="M3.27 3L2 4.27l9 9v.28c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4v-1.73l5.73 5.73L20 19.73 3.27 3z" fill-opacity="0.3"/>
              </svg>
            </button>
            <button
              @click="clearChat"
              class="px-3 py-1.5 bg-white/20 hover:bg-white/30 text-white text-sm rounded-lg transition-colors"
            >
              清空
            </button>
            <button
              @click="showSettings = !showSettings"
              :class="[
                'p-1.5 rounded-lg transition-colors',
                showSettings ? 'bg-white/40' : 'bg-white/20 hover:bg-white/30'
              ]"
              title="设置/故事"
            >
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </header>

      <!-- 主内容区 - 根据模式显示不同内容 -->
      <div class="flex-1 min-h-0 flex flex-col">
        <!-- 通话中：显示角色头像和/或摄像头预览 -->
        <template v-if="voiceCall.isInCall.value">
          <div class="flex-1 flex flex-col items-center justify-center pb-16 bg-gradient-to-b from-white/50 to-white relative">

            <!-- 摄像头视频（单一元素，通过CSS切换位置） -->
            <div
              v-if="isCameraOn"
              class="transition-all duration-300 ease-in-out rounded-2xl overflow-hidden shadow-lg bg-black"
              :class="isAvatarMain
                ? 'absolute top-4 right-4 w-20 h-28 cursor-pointer z-20 border-2 border-white hover:scale-105'
                : 'w-72 h-96'"
              @click.stop="isAvatarMain && (isAvatarMain = false)"
            >
              <video
                ref="cameraPreviewRef"
                autoplay
                muted
                playsinline
                class="w-full h-full object-cover"
                :style="{ transform: videoCapture.isFrontCamera.value ? 'scaleX(-1)' : 'none' }"
              ></video>
              <!-- 小窗时：切换提示图标 -->
              <div v-if="isAvatarMain" class="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 hover:opacity-100 transition-opacity">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                </svg>
              </div>
              <!-- 小窗时：切换摄像头按钮 -->
              <button
                v-if="isAvatarMain"
                @click.stop="videoCapture.switchCamera()"
                class="absolute bottom-1 right-1 w-5 h-5 bg-black/50 text-white rounded-full flex items-center justify-center"
                title="切换前后摄像头"
              >
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <!-- 主画面时：通话中红点 -->
              <div v-if="!isAvatarMain" class="absolute top-2 right-2 w-4 h-4 bg-red-500 rounded-full border-2 border-white animate-pulse"></div>
            </div>

            <!-- AI角色（单一元素，通过CSS切换位置） -->
            <div
              class="transition-all duration-300 ease-in-out"
              :class="isCameraOn && !isAvatarMain
                ? 'absolute top-4 right-4 w-20 h-28 cursor-pointer z-20 rounded-xl overflow-hidden shadow-lg border-2 border-white bg-gradient-to-b from-pink-50 to-white flex items-center justify-center hover:scale-105'
                : 'relative'"
              @click.stop="isCameraOn && !isAvatarMain && (isAvatarMain = true)"
            >
              <Avatar3D
                :type="mascotType"
                :is-listening="voiceCall.isRecording.value"
                :is-thinking="voiceCall.isProcessing.value"
                :is-speaking="voiceCall.isSpeaking.value"
                :size="isCameraOn && !isAvatarMain ? 70 : 280"
              />
              <!-- 小窗时：切换提示图标 -->
              <div v-if="isCameraOn && !isAvatarMain" class="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 hover:opacity-100 transition-opacity rounded-xl">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                </svg>
              </div>
              <!-- 主画面时：通话中红点 -->
              <div v-if="!isCameraOn || isAvatarMain" class="absolute top-0 right-4 w-5 h-5 bg-red-500 rounded-full border-2 border-white animate-pulse z-10"></div>
            </div>

            <!-- 状态指示 -->
            <div class="flex gap-2 mt-3">
              <span class="w-2.5 h-2.5 rounded-full bg-green-400" title="已连接"></span>
              <span
                class="w-2.5 h-2.5 rounded-full transition-colors"
                :class="voiceCall.isRecording.value ? 'bg-pink-400 animate-pulse' : 'bg-gray-300'"
                title="录音状态"
              ></span>
              <span
                class="w-2.5 h-2.5 rounded-full transition-colors"
                :class="voiceCall.isSpeaking.value ? 'bg-orange-400 animate-pulse' : 'bg-gray-300'"
                title="播放状态"
              ></span>
              <span
                class="w-2.5 h-2.5 rounded-full transition-colors"
                :class="voiceCall.isListening.value ? 'bg-blue-400 animate-pulse' : 'bg-gray-300'"
                title="VAD检测"
              ></span>
            </div>

            <!-- 状态文字和音量显示 -->
            <div class="mt-4 text-xs text-gray-400">
              {{ statusText }} | 音量: {{ callRecorder.audioLevel.value }}
            </div>
          </div>
        </template>

        <!-- 非通话时：显示聊天消息或欢迎界面 -->
        <template v-else>
          <div class="flex-1 min-h-0 flex flex-col relative">
            <!-- 摄像头预览（右上角，大/小切换） -->
            <div
              v-if="isCameraOn"
              class="absolute top-2 right-2 z-20 cursor-pointer transition-all duration-300 ease-in-out"
              :class="isCameraMinimized ? 'w-24 h-32' : 'w-44 h-60'"
              @click="isCameraMinimized = !isCameraMinimized"
            >
              <div class="w-full h-full rounded-xl overflow-hidden shadow-lg bg-black border-2 border-white hover:scale-105 transition-transform">
                <video
                  ref="cameraPreviewRef"
                  autoplay
                  muted
                  playsinline
                  class="w-full h-full object-cover"
                  :style="{ transform: videoCapture.isFrontCamera.value ? 'scaleX(-1)' : 'none' }"
                ></video>
                <!-- 缩放图标 -->
                <div class="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 hover:opacity-100 transition-opacity">
                  <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path v-if="isCameraMinimized" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                    <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
                  </svg>
                </div>
              </div>
              <!-- 切换摄像头按钮 -->
              <button
                @click.stop="videoCapture.switchCamera()"
                :class="[
                  'absolute bottom-1.5 right-1.5 bg-black/50 text-white rounded-full flex items-center justify-center hover:bg-black/70',
                  isCameraMinimized ? 'w-6 h-6' : 'w-8 h-8'
                ]"
              >
                <svg :class="isCameraMinimized ? 'w-3.5 h-3.5' : 'w-4 h-4'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
            </div>

            <!-- 聊天区域或欢迎界面 -->
            <ChatArea
              v-if="chat.messages.value.length > 0 || chat.isLoading.value"
              :messages="chat.messages.value"
              :streaming-content="chat.streamingContent.value"
              :is-loading="chat.isLoading.value"
              :current-skill="chat.currentSkill.value"
              :tool-calls="chat.toolCalls.value"
              class="flex-1 min-h-0"
            />
            <!-- 无消息时显示欢迎界面 -->
            <div v-else class="flex-1 flex flex-col items-center justify-center text-center px-8">
              <Avatar3D
                :type="mascotType"
                :size="200"
                class="mb-2"
              />
              <h2 class="text-xl font-semibold text-gray-700 mb-2">你好，我是{{ settings.assistantName || '小智' }}</h2>
              <p class="text-gray-500 text-sm mb-6">
                {{ isCameraOn ? '发送消息时会自动捕获画面' : '点击通话按钮开始对话，或输入文字发送' }}
              </p>
            </div>
          </div>
        </template>
      </div>

      <!-- 底部输入区 -->
      <footer class="flex-shrink-0 px-4 py-3 md:pb-4 bg-white safe-bottom">
        <!-- ========== 通话模式：简洁的 3 个大按钮 ========== -->
        <template v-if="voiceCall.isInCall.value">
          <!-- 状态提示 -->
          <div class="text-center text-sm text-gray-500 mb-4">
            {{ statusText }}
          </div>

          <!-- 3 个大按钮 -->
          <div class="flex items-center justify-center gap-8">
            <!-- 静音按钮 -->
            <div class="flex flex-col items-center gap-1">
              <button
                @click="toggleMute"
                :class="[
                  'w-14 h-14 rounded-full flex items-center justify-center transition-all shadow-md',
                  isMuted
                    ? 'bg-red-100 text-red-500 hover:bg-red-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                ]"
              >
                <svg v-if="isMuted" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
                </svg>
                <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
              </button>
              <span class="text-xs text-gray-500">{{ isMuted ? '取消静音' : '静音' }}</span>
            </div>

            <!-- 挂断按钮 -->
            <div class="flex flex-col items-center gap-1">
              <button
                @click="toggleCall"
                class="w-16 h-16 rounded-full flex items-center justify-center bg-red-500 hover:bg-red-600 text-white transition-all shadow-lg"
              >
                <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 8l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2M5 3a2 2 0 00-2 2v1c0 8.284 6.716 15 15 15h1a2 2 0 002-2v-3.28a1 1 0 00-.684-.948l-4.493-1.498a1 1 0 00-1.21.502l-1.13 2.257a11.042 11.042 0 01-5.516-5.517l2.257-1.128a1 1 0 00.502-1.21L9.228 3.683A1 1 0 008.279 3H5z" />
                </svg>
              </button>
              <span class="text-xs text-gray-500">挂断</span>
            </div>

            <!-- 摄像头按钮 -->
            <div class="flex flex-col items-center gap-1">
              <button
                @click="toggleCamera"
                :class="[
                  'w-14 h-14 rounded-full flex items-center justify-center transition-all shadow-md',
                  isCameraOn
                    ? 'bg-blue-100 text-blue-500 hover:bg-blue-200'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                ]"
              >
                <svg v-if="isCameraOn" class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3l18 18" />
                </svg>
              </button>
              <span class="text-xs text-gray-500">{{ isCameraOn ? '关闭' : '摄像头' }}</span>
            </div>
          </div>
        </template>

        <!-- ========== 非通话模式：输入框和按钮 ========== -->
        <template v-else>
          <!-- 待发送媒体预览 -->
          <div v-if="pendingMedia" class="mb-2 flex items-center gap-2 px-2">
            <div class="relative">
              <img v-if="pendingMedia.type === 'image'" :src="pendingMedia.data" class="w-16 h-16 object-cover rounded-lg border" />
              <video v-else :src="pendingMedia.data" class="w-16 h-16 object-cover rounded-lg border" />
              <button
                @click="clearPendingMedia"
                class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600"
              >
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <span class="text-xs text-gray-400">{{ pendingMedia.type === 'image' ? '图片' : '视频' }}已选择</span>
          </div>

          <!-- 隐藏的媒体输入 -->
          <input
            ref="mediaInputRef"
            type="file"
            accept="image/*,video/*"
            class="hidden"
            @change="handleMediaSelect"
          />

          <!-- 输入框（按钮全部在内部） -->
          <div class="flex items-center bg-gray-50 border border-gray-200 rounded-full px-2 py-1.5 focus-within:ring-2 focus-within:ring-pink-400 focus-within:border-transparent">
            <!-- 左侧按钮：附件、摄像头 -->
            <div class="flex items-center flex-shrink-0">
              <button
                @click="triggerMediaSelect"
                :disabled="chat.isLoading.value || isAnalyzingMedia"
                class="w-7 h-7 rounded-full flex items-center justify-center transition-colors bg-green-500 hover:bg-green-600 text-white disabled:bg-gray-200 disabled:text-gray-400"
                title="选择图片/视频"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              </button>
              <button
                v-if="videoCapture.isSupported.value"
                @click="toggleCamera"
                :disabled="chat.isLoading.value"
                :class="[
                  'w-7 h-7 rounded-full flex items-center justify-center transition-colors ml-0.5',
                  isCameraOn
                    ? 'bg-blue-500 hover:bg-blue-600 text-white'
                    : 'bg-gray-200 hover:bg-gray-300 text-gray-500'
                ]"
                :title="isCameraOn ? '关闭摄像头' : '开启摄像头'"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>

            <!-- 输入框 -->
            <input
              v-model="inputText"
              @keydown="handleKeydown"
              :disabled="chat.isLoading.value"
              placeholder="输入消息..."
              class="flex-1 min-w-0 bg-transparent border-none outline-none text-sm text-gray-700 placeholder-gray-400 disabled:text-gray-400 mx-2"
              inputmode="text"
              autocomplete="off"
            />

            <!-- 右侧按钮：语音、通话、发送 -->
            <div class="flex items-center flex-shrink-0">
              <button
                @click="toggleTranscribe"
                :disabled="isTranscribing"
                :class="[
                  'w-7 h-7 rounded-full flex items-center justify-center transition-colors',
                  transcribeRecorder.isRecording.value
                    ? 'bg-red-500 text-white animate-pulse'
                    : 'bg-pink-500 hover:bg-pink-600 text-white'
                ]"
                :title="transcribeRecorder.isRecording.value ? '停止录音' : '语音输入'"
              >
                <svg v-if="isTranscribing" class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <svg v-else class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                </svg>
              </button>
              <button
                @click="toggleCall"
                class="w-7 h-7 rounded-full flex items-center justify-center transition-colors ml-0.5 bg-gray-200 hover:bg-gray-300 text-gray-500"
                :title="isCameraOn ? '视频通话' : '语音通话'"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
              </button>
              <button
                @click="chat.isLoading.value ? chat.abort() : handleSend()"
                :disabled="!chat.isLoading.value && !canSend"
                :class="[
                  'w-7 h-7 rounded-full flex items-center justify-center transition-colors ml-0.5',
                  chat.isLoading.value
                    ? 'bg-blue-500 hover:bg-blue-600 text-white animate-breathing'
                    : canSend
                      ? 'bg-blue-500 hover:bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                ]"
                :title="chat.isLoading.value ? '停止生成' : '发送'"
              >
                <svg v-if="chat.isLoading.value" class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
                <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 10l7-7m0 0l7 7m-7-7v18" />
                </svg>
              </button>
            </div>
          </div>
        </template>
      </footer>
      </div>

      <!-- 右侧：设置/故事面板 -->
      <RightPanel
        :show="showSettings"
        @close="showSettings = false"
      />
    </div>
  </div>
</template>

<style scoped>
/* 动画基础 */

@keyframes ping-slow {
  0% {
    transform: scale(1);
    opacity: 0.8;
  }
  100% {
    transform: scale(1.8);
    opacity: 0;
  }
}

.animate-ping-slow {
  animation: ping-slow 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
}

.animation-delay-200 {
  animation-delay: 0.2s;
}

/* 说话时的轻微弹跳动画 */
@keyframes bounce-slow {
  0%, 100% {
    transform: translateY(0) scale(1.05);
  }
  50% {
    transform: translateY(-8px) scale(1.08);
  }
}

.animate-bounce-slow {
  animation: bounce-slow 0.6s ease-in-out infinite;
}

/* 星星装饰 */
.star {
  position: absolute;
  width: 20px;
  height: 20px;
  background: #FFD700;
  clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
  animation: twinkle 2s ease-in-out infinite;
  opacity: 0.8;
}

@keyframes twinkle {
  0%, 100% {
    transform: scale(1) rotate(0deg);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.2) rotate(15deg);
    opacity: 1;
  }
}

/* 爱心装饰 */
.heart {
  position: absolute;
  width: 20px;
  height: 20px;
  background: #FF69B4;
  transform: rotate(-45deg);
  animation: heartbeat 1.5s ease-in-out infinite;
  opacity: 0.7;
}

.heart::before,
.heart::after {
  content: '';
  position: absolute;
  width: 20px;
  height: 20px;
  background: #FF69B4;
  border-radius: 50%;
}

.heart::before {
  top: -10px;
  left: 0;
}

.heart::after {
  top: 0;
  left: 10px;
}

@keyframes heartbeat {
  0%, 100% {
    transform: rotate(-45deg) scale(1);
  }
  50% {
    transform: rotate(-45deg) scale(1.1);
  }
}

/* 圆点装饰 */
.dot {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  opacity: 0.6;
  animation: bounce-dot 3s ease-in-out infinite;
}

@keyframes bounce-dot {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

/* 呼吸效果 */
@keyframes breathing {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(0.95);
  }
}

.animate-breathing {
  animation: breathing 1.5s ease-in-out infinite;
}
</style>
