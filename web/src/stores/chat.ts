/**
 * 聊天状态管理
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ChatMessage } from '@/api/chat'

export interface Message extends ChatMessage {
  id: string
  timestamp: number
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const isLoading = ref(false)
  const currentSkill = ref<string | null>(null)

  const history = computed<ChatMessage[]>(() =>
    messages.value.map(({ role, content }) => ({ role, content }))
  )

  function addMessage(role: 'user' | 'assistant', content: string): Message {
    const message: Message = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      role,
      content,
      timestamp: Date.now(),
    }
    messages.value.push(message)
    return message
  }

  function updateLastMessage(content: string): void {
    const lastMessage = messages.value[messages.value.length - 1]
    if (lastMessage && lastMessage.role === 'assistant') {
      lastMessage.content = content
    }
  }

  function clear(): void {
    messages.value = []
  }

  return {
    messages,
    isLoading,
    currentSkill,
    history,
    addMessage,
    updateLastMessage,
    clear,
  }
})
