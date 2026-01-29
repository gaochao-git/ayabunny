/**
 * API 配置
 */

// 获取 API 基础 URL
// 开发环境用 Vite 代理（相对路径）
// 生产环境/App 用环境变量指定的服务器地址
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || ''
export const FUNASR_WS_URL = import.meta.env.VITE_FUNASR_WS_URL || 'ws://127.0.0.1:10096'
export const VAD_WS_URL = import.meta.env.VITE_VAD_WS_URL || 'ws://127.0.0.1:6002'

/**
 * 获取完整的 API URL
 */
export function getApiUrl(path: string): string {
  if (API_BASE_URL) {
    return `${API_BASE_URL}${path}`
  }
  return path
}

/**
 * 获取完整的 WebSocket URL
 */
export function getWsUrl(path: string): string {
  if (WS_BASE_URL) {
    return `${WS_BASE_URL}${path}`
  }
  // 开发环境返回相对 ws 路径，由 vite 代理处理
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}
