<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSettingsStore, ASR_SERVICES, LLM_MODELS, TTS_VOICES, VAD_TYPES, BACKGROUNDS, AVATARS } from '@/stores/settings'
import { getStories, createStory, updateStory, deleteStory, generateStory, type Story } from '@/api/skills'
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

// ========== 设置相关 ==========
const silenceDurationDisplay = computed(() => {
  return (settings.silenceDuration / 1000).toFixed(1) + 's'
})

const vadIgnoreTimeDisplay = computed(() => {
  return settings.vadIgnoreTime + 'ms'
})

const tooltips = {
  asrService: '选择语音识别服务。FunASR中文识别效果好；Whisper多语言支持好。',
  silenceThreshold: '当麦克风音量低于此值时判定为静音。',
  silenceDuration: '静音持续多长时间后自动停止录音并发送。',
  llmModel: '选择大语言模型。',
  llmTemperature: '控制AI回复的随机性。0=稳定；1.5=创意。',
  llmMaxTokens: '限制AI单次回复的最大长度。',
  llmMaxHistory: '保留多少轮对话历史作为上下文。',
  ttsVoice: '选择语音合成的声音角色。',
  ttsSpeed: '调整语音播放速度。0.5=慢速，1.0=正常，2.0=快速。',
  ttsGain: '放大语音播放的音量。',
  vadEnabled: '开启后，当AI说话时如果检测到你在说话，会自动停止播放。',
  vadType: '选择语音活动检测方式。',
  vadThreshold: '打断检测的音量阈值。（仅简单模式）',
  vadTriggerCount: '连续检测到多少次超过阈值才触发打断。',
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

// 合并的音色选项（预设 + 自定义）
const allVoiceOptions = computed(() => {
  const preset = TTS_VOICES.map(v => ({
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
      settings.ttsVoice = 'alex'  // 默认值
    } else {
      settings.ttsCustomVoiceId = null
      settings.ttsVoice = val
    }
  },
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

// ========== 故事管理相关 ==========
const SKILL_ID = 'storytelling'
const stories = ref<Story[]>([])
const isLoading = ref(false)
const showEditor = ref(false)
const editingStory = ref<Story | null>(null)
const isGenerating = ref(false)

const form = ref({
  title: '',
  content: '',
})

async function loadStories() {
  isLoading.value = true
  try {
    stories.value = await getStories(SKILL_ID)
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
  const fullStory = await import('@/api/skills').then(m => m.getStory(SKILL_ID, story.id))
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
      await updateStory(SKILL_ID, editingStory.value.id, {
        title: form.value.title,
        content: form.value.content,
      })
    } else {
      await createStory(SKILL_ID, {
        title: form.value.title,
        content: form.value.content,
      })
    }
    showEditor.value = false
    await loadStories()
  } catch (error) {
    console.error('Failed to save story:', error)
    alert('保存失败')
  }
}

async function handleDelete(story: Story) {
  if (!confirm(`确定要删除「${story.title}」吗？`)) return
  try {
    await deleteStory(SKILL_ID, story.id)
    await loadStories()
  } catch (error) {
    console.error('Failed to delete story:', error)
    alert('删除失败')
  }
}

async function handleGenerate() {
  if (!form.value.title.trim()) {
    alert('请先输入故事名称')
    return
  }
  isGenerating.value = true
  try {
    const result = await generateStory(SKILL_ID, form.value.title.trim())
    form.value.content = result.content
  } catch (error: any) {
    console.error('Failed to generate story:', error)
    alert('生成失败: ' + (error.message || '未知错误'))
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
        故事管理
      </button>
    </div>

    <!-- 设置面板 -->
    <template v-if="activeTab === 'settings'">
      <!-- 设置内容 -->
      <div class="flex-1 overflow-y-auto p-4 pr-4 md:pr-6 space-y-3 bg-gray-50 md:border-l border-gray-200">
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
            <div class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.ttsVoice">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">声音</span>
              </div>
              <select v-model="selectedVoiceId" class="w-full px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-yellow-500">
                <optgroup label="预设音色">
                  <option v-for="voice in TTS_VOICES" :key="voice.id" :value="voice.id">{{ voice.name }}</option>
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
              <input type="range" v-model.number="settings.ttsGain" min="1" max="20" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-yellow-500" />
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
                <option v-for="vad in VAD_TYPES" :key="vad.id" :value="vad.id">{{ vad.name }}</option>
              </select>
            </div>
            <div v-show="settings.vadType === 'simple'" class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.vadThreshold">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">打断阈值</span>
                <span class="text-sm font-medium">{{ settings.vadThreshold }}</span>
              </div>
              <input type="range" v-model.number="settings.vadThreshold" min="10" max="80" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-500" />
            </div>
            <div v-show="settings.vadType === 'simple'" class="bg-white border rounded-lg p-2 cursor-help" :title="tooltips.vadTriggerCount">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">触发次数</span>
                <span class="text-sm font-medium">{{ settings.vadTriggerCount }}</span>
              </div>
              <input type="range" v-model.number="settings.vadTriggerCount" min="2" max="10" class="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-red-500" />
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

        <!-- 外观设置 -->
        <section class="space-y-2">
          <div class="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-purple-100 text-purple-600">
            ⑤ 外观设置
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <!-- 角色选择 -->
            <div class="bg-white border rounded-lg p-2">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">角色形象</span>
              </div>
              <div class="grid grid-cols-2 gap-1">
                <button
                  v-for="av in AVATARS"
                  :key="av.id"
                  @click="settings.avatar = av.id"
                  :class="[
                    'p-2 rounded-lg text-xs text-center transition-colors',
                    settings.avatar === av.id
                      ? 'bg-purple-100 text-purple-600 ring-2 ring-purple-400'
                      : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                  ]"
                >
                  <span class="text-lg">{{ av.icon }}</span>
                  <div>{{ av.name }}</div>
                </button>
              </div>
            </div>
            <!-- 背景选择 -->
            <div class="bg-white border rounded-lg p-2">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">背景主题</span>
              </div>
              <div class="grid grid-cols-5 gap-1">
                <button
                  v-for="bg in BACKGROUNDS"
                  :key="bg.id"
                  @click="settings.background = bg.id"
                  :class="[
                    'w-8 h-8 rounded-full transition-transform',
                    settings.background === bg.id ? 'ring-2 ring-purple-400 scale-110' : 'hover:scale-105'
                  ]"
                  :style="{ background: `linear-gradient(135deg, ${bg.colors[0]}, ${bg.colors[1]})` }"
                  :title="bg.name"
                ></button>
              </div>
            </div>
            <!-- 助手名字 -->
            <div class="bg-white border rounded-lg p-2 sm:col-span-2">
              <div class="flex justify-between items-center mb-2">
                <span class="text-sm text-gray-600">助手名字</span>
                <span class="text-xs text-gray-400">喊名字可打断</span>
              </div>
              <input
                v-model="settings.assistantName"
                type="text"
                placeholder="给助手起个名字"
                maxlength="10"
                class="w-full px-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
          </div>
        </section>
      </div>
    </template>

    <!-- 故事管理面板 -->
    <template v-else-if="activeTab === 'stories'">
      <!-- 工具栏 -->
      <div class="bg-gray-50 md:border-l border-b border-gray-200 px-4 py-2 flex items-center justify-between">
        <span class="text-sm text-gray-500">共 {{ stories.length }} 个故事</span>
        <button
          @click="openCreate"
          class="flex items-center gap-1 px-3 py-1.5 bg-pink-500 hover:bg-pink-600 text-white text-sm rounded-lg transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          添加
        </button>
      </div>

      <!-- 故事列表 -->
      <div class="flex-1 overflow-y-auto bg-gray-50 md:border-l border-gray-200">
        <!-- 加载状态 -->
        <div v-if="isLoading" class="flex justify-center py-12">
          <div class="w-8 h-8 border-4 border-pink-200 border-t-pink-500 rounded-full animate-spin"></div>
        </div>

        <!-- 故事列表 -->
        <div v-else-if="stories.length > 0" class="p-3 space-y-2">
          <div
            v-for="story in stories"
            :key="story.id"
            class="bg-white rounded-lg border p-3 flex items-center justify-between hover:shadow-sm transition-shadow"
          >
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-lg flex-shrink-0">📖</span>
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
            <span class="text-2xl">📚</span>
          </div>
          <p class="text-gray-500 text-sm mb-3">还没有故事</p>
          <button
            @click="openCreate"
            class="text-pink-500 hover:text-pink-600 text-sm font-medium"
          >
            添加第一个故事
          </button>
        </div>
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
                {{ editingStory ? '编辑故事' : '添加故事' }}
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
                    placeholder="输入故事名称，如：白雪公主"
                    class="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-pink-500"
                    :disabled="isGenerating"
                  />
                  <button
                    v-if="!editingStory"
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
                <p v-if="!editingStory" class="text-xs text-gray-400 mt-1">输入故事名称后点击"自动获取"，AI 会自动生成故事内容</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">内容</label>
                <textarea
                  v-model="form.content"
                  placeholder="故事内容（支持 Markdown 格式）"
                  rows="12"
                  class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-pink-500 resize-none font-mono text-sm"
                  :disabled="isGenerating"
                ></textarea>
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
