<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useSettingsStore, ASR_SERVICES, LLM_MODELS, TTS_MODELS, TTS_VOICES, DEFAULT_TTS_VOICES, VAD_TYPES, BACKGROUNDS, AVATARS } from '@/stores/settings'
import { getSkills, getStories, createStory, updateStory, deleteStory, generateStory, type Story, type SkillSummary } from '@/api/skills'
import { getBGMList, uploadBGM, type BGMItem } from '@/api/bgm'
import { getSongs, getSongAudioUrl, uploadSong, deleteSong, type Song } from '@/api/songs'
import { getCustomVoices, createCustomVoice, deleteCustomVoice, testCustomVoice, getVoiceAudioUrl, type CustomVoice } from '@/api/tts'

const settings = useSettingsStore()

defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

// Tab 状态
type TabType = 'settings' | 'stories'
const activeTab = ref<TabType>('settings')

// 设置子 Tab（基础/高级）
type SettingsSubTab = 'basic' | 'advanced'
const settingsSubTab = ref<SettingsSubTab>('basic')

// ========== 设置相关 ==========
const silenceDurationDisplay = computed(() => {
  return (settings.silenceDuration / 1000).toFixed(1) + 's'
})

const vadIgnoreTimeDisplay = computed(() => {
  return settings.vadIgnoreTime + 'ms'
})

// 同音词输入
const aliasInput = ref('')

function addAlias() {
  const val = aliasInput.value.trim()
  if (val && !settings.assistantAliases.includes(val)) {
    settings.assistantAliases.push(val)
  }
  aliasInput.value = ''
}

function removeAlias(index: number) {
  settings.assistantAliases.splice(index, 1)
}

const tooltips = {
  asrService: '选择语音识别服务。FunASR中文识别效果好；Whisper多语言支持好。',
  silenceThreshold: '当麦克风音量低于此值时判定为静音。',
  silenceDuration: '静音持续多长时间后自动停止录音并发送。',
  llmModel: '选择大语言模型。',
  llmTemperature: '控制AI回复的随机性。0=稳定；1.5=创意。',
  llmMaxTokens: '限制AI单次回复的最大长度。',
  llmMaxHistory: '保留多少轮对话历史作为上下文。',
  ttsModel: '选择语音合成模型。',
  ttsVoice: '选择语音合成的声音角色。',
  ttsSpeed: '调整语音播放速度。0.5=慢速，1.0=正常，2.0=快速。',
  ttsGain: '放大语音播放的音量。',
  vadEnabled: '开启后，当AI说话时如果检测到你在说话，会自动停止播放。',
  vadType: '选择语音活动检测方式。',
  vadIgnoreTime: 'AI开始说话后忽略麦克风输入的时间。',
}

// ========== 自定义音色相关 ==========
const customVoices = ref<CustomVoice[]>([])
const isLoadingVoices = ref(false)
const isRecording = ref(false)
const recordingTime = ref(0)
const newVoiceName = ref('')
const showVoiceRecorder = ref(false)

let mediaRecorder: MediaRecorder | null = null
let recordedChunks: Blob[] = []
let recordingTimer: number | null = null

// 当前模型的预设音色列表
const currentModelVoices = computed(() => {
  const modelId = settings.ttsModel as keyof typeof TTS_VOICES
  return TTS_VOICES[modelId] || DEFAULT_TTS_VOICES
})

// 合并的音色选项（预设 + 自定义）
const allVoiceOptions = computed(() => {
  const preset = currentModelVoices.value.map(v => ({
    id: v.id,
    name: v.name,
    isCustom: false,
  }))
  const custom = customVoices.value.map(v => ({
    id: `custom:${v.id}`,
    name: `🎤 ${v.name}`,
    isCustom: true,
  }))
  return [...preset, ...custom]
})

// 当前选中的音色 ID（处理自定义音色前缀）
const selectedVoiceId = computed({
  get: () => {
    if (settings.ttsCustomVoiceId) {
      return `custom:${settings.ttsCustomVoiceId}`
    }
    return settings.ttsVoice
  },
  set: (val: string) => {
    if (val.startsWith('custom:')) {
      settings.ttsCustomVoiceId = val.replace('custom:', '')
      settings.ttsVoice = currentModelVoices.value[0]?.id || 'alex'
    } else {
      settings.ttsCustomVoiceId = null
      settings.ttsVoice = val
    }
  },
})

// 监听 TTS 模型变化，自动重置音色为新模型的第一个
watch(() => settings.ttsModel, (newModel) => {
  const modelId = newModel as keyof typeof TTS_VOICES
  const voices = TTS_VOICES[modelId] || DEFAULT_TTS_VOICES
  // 如果当前音色不在新模型的音色列表中，重置为第一个
  const currentVoice = settings.ttsVoice
  const voiceExists = voices.some(v => v.id === currentVoice)
  if (!voiceExists && !settings.ttsCustomVoiceId) {
    settings.ttsVoice = voices[0]?.id || 'alex'
  }
})

async function loadCustomVoices() {
  isLoadingVoices.value = true
  try {
    customVoices.value = await getCustomVoices()
  } catch (error) {
    console.error('Failed to load custom voices:', error)
  } finally {
    isLoadingVoices.value = false
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
    recordedChunks = []

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        recordedChunks.push(e.data)
      }
    }

    mediaRecorder.onstop = async () => {
      console.log('[Voice] 录制停止，时长:', recordingTime.value, '秒')
      stream.getTracks().forEach(track => track.stop())
      if (recordingTimer) {
        clearInterval(recordingTimer)
        recordingTimer = null
      }
    }

    // 每秒收集一次数据，确保录制稳定
    mediaRecorder.start(1000)
    isRecording.value = true
    recordingTime.value = 0

    // 计时器
    recordingTimer = window.setInterval(() => {
      recordingTime.value++
    }, 1000)

    console.log('[Voice] 开始录制音色')
  } catch (error) {
    console.error('Failed to start recording:', error)
    alert('无法访问麦克风')
  }
}

