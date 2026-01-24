/**
 * TTS 语音合成 API - SiliconFlow IndexTTS-2 云端
 */

export interface TTSOptions {
  text: string
  voice?: string  // IndexTTS-2 音色: alex, benjamin, charles, david, anna, bella, claire, diana
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
