/**
 * 对话 Composable
 */

import { ref, computed } from 'vue'
import { streamChat, type ChatMessage, type ChatEvent, type ChatOptions } from '@/api/chat'
import { useSettingsStore } from '@/stores/settings'

export interface ToolCall {
  name: string
  input: Record<string, unknown>
  output?: string
  status: 'running' | 'done'
  timestamp: number
}

export interface Message extends ChatMessage {
  id: string
  timestamp: number
  toolCalls?: ToolCall[]  // 工具调用记录
}

// 音乐控制动作
export interface MusicAction {
  type: 'play' | 'pause' | 'resume' | 'stop' | 'next'
  song?: {
    id: string
    title: string
    file: string
  }
}

export function useChat() {
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const currentSkill = ref<string | null>(null)
  const currentBgm = ref<string | null>(null)  // 当前故事的背景音乐
  const streamingContent = ref('')
  const toolCalls = ref<ToolCall[]>([])  // 当前响应的工具调用记录
  const musicAction = ref<MusicAction | null>(null)  // 音乐控制动作

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
    toolCalls.value = []  // 清空工具调用记录

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

      // 添加完整的助手消息（包含工具调用记录）
      if (fullResponse) {
        const message: Message = {
          id: generateId(),
          role: 'assistant',
          content: fullResponse,
          timestamp: Date.now(),
          toolCalls: toolCalls.value.length > 0 ? [...toolCalls.value] : undefined,
        }
        messages.value.push(message)
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
        // 提取 BGM 信息（如果有）
        currentBgm.value = (event as any).bgm || null
        // 记录工具调用开始
        toolCalls.value.push({
          name: event.name || 'unknown',
          input: event.input || {},
          status: 'running',
          timestamp: Date.now(),
        })
        console.log(`[Tool] 调用工具: ${event.name}`, event.input, 'bgm:', currentBgm.value)
        break
      case 'skill_end':
        currentSkill.value = null
        currentBgm.value = null
        // 更新工具调用结果
        const lastCall = toolCalls.value.find(
          t => t.name === event.name && t.status === 'running'
        )
        if (lastCall) {
          lastCall.status = 'done'
          lastCall.output = event.output
        }
        console.log(`[Tool] 工具返回: ${event.name}`, event.output?.slice(0, 200))
        break
      case 'music':
        // 音乐控制事件
        const musicEvent = event as any
        musicAction.value = {
          type: musicEvent.action || 'play',
          song: musicEvent.song,
        }
        console.log(`[Music] 收到音乐控制:`, musicAction.value)
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
    currentBgm.value = null
    musicAction.value = null
  }

  /**
   * 清除音乐动作（处理后调用）
   */
  function clearMusicAction(): void {
    musicAction.value = null
  }

  return {
    messages,
    isLoading,
    currentSkill,
    currentBgm,  // 当前故事的背景音乐
    streamingContent,
    toolCalls,  // 当前工具调用记录
    musicAction,  // 音乐控制动作
    send,
    abort,  // 取消当前请求
    clear,
    clearMusicAction,
    addUserMessage,
    addAssistantMessage,
  }
}
