<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'

type MascotType = 'rabbit' | 'bear' | 'cat' | 'dino' | 'panda'

const props = defineProps<{
  type?: MascotType
  isListening?: boolean
  isThinking?: boolean
  isSpeaking?: boolean
  size?: number
}>()

const containerRef = ref<HTMLDivElement | null>(null)

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let mascotGroup: THREE.Group | null = null
let headGroup: THREE.Group | null = null
let bodyGroup: THREE.Group | null = null
let earsGroup: THREE.Group | null = null
let mouthGroup: THREE.Group | null = null
let mainLight: THREE.PointLight | null = null
let frameId: number | null = null

const targetRotation = { x: 0, y: 0 }
const currentRotation = { x: 0, y: 0 }

function getMaterial(color: number) {
  return new THREE.MeshPhysicalMaterial({
    color,
    roughness: 0.15,
    metalness: 0.02,
    clearcoat: 0.8,
    clearcoatRoughness: 0.1,
    sheen: 1.0,
    sheenColor: new THREE.Color(0xffffff),
  })
}

function createScene() {
  if (!containerRef.value) return

  const size = props.size || 280

  // Scene
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(40, 1, 0.1, 1000)
  camera.position.z = 6

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(size, size)
  containerRef.value.appendChild(renderer.domElement)

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 1.2)
  scene.add(ambientLight)

  mainLight = new THREE.PointLight(0xffffff, 45)
  mainLight.position.set(3, 4, 6)
  scene.add(mainLight)

  const backLight = new THREE.DirectionalLight(0xffffff, 0.8)
  backLight.position.set(-3, 2, -4)
  scene.add(backLight)

  // Create mascot
  mascotGroup = new THREE.Group()
  headGroup = new THREE.Group()
  earsGroup = new THREE.Group()
  mouthGroup = new THREE.Group()
  bodyGroup = new THREE.Group()

  setupMascot(props.type || 'rabbit')

  headGroup.add(earsGroup, mouthGroup)
  mascotGroup.add(headGroup, bodyGroup)
  scene.add(mascotGroup)
}