async function stopRecording() {
  if (!mediaRecorder) return

  console.log('[Voice] 停止录制，收集音频数据...')
  return new Promise<Blob>((resolve) => {
    mediaRecorder!.onstop = () => {
      const blob = new Blob(recordedChunks, { type: 'audio/webm' })
      console.log('[Voice] 音频数据收集完成，大小:', blob.size, 'bytes')
      if (recordingTimer) {
        clearInterval(recordingTimer)
        recordingTimer = null
      }
      resolve(blob)
    }
    mediaRecorder!.stop()
    isRecording.value = false
  })
}

async function handleSaveVoice() {
  console.log('[Voice] 用户点击保存，录制时长:', recordingTime.value, '秒')

  if (!newVoiceName.value.trim()) {
    alert('请输入音色名称')
    return
  }

  const audioBlob = await stopRecording()
  if (!audioBlob || audioBlob.size === 0) {
    alert('录音失败，请重试')
    return
  }

  try {
    console.log('[Voice] 上传音色:', newVoiceName.value.trim(), '大小:', audioBlob.size)
    await createCustomVoice(audioBlob, newVoiceName.value.trim())
    newVoiceName.value = ''
    showVoiceRecorder.value = false
    await loadCustomVoices()
    alert('音色创建成功！')
  } catch (error: any) {
    console.error('Failed to create voice:', error)
    alert('创建失败: ' + (error.message || '未知错误'))
  }
}

function handleCancelRecording() {
  if (mediaRecorder && isRecording.value) {
    mediaRecorder.stop()
  }
  isRecording.value = false
  recordingTime.value = 0
  newVoiceName.value = ''
  showVoiceRecorder.value = false
}

async function handleDeleteVoice(voice: CustomVoice) {
  if (!confirm(`确定要删除音色「${voice.name}」吗？`)) return
  try {
    await deleteCustomVoice(voice.id)
    // 如果删除的是当前选中的音色，重置为预设
    if (settings.ttsCustomVoiceId === voice.id) {
      settings.ttsCustomVoiceId = null
    }
    await loadCustomVoices()
  } catch (error) {
    console.error('Failed to delete voice:', error)
    alert('删除失败')
  }
}

async function handleTestVoice(voice: CustomVoice) {
  try {
    const audioData = await testCustomVoice(voice.id)
    const audioBlob = new Blob([audioData], { type: 'audio/mpeg' })
    const audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)
    audio.play()
  } catch (error) {
    console.error('Failed to test voice:', error)
    alert('测试失败')
  }
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ========== 内容管理相关 ==========
// 可用技能列表
const availableSkills = ref<SkillSummary[]>([])
const currentSkillId = ref('storytelling')

// 技能配置
const skillConfig: Record<string, { label: string; icon: string; unit: string; placeholder: { title: string; content: string }; hint?: string; isAudio?: boolean }> = {
  storytelling: {
    label: '故事',
    icon: '📖',
    unit: '个故事',
    placeholder: {
      title: '输入故事名称，如：白雪公主',
      content: '故事内容（支持 Markdown 格式）',
    },
  },
  poetry: {
    label: '古诗',
    icon: '📜',
    unit: '首古诗',
    placeholder: {
      title: '输入诗词名称，如：静夜思',
      content: '作者\n\n诗句第一行\n\n诗句第二行\n\n---\n\n**讲给宝宝听**\n\n简单的解释',
    },
    hint: '格式：作者 → 诗句 → 分隔线(---) → 讲给宝宝听',
  },
  english: {
    label: '英语',
    icon: '🔤',
    unit: '个分类',
    placeholder: {
      title: '输入分类名称，如：水果、动物',
      content: '# 单词 Word\n\n**读音**: /音标/\n\n**跟我说**: 简单例句\n\n**一起玩**: 互动建议',
    },
    hint: '每个单词包含：音标、例句、互动游戏',
  },
  songs: {
    label: '儿歌',
    icon: '🎵',
    unit: '首儿歌',
    placeholder: {
      title: '歌曲名称',
      content: '',
    },
    hint: '儿歌为音频文件，需上传 MP3',
    isAudio: true,
  },
}

// 当前技能配置
const currentConfig = computed(() => skillConfig[currentSkillId.value] || skillConfig.storytelling)

// 技能显示名称映射（兼容旧代码）
const skillLabels: Record<string, string> = {
  storytelling: '故事',
  poetry: '古诗',
  english: '英语',
  songs: '儿歌',
}

const stories = ref<Story[]>([])
const songsList = ref<Song[]>([])
const isLoading = ref(false)
const showEditor = ref(false)
const editingStory = ref<Story | null>(null)
const isGenerating = ref(false)

// 儿歌上传相关
const showSongUploader = ref(false)
const isUploadingSong = ref(false)
const newSongTitle = ref('')
const newSongTitleEn = ref('')
const newSongKeywords = ref('')
const newSongFile = ref<File | null>(null)

// BGM 列表
const bgmList = ref<BGMItem[]>([])
const isLoadingBGM = ref(false)
const isUploadingBGM = ref(false)

const form = ref({
  title: '',
  content: '',
})

// 加载 BGM 列表
async function loadBGMList() {
  if (isLoadingBGM.value) return  // 正在加载
  isLoadingBGM.value = true
  try {
    bgmList.value = await getBGMList()
  } catch (error) {
    console.error('Failed to load BGM list:', error)
  } finally {
    isLoadingBGM.value = false
  }
}

