/**
 * ASR 语音识别 API
 */

import { useSettingsStore, type ASRService } from '@/stores/settings'

export interface ASRResult {
  success: boolean
  text: string
  segments?: Array<{
    start: number
    end: number
    text: string
  }>
}

// ASR 服务端点配置
const ASR_ENDPOINTS: Record<ASRService, string> = {
  sensevoice: '/api/asr/sensevoice/transcribe',
  whisper: '/api/asr/whisper/transcribe',
  funasr: '/api/asr/funasr/transcribe',
}

/**
 * 语音转文字
 */
export async function transcribe(audioBlob: Blob, service?: ASRService): Promise<ASRResult> {
  // 获取当前设置的 ASR 服务
  const settings = useSettingsStore()
  const asrService = service ?? settings.asrService
  const endpoint = ASR_ENDPOINTS[asrService]

  const formData = new FormData()
  // 使用正确的文件扩展名（与录音格式 webm 匹配）
  formData.append('audio', audioBlob, 'recording.webm')

  console.log(`[ASR] 使用 ${asrService} 服务: ${endpoint}`)

  const response = await fetch(endpoint, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(`ASR error! status: ${response.status}`)
  }

  return response.json()
}

/**
 * 检查 ASR 服务健康状态
 */
export async function checkASRHealth(): Promise<boolean> {
  try {
    const response = await fetch('/api/asr/health')
    const data = await response.json()
    return data.status === 'healthy'
  } catch {
    return false
  }
}