function setupMascot(type: MascotType) {
  if (!headGroup || !bodyGroup || !earsGroup || !mouthGroup) return

  // Clear existing
  while (headGroup.children.length > 0) headGroup.remove(headGroup.children[0])
  while (bodyGroup.children.length > 0) bodyGroup.remove(bodyGroup.children[0])
  while (earsGroup.children.length > 0) earsGroup.remove(earsGroup.children[0])
  while (mouthGroup.children.length > 0) mouthGroup.remove(mouthGroup.children[0])

  const materials: Record<string, THREE.Material> = {
    rabbit: getMaterial(0xe0e2e8),      // 柔和浅灰色
    rabbitInner: getMaterial(0xffc0cb), // 粉色内耳
    bear: getMaterial(0xc9956c),        // 温暖浅棕色
    cat: getMaterial(0xfff5e6),         // 奶油色
    catInner: getMaterial(0xffcad4),    // 猫内耳粉色
    dino: getMaterial(0x98d8aa),        // 薄荷绿
    dinoScales: getMaterial(0xf9d56e),  // 阳光黄
    panda: getMaterial(0xffffff),       // 白色
    pandaBlack: getMaterial(0x2d2d2d),  // 黑色
    eye: new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.1 }),
    eyeHighlight: new THREE.MeshBasicMaterial({ color: 0xffffff }),
    blush: new THREE.MeshBasicMaterial({ color: 0xffb6c1, transparent: true, opacity: 0.5 }),
    snout: getMaterial(0xfff0e6),       // 米白色
    nose: new THREE.MeshStandardMaterial({ color: 0x4a3728 }),
    mouthLine: new THREE.MeshStandardMaterial({ color: 0x4a4a4a })
  }

  // Body
  const bodyGeom = new THREE.SphereGeometry(0.9, 32, 32)
  const bodyMaterial = type === 'panda' ? materials.panda : materials[type]
  const body = new THREE.Mesh(bodyGeom, bodyMaterial)
  body.scale.set(1, 0.9, 0.8)
  body.position.y = -1.2
  bodyGroup.add(body)

  // Head
  const headGeom = new THREE.SphereGeometry(1.2, 64, 64)
  const headMaterial = type === 'panda' ? materials.panda : materials[type]
  const head = new THREE.Mesh(headGeom, headMaterial)
  head.scale.set(1.08, 1, 1.02)
  headGroup.add(head)

  // Eyes
  const createEye = (x: number) => {
    const eyeWrap = new THREE.Group()
    const eye = new THREE.Mesh(new THREE.SphereGeometry(0.16, 32, 32), materials.eye)
    const highlight = new THREE.Mesh(new THREE.SphereGeometry(0.04, 16, 16), materials.eyeHighlight)
    highlight.position.set(0.05, 0.05, 0.14)
    eyeWrap.add(eye, highlight)
    eyeWrap.position.set(x, 0.1, 1.05)
    return eyeWrap
  }
  headGroup.add(createEye(-0.48), createEye(0.48))

  // Blush
  const blushGeom = new THREE.CircleGeometry(0.22, 32)
  const leftBlush = new THREE.Mesh(blushGeom, materials.blush)
  leftBlush.position.set(-0.75, -0.35, 1.15)
  const rightBlush = new THREE.Mesh(blushGeom, materials.blush)
  rightBlush.position.set(0.75, -0.35, 1.15)
  headGroup.add(leftBlush, rightBlush)

  // Type-specific features
  if (type === 'rabbit') {
    // Rabbit ears
    const createRabbitEar = (x: number, rotZ: number) => {
      const earGroup = new THREE.Group()
      const outerEar = new THREE.Mesh(new THREE.CapsuleGeometry(0.26, 1.3, 10, 20), materials.rabbit)
      const innerEar = new THREE.Mesh(new THREE.CapsuleGeometry(0.14, 1.0, 10, 20), materials.rabbitInner)
      innerEar.position.z = 0.1
      innerEar.position.y = -0.1
      earGroup.add(outerEar, innerEar)
      earGroup.position.set(x, 1.3, 0)
      earGroup.rotation.z = rotZ
      earGroup.rotation.x = -0.1
      return earGroup
    }
    earsGroup.add(createRabbitEar(-0.5, 0.25), createRabbitEar(0.5, -0.25))

    // Rabbit mouth
    const mouthPart = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.015, 16, 32, Math.PI), materials.mouthLine)
    mouthPart.position.set(0, -0.4, 1.18)
    mouthPart.rotation.x = Math.PI
    mouthGroup.add(mouthPart)

  } else if (type === 'bear') {
    // Bear ears
    const earGeom = new THREE.SphereGeometry(0.4, 32, 32)
    const lEar = new THREE.Mesh(earGeom, materials.bear)
    lEar.position.set(-0.85, 0.95, 0)
    const rEar = new THREE.Mesh(earGeom, materials.bear)
    rEar.position.set(0.85, 0.95, 0)
    earsGroup.add(lEar, rEar)

    // Bear snout
    const snout = new THREE.Mesh(new THREE.SphereGeometry(0.42, 32, 32), materials.snout)
    snout.scale.set(1.1, 0.85, 0.7)
    snout.position.set(0, -0.3, 1.05)
    headGroup.add(snout)

    const nose = new THREE.Mesh(new THREE.SphereGeometry(0.1, 32, 32), materials.nose)
    nose.position.set(0, -0.18, 1.38)
    headGroup.add(nose)

    const mouthPart = new THREE.Mesh(new THREE.TorusGeometry(0.09, 0.018, 16, 32, Math.PI), materials.mouthLine)
    mouthPart.position.set(0, -0.4, 1.4)
    mouthPart.rotation.x = Math.PI
    mouthGroup.add(mouthPart)

  } else if (type === 'cat') {
    // Cat ears
    const createCatEar = (x: number, rotZ: number) => {
      const earGroup = new THREE.Group()
      const outerEar = new THREE.Mesh(new THREE.CapsuleGeometry(0.24, 0.5, 8, 20), materials.cat)
      outerEar.scale.set(1.4, 1.2, 0.8)
      const innerEar = new THREE.Mesh(new THREE.CapsuleGeometry(0.12, 0.4, 8, 20), materials.catInner)
      innerEar.position.set(0, -0.05, 0.1)
      innerEar.scale.set(1.2, 1, 1)
      earGroup.add(outerEar, innerEar)
      earGroup.position.set(x, 1.0, 0)
      earGroup.rotation.z = rotZ
      earGroup.rotation.x = -0.1
      return earGroup
    }
    earsGroup.add(createCatEar(-0.65, 0.4), createCatEar(0.65, -0.4))

    // Cat muzzle
    const muzzleGeom = new THREE.SphereGeometry(0.22, 32, 32)
    const lMuzzle = new THREE.Mesh(muzzleGeom, materials.snout)
    lMuzzle.scale.set(1, 0.8, 0.6)
    lMuzzle.position.set(-0.16, -0.3, 1.12)
    const rMuzzle = new THREE.Mesh(muzzleGeom, materials.snout)
    rMuzzle.scale.set(1, 0.8, 0.6)
    rMuzzle.position.set(0.16, -0.3, 1.12)
    headGroup.add(lMuzzle, rMuzzle)

    // Cat nose
    const nose = new THREE.Mesh(new THREE.SphereGeometry(0.06, 16, 16), new THREE.MeshBasicMaterial({ color: 0xffb6c1 }))
    nose.scale.set(1.2, 0.8, 1)
    nose.position.set(0, -0.2, 1.25)
    headGroup.add(nose)

    // Cat mouth
    const mouthL = new THREE.Mesh(new THREE.TorusGeometry(0.08, 0.015, 8, 20, Math.PI), materials.mouthLine)
    mouthL.position.set(-0.08, -0.35, 1.25)
    mouthL.rotation.x = Math.PI
    const mouthR = new THREE.Mesh(new THREE.TorusGeometry(0.08, 0.015, 8, 20, Math.PI), materials.mouthLine)
    mouthR.position.set(0.08, -0.35, 1.25)
    mouthR.rotation.x = Math.PI
    mouthGroup.add(mouthL, mouthR)

  } else if (type === 'dino') {
    // Dino snout
    const snout = new THREE.Mesh(new THREE.SphereGeometry(0.5, 32, 32), materials.dino)
    snout.scale.set(1.2, 0.8, 1)
    snout.position.set(0, -0.3, 1.05)
    headGroup.add(snout)

    // Dino scales (spikes on head)
    for (let i = 0; i < 3; i++) {
      const scale = new THREE.Mesh(new THREE.CapsuleGeometry(0.15, 0.2, 8, 10), materials.dinoScales)
      scale.position.set(0, 1.1 + (i * 0.3), -0.5 + (i * 0.4))
      scale.rotation.x = -0.5
      earsGroup.add(scale)
    }

    // Dino mouth
    const mouthPart = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.02, 16, 32, Math.PI), materials.mouthLine)
    mouthPart.position.set(0, -0.45, 1.35)
    mouthPart.rotation.x = Math.PI
    mouthGroup.add(mouthPart)

  } else if (type === 'panda') {
    // Panda black eye patches
    const patchGeom = new THREE.SphereGeometry(0.28, 32, 32)
    const lPatch = new THREE.Mesh(patchGeom, materials.pandaBlack)
    lPatch.scale.set(1, 1.2, 0.4)
    lPatch.position.set(-0.48, 0.1, 1)
    const rPatch = new THREE.Mesh(patchGeom, materials.pandaBlack)
    rPatch.scale.set(1, 1.2, 0.4)
    rPatch.position.set(0.48, 0.1, 1)
    headGroup.add(lPatch, rPatch)

    // Panda ears (black)
    const earGeom = new THREE.SphereGeometry(0.38, 32, 32)
    const lEar = new THREE.Mesh(earGeom, materials.pandaBlack)
    lEar.position.set(-0.85, 0.95, 0)
    const rEar = new THREE.Mesh(earGeom, materials.pandaBlack)
    rEar.position.set(0.85, 0.95, 0)
    earsGroup.add(lEar, rEar)

    // Panda nose (black)
    const nose = new THREE.Mesh(new THREE.SphereGeometry(0.08, 32, 32), materials.pandaBlack)
    nose.position.set(0, -0.15, 1.3)
    headGroup.add(nose)

    // Panda mouth
    const mouthPart = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.015, 16, 32, Math.PI), materials.mouthLine)
    mouthPart.position.set(0, -0.35, 1.3)
    mouthPart.rotation.x = Math.PI
    mouthGroup.add(mouthPart)
  }

  headGroup.add(earsGroup, mouthGroup)
}

