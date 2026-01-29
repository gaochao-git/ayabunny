<script setup lang="ts">
/**
 * 小智卡通人物组件
 * 随手机运动而活动
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { Motion } from '@capacitor/motion'

const props = defineProps<{
  /** 是否启用运动感应 */
  motionEnabled?: boolean
  /** 灵敏度（默认 5） */
  sensitivity?: number
}>()

const sensitivity = computed(() => props.sensitivity ?? 5)

// 位置偏移
const offsetX = ref(0)
const offsetY = ref(0)
const rotation = ref(0)
const scale = ref(1)

// 眼睛位置
const eyeOffsetX = ref(0)
const eyeOffsetY = ref(0)

// 表情状态
const expression = ref<'normal' | 'happy' | 'surprised' | 'dizzy'>('normal')

// 是否正在监听
const isListening = ref(false)

// 上次加速度
let lastX = 0
let lastY = 0
let lastZ = 0

// 动画帧
let animationFrame: number | null = null

/**
 * 处理加速度数据
 */
function handleAcceleration(event: any) {
  const accel = event.acceleration || event.accelerationIncludingGravity || { x: 0, y: 0, z: 0 }
  const { x, y, z } = accel

  // 计算变化量
  const deltaX = x - lastX
  const deltaY = y - lastY
  const deltaZ = z - lastZ
  const totalDelta = Math.sqrt(deltaX * deltaX + deltaY * deltaY + deltaZ * deltaZ)

  lastX = x
  lastY = y
  lastZ = z

  // 根据加速度设置偏移（带阻尼）
  const dampingFactor = 0.3
  offsetX.value += (x * sensitivity.value - offsetX.value) * dampingFactor
  offsetY.value += (-y * sensitivity.value - offsetY.value) * dampingFactor

  // 限制偏移范围
  offsetX.value = Math.max(-30, Math.min(30, offsetX.value))
  offsetY.value = Math.max(-30, Math.min(30, offsetY.value))

  // 旋转跟随 X 轴
  rotation.value += (x * 2 - rotation.value) * dampingFactor
  rotation.value = Math.max(-15, Math.min(15, rotation.value))

  // 眼睛跟随（更灵敏）
  eyeOffsetX.value = offsetX.value * 0.3
  eyeOffsetY.value = offsetY.value * 0.3

  // 根据力度改变表情
  if (totalDelta > 15) {
    expression.value = 'dizzy'
    scale.value = 1.1
  } else if (totalDelta > 8) {
    expression.value = 'surprised'
    scale.value = 1.05
  } else if (totalDelta > 3) {
    expression.value = 'happy'
    scale.value = 1
  } else {
    expression.value = 'normal'
    scale.value = 1
  }
}

/**
 * Web 端使用 DeviceMotion API
 */
function handleDeviceMotion(event: DeviceMotionEvent) {
  handleAcceleration({
    acceleration: event.acceleration || event.accelerationIncludingGravity
  })
}

/**
 * 开始监听
 */
async function startMotionListening() {
  if (isListening.value) return

  try {
    // 尝试使用 Capacitor Motion
    if (typeof Motion !== 'undefined' && Motion.addListener) {
      try {
        await Motion.requestPermissions?.()
        await Motion.addListener('accel', handleAcceleration)
        isListening.value = true
        console.log('[Mascot] 使用 Capacitor Motion')
        return
      } catch (e) {
        console.log('[Mascot] Capacitor Motion 不可用，尝试 Web API')
      }
    }

    // 降级到 Web DeviceMotion API
    if (typeof DeviceMotionEvent !== 'undefined') {
      // iOS 13+ 需要请求权限
      if (typeof (DeviceMotionEvent as any).requestPermission === 'function') {
        const permission = await (DeviceMotionEvent as any).requestPermission()
        if (permission !== 'granted') {
          console.warn('[Mascot] 运动权限被拒绝')
          return
        }
      }
      window.addEventListener('devicemotion', handleDeviceMotion)
      isListening.value = true
      console.log('[Mascot] 使用 Web DeviceMotion API')
    }
  } catch (error) {
    console.error('[Mascot] 启动运动监听失败:', error)
  }
}

/**
 * 停止监听
 */
async function stopMotionListening() {
  if (!isListening.value) return

  try {
    if (typeof Motion !== 'undefined' && Motion.removeAllListeners) {
      await Motion.removeAllListeners()
    }
    window.removeEventListener('devicemotion', handleDeviceMotion)
    isListening.value = false
  } catch (error) {
    console.error('[Mascot] 停止监听失败:', error)
  }
}

/**
 * 缓慢回到中心位置
 */
function animateToCenter() {
  const animate = () => {
    if (isListening.value) return

    offsetX.value *= 0.95
    offsetY.value *= 0.95
    rotation.value *= 0.95
    eyeOffsetX.value *= 0.95
    eyeOffsetY.value *= 0.95

    if (Math.abs(offsetX.value) > 0.1 || Math.abs(offsetY.value) > 0.1) {
      animationFrame = requestAnimationFrame(animate)
    }
  }
  animate()
}

