<template>
  <div class="emotion-core-3d" ref="containerRef"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as THREE from 'three'

const props = defineProps({
  mood: { type: Number, default: 0.5 }
})

const containerRef = ref(null)

let renderer, scene, camera
let crystalGroup, crystalMesh, wireMesh, coreMesh, clock, animId, k1
let crystalMat, wireMat

// Mouse drag interaction
let isDragging = false
let dragRotY = 0, dragRotX = 0
let prevMX, prevMY
let onMouseDown, onMouseMove, onMouseUp

// 颜色映射：0 = 深红（消极），0.5 = 半透明，1 = 深绿（积极）
function moodColor(t) {
  const c = new THREE.Color()
  // 从深红 (0°) 到深绿 (~140°)，保持低亮度高饱和度
  const hue = t * 0.38                  // 0.00 → 0.38
  const sat = 0.85 - t * 0.10           // 0.85 → 0.75
  const light = 0.14 + t * 0.03         // 0.14 → 0.17
  return c.setHSL(hue, sat, light)
}

// 顶点噪声
function noise3D(x, y, z) {
  return Math.sin(x * 3.2 + y * 4.8 + z * 2.5) * Math.cos(y * 3.9 + z * 3.1 + x * 1.6)
}

function initScene() {
  const container = containerRef.value
  if (!container) return

  const w = container.clientWidth
  const h = container.clientHeight

  scene = new THREE.Scene()
  scene.background = null

  camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 20)
  camera.position.set(0, 0, 4.2)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setClearColor(0x000000, 0)
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  container.appendChild(renderer.domElement)

  // Lights
  scene.add(new THREE.AmbientLight(0xeeddcc, 2.5))
  k1 = new THREE.PointLight(0xbbccee, 50, 12)
  k1.position.set(3, 2, 4)
  scene.add(k1)
  const k2 = new THREE.PointLight(0xeeccbb, 40, 10)
  k2.position.set(-3, -1, 2)
  scene.add(k2)

  clock = new THREE.Clock()

  // Mouse drag to rotate
  const el = renderer.domElement
  onMouseDown = (e) => { isDragging = true; prevMX = e.clientX; prevMY = e.clientY; el.style.cursor = 'grabbing' }
  onMouseMove = (e) => {
    if (!isDragging) return
    dragRotY += (e.clientX - prevMX) * 0.01
    dragRotX += (e.clientY - prevMY) * 0.01
    prevMX = e.clientX; prevMY = e.clientY
  }
  onMouseUp = () => { isDragging = false; el.style.cursor = 'grab' }
  el.addEventListener('mousedown', onMouseDown)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
  el.style.cursor = 'grab'

  // ── Crystal core ──
  crystalGroup = new THREE.Group()

  // Main crystal geometry with vertex attributes for wobble
  const crystalGeo = new THREE.IcosahedronGeometry(1.25, 2)
  const posArr = crystalGeo.attributes.position
  const origins = new Float32Array(posArr.count * 3)
  const nphases = new Float32Array(posArr.count)
  for (let i = 0; i < posArr.count; i++) {
    origins[i * 3] = posArr.getX(i)
    origins[i * 3 + 1] = posArr.getY(i)
    origins[i * 3 + 2] = posArr.getZ(i)
    nphases[i] = Math.random() * Math.PI * 2
  }
  crystalGeo.setAttribute('origin', new THREE.BufferAttribute(origins, 3))
  crystalGeo.setAttribute('noisePhase', new THREE.BufferAttribute(nphases, 1))

  crystalMat = new THREE.MeshStandardMaterial({
    color: 0x556688,
    emissive: 0x111122,
    emissiveIntensity: 0.4,
    metalness: 0.05,
    roughness: 0.45,
    flatShading: true,
    transparent: true,
    opacity: 0.55
  })
  crystalMesh = new THREE.Mesh(crystalGeo, crystalMat)
  crystalGroup.add(crystalMesh)

  // Wireframe
  const wireGeo = new THREE.IcosahedronGeometry(1.40, 2)
  wireMat = new THREE.MeshBasicMaterial({
    color: 0x446688,
    wireframe: true,
    transparent: true,
    opacity: 0.25
  })
  wireMesh = new THREE.Mesh(wireGeo, wireMat)
  crystalGroup.add(wireMesh)

  // Inner octahedron
  const coreGeo = new THREE.OctahedronGeometry(0.38, 0)
  const coreMat = new THREE.MeshBasicMaterial({
    color: 0x6688aa,
    transparent: true,
    opacity: 0.2
  })
  coreMesh = new THREE.Mesh(coreGeo, coreMat)
  crystalGroup.add(coreMesh)

  scene.add(crystalGroup)

  animate()
}