// 上传自定义 BGM
async function handleUploadBGM(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  isUploadingBGM.value = true
  try {
    const newBGM = await uploadBGM(file)
    bgmList.value.push(newBGM)
  } catch (error: any) {
    console.error('Failed to upload BGM:', error)
    alert('上传失败: ' + (error.message || '未知错误'))
  } finally {
    isUploadingBGM.value = false
    input.value = ''  // 重置文件选择
  }
}

// 试听 BGM
let previewAudio: HTMLAudioElement | null = null
const isPreviewPlaying = ref(false)

function previewBGM(bgmId: string) {
  if (!bgmId) return

  // 如果正在播放同一个，则暂停
  if (previewAudio && isPreviewPlaying.value) {
    previewAudio.pause()
    previewAudio = null
    isPreviewPlaying.value = false
    return
  }

  // 停止之前的播放
  if (previewAudio) {
    previewAudio.pause()
  }

  previewAudio = new Audio(`/bgm/${bgmId}`)
  previewAudio.volume = 0.5

  previewAudio.onended = () => {
    isPreviewPlaying.value = false
    previewAudio = null
  }

  previewAudio.play().then(() => {
    isPreviewPlaying.value = true
  }).catch(e => {
    console.warn('播放失败:', e)
    isPreviewPlaying.value = false
  })
}

// 停止试听
function stopPreviewBGM() {
  if (previewAudio) {
    previewAudio.pause()
    previewAudio = null
  }
  isPreviewPlaying.value = false
}

// 加载可用技能列表
async function loadSkills() {
  try {
    const skills = await getSkills()
    // 只保留有 contentDir 的技能（可管理内容的技能）
    const filteredSkills = skills.filter(s =>
      s.id === 'storytelling' || s.id === 'poetry' || s.id === 'english'
    )
    // 手动添加 songs 技能（它有独立 API）
    filteredSkills.push({
      id: 'songs',
      name: '儿歌',
      version: '1.0.0',
      icon: '🎵',
      keywords: ['儿歌', '歌曲'],
      triggers: [],
      tools: ['play_song'],
    })
    availableSkills.value = filteredSkills
  } catch (error) {
    console.error('Failed to load skills:', error)
  }
}

// 加载儿歌列表
async function loadSongsList() {
  isLoading.value = true
  try {
    songsList.value = await getSongs()
  } catch (error) {
    console.error('Failed to load songs:', error)
  } finally {
    isLoading.value = false
  }
}

// 处理儿歌文件选择
function handleSongFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    newSongFile.value = file
    // 如果没有填写标题，用文件名（去掉扩展名）作为默认标题
    if (!newSongTitle.value) {
      newSongTitle.value = file.name.replace(/\.[^/.]+$/, '')
    }
  }
}

// 上传儿歌
async function handleUploadSong() {
  if (!newSongFile.value || !newSongTitle.value.trim()) {
    alert('请选择文件并填写歌曲名称')
    return
  }

  isUploadingSong.value = true
  try {
    const keywords = newSongKeywords.value
      .split(/[,，]/)
      .map(k => k.trim())
      .filter(k => k)

    await uploadSong(
      newSongFile.value,
      newSongTitle.value.trim(),
      newSongTitleEn.value.trim() || undefined,
      keywords.length > 0 ? keywords : undefined
    )

    // 重置表单
    newSongFile.value = null
    newSongTitle.value = ''
    newSongTitleEn.value = ''
    newSongKeywords.value = ''
    showSongUploader.value = false

    // 重新加载列表
    await loadSongsList()
  } catch (error: any) {
    console.error('Failed to upload song:', error)
    alert('上传失败: ' + (error.message || '未知错误'))
  } finally {
    isUploadingSong.value = false
  }
}

// 删除儿歌
async function handleDeleteSong(song: Song) {
  if (!confirm(`确定要删除「${song.title}」吗？`)) return

  try {
    await deleteSong(song.id)
    await loadSongsList()
  } catch (error: any) {
    console.error('Failed to delete song:', error)
    alert('删除失败: ' + (error.message || '未知错误'))
  }
}

// 试播放儿歌
let songPreviewAudio: HTMLAudioElement | null = null
const playingSongId = ref<string | null>(null)

function previewSong(song: Song) {
  // 如果正在播放同一首，则停止
  if (playingSongId.value === song.id) {
    stopSongPreview()
    return
  }

  // 停止之前的播放
  stopSongPreview()

  // 播放新的
  songPreviewAudio = new Audio(getSongAudioUrl(song.file))
  songPreviewAudio.volume = 0.8

  songPreviewAudio.onended = () => {
    playingSongId.value = null
    songPreviewAudio = null
  }

  songPreviewAudio.onerror = () => {
    playingSongId.value = null
    songPreviewAudio = null
    alert('播放失败，音频文件可能不存在')
  }

  songPreviewAudio.play().then(() => {
    playingSongId.value = song.id
  }).catch(e => {
    console.warn('播放失败:', e)
    alert('播放失败: ' + e.message)
  })
}

function stopSongPreview() {
  if (songPreviewAudio) {
    songPreviewAudio.pause()
    songPreviewAudio = null
  }
  playingSongId.value = null
}

// 取消上传儿歌
function cancelSongUpload() {
  newSongFile.value = null
  newSongTitle.value = ''
  newSongTitleEn.value = ''
  newSongKeywords.value = ''
  showSongUploader.value = false
}

// 切换技能
function switchSkill(skillId: string) {
  currentSkillId.value = skillId
  if (skillId === 'songs') {
    loadSongsList()
  } else {
    loadStories()
  }
}

async function loadStories() {
  isLoading.value = true
  try {
    stories.value = await getStories(currentSkillId.value)
  } catch (error) {
    console.error('Failed to load stories:', error)
  } finally {
    isLoading.value = false
  }
}

function openCreate() {
  editingStory.value = null
  form.value = { title: '', content: '' }
  showEditor.value = true
}

