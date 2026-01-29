/**
 * 技能管理 API
 *
 * 支持 Agent Skills 规范的渐进加载
 */

import { getApiUrl } from './config'

export interface SkillSummary {
  id: string
  name: string
  version: string
  icon: string
  keywords: string[]
  triggers: string[]  // 触发条件（只返回前几个）
  tools: string[]
}

export interface SkillDetail extends SkillSummary {
  content: string  // SKILL.md 完整内容
}

// 向后兼容旧接口
export interface Skill {
  id: string
  name: string
  description?: string
  icon: string
}

export interface Story {
  id: string
  title: string
  content?: string
  filename?: string
  bgm?: string | null  // 背景音乐文件名
}

/**
 * 获取所有技能列表（只返回摘要，支持渐进加载）
 */
export async function getSkills(): Promise<SkillSummary[]> {
  const response = await fetch(getApiUrl('/api/skills'))
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  const data = await response.json()
  return data.skills
}

/**
 * 获取技能完整内容（按需加载）
 */
export async function getSkill(skillId: string): Promise<SkillDetail> {
  const response = await fetch(getApiUrl(`/api/skills/${skillId}`))
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

/**
 * 重新加载技能（开发调试用）
 */
export async function reloadSkills(): Promise<{ count: number; skills: string[] }> {
  const response = await fetch(getApiUrl('/api/skills/reload'), { method: 'POST' })
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

/**
 * 获取故事列表
 */
export async function getStories(skillId: string): Promise<Story[]> {
  const response = await fetch(getApiUrl(`/api/skills/${skillId}/stories`))
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  const data = await response.json()
  return data.stories
}

/**
 * 获取故事详情
 */
export async function getStory(skillId: string, storyId: string): Promise<Story> {
  const response = await fetch(getApiUrl(`/api/skills/${skillId}/stories/${storyId}`))
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

/**
 * 创建故事
 */
export async function createStory(
  skillId: string,
  story: { title: string; content: string; category?: string; bgm?: string | null }
): Promise<Story> {
  const response = await fetch(getApiUrl(`/api/skills/${skillId}/stories`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(story),
  })
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

/**
 * 更新故事
 */
export async function updateStory(
  skillId: string,
  storyId: string,
  story: { title?: string; content?: string; category?: string; bgm?: string | null }
): Promise<Story> {
  const response = await fetch(getApiUrl(`/api/skills/${skillId}/stories/${storyId}`), {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(story),
  })
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  return response.json()
}

/**
 * 删除故事
 */
export async function deleteStory(skillId: string, storyId: string): Promise<void> {
  const response = await fetch(getApiUrl(`/api/skills/${skillId}/stories/${storyId}`), {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
}

/**
 * 自动生成故事内容
 */
export async function generateStory(
  skillId: string,
  title: string
): Promise<{ title: string; content: string }> {
  const response = await fetch(getApiUrl(`/api/skills/${skillId}/stories/generate`), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ title }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `HTTP error! status: ${response.status}`)
  }
  return response.json()
}