function animate() {
  animId = requestAnimationFrame(animate)
  const dt = Math.min(clock.getDelta(), 0.1)
  const t = clock.elapsedTime

  const mc = moodColor(props.mood)

  // Organic twitch (subtle)
  const twitchEnergy = (Math.sin(t * 2.8) * 0.5 + 0.5) * 0.3
  const twitch = Math.max(0, Math.sin(twitchEnergy * 2.2) * Math.exp(-twitchEnergy * 0.35)) * 0.4
  const twS = 1 + twitch * 0.08
  const twX = Math.sin(t * 13) * twitch * 0.03
  const twY = Math.cos(t * 14) * twitch * 0.03

  // Breathing
  const breath = 1 + Math.sin(t * 1.1) * 0.04 + Math.sin(t * 2.3) * 0.02
  // 大小按 |vader| 线性比例：+0.87→87%最大直径，+0.01→20%最大直径（保底）
  // 最大直径不超过显示范围（1.10 = 含呼吸抽搐时晶体直径约占视口 85%）
  const intensity = Math.abs(props.mood - 0.5) * 2  // 0~1 = |vader_normalized|
  const sizeScale = 1.10 * Math.max(0.24, intensity)  // 0.264 ~ 1.10
  const scale = breath * sizeScale * twS

  crystalGroup.scale.setScalar(scale)
  crystalGroup.position.set(twX, twY, 0)
  // Rotation: time-based auto-rotate + mouse drag offset
  if (!isDragging) {
    dragRotY *= 0.94  // smooth decay when released
    dragRotX *= 0.94
  }
  crystalGroup.rotation.y = t * 0.3 + dragRotY
  crystalGroup.rotation.x = t * 0.12 + dragRotX

  wireMesh.rotation.y = -(t * 0.15) + dragRotY * 0.3
  wireMesh.rotation.x = -(t * 0.1) + dragRotX * 0.3

  // Vertex wobble
  const pos = crystalMesh.geometry.attributes.position
  const oData = crystalMesh.geometry.attributes.origin.array
  const pData = crystalMesh.geometry.attributes.noisePhase.array
  const arr = pos.array
  const ns = 0.02 + twitch * 0.08
  for (let i = 0; i < pos.count; i++) {
    const ox = oData[i * 3], oy = oData[i * 3 + 1], oz = oData[i * 3 + 2]
    const n = noise3D(ox + t * 0.45, oy + t * 0.35, oz + pData[i])
    arr[i * 3] = ox + n * ns
    arr[i * 3 + 1] = oy + n * ns * 0.7
    arr[i * 3 + 2] = oz + n * ns * 0.6
  }
  pos.needsUpdate = true

  // Apply mood color to all elements
  // 填充晶体：中性时透明（只剩框架），极端时实心显色
  const fillOpa = 0.0 + intensity * 0.85            // 0.00 → 0.85
  crystalMat.opacity = fillOpa
  crystalMat.emissiveIntensity = 0.1 + intensity * 0.5
  // 框架：始终可见，颜色随情绪变化
  wireMat.opacity = 0.25
  // 内核：中性时隐藏
  coreMesh.material.opacity = intensity * 0.3

  crystalMat.color.copy(mc)
  crystalMat.emissive.copy(mc).multiplyScalar(0.25)
  wireMat.color.copy(mc)
  coreMesh.material.color.copy(mc).multiplyScalar(0.7)
  k1.color.copy(mc).multiplyScalar(0.6)

  renderer.render(scene, camera)
}

function handleResize() {
  const container = containerRef.value
  if (!container || !renderer) return
  const w = container.clientWidth
  const h = container.clientHeight
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  renderer.setSize(w, h)
}

function disposeScene() {
  if (animId) cancelAnimationFrame(animId)
  if (renderer) {
    if (onMouseDown) renderer.domElement.removeEventListener('mousedown', onMouseDown)
    if (onMouseMove) window.removeEventListener('mousemove', onMouseMove)
    if (onMouseUp) window.removeEventListener('mouseup', onMouseUp)
    renderer.dispose()
    if (renderer.domElement && renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  }
  if (crystalMesh) {
    crystalMesh.geometry.dispose()
    crystalMesh.material.dispose()
  }
  if (wireMesh) {
    wireMesh.geometry.dispose()
    wireMesh.material.dispose()
  }
}

onMounted(() => {
  initScene()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  disposeScene()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.emotion-core-3d {
  width: 180px;
  height: 180px;
  flex-shrink: 0;
  border-radius: 12px;
  overflow: hidden;
  background: transparent;
}
</style>
