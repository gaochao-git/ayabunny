/**
 * 视频分析 API
 */

import { getApiUrl } from './config'

export interface VideoEvent {
  type: 'token' | 'info' | 'done' | 'error'
  content?: string
}

export interface AnalyzeFrameOptions {
  frame: string  // base64 图片
  question?: string
  context?: string
  signal?: AbortSignal
}

export interface AnalyzeFramesOptions {
  frames: string[]  // base64 图片数组
  question?: string
  signal?: AbortSignal
}

/**
 * 分析单帧图片（SSE 流式）
 */
export async function* analyzeFrame(options: AnalyzeFrameOptions): AsyncGenerator<VideoEvent> {
  const response = await fetch(getApiUrl('/api/video/analyze-frame'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      frame: options.frame,
      question: options.question || '',
      context: options.context || '',
    }),
    signal: options.signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  yield* parseSSE(response)
}

/**
 * 分析多帧图片（SSE 流式）
 */
export async function* analyzeFrames(options: AnalyzeFramesOptions): AsyncGenerator<VideoEvent> {
  const response = await fetch(getApiUrl('/api/video/analyze-frames'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      frames: options.frames,
      question: options.question || '',
    }),
    signal: options.signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  yield* parseSSE(response)
}

/**
 * 分析视频文件（SSE 流式）
 */
export async function* analyzeVideo(
  file: Blob,
  question: string = '',
  interval: number = 2.0,
  signal?: AbortSignal
): AsyncGenerator<VideoEvent> {
  const formData = new FormData()
  formData.append('file', file, 'video.webm')
  formData.append('question', question)
  formData.append('interval', interval.toString())

  const response = await fetch(getApiUrl('/api/video/analyze-video'), {
    method: 'POST',
    body: formData,
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  yield* parseSSE(response)
}

/**
 * 解析 SSE 响应
 */
async function* parseSSE(response: Response): AsyncGenerator<VideoEvent> {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          yield data as VideoEvent
        } catch {
          // 忽略解析错误
        }
      }
    }
  }
}