function onMouseMove(e: MouseEvent) {
  if (!mainLight) return
  const x = (e.clientX / window.innerWidth) * 2 - 1
  const y = -(e.clientY / window.innerHeight) * 2 + 1
  targetRotation.y = x * 0.45
  targetRotation.x = -y * 0.25
  mainLight.position.x = 3 + x * 2
  mainLight.position.y = 4 + y * 2
}

function animate() {
  frameId = requestAnimationFrame(animate)

  if (!mascotGroup || !bodyGroup || !headGroup || !earsGroup || !mouthGroup || !renderer || !scene || !camera) return

  const time = Date.now() * 0.002

  // Smooth rotation
  currentRotation.x += (targetRotation.x - currentRotation.x) * 0.08
  currentRotation.y += (targetRotation.y - currentRotation.y) * 0.08
  mascotGroup.rotation.x = currentRotation.x
  mascotGroup.rotation.y = currentRotation.y

  // Breathing
  const breathScale = 1 + Math.sin(time) * 0.02
  bodyGroup.scale.set(breathScale, breathScale, breathScale)
  headGroup.position.y = Math.sin(time) * 0.05

  // Listening: ears wiggle (slower, gentler movement)
  if (props.isListening) {
    earsGroup.children.forEach((ear, i) => {
      ear.rotation.z += Math.sin(time * 3 + i * Math.PI) * 0.015
    })
  }

  // Speaking: mouth moves
  if (props.isSpeaking) {
    const mouthS = 1 + Math.sin(time * 18) * 0.3
    mouthGroup.scale.set(1, mouthS, 1)
    mouthGroup.position.y = -Math.sin(time * 18) * 0.03
  } else {
    mouthGroup.scale.lerp(new THREE.Vector3(1, 1, 1), 0.1)
    mouthGroup.position.y = 0
  }

  // Thinking: head wobble
  if (props.isThinking) {
    mascotGroup.rotation.y += Math.sin(time * 4) * 0.06
  }

  renderer.render(scene, camera)
}

