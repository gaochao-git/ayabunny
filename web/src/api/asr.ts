/**
 * ASR 语音识别 API
 */

export interface ASRResult {
  success: boolean
  text: string
  segments?: Array<{
    start: number
    end: number
    text: string
  }>
}

/**
 * 语音转文字
 */
export async function transcribe(audioBlob: Blob): Promise<ASRResult> {
  const formData = new FormData()
  // 使用正确的文件扩展名（与录音格式 webm 匹配）
  formData.append('audio', audioBlob, 'recording.webm')

  const response = await fetch('/api/asr/transcribe', {
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