async function openEdit(story: Story) {
  editingStory.value = story
  const fullStory = await import('@/api/skills').then(m => m.getStory(currentSkillId.value, story.id))
  form.value = {
    title: fullStory.title,
    content: fullStory.content?.replace(/^#\s+.+\n\n/, '') || '',
  }
  showEditor.value = true
}

async function handleSave() {
  if (!form.value.title.trim() || !form.value.content.trim()) {
    alert('请填写标题和内容')
    return
  }

  try {
    if (editingStory.value) {
      await updateStory(currentSkillId.value, editingStory.value.id, {
        title: form.value.title,
        content: form.value.content,
      })
    } else {
      await createStory(currentSkillId.value, {
        title: form.value.title,
        content: form.value.content,
      })
    }
    showEditor.value = false
    await loadStories()
  } catch (error: any) {
    console.error('Failed to save story:', error)
    const message = error?.response?.data?.detail || error?.message || '未知错误'
    alert(`保存失败: ${message}`)
  }
}

async function handleDelete(story: Story) {
  if (!confirm(`确定要删除「${story.title}」吗？`)) return
  try {
    await deleteStory(currentSkillId.value, story.id)
    await loadStories()
  } catch (error: any) {
    console.error('Failed to delete story:', error)
    const message = error?.response?.data?.detail || error?.message || '未知错误'
    alert(`删除失败: ${message}`)
  }
}

async function handleGenerate() {
  if (!form.value.title.trim()) {
    alert('请先输入标题')
    return
  }
  isGenerating.value = true
  try {
    const result = await generateStory(currentSkillId.value, form.value.title.trim())
    form.value.content = result.content
  } catch (error: any) {
    console.error('Failed to generate story:', error)
    const message = error?.response?.data?.detail || error?.message || '未知错误'
    alert(`生成失败: ${message}`)
  } finally {
    isGenerating.value = false
  }
}

// 切换到故事 Tab 时加载数据
function switchTab(tab: TabType) {
  activeTab.value = tab
  if (tab === 'stories' && stories.value.length === 0) {
    loadStories()
  }
}

onMounted(() => {
  // 加载自定义音色
  loadCustomVoices()
  // 加载可用技能
  loadSkills()
  // 加载 BGM 列表
  loadBGMList()

  if (activeTab.value === 'stories') {
    loadStories()
  }
})

onUnmounted(() => {
  // 清理录音资源
  if (recordingTimer) {
    clearInterval(recordingTimer)
  }
  if (mediaRecorder && isRecording.value) {
    mediaRecorder.stop()
  }
  // 停止儿歌试听
  stopSongPreview()
  // 停止BGM试听
  stopPreviewBGM()
})
</script>

<template>
  <div
    v-if="show"
    class="absolute inset-0 md:relative md:inset-auto w-full md:w-[480px] h-full flex-shrink-0 flex flex-col overflow-hidden bg-white z-20"
  >
    <!-- 头部标题 -->
    <div class="flex-shrink-0 bg-gradient-to-r from-pink-400 via-pink-500 to-orange-400 px-4 h-14 flex items-center justify-between safe-top">
      <div class="flex items-center gap-2">
        <!-- 手机端返回按钮 -->
        <button
          @click="emit('close')"
          class="md:hidden p-1.5 hover:bg-white/20 rounded-lg transition-colors"
        >
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <h2 class="text-white text-lg font-semibold">家长控制台</h2>
      </div>
      <!-- PC端关闭按钮 -->
      <button
        @click="emit('close')"
        class="hidden md:block p-1.5 hover:bg-white/20 rounded-lg transition-colors"
      >
        <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Tab 切换 -->
    <div class="bg-gray-100 md:border-l border-b border-gray-200 px-2 py-1.5 flex gap-1">
      <button
        @click="switchTab('settings')"
        :class="[
          'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
          activeTab === 'settings'
            ? 'bg-white text-pink-500 shadow-sm'
            : 'text-gray-500 hover:text-gray-700 hover:bg-white/50'
        ]"
      >
        参数设置
      </button>
      <button
        @click="switchTab('stories')"
        :class="[
          'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
          activeTab === 'stories'
            ? 'bg-white text-pink-500 shadow-sm'
            : 'text-gray-500 hover:text-gray-700 hover:bg-white/50'
        ]"
      >
        内容管理
      </button>
    </div>

    <!-- 设置面板 -->
    <template v-if="activeTab === 'settings'">
      <!-- 设置子 Tab 切换 -->
      <div class="bg-white md:border-l border-b border-gray-200 px-4 py-2 flex gap-4">
        <button
          @click="settingsSubTab = 'basic'"
          :class="[
            'text-sm font-medium transition-colors pb-1 border-b-2',
            settingsSubTab === 'basic'
              ? 'text-pink-500 border-pink-500'
              : 'text-gray-400 border-transparent hover:text-gray-600'
          ]"
        >
          基础配置
        </button>
        <button
          @click="settingsSubTab = 'advanced'"
          :class="[
            'text-sm font-medium transition-colors pb-1 border-b-2',
            settingsSubTab === 'advanced'
              ? 'text-pink-500 border-pink-500'
              : 'text-gray-400 border-transparent hover:text-gray-600'
          ]"
        >
          高级配置
        </button>
      </div>

      <!-- 基础配置 -->
      <div v-if="settingsSubTab === 'basic'" class="flex-1 overflow-y-auto p-4 pr-4 md:pr-6 space-y-3 bg-gray-50 md:border-l border-gray-200">
        <!-- 助手名字 -->
        <section class="space-y-2">
          <div class="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-pink-100 text-pink-600">
            助手名字
          </div>
          <div class="bg-white border rounded-lg p-3">
            <div class="flex gap-3">
              <!-- 名字 -->
              <div class="w-24 flex-shrink-0">
                <label class="text-xs text-gray-500 mb-1 block">名字</label>
                <input
                  v-model="settings.assistantName"
                  type="text"
                  placeholder="小智"
                  maxlength="10"
                  class="w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-pink-500"
                />
              </div>
              <!-- 同音词 -->
              <div class="flex-1 min-w-0">
                <label class="text-xs text-gray-500 mb-1 block">同音词（回车添加）</label>
                <div class="flex flex-wrap gap-1.5 p-2 border rounded-lg min-h-[42px] bg-white focus-within:ring-2 focus-within:ring-pink-500">
                  <span
                    v-for="(alias, index) in settings.assistantAliases"
                    :key="index"
                    class="inline-flex items-center gap-1 px-2 py-0.5 bg-pink-100 text-pink-600 text-sm rounded-full"
                  >
                    {{ alias }}
                    <button
                      @click="removeAlias(index)"
                      class="w-4 h-4 flex items-center justify-center hover:bg-pink-200 rounded-full"
                    >
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </span>
                  <input
                    v-model="aliasInput"
                    @keydown.enter.prevent="addAlias"
                    type="text"
                    placeholder="输入同音词"
                    class="flex-1 min-w-[80px] text-sm outline-none bg-transparent"
                  />
                </div>
              </div>
            </div>
            <p class="text-xs text-gray-400 mt-2">喊名字或同音词都可以打断 AI 说话</p>
          </div>
        </section>

        <!-- 角色形象 -->
        <section class="space-y-2">
          <div class="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-600">
            角色形象
          </div>
          <div class="bg-white border rounded-lg p-3">
            <div class="flex justify-center gap-3">
              <button
                v-for="av in AVATARS"
                :key="av.id"
                @click="settings.avatar = av.id"
                :class="[
                  'w-12 h-12 rounded-full flex items-center justify-center text-2xl transition-all',
                  settings.avatar === av.id
                    ? 'bg-purple-100 ring-2 ring-purple-400 scale-110'
                    : 'bg-gray-50 hover:bg-gray-100 hover:scale-105'
                ]"
                :title="av.name"
              >
                {{ av.icon }}
              </button>
            </div>
          </div>
        </section>

        <!-- 背景主题 -->
        <section class="space-y-2">
          <div class="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-orange-100 text-orange-600">
            背景主题
          </div>
          <div class="bg-white border rounded-lg p-3">
            <div class="flex gap-3 justify-center">
              <button
                v-for="bg in BACKGROUNDS"
                :key="bg.id"
                @click="settings.background = bg.id"
                :class="[
                  'w-12 h-12 rounded-full transition-transform flex-shrink-0',
                  settings.background === bg.id ? 'ring-3 ring-purple-400 scale-110' : 'hover:scale-105'
                ]"
                :style="{ background: `linear-gradient(135deg, ${bg.colors[0]}, ${bg.colors[1]})` }"
                :title="bg.name"
              ></button>
            </div>
          </div>
        </section>

        <!-- 背景音乐 -->
        <section class="space-y-2">
          <div class="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-yellow-100 text-yellow-600">
            背景音乐
          </div>
          <div class="bg-white border rounded-lg p-3">
            <!-- 开关和音量 -->
            <div class="flex items-center justify-between mb-3">
              <span class="text-sm text-gray-600">讲故事时播放</span>
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" v-model="settings.bgmEnabled" class="sr-only peer" />
                <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-yellow-500"></div>
              </label>
            </div>
            <div v-if="settings.bgmEnabled" class="flex items-center gap-2 mb-3">
              <span class="text-xs text-gray-500">音量</span>
              <input type="range" v-model.number="settings.bgmVolume" min="0" max="1" step="0.1" class="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-yellow-500" />
              <span class="text-xs text-gray-500 w-8">{{ Math.round(settings.bgmVolume * 100) }}%</span>
            </div>
            <!-- 音乐列表 -->
            <div v-if="settings.bgmEnabled" class="space-y-2">
              <div class="flex items-center justify-between">
                <span class="text-xs text-gray-500">音乐库</span>
                <label class="px-2 py-1 bg-yellow-100 hover:bg-yellow-200 text-yellow-700 text-xs rounded-lg transition-colors cursor-pointer flex items-center gap-1">
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                  </svg>
                  <span>{{ isUploadingBGM ? '上传中...' : '上传音乐' }}</span>
                  <input
                    type="file"
                    accept=".mp3,.wav,.ogg,.m4a"
                    class="hidden"
                    :disabled="isUploadingBGM"
                    @change="handleUploadBGM"
                  />
                </label>
              </div>
              <div v-if="bgmList.length > 0" class="max-h-32 overflow-y-auto space-y-1">
                <div
                  v-for="bgm in bgmList"
                  :key="bgm.id"
                  class="flex items-center justify-between p-2 bg-gray-50 rounded-lg text-sm"
                >
                  <span class="truncate flex-1">{{ bgm.preset ? '🎵' : '📁' }} {{ bgm.name }}</span>
                  <button
                    @click="previewBGM(bgm.id)"
                    class="p-1 hover:bg-yellow-100 rounded transition-colors flex-shrink-0"
                    title="试听"
                  >
                    <svg class="w-4 h-4 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </button>
                </div>
              </div>
              <p v-else class="text-xs text-gray-400 text-center py-2">加载中...</p>
            </div>
            <p class="text-xs text-gray-400 mt-2">讲故事时会随机播放音乐库中的背景音乐</p>
          </div>
        </section>

      </div>

      <!-- 高级配置 -->
      <div v-else class="flex-1 overflow-y-auto p-4 pr-4 md:pr-6 space-y-3 bg-gray-50 md:border-l border-gray-200">
        <!-- ASR -->
        <section class="space-y-2">
          <div class="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-blue-100 text-blue-600">
            ① ASR 语音识别
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.asrService">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">识别服务</span>
              </div>
              <select v-model="settings.asrService" class="w-full px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option v-for="asr in ASR_SERVICES" :key="asr.id" :value="asr.id">{{ asr.name }}</option>
              </select>
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.silenceThreshold">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">静音阈值</span>
                <span class="text-sm font-medium">{{ settings.silenceThreshold }}</span>
              </div>
              <input type="range" v-model.number="settings.silenceThreshold" min="5" max="50" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500" />
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.silenceDuration">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">静音时长</span>
                <span class="text-sm font-medium">{{ silenceDurationDisplay }}</span>
              </div>
              <input type="range" v-model.number="settings.silenceDuration" min="500" max="3000" step="100" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-500" />
            </div>
          </div>
        </section>

        <!-- LLM -->
        <section class="space-y-2">
          <div class="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-600">
            ② LLM 大语言模型
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.llmModel">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">模型</span>
              </div>
              <select v-model="settings.llmModel" class="w-full px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
                <option v-for="model in LLM_MODELS" :key="model.id" :value="model.id">{{ model.name }}</option>
              </select>
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.llmTemperature">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">温度</span>
                <span class="text-sm font-medium">{{ settings.llmTemperature }}</span>
              </div>
              <input type="range" v-model.number="settings.llmTemperature" min="0" max="1.5" step="0.1" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500" />
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.llmMaxTokens">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">最大输出</span>
                <span class="text-sm font-medium">{{ settings.llmMaxTokens }}</span>
              </div>
              <input type="range" v-model.number="settings.llmMaxTokens" min="200" max="4000" step="100" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500" />
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.llmMaxHistory">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">记忆轮数</span>
                <span class="text-sm font-medium">{{ settings.llmMaxHistory }}</span>
              </div>
              <input type="range" v-model.number="settings.llmMaxHistory" min="5" max="50" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-green-500" />
            </div>
          </div>
        </section>

        <!-- TTS -->
        <section class="space-y-2">
          <div class="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-yellow-100 text-yellow-600">
            ③ TTS 语音合成
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.ttsModel">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">模型</span>
              </div>
              <select v-model="settings.ttsModel" class="w-full px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500">
                <option v-for="model in TTS_MODELS" :key="model.id" :value="model.id">{{ model.name }}</option>
              </select>
              <p class="text-xs text-gray-400 mt-1">{{ TTS_MODELS.find(m => m.id === settings.ttsModel)?.desc }}</p>
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.ttsVoice">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">声音</span>
              </div>
              <select v-model="selectedVoiceId" class="w-full px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500">
                <optgroup label="预设音色">
                  <option v-for="voice in currentModelVoices" :key="voice.id" :value="voice.id">{{ voice.name }}</option>
                </optgroup>
                <optgroup v-if="customVoices.length > 0" label="自定义音色">
                  <option v-for="voice in customVoices" :key="voice.id" :value="`custom:${voice.id}`">🎤 {{ voice.name }}</option>
                </optgroup>
              </select>
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.ttsSpeed">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">语速</span>
                <span class="text-sm font-medium">{{ settings.ttsSpeed.toFixed(1) }}x</span>
              </div>
              <input type="range" v-model.number="settings.ttsSpeed" min="0.5" max="2" step="0.1" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-yellow-500" />
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.ttsGain">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">音量增益</span>
                <span class="text-sm font-medium">{{ settings.ttsGain }}x</span>
              </div>
              <input type="range" v-model.number="settings.ttsGain" min="0" max="20" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-yellow-500" />
            </div>
          </div>

          <!-- 自定义音色管理 -->
          <div class="bg-white border rounded-lg p-3">
            <div class="flex justify-between items-center mb-2">
              <span class="text-sm text-gray-600">自定义音色</span>
              <button
                v-if="!showVoiceRecorder"
                @click="showVoiceRecorder = true"
                class="flex items-center gap-1 px-2 py-1 bg-yellow-100 hover:bg-yellow-200 text-yellow-700 text-xs rounded-lg transition-colors"
              >
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
                录制音色
              </button>
            </div>

            <!-- 录音界面 -->
            <div v-if="showVoiceRecorder" class="space-y-2 mb-3 p-2 bg-yellow-50 rounded-lg">
              <input
                v-model="newVoiceName"
                type="text"
                placeholder="输入音色名称"
                class="w-full px-2 py-1.5 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500"
                :disabled="isRecording"
              />
              <div class="flex items-center gap-2">
                <button
                  v-if="!isRecording"
                  @click="startRecording"
                  class="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-red-500 hover:bg-red-600 text-white text-sm rounded-lg transition-colors"
                >
                  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="6" />
                  </svg>
                  开始录制
                </button>
                <template v-else>
                  <div class="flex-1 flex items-center gap-2 px-3 py-2 bg-red-100 rounded-lg">
                    <div class="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
                    <span class="text-sm text-red-600">录制中 {{ formatTime(recordingTime) }}</span>
                  </div>
                  <button
                    @click="handleSaveVoice"
                    :disabled="recordingTime < 3"
                    class="px-3 py-2 bg-green-500 hover:bg-green-600 disabled:bg-gray-300 text-white text-sm rounded-lg transition-colors"
                    :title="recordingTime < 3 ? '至少录制3秒' : ''"
                  >
                    保存
                  </button>
                </template>
                <button
                  @click="handleCancelRecording"
                  class="px-3 py-2 bg-gray-200 hover:bg-gray-300 text-gray-600 text-sm rounded-lg transition-colors"
                >
                  取消
                </button>
              </div>
              <p class="text-xs text-gray-500">💡 请说一段10-30秒的话语作为参考音频</p>
            </div>

            <!-- 自定义音色列表 -->
            <div v-if="customVoices.length > 0" class="space-y-1">
              <div
                v-for="voice in customVoices"
                :key="voice.id"
                class="flex items-center justify-between p-2 bg-gray-50 rounded-lg"
              >
                <div class="flex items-center gap-2 min-w-0">
                  <span class="text-sm">🎤</span>
                  <span class="text-sm text-gray-700 truncate">{{ voice.name }}</span>
                </div>
                <div class="flex items-center gap-1 flex-shrink-0">
                  <button
                    @click="handleTestVoice(voice)"
                    class="p-1 hover:bg-yellow-100 rounded transition-colors"
                    title="试听"
                  >
                    <svg class="w-4 h-4 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </button>
                  <button
                    @click="handleDeleteVoice(voice)"
                    class="p-1 hover:bg-red-100 rounded transition-colors"
                    title="删除"
                  >
                    <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            <!-- 空状态 -->
            <div v-else-if="!showVoiceRecorder" class="text-center py-3">
              <p class="text-xs text-gray-400">还没有自定义音色</p>
            </div>
          </div>
        </section>

        <!-- VAD -->
        <section class="space-y-2">
          <div class="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-600">
            ④ VAD 打断检测
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.vadEnabled">
              <label class="flex items-center justify-between cursor-pointer">
                <span class="text-sm text-gray-600">启用语音打断</span>
                <input type="checkbox" v-model="settings.vadEnabled" class="w-5 h-5 rounded text-red-500 focus:ring-red-500" />
              </label>
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.vadType">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">检测方式</span>
              </div>
              <select v-model="settings.vadType" class="w-full px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500">
                <option v-for="vad in VAD_TYPES" :key="vad.id" :value="vad.id" :title="vad.desc">{{ vad.name }}</option>
              </select>
              <p class="text-xs text-gray-400 mt-1">{{ VAD_TYPES.find(v => v.id === settings.vadType)?.desc }}</p>
            </div>
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.vadIgnoreTime">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">忽略时间</span>
                <span class="text-sm font-medium">{{ vadIgnoreTimeDisplay }}</span>
              </div>
              <input type="range" v-model.number="settings.vadIgnoreTime" min="300" max="1500" step="100" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-500" />
            </div>
          </div>
        </section>

      </div>
    </template>

    <!-- 内容管理面板 -->
    <template v-else-if="activeTab === 'stories'">
      <!-- 技能 Tab 切换 -->
      <div class="bg-white md:border-l border-b border-gray-200 px-4 py-2 flex gap-4">
        <button
          v-for="skill in availableSkills"
          :key="skill.id"
          @click="switchSkill(skill.id)"
          :class="[
            'text-sm font-medium transition-colors pb-1 border-b-2 flex items-center gap-1',
            currentSkillId === skill.id
              ? 'text-pink-500 border-pink-500'
              : 'text-gray-400 border-transparent hover:text-gray-600'
          ]"
        >
          <span>{{ skill.icon }}</span>
          <span>{{ skillLabels[skill.id] || skill.name }}</span>
        </button>
      </div>

      <!-- 工具栏 -->
      <div class="bg-gray-50 md:border-l border-b border-gray-200 px-4 py-2 flex items-center justify-between">
        <span class="text-sm text-gray-500">
          共 {{ currentSkillId === 'songs' ? songsList.length : stories.length }} {{ currentConfig.unit }}
        </span>
        <button
          v-if="currentSkillId === 'songs'"
          @click="showSongUploader = true"
          class="flex items-center gap-1 px-3 py-1.5 bg-pink-500 hover:bg-pink-600 text-white text-sm rounded-lg transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          上传
        </button>
        <button
          v-else
          @click="openCreate"
          class="flex items-center gap-1 px-3 py-1.5 bg-pink-500 hover:bg-pink-600 text-white text-sm rounded-lg transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          添加
        </button>
      </div>

      <!-- 内容列表 -->
      <div class="flex-1 overflow-y-auto bg-gray-50 md:border-l border-gray-200">
        <!-- 加载状态 -->
        <div v-if="isLoading" class="flex justify-center py-12">
          <div class="w-8 h-8 border-4 border-pink-200 border-t-pink-500 rounded-full animate-spin"></div>
        </div>

        <!-- 儿歌列表（独立显示） -->
        <template v-else-if="currentSkillId === 'songs'">
          <!-- 上传表单 -->
          <div v-if="showSongUploader" class="p-3 bg-yellow-50 border-b">
            <div class="space-y-3">
              <div>
                <label class="block text-xs text-gray-500 mb-1">选择音频文件 *</label>
                <input
                  type="file"
                  accept=".mp3,.wav,.ogg,.m4a"
                  @change="handleSongFileSelect"
                  class="w-full text-sm text-gray-500 file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-pink-100 file:text-pink-700 hover:file:bg-pink-200"
                />
              </div>
              <div class="grid grid-cols-2 gap-2">
                <div>
                  <label class="block text-xs text-gray-500 mb-1">歌曲名称 *</label>
                  <input
                    v-model="newSongTitle"
                    type="text"
                    placeholder="如：小星星"
                    class="w-full px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-pink-500"
                  />
                </div>
                <div>
                  <label class="block text-xs text-gray-500 mb-1">英文名（可选）</label>
                  <input
                    v-model="newSongTitleEn"
                    type="text"
                    placeholder="如：Twinkle Star"
                    class="w-full px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-pink-500"
                  />
                </div>
              </div>
              <div>
                <label class="block text-xs text-gray-500 mb-1">关键词（逗号分隔，可选）</label>
                <input
                  v-model="newSongKeywords"
                  type="text"
                  placeholder="如：星星, 夜晚, twinkle"
                  class="w-full px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-pink-500"
                />
              </div>
              <div class="flex justify-end gap-2">
                <button
                  @click="cancelSongUpload"
                  class="px-3 py-1.5 text-gray-600 hover:bg-gray-100 rounded-lg text-sm"
                >
                  取消
                </button>
                <button
                  @click="handleUploadSong"
                  :disabled="isUploadingSong || !newSongFile || !newSongTitle.trim()"
                  class="px-3 py-1.5 bg-pink-500 hover:bg-pink-600 disabled:bg-gray-300 text-white rounded-lg text-sm flex items-center gap-1"
                >
                  <svg v-if="isUploadingSong" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  {{ isUploadingSong ? '上传中...' : '上传' }}
                </button>
              </div>
            </div>
          </div>

          <div v-if="songsList.length > 0" class="p-3 space-y-2">
            <div
              v-for="song in songsList"
              :key="song.id"
              class="bg-white rounded-lg border p-3 flex items-center justify-between hover:shadow-sm transition-shadow"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span class="text-lg flex-shrink-0">🎵</span>
                <div class="min-w-0">
                  <span class="text-sm font-medium text-gray-800 block truncate">{{ song.title }}</span>
                  <span class="text-xs text-gray-400">{{ song.title_en }}</span>
                </div>
              </div>
              <div class="flex items-center gap-1 flex-shrink-0">
                <button
                  @click="previewSong(song)"
                  class="p-1.5 hover:bg-pink-50 rounded transition-colors"
                  :title="playingSongId === song.id ? '停止' : '试听'"
                >
                  <svg v-if="playingSongId === song.id" class="w-4 h-4 text-pink-500" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="6" y="6" width="12" height="12" rx="2" />
                  </svg>
                  <svg v-else class="w-4 h-4 text-pink-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </button>
                <button
                  @click="handleDeleteSong(song)"
                  class="p-1.5 hover:bg-red-50 rounded transition-colors"
                  title="删除"
                >
                  <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <!-- 空状态 -->
          <div v-else-if="!showSongUploader" class="text-center py-12 px-4">
            <div class="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 flex items-center justify-center">
              <span class="text-2xl">🎵</span>
            </div>
            <p class="text-gray-500 text-sm mb-3">还没有儿歌</p>
            <button
              @click="showSongUploader = true"
              class="text-pink-500 hover:text-pink-600 text-sm font-medium"
            >
              上传第一首儿歌
            </button>
          </div>
        </template>

        <!-- 故事/古诗/英语列表 -->
        <template v-else>
          <div v-if="stories.length > 0" class="p-3 space-y-2">
            <div
              v-for="story in stories"
              :key="story.id"
              class="bg-white rounded-lg border p-3 flex items-center justify-between hover:shadow-sm transition-shadow"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span class="text-lg flex-shrink-0">{{ currentConfig.icon }}</span>
                <span class="text-sm font-medium text-gray-800 truncate">{{ story.title }}</span>
              </div>
              <div class="flex items-center gap-1 flex-shrink-0">
                <button
                  @click="openEdit(story)"
                  class="p-1.5 hover:bg-gray-100 rounded transition-colors"
                  title="编辑"
                >
                  <svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <button
                  @click="handleDelete(story)"
                  class="p-1.5 hover:bg-red-50 rounded transition-colors"
                  title="删除"
                >
                  <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-else class="text-center py-12 px-4">
            <div class="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 flex items-center justify-center">
              <span class="text-2xl">{{ currentConfig.icon }}</span>
            </div>
            <p class="text-gray-500 text-sm mb-3">还没有{{ currentConfig.label }}</p>
            <button
              @click="openCreate"
              class="text-pink-500 hover:text-pink-600 text-sm font-medium"
            >
              添加第一{{ currentConfig.unit }}
            </button>
          </div>
        </template>
      </div>
    </template>

    <!-- 故事编辑器弹窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showEditor"
          class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          @click.self="showEditor = false"
        >
          <div class="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
            <div class="flex items-center justify-between p-4 border-b">
              <h2 class="text-lg font-semibold">
                {{ editingStory ? '编辑' : '添加' }}{{ currentConfig.label }}
              </h2>
              <button @click="showEditor = false" class="p-2 hover:bg-gray-100 rounded-lg">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div class="flex-1 overflow-y-auto p-4 space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">标题</label>
                <div class="flex gap-2">
                  <input
                    v-model="form.title"
                    type="text"
                    :placeholder="currentConfig.placeholder.title"
                    class="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-pink-500"
                    :disabled="isGenerating"
                  />
                  <!-- 故事才有自动获取按钮 -->
                  <button
                    v-if="!editingStory && currentSkillId === 'storytelling'"
                    @click="handleGenerate"
                    :disabled="isGenerating || !form.title.trim()"
                    class="px-4 py-2 bg-green-500 hover:bg-green-600 disabled:bg-gray-300 text-white rounded-lg transition-colors whitespace-nowrap flex items-center gap-2"
                  >
                    <svg v-if="isGenerating" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>{{ isGenerating ? '生成中...' : '自动获取' }}</span>
                  </button>
                </div>
                <p v-if="!editingStory && currentSkillId === 'storytelling'" class="text-xs text-gray-400 mt-1">输入名称后点击"自动获取"，AI 会自动生成内容</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">内容</label>
                <textarea
                  v-model="form.content"
                  :placeholder="currentConfig.placeholder.content"
                  :rows="currentSkillId === 'storytelling' ? 12 : 10"
                  class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-pink-500 resize-none font-mono text-sm"
                  :disabled="isGenerating"
                ></textarea>
                <p v-if="currentConfig.hint" class="text-xs text-gray-400 mt-1">{{ currentConfig.hint }}</p>
              </div>

            </div>

            <div class="flex justify-end gap-3 p-4 border-t">
              <button @click="showEditor = false" class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">
                取消
              </button>
              <button @click="handleSave" class="px-4 py-2 bg-pink-500 hover:bg-pink-600 text-white rounded-lg">
                保存
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
