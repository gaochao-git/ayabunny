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

// 工具调用展开状态：key = messageId-toolIndex 或 streaming-toolIndex
const expandedTools = ref<Set<string>>(new Set())

// 切换工具展开/折叠
function toggleTool(key: string) {
  if (expandedTools.value.has(key)) {
    expandedTools.value.delete(key)
  } else {
    expandedTools.value.add(key)
  }
}

// 检查工具是否展开
function isToolExpanded(key: string): boolean {
  return expandedTools.value.has(key)
}

// 格式化 JSON 显示
function formatJson(obj: unknown): string {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

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
        <!-- 工具调用记录（可折叠） -->
        <div
          v-if="message.toolCalls && message.toolCalls.length > 0"
          class="mb-2 max-w-[90%]"
        >
          <div
            v-for="(tool, idx) in message.toolCalls"
            :key="idx"
            class="bg-blue-50 border border-blue-200 rounded-lg overflow-hidden mb-1 text-xs"
          >
            <!-- 折叠头部（可点击） -->
            <div
              class="flex items-center gap-1 px-3 py-2 cursor-pointer hover:bg-blue-100 transition-colors"
              @click="toggleTool(`${message.id}-${idx}`)"
            >
              <span class="text-gray-400 text-[10px] transition-transform" :class="{ 'rotate-90': isToolExpanded(`${message.id}-${idx}`) }">▶</span>
              <span>🔧</span>
              <span class="text-blue-600 font-medium">{{ tool.name }}</span>
              <span class="text-green-500">✓</span>
              <span class="text-gray-400 ml-auto text-[10px]">点击{{ isToolExpanded(`${message.id}-${idx}`) ? '收起' : '展开' }}</span>
            </div>
            <!-- 展开内容 -->
            <div
              v-if="isToolExpanded(`${message.id}-${idx}`)"
              class="px-3 py-2 border-t border-blue-200 bg-white/50"
            >
              <div class="text-gray-600 mb-2">
                <div class="text-gray-400 mb-1">参数:</div>
                <pre class="bg-gray-100 p-2 rounded text-[11px] overflow-x-auto whitespace-pre-wrap break-all">{{ formatJson(tool.input) }}</pre>
              </div>
              <div v-if="tool.output" class="text-gray-600">
                <div class="text-gray-400 mb-1">结果:</div>
                <pre class="bg-green-50 p-2 rounded text-[11px] overflow-x-auto whitespace-pre-wrap break-all text-green-700">{{ tool.output }}</pre>
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
          <!-- 图片（如果有） -->
          <img
            v-if="message.image"
            :src="message.image"
            class="max-w-full max-h-48 rounded-lg mb-2"
          />
          <p class="whitespace-pre-wrap text-sm leading-relaxed">
            {{ message.content }}
          </p>
        </div>
      </div>
    </div>

    <!-- 正在进行的工具调用（流式时显示，可折叠） -->
    <div v-if="toolCalls && toolCalls.length > 0" class="flex flex-col message-enter">
      <span class="text-xs text-gray-400 mb-1 ml-1">小智</span>
      <div class="max-w-[90%]">
        <div
          v-for="(tool, idx) in toolCalls"
          :key="idx"
          class="bg-blue-50 border border-blue-200 rounded-lg overflow-hidden mb-1 text-xs"
        >
          <!-- 折叠头部（可点击） -->
          <div
            class="flex items-center gap-1 px-3 py-2 cursor-pointer hover:bg-blue-100 transition-colors"
            @click="toggleTool(`streaming-${idx}`)"
          >
            <span class="text-gray-400 text-[10px] transition-transform" :class="{ 'rotate-90': isToolExpanded(`streaming-${idx}`) }">▶</span>
            <span class="animate-spin" v-if="tool.status === 'running'">⚙️</span>
            <span v-else>🔧</span>
            <span class="text-blue-600 font-medium">{{ tool.name }}</span>
            <span v-if="tool.status === 'running'" class="text-blue-400 animate-pulse">调用中...</span>
            <span v-else class="text-green-500">✓</span>
            <span class="text-gray-400 ml-auto text-[10px]">点击{{ isToolExpanded(`streaming-${idx}`) ? '收起' : '展开' }}</span>
          </div>
          <!-- 展开内容 -->
          <div
            v-if="isToolExpanded(`streaming-${idx}`)"
            class="px-3 py-2 border-t border-blue-200 bg-white/50"
          >
            <div class="text-gray-600 mb-2">
              <div class="text-gray-400 mb-1">参数:</div>
              <pre class="bg-gray-100 p-2 rounded text-[11px] overflow-x-auto whitespace-pre-wrap break-all">{{ formatJson(tool.input) }}</pre>
            </div>
            <div v-if="tool.output" class="text-gray-600">
              <div class="text-gray-400 mb-1">结果:</div>
              <pre class="bg-green-50 p-2 rounded text-[11px] overflow-x-auto whitespace-pre-wrap break-all text-green-700">{{ tool.output }}</pre>
            </div>
            <div v-else-if="tool.status === 'running'" class="text-gray-400 italic">
              等待结果...
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
