/**
 * 视频捕获 Composable
 *
 * 支持两种模式：
 * 1. 录制模式：录制短视频（15-60秒）
 * 2. 实时模式：持续预览 + 周期性帧采样
 */

import { ref, onUnmounted, type Ref } from 'vue'

export interface UseVideoCaptureOptions {
  maxDuration?: number      // 最大录制时长（秒），默认 60
  frameInterval?: number    // 实时模式帧采样间隔（毫秒），默认 3000
  resolution?: {
    width: number
    height: number
  }
}

export interface UseVideoCaptureReturn {
  // 状态
  isSupported: Ref<boolean>
  isPreviewActive: Ref<boolean>
  isRecording: Ref<boolean>
  isStreaming: Ref<boolean>
  duration: Ref<number>
  videoUrl: Ref<string | null>

  // 方法
  startPreview: (videoElement: HTMLVideoElement) => Promise<void>
  stopPreview: () => void
  startRecording: () => Promise<void>
  stopRecording: () => Promise<Blob>
  startStreaming: (onFrame: (base64: string) => void) => void
  stopStreaming: () => void
  captureFrame: () => string | null
}

export function useVideoCapture(options: UseVideoCaptureOptions = {}): UseVideoCaptureReturn {
  const {
    maxDuration = 60,
    frameInterval = 3000,
    resolution = { width: 640, height: 480 }
  } = options

  // 状态
  const isSupported = ref(
    typeof navigator !== 'undefined' &&
    'mediaDevices' in navigator &&
    'getUserMedia' in navigator.mediaDevices
  )
  const isPreviewActive = ref(false)
  const isRecording = ref(false)
  const isStreaming = ref(false)
  const duration = ref(0)
  const videoUrl = ref<string | null>(null)

  // 内部变量
  let mediaStream: MediaStream | null = null
  let mediaRecorder: MediaRecorder | null = null
  let videoElement: HTMLVideoElement | null = null
  let recordedChunks: Blob[] = []
  let durationTimer: ReturnType<typeof setInterval> | null = null
  let streamingTimer: ReturnType<typeof setInterval> | null = null
  let canvas: HTMLCanvasElement | null = null
  let canvasCtx: CanvasRenderingContext2D | null = null

  /**
   * 开始摄像头预览
   */
  async function startPreview(element: HTMLVideoElement): Promise<void> {
    if (!isSupported.value) {
      throw new Error('视频捕获不支持')
    }

    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: resolution.width },
          height: { ideal: resolution.height },
          facingMode: 'user'  // 前置摄像头
        },
        audio: true  // 同时获取音频
      })

      videoElement = element
      videoElement.srcObject = mediaStream
      videoElement.muted = true  // 避免回声
      await videoElement.play()

      // 初始化 canvas 用于帧捕获
      canvas = document.createElement('canvas')
      canvas.width = resolution.width
      canvas.height = resolution.height
      canvasCtx = canvas.getContext('2d')

      isPreviewActive.value = true
      console.log('[VideoCapture] Preview started')
    } catch (error) {
      console.error('[VideoCapture] Failed to start preview:', error)
      throw error
    }
  }

  /**
   * 停止摄像头预览
   */
  function stopPreview(): void {
    stopRecording().catch(() => {})
    stopStreaming()

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop())
      mediaStream = null
    }

    if (videoElement) {
      videoElement.srcObject = null
      videoElement = null
    }

    canvas = null
    canvasCtx = null
    isPreviewActive.value = false
    console.log('[VideoCapture] Preview stopped')
  }

  /**
   * 开始录制视频
   */
  async function startRecording(): Promise<void> {
    if (!mediaStream) {
      throw new Error('请先开始预览')
    }

    if (isRecording.value) {
      return
    }

    recordedChunks = []
    duration.value = 0

    // 清理之前的 URL
    if (videoUrl.value) {
      URL.revokeObjectURL(videoUrl.value)
      videoUrl.value = null
    }

    // 选择支持的格式
    const mimeTypes = [
      'video/webm;codecs=vp9,opus',
      'video/webm;codecs=vp8,opus',
      'video/webm',
      'video/mp4'
    ]

    let selectedMimeType = ''
    for (const mimeType of mimeTypes) {
      if (MediaRecorder.isTypeSupported(mimeType)) {
        selectedMimeType = mimeType
        break
      }
    }

    if (!selectedMimeType) {
      throw new Error('浏览器不支持视频录制')
    }

    mediaRecorder = new MediaRecorder(mediaStream, {
      mimeType: selectedMimeType,
      videoBitsPerSecond: 1000000  // 1Mbps
    })

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data)
      }
    }

    mediaRecorder.start(1000)  // 每秒收集数据
    isRecording.value = true

    // 录制时长计时
    durationTimer = setInterval(() => {
      duration.value++
      if (duration.value >= maxDuration) {
        stopRecording()
      }
    }, 1000)

    console.log('[VideoCapture] Recording started')
  }

  /**
   * 停止录制视频
   */
  async function stopRecording(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      if (!mediaRecorder || !isRecording.value) {
        reject(new Error('未在录制'))
        return
      }

      if (durationTimer) {
        clearInterval(durationTimer)
        durationTimer = null
      }

      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunks, {
          type: mediaRecorder?.mimeType || 'video/webm'
        })

        videoUrl.value = URL.createObjectURL(blob)
        isRecording.value = false
        console.log('[VideoCapture] Recording stopped, size:', blob.size)
        resolve(blob)
      }

      mediaRecorder.stop()
    })
  }

  /**
   * 开始实时帧采样
   */
  function startStreaming(onFrame: (base64: string) => void): void {
    if (isStreaming.value) return

    isStreaming.value = true

    // 立即发送第一帧
    const firstFrame = captureFrame()
    if (firstFrame) {
      onFrame(firstFrame)
    }

    // 周期性采样
    streamingTimer = setInterval(() => {
      const frame = captureFrame()
      if (frame) {
        onFrame(frame)
      }
    }, frameInterval)

    console.log('[VideoCapture] Streaming started, interval:', frameInterval)
  }

  /**
   * 停止实时帧采样
   */
  function stopStreaming(): void {
    if (streamingTimer) {
      clearInterval(streamingTimer)
      streamingTimer = null
    }
    isStreaming.value = false
    console.log('[VideoCapture] Streaming stopped')
  }

  /**
   * 捕获当前帧
   */
  function captureFrame(): string | null {
    if (!videoElement || !canvas || !canvasCtx) {
      return null
    }

    // 绘制当前视频帧到 canvas
    canvasCtx.drawImage(videoElement, 0, 0, canvas.width, canvas.height)

    // 转换为 base64（不含前缀）
    const dataUrl = canvas.toDataURL('image/jpeg', 0.7)
    return dataUrl.replace(/^data:image\/\w+;base64,/, '')
  }

  /**
   * 清理资源
   */
  function cleanup(): void {
    stopPreview()
    if (videoUrl.value) {
      URL.revokeObjectURL(videoUrl.value)
      videoUrl.value = null
    }
  }

  onUnmounted(cleanup)

  return {
    isSupported,
    isPreviewActive,
    isRecording,
    isStreaming,
    duration,
    videoUrl,
    startPreview,
    stopPreview,
    startRecording,
    stopRecording,
    startStreaming,
    stopStreaming,
    captureFrame,
  }
}
