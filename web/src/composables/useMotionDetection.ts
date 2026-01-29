/**
 * 运动检测 Composable
 * 检测手机是否被拿起/移动
 */

import { ref, onUnmounted } from 'vue'
import { Motion, type AccelListenerEvent } from '@capacitor/motion'

export interface UseMotionDetectionOptions {
  /** 触发移动的加速度阈值（默认 1.5，越小越敏感） */
  threshold?: number
  /** 静止判定时间（毫秒，默认 2000） */
  stillTimeout?: number
  /** 移动开始回调 */
  onMotionStart?: () => void
  /** 静止回调（停止移动一段时间后） */
  onMotionEnd?: () => void
  /** 手机被拿起回调（检测到明显移动） */
  onPickedUp?: () => void
}

export function useMotionDetection(options: UseMotionDetectionOptions = {}) {
  const {
    threshold = 1.5,
    stillTimeout = 2000,
    onMotionStart,
    onMotionEnd,
    onPickedUp
  } = options

  const isListening = ref(false)
  const isMoving = ref(false)
  const lastAcceleration = ref({ x: 0, y: 0, z: 0 })

  let stillTimer: ReturnType<typeof setTimeout> | null = null
  let wasStill = true

  /**
   * 计算加速度变化量
   */
  function calculateDelta(event: AccelListenerEvent): number {
    const { x, y, z } = event.acceleration || { x: 0, y: 0, z: 0 }
    const last = lastAcceleration.value

    // 计算加速度变化（去除重力后的变化）
    const delta = Math.sqrt(
      Math.pow(x - last.x, 2) +
      Math.pow(y - last.y, 2) +
      Math.pow(z - last.z, 2)
    )

    lastAcceleration.value = { x, y, z }
    return delta
  }

  /**
   * 处理加速度数据
   */
  function handleAcceleration(event: AccelListenerEvent) {
    const delta = calculateDelta(event)

    if (delta > threshold) {
      // 检测到移动
      if (!isMoving.value) {
        isMoving.value = true
        onMotionStart?.()

        // 如果之前是静止状态，触发"拿起"事件
        if (wasStill) {
          wasStill = false
          onPickedUp?.()
        }
      }

      // 重置静止计时器
      if (stillTimer) {
        clearTimeout(stillTimer)
      }
      stillTimer = setTimeout(() => {
        isMoving.value = false
        wasStill = true
        onMotionEnd?.()
      }, stillTimeout)
    }
  }

  /**
   * 开始监听运动
   */
  async function startListening() {
    if (isListening.value) return

    try {
      // 请求权限（iOS 需要）
      const permission = await Motion.requestPermissions()
      if (permission.accel === 'granted') {
        await Motion.addListener('accel', handleAcceleration)
        isListening.value = true
        console.log('[Motion] 开始监听运动')
      } else {
        console.warn('[Motion] 权限被拒绝')
      }
    } catch (error) {
      console.error('[Motion] 启动失败:', error)
    }
  }

  /**
   * 停止监听运动
   */
  async function stopListening() {
    if (!isListening.value) return

    try {
      await Motion.removeAllListeners()
      isListening.value = false
      isMoving.value = false

      if (stillTimer) {
        clearTimeout(stillTimer)
        stillTimer = null
      }

      console.log('[Motion] 停止监听运动')
    } catch (error) {
      console.error('[Motion] 停止失败:', error)
    }
  }

  onUnmounted(() => {
    stopListening()
  })

  return {
    isListening,
    isMoving,
    startListening,
    stopListening
  }
}
