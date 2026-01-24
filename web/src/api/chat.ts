/**
 * 对话 API
 */

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatEvent {
  type: 'token' | 'skill_start' | 'skill_end' | 'done' | 'error'
  content?: string
  name?: string
  input?: Record<string, unknown>
  output?: string
  message?: string
}

export interface ChatOptions {
  model?: string
  temperature?: number
  maxTokens?: number
}

/**
 * 发送聊天消息（SSE 流式）
 */
export async function* streamChat(
  message: string,
  history: ChatMessage[] = [],
  options: ChatOptions = {}
): AsyncGenerator<ChatEvent> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      history,
      model: options.model,
      temperature: options.temperature,
      max_tokens: options.maxTokens,
    }),
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

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
          yield data as ChatEvent
        } catch {
          // 忽略解析错误
        }
      }
    }
  }
}

/**
 * 发送聊天消息（非流式）
 */
export async function sendChat(
  message: string,
  history: ChatMessage[] = [],
  options: ChatOptions = {}
): Promise<string> {
  const response = await fetch('/api/chat/simple', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      history,
      model: options.model,
      temperature: options.temperature,
      max_tokens: options.maxTokens,
    }),
  })

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const data = await response.json()
  return data.response
}
