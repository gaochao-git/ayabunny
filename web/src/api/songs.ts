/**
 * 儿歌 API
 */

import { getApiUrl } from './config'

export interface Song {
  id: string
  title: string
  title_en: string
  file: string
  keywords: string[]
}

/**
 * 获取儿歌列表
 */
export async function getSongs(): Promise<Song[]> {
  const response = await fetch(getApiUrl('/api/songs'))
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }
  const data = await response.json()
  return data.songs
}

/**
 * 获取歌曲音频 URL
 */
export function getSongAudioUrl(filename: string): string {
  return getApiUrl(`/api/songs/audio/${filename}`)
}

/**
 * 上传儿歌
 */
export async function uploadSong(
  file: File,
  title: string,
  titleEn?: string,
  keywords?: string[]
): Promise<Song> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('title', title)
  if (titleEn) formData.append('title_en', titleEn)
  if (keywords && keywords.length > 0) {
    formData.append('keywords', keywords.join(','))
  }

  const response = await fetch(getApiUrl('/api/songs/upload'), {
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
 * 删除儿歌
 */
export async function deleteSong(songId: string): Promise<void> {
  const response = await fetch(getApiUrl(`/api/songs/${songId}`), {
    method: 'DELETE',
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `HTTP error! status: ${response.status}`)
  }
}
