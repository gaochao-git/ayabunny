/**
 * 对话 Composable
 */

import { ref, computed } from 'vue'
import { streamChat, type ChatMessage, type ChatEvent, type ChatOptions } from '@/api/chat'
import { useSettingsStore } from '@/stores/settings'

export interface Message extends ChatMessage {
  id: string
  timestamp: number
  skill?: {
    name: string
    status: 'pending' | 'running' | 'done'
  }
}

export function useChat() {
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const currentSkill = ref<string | null>(null)
  const streamingContent = ref('')

  // 用于取消请求
  let abortController: AbortController | null = null

  const history = computed<ChatMessage[]>(() =>
    messages.value.map(({ role, content }) => ({ role, content }))
  )

  /**
   * 生成消息 ID
   */
  function generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
  }

  /**
   * 添加用户消息
   */
  function addUserMessage(content: string): Message {
    const message: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    messages.value.push(message)
    return message
  }

  /**
   * 添加助手消息
   */
  function addAssistantMessage(content: string): Message {
    const message: Message = {
      id: generateId(),
      role: 'assistant',
      content,
      timestamp: Date.now(),
    }
    messages.value.push(message)
    return message
  }

  /**
   * 发送消息（流式）
   * @param content 用户消息
   * @param onSentence 可选回调，每当检测到完整句子时调用（用于流式 TTS）
   */
  async function send(content: string, onSentence?: (sentence: string) => void): Promise<string> {
    if (isLoading.value) return ''

    // 创建新的 AbortController
    abortController = new AbortController()

    // 获取 LLM 设置
    const settings = useSettingsStore()
    const chatOptions: ChatOptions = {
      model: settings.llmModel,
      temperature: settings.llmTemperature,
      maxTokens: settings.llmMaxTokens,
      assistantName: settings.assistantName,
      signal: abortController.signal,  // 传递 AbortSignal
    }

    // 添加用户消息
    addUserMessage(content)

    isLoading.value = true
    streamingContent.value = ''
    currentSkill.value = null

    let fullResponse = ''
    let pendingSentence = ''  // 待发送的句子缓冲

    // 分句策略：强分隔符立即触发，弱分隔符需要累积一定长度
    const strongEnders = /[。！？.!?\n]/  // 强分隔符：句子结束
    const weakEnders = /[，,；;：:]/       // 弱分隔符：短暂停顿
    const minLengthForWeak = 15           // 弱分隔符触发的最小长度
    const maxBufferLength = 50            // 最大缓冲长度（避免长句等太久）

    try {
      // 流式获取响应
      for await (const event of streamChat(content, history.value.slice(0, -1), chatOptions)) {
        handleEvent(event)

        if (event.type === 'token' && event.content) {
          fullResponse += event.content
          streamingContent.value = fullResponse

          // 流式 TTS：智能分句
          if (onSentence) {
            pendingSentence += event.content

            // 检查是否触发 TTS
            const isStrongEnd = strongEnders.test(event.content)
            const isWeakEnd = weakEnders.test(event.content)
            const sentence = pendingSentence.trim()

            // 触发条件：
            // 1. 强分隔符（句号等）：立即触发
            // 2. 弱分隔符（逗号等）+ 长度达到阈值：触发
            // 3. 缓冲区超过最大长度：强制触发
            const shouldTrigger = sentence.length > 0 && (
              isStrongEnd ||
              (isWeakEnd && sentence.length >= minLengthForWeak) ||
              sentence.length >= maxBufferLength
            )

            if (shouldTrigger) {
              onSentence(sentence)
              pendingSentence = ''
            }
          }
        }
      }

      // 发送剩余的文本（如果有）
      if (onSentence && pendingSentence.trim().length > 0) {
        onSentence(pendingSentence.trim())
      }

      // 添加完整的助手消息
      if (fullResponse) {
        addAssistantMessage(fullResponse)
      }

      return fullResponse
    } catch (error) {
      // 忽略取消错误
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[Chat] 请求已取消')
        return fullResponse
      }
      console.error('Chat error:', error)
      throw error
    } finally {
      isLoading.value = false
      streamingContent.value = ''
      currentSkill.value = null
      abortController = null
    }
  }

  /**
   * 取消当前请求
   */
  function abort(): void {
    if (abortController) {
      console.log('[Chat] 取消请求')
      abortController.abort()
      abortController = null
    }
  }

  /**
   * 处理 SSE 事件
   */
  function handleEvent(event: ChatEvent): void {
    switch (event.type) {
      case 'skill_start':
        currentSkill.value = event.name || null
        break
      case 'skill_end':
        currentSkill.value = null
        break
      case 'error':
        console.error('Chat error:', event.message)
        break
    }
  }

  /**
   * 清空消息
   */
  function clear(): void {
    messages.value = []
    streamingContent.value = ''
    currentSkill.value = null
  }

  return {
    messages,
    isLoading,
    currentSkill,
    streamingContent,
    send,
    abort,  // 取消当前请求
    clear,
    addUserMessage,
    addAssistantMessage,
  }
}
