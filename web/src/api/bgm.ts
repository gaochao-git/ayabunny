/**
 * 背景音乐管理 API
 */

export interface BGMItem {
  id: string       // 文件名（如 "sweet-dreams.mp3" 或 "custom/xxx.mp3"）
  name: string     // 显示名称
  preset: boolean  // 是否预设
}

/**
 * 获取 BGM 列表
 */
export async function getBGMList(): Promise<BGMItem[]> {
  const response = await fetch('/api/bgm')
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  const data = await response.json()
  return data.bgm
}

/**
 * 上传自定义 BGM
 */
export async function uploadBGM(file: File, name?: string): Promise<BGMItem> {
  const formData = new FormData()
  formData.append('file', file)
  if (name) {
    formData.append('name', name)
  }

  const response = await fetch('/api/bgm/upload', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `HTTP error! status: ${response.status}`)
  }

  return response.json()
}

/**
 * 删除自定义 BGM
 */
export async function deleteBGM(id: string): Promise<void> {
  const response = await fetch(`/api/bgm/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `HTTP error! status: ${response.status}`)
  }
}

/**
 * 获取 BGM 播放 URL
 */
export function getBGMUrl(id: string): string {
  if (!id) return ''
  // 预设 BGM 在 /bgm/ 目录
  // 自定义 BGM 在 /bgm/custom/ 目录
  return `/bgm/${id}`
}
