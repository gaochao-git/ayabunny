<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import type { Message, ToolCall } from '@/composables/useChat'

const props = defineProps<{
  messages: Message[]
  streamingContent: string
  isLoading: boolean
  currentSkill?: string | null
  toolCalls?: ToolCall[]  // 当前正在进行的工具调用
}>()

const containerRef = ref<HTMLDivElement | null>(null)

// 自动滚动到底部
watch(
  () => [props.messages.length, props.streamingContent],
  async () => {
    await nextTick()
    if (containerRef.value) {
      containerRef.value.scrollTop = containerRef.value.scrollHeight
    }
  }
)
</script>

<template>
  <div
    ref="containerRef"
    class="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50"
  >
    <!-- 消息列表 -->
    <div
      v-for="message in messages"
      :key="message.id"
      class="message-enter"
    >
      <!-- 助手消息 -->
      <div v-if="message.role === 'assistant'" class="flex flex-col">
        <span class="text-xs text-gray-400 mb-1 ml-1">小智</span>
        <!-- 工具调用记录（调试用） -->
        <div
          v-if="message.toolCalls && message.toolCalls.length > 0"
          class="mb-2 max-w-[90%]"
        >
          <div
            v-for="(tool, idx) in message.toolCalls"
            :key="idx"
            class="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 mb-1 text-xs"
          >
            <div class="flex items-center gap-1 text-blue-600 font-medium">
              <span>🔧</span>
              <span>{{ tool.name }}</span>
              <span class="text-blue-400">({{ tool.status === 'done' ? '完成' : '运行中' }})</span>
            </div>
            <div class="mt-1 text-gray-600">
              <div><span class="text-gray-400">参数:</span> {{ JSON.stringify(tool.input) }}</div>
              <div v-if="tool.output" class="mt-1">
                <span class="text-gray-400">结果:</span>
                <span class="text-green-600">{{ tool.output.slice(0, 100) }}{{ tool.output.length > 100 ? '...' : '' }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm max-w-[85%]">
          <p class="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
            {{ message.content }}
          </p>
        </div>
      </div>

      <!-- 用户消息 -->
      <div v-else class="flex justify-end">
        <div class="bg-gradient-to-r from-pink-400 to-orange-400 text-white rounded-2xl rounded-tr-sm px-4 py-3 max-w-[85%]">
          <p class="whitespace-pre-wrap text-sm leading-relaxed">
            {{ message.content }}
          </p>
        </div>
      </div>
    </div>

    <!-- 正在进行的工具调用（流式时显示） -->
    <div v-if="toolCalls && toolCalls.length > 0" class="flex flex-col message-enter">
      <span class="text-xs text-gray-400 mb-1 ml-1">小智</span>
      <div class="max-w-[90%]">
        <div
          v-for="(tool, idx) in toolCalls"
          :key="idx"
          class="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 mb-1 text-xs"
        >
          <div class="flex items-center gap-1 text-blue-600 font-medium">
            <span class="animate-spin" v-if="tool.status === 'running'">⚙️</span>
            <span v-else>🔧</span>
            <span>{{ tool.name }}</span>
            <span v-if="tool.status === 'running'" class="text-blue-400 animate-pulse">调用中...</span>
            <span v-else class="text-green-500">✓ 完成</span>
          </div>
          <div class="mt-1 text-gray-600">
            <div><span class="text-gray-400">参数:</span> {{ JSON.stringify(tool.input) }}</div>
            <div v-if="tool.output" class="mt-1">
              <span class="text-gray-400">结果:</span>
              <span class="text-green-600">{{ tool.output.slice(0, 100) }}{{ tool.output.length > 100 ? '...' : '' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 流式输出 -->
    <div v-if="streamingContent" class="flex flex-col message-enter">
      <span class="text-xs text-gray-400 mb-1 ml-1">小智</span>
      <div class="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm max-w-[85%]">
        <p class="whitespace-pre-wrap text-sm leading-relaxed text-gray-700 typing-cursor">
          {{ streamingContent }}
        </p>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="isLoading && !streamingContent" class="flex flex-col">
      <span class="text-xs text-gray-400 mb-1 ml-1">小智</span>
      <div class="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm inline-block">
        <div class="flex space-x-1.5">
          <span class="w-2 h-2 bg-pink-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-2 h-2 bg-pink-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-2 h-2 bg-pink-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
        </div>
      </div>
    </div>

    <!-- 空状态 - 初始欢迎消息 -->
    <div v-if="messages.length === 0 && !isLoading && !streamingContent" class="flex flex-col">
      <span class="text-xs text-gray-400 mb-1 ml-1">小智</span>
      <div class="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm max-w-[85%]">
        <p class="text-sm leading-relaxed text-gray-700">
          对话已清空，让我们重新开始吧！
        </p>
      </div>
    </div>
  </div>
</template>