onMounted(() => {
  if (props.motionEnabled !== false) {
    startMotionListening()
  }
})

onUnmounted(() => {
  stopMotionListening()
  if (animationFrame) {
    cancelAnimationFrame(animationFrame)
  }
})

// 暴露方法
defineExpose({
  startMotionListening,
  stopMotionListening,
  isListening
})
</script>

<template>
  <div class="mascot-container">
    <svg
      viewBox="0 0 200 200"
      class="mascot"
      :style="{
        transform: `translate(${offsetX}px, ${offsetY}px) rotate(${rotation}deg) scale(${scale})`,
      }"
    >
      <!-- 身体 -->
      <ellipse cx="100" cy="120" rx="50" ry="45" fill="#FFB6C1" class="body" />

      <!-- 头 -->
      <circle cx="100" cy="70" r="45" fill="#FFE4E1" class="head" />

      <!-- 腮红 -->
      <ellipse cx="65" cy="80" rx="12" ry="8" fill="#FFB6C1" opacity="0.6" />
      <ellipse cx="135" cy="80" rx="12" ry="8" fill="#FFB6C1" opacity="0.6" />

      <!-- 眼睛容器 -->
      <g :style="{ transform: `translate(${eyeOffsetX}px, ${eyeOffsetY}px)` }">
        <!-- 左眼 -->
        <ellipse cx="80" cy="65" rx="10" ry="12" fill="white" />
        <circle
          cx="80"
          cy="65"
          r="5"
          fill="#333"
          :class="{ 'eye-dizzy': expression === 'dizzy' }"
        />
        <circle cx="82" cy="63" r="2" fill="white" />

        <!-- 右眼 -->
        <ellipse cx="120" cy="65" rx="10" ry="12" fill="white" />
        <circle
          cx="120"
          cy="65"
          r="5"
          fill="#333"
          :class="{ 'eye-dizzy': expression === 'dizzy' }"
        />
        <circle cx="122" cy="63" r="2" fill="white" />
      </g>

      <!-- 嘴巴 -->
      <path
        v-if="expression === 'normal'"
        d="M 90 90 Q 100 100, 110 90"
        fill="none"
        stroke="#FF69B4"
        stroke-width="3"
        stroke-linecap="round"
      />
      <ellipse
        v-else-if="expression === 'surprised'"
        cx="100"
        cy="92"
        rx="8"
        ry="10"
        fill="#FF69B4"
      />
      <path
        v-else-if="expression === 'happy'"
        d="M 85 88 Q 100 105, 115 88"
        fill="none"
        stroke="#FF69B4"
        stroke-width="3"
        stroke-linecap="round"
      />
      <g v-else-if="expression === 'dizzy'">
        <path
          d="M 90 90 Q 100 95, 110 90"
          fill="none"
          stroke="#FF69B4"
          stroke-width="3"
          stroke-linecap="round"
        />
        <!-- 晕圈 -->
        <text x="60" y="40" font-size="16" fill="#FFB6C1">*</text>
        <text x="130" y="35" font-size="16" fill="#FFB6C1">*</text>
      </g>

      <!-- 耳朵 -->
      <ellipse cx="55" cy="45" rx="12" ry="18" fill="#FFE4E1" />
      <ellipse cx="55" cy="45" rx="6" ry="10" fill="#FFB6C1" />
      <ellipse cx="145" cy="45" rx="12" ry="18" fill="#FFE4E1" />
      <ellipse cx="145" cy="45" rx="6" ry="10" fill="#FFB6C1" />

      <!-- 小手 -->
      <ellipse
        cx="55"
        cy="130"
        rx="15"
        ry="12"
        fill="#FFE4E1"
        :style="{ transform: `rotate(${-rotation * 0.5}deg)`, transformOrigin: '55px 130px' }"
      />
      <ellipse
        cx="145"
        cy="130"
        rx="15"
        ry="12"
        fill="#FFE4E1"
        :style="{ transform: `rotate(${rotation * 0.5}deg)`, transformOrigin: '145px 130px' }"
      />

      <!-- 小脚 -->
      <ellipse cx="80" cy="165" rx="18" ry="10" fill="#FFB6C1" />
      <ellipse cx="120" cy="165" rx="18" ry="10" fill="#FFB6C1" />
    </svg>

    <!-- 状态提示 -->
    <div v-if="expression === 'dizzy'" class="status-text">好晕~</div>
    <div v-else-if="expression === 'surprised'" class="status-text">哇!</div>
  </div>
</template>

<style scoped>
.mascot-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
}

.mascot {
  width: 150px;
  height: 150px;
  transition: transform 0.1s ease-out;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.1));
}

.body {
  animation: breathe 3s ease-in-out infinite;
}

@keyframes breathe {
  0%, 100% { transform: scaleY(1); }
  50% { transform: scaleY(1.03); }
}

.eye-dizzy {
  animation: spin 0.5s linear infinite;
  transform-origin: center;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.status-text {
  margin-top: 8px;
  font-size: 14px;
  color: #FF69B4;
  font-weight: 500;
  animation: bounce 0.5s ease-in-out;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}
</style>