function cleanup() {
  if (frameId) {
    cancelAnimationFrame(frameId)
    frameId = null
  }
  window.removeEventListener('mousemove', onMouseMove)
  if (renderer && containerRef.value) {
    containerRef.value.removeChild(renderer.domElement)
    renderer.dispose()
    renderer = null
  }
  scene = null
  camera = null
  mascotGroup = null
  headGroup = null
  bodyGroup = null
  earsGroup = null
  mouthGroup = null
  mainLight = null
}

onMounted(() => {
  createScene()
  window.addEventListener('mousemove', onMouseMove)
  animate()
})

onUnmounted(() => {
  cleanup()
})

// Watch for type changes
watch(() => props.type, (newType) => {
  if (newType) {
    setupMascot(newType)
  }
})
</script>

<template>
  <div class="relative flex flex-col items-center">
    <!-- Glow effect -->
    <div
      class="absolute inset-0 w-full h-full rounded-full transition-all duration-1000 blur-[60px] pointer-events-none"
      :class="isListening ? 'bg-indigo-400/30' : 'bg-pink-300/10'"
    ></div>

    <!-- 3D Canvas -->
    <div
      ref="containerRef"
      class="flex items-center justify-center cursor-grab active:cursor-grabbing transform-gpu transition-all duration-500 hover:scale-[1.02]"
      :style="{ width: `${size || 280}px`, height: `${size || 280}px` }"
    />

    <!-- Status bar -->
    <div
      class="mt-2 px-6 py-3 rounded-[2rem] bg-white/70 backdrop-blur-xl border-2 border-white transition-all duration-500 shadow-xl"
      :class="{
        'scale-110 shadow-indigo-200': isListening,
        'shadow-pink-200 border-pink-100': isSpeaking && !isListening
      }"
    >
      <div class="flex items-center gap-3">
        <div class="flex gap-1 items-end h-5">
          <div
            v-for="i in 3"
            :key="i"
            class="w-1 rounded-full transition-all duration-300"
            :class="isListening ? 'bg-indigo-500 animate-bounce' : isSpeaking ? 'bg-pink-400 animate-pulse' : 'bg-slate-200'"
            :style="{
              animationDelay: `${i * 0.15}s`,
              height: isListening || isSpeaking ? `${10 + Math.random() * 14}px` : '10px'
            }"
          />
        </div>
        <span class="text-xs font-bold text-slate-600 tracking-wider">
          {{ isListening ? '正在聆听' : isThinking ? '思考中' : isSpeaking ? '小智说' : '陪你玩' }}
        </span>
      </div>
    </div>
  </div>
</template>
