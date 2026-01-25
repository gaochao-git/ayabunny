/**
 * TTS 语音合成 API - SiliconFlow IndexTTS-2 云端 + 音色克隆
 */

export interface TTSOptions {
  text: string
  voice?: string  // IndexTTS-2 音色: alex, benjamin, charles, david, anna, bella, claire, diana
  customVoiceId?: string  // 自定义音色 ID（优先级高于 voice）
}

export interface CustomVoice {
  id: string
  name: string
  description: string
  created_at: string
  audio_file: string
  duration: number
}

/**
 * 文字转语音
 */
export async function synthesize(options: TTSOptions): Promise<ArrayBuffer> {
  const response = await fetch('/api/tts/synthesize', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text: options.text,
      voice: options.voice || 'alex',
      custom_voice_id: options.customVoiceId,
    }),
  })

  if (!response.ok) {
    throw new Error(`TTS error! status: ${response.status}`)
  }

  return response.arrayBuffer()
}

/**
 * 检查 TTS 服务健康状态
 */
export async function checkTTSHealth(): Promise<boolean> {
  try {
    const response = await fetch('/api/tts/health')
    const data = await response.json()
    return data.status === 'healthy'
  } catch {
    return false
  }
}

// ========== 自定义音色管理 ==========

/**
 * 获取所有自定义音色
 */
export async function getCustomVoices(): Promise<CustomVoice[]> {
  const response = await fetch('/api/tts/voices')
  if (!response.ok) {
    throw new Error(`Failed to get voices: ${response.status}`)
  }
  const data = await response.json()
  return data.voices
}

/**
 * 创建自定义音色（上传参考音频）
 */
export async function createCustomVoice(
  audio: Blob,
  name: string,
  description: string = ''
): Promise<CustomVoice> {
  const formData = new FormData()
  formData.append('audio', audio, 'voice.webm')
  formData.append('name', name)
  formData.append('description', description)

  const response = await fetch('/api/tts/voices', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`Failed to create voice: ${error}`)
  }

  const data = await response.json()
  return data.voice
}

/**
 * 删除自定义音色
 */
export async function deleteCustomVoice(voiceId: string): Promise<void> {
  const response = await fetch(`/api/tts/voices/${voiceId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error(`Failed to delete voice: ${response.status}`)
  }
}

/**
 * 测试自定义音色
 */
export async function testCustomVoice(
  voiceId: string,
  text: string = '你好，这是一段测试语音。'
): Promise<ArrayBuffer> {
  const response = await fetch(`/api/tts/voices/${voiceId}/test`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text }),
  })

  if (!response.ok) {
    throw new Error(`Failed to test voice: ${response.status}`)
  }

  return response.arrayBuffer()
}

/**
 * 获取音色参考音频 URL
 */
export function getVoiceAudioUrl(voiceId: string): string {
  return `/api/tts/voices/${voiceId}/audio`
}
