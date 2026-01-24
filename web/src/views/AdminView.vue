<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getStories, createStory, updateStory, deleteStory, type Story } from '@/api/skills'

const SKILL_ID = 'storytelling'

// 状态
const stories = ref<Story[]>([])
const isLoading = ref(false)
const showEditor = ref(false)
const editingStory = ref<Story | null>(null)

// 表单数据
const form = ref({
  title: '',
  content: '',
})

// 加载故事列表
async function loadStories() {
  isLoading.value = true
  try {
    stories.value = await getStories(SKILL_ID)
  } catch (error) {
    console.error('Failed to load stories:', error)
  } finally {
    isLoading.value = false
  }
}

// 打开编辑器（新建）
function openCreate() {
  editingStory.value = null
  form.value = { title: '', content: '' }
  showEditor.value = true
}

// 打开编辑器（编辑）
async function openEdit(story: Story) {
  editingStory.value = story
  // 获取完整内容
  const fullStory = await import('@/api/skills').then(m => m.getStory(SKILL_ID, story.id))
  form.value = {
    title: fullStory.title,
    content: fullStory.content?.replace(/^#\s+.+\n\n/, '') || '', // 移除标题行
  }
  showEditor.value = true
}

// 保存故事
async function handleSave() {
  if (!form.value.title.trim() || !form.value.content.trim()) {
    alert('请填写标题和内容')
    return
  }

  try {
    if (editingStory.value) {
      // 更新
      await updateStory(SKILL_ID, editingStory.value.id, {
        title: form.value.title,
        content: form.value.content,
      })
    } else {
      // 创建
      await createStory(SKILL_ID, {
        title: form.value.title,
        content: form.value.content,
      })
    }

    showEditor.value = false
    await loadStories()
  } catch (error) {
    console.error('Failed to save story:', error)
    alert('保存失败')
  }
}

// 删除故事
async function handleDelete(story: Story) {
  if (!confirm(`确定要删除「${story.title}」吗？`)) {
    return
  }

  try {
    await deleteStory(SKILL_ID, story.id)
    await loadStories()
  } catch (error) {
    console.error('Failed to delete story:', error)
    alert('删除失败')
  }
}

onMounted(loadStories)
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- 头部 -->
    <header class="bg-white border-b px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <router-link
          to="/"
          class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
          </svg>
        </router-link>
        <h1 class="font-semibold text-gray-900">故事管理</h1>
      </div>

      <button
        @click="openCreate"
        class="flex items-center gap-2 px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        添加故事
      </button>
    </header>

    <!-- 内容区 -->
    <main class="max-w-4xl mx-auto p-4">
      <!-- 加载状态 -->
      <div v-if="isLoading" class="flex justify-center py-12">
        <div class="w-8 h-8 border-4 border-primary-200 border-t-primary-500 rounded-full animate-spin"></div>
      </div>

      <!-- 故事列表 -->
      <div v-else-if="stories.length > 0" class="space-y-3">
        <div
          v-for="story in stories"
          :key="story.id"
          class="bg-white rounded-lg border p-4 flex items-center justify-between hover:shadow-sm transition-shadow"
        >
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center">
              <span class="text-xl">📖</span>
            </div>
            <div>
              <h3 class="font-medium text-gray-900">{{ story.title }}</h3>
              <p class="text-sm text-gray-500">{{ story.id }}.md</p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <button
              @click="openEdit(story)"
              class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title="编辑"
            >
              <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              @click="handleDelete(story)"
              class="p-2 hover:bg-red-50 rounded-lg transition-colors"
              title="删除"
            >
              <svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-else class="text-center py-12">
        <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 flex items-center justify-center">
          <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        </div>
        <p class="text-gray-500 mb-4">还没有故事</p>
        <button
          @click="openCreate"
          class="text-primary-500 hover:text-primary-600 font-medium"
        >
          添加第一个故事
        </button>
      </div>
    </main>

    <!-- 编辑器弹窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showEditor"
          class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
        >
          <div class="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
            <!-- 弹窗头部 -->
            <div class="flex items-center justify-between p-4 border-b">
              <h2 class="text-lg font-semibold">
                {{ editingStory ? '编辑故事' : '添加故事' }}
              </h2>
              <button
                @click="showEditor = false"
                class="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <!-- 表单 -->
            <div class="flex-1 overflow-y-auto p-4 space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">标题</label>
                <input
                  v-model="form.title"
                  type="text"
                  placeholder="故事标题"
                  class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">内容</label>
                <textarea
                  v-model="form.content"
                  placeholder="故事内容（支持 Markdown 格式）"
                  rows="12"
                  class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none font-mono text-sm"
                ></textarea>
              </div>
            </div>

            <!-- 弹窗底部 -->
            <div class="flex justify-end gap-3 p-4 border-t">
              <button
                @click="showEditor = false"
                class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                @click="handleSave"
                class="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white rounded-lg transition-colors"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
