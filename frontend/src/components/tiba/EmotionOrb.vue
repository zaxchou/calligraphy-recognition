<template>
  <div class="emotion-orb" ref="containerRef"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Renderer, Program, Mesh, Color, Triangle, RenderTarget } from 'ogl'
import { clamp, emotionColors, emotionGlassSize, emotionEnergy } from './emotionOrbUtils'

// 情绪玻璃光球（OGL 着色器），替代旧 EmotionCore3D 水晶。
// value = vader_normalized ∈ [-1, 1]，与 VADER 条显示的分数同源。
// 浅色适配（宣纸卡片场景）已固化在着色器参数与样式中，见交接文档 §6。
const props = defineProps({
  value: { type: Number, default: 0 }
})

const containerRef = ref(null)

const MAX_STRANDS = 12, MAX_COLORS = 8
const VERT = `#version 300 es
in vec2 position; void main(){ gl_Position = vec4(position,0.0,1.0); }`
const FRAG = `#version 300 es
precision highp float;
uniform float uTime; uniform vec2 uResolution;
uniform vec3 uColors[${MAX_COLORS}]; uniform int uColorCount; uniform int uStrandCount;
uniform float uSpeed, uAmplitude, uWaviness, uThickness, uGlow, uTaper, uSpread, uHueShift, uIntensity, uOpacity, uScale, uSaturation;
out vec4 fragColor; const float PI = 3.14159265;
vec3 spectrum(float t){ return 0.5 + 0.5*cos(2.0*PI*(t+vec3(0.0,0.33,0.67))); }
vec3 samplePalette(float t){ t=fract(t); float sc=t*float(uColorCount); int idx=int(floor(sc)); float bl=fract(sc); int nx=idx+1; if(nx>=uColorCount) nx=0; return mix(uColors[idx],uColors[nx],bl); }
vec3 strandColor(float t){ if(uColorCount>0) return samplePalette(t); return spectrum(t); }
void main(){
  vec2 uv=(gl_FragCoord.xy-0.5*uResolution)/min(uResolution.x,uResolution.y); uv/=max(uScale,0.0001);
  float e=0.06+uIntensity*0.94; float env=pow(max(cos(uv.x*PI*1.3),0.0),uTaper);
  vec3 col=vec3(0.0);
  for(int i=0;i<${MAX_STRANDS};i++){ if(i>=uStrandCount) break;
    float fi=float(i); float ph=fi*1.7*uSpread; float freq=(2.0+fi*0.35)*uWaviness; float spd=1.4+fi*1.2;
    float tt=uTime*uSpeed;
    float w=sin(uv.x*freq+tt*spd+ph)*0.60 + sin(uv.x*freq*1.1-tt*spd*0.7+ph*1.7)*0.40;
    float amp=(0.1+0.02*e)*env*uAmplitude; float y=w*amp;
    float d=abs(uv.y-y); float thick=(0.001+0.05*e)*(0.35+env)*uThickness;
    float g=thick/(d+thick*0.45); g=g*g;
    float h=fi/float(uStrandCount)+uv.x*0.30+uTime*0.04+uHueShift;
    col+=strandColor(h)*g*env;
  }
  col*=0.45+0.7*e; col=1.0-exp(-col*uGlow);
  float gray=dot(col,vec3(0.2126,0.7152,0.0722)); col=max(mix(vec3(gray),col,uSaturation),0.0);
  float lum=max(max(col.r,col.g),col.b); float alpha=clamp(lum,0.0,1.0)*uOpacity;
  fragColor=vec4(col*uOpacity,alpha);
}`
const GLASS_FRAG = `#version 300 es
precision highp float;
uniform sampler2D uScene; uniform vec2 uResolution;
uniform float uRadius, uRefraction, uDispersion, uLight;
uniform vec3 uTint;
out vec4 fragColor;
vec2 toUv(vec2 p){ return p*(min(uResolution.x,uResolution.y)/uResolution)+0.5; }
void main(){
  vec2 p=(gl_FragCoord.xy-0.5*uResolution)/min(uResolution.x,uResolution.y); float d=length(p); float r=uRadius;
  float edge=fwidth(d)*1.5; float mask=1.0-smoothstep(r-edge,r+edge,d);
  if(mask<=0.0){ fragColor=vec4(0.0); return; }
  float z=sqrt(max(r*r-d*d,0.0))/r; float nd=d/r;
  vec2 dir=d>0.0?p/d:vec2(0.0);
  float lens=smoothstep(0.85,1.0,nd)*pow(nd,6.0);
  vec2 offset=-dir*lens*uRefraction*0.15; vec2 disp=-dir*lens*uDispersion*0.012;
  vec3 light;
  light.r=texture(uScene,toUv(p+offset-disp)).r;
  light.g=texture(uScene,toUv(p+offset)).g;
  light.b=texture(uScene,toUv(p+offset+disp)).b;
  float fres=pow(1.0-z,3.0);
  vec3 rimCol = mix(vec3(1.0), uTint, uLight);
  vec3 rim = rimCol * fres * mix(0.18, 0.55, uLight);
  vec2 lightDir=normalize(vec2(-0.55,0.6));
  float spec=pow(max(dot(p/max(r,1e-4),lightDir),0.0),6.0); spec*=smoothstep(r,r*0.55,d);
  vec3 emissive=light+rim+vec3(spec)*0.4;
  float emissiveA=clamp(max(max(emissive.r,emissive.g),emissive.b),0.0,1.0);
  float bodyA = mix(0.05, 0.13, uLight) + fres * mix(0.05, 0.16, uLight);
  float outA = emissiveA + bodyA * (1.0 - emissiveA);
  fragColor=vec4(emissive*mask,outA*mask);
}`

const hexToRgb01 = (hex) => {
  const c = new Color(hex)
  return [c.r, c.g, c.b]
}
const buildPalette = (colors) => {
  const padded = []
  for (let i = 0; i < MAX_COLORS; i++) {
    const c = new Color(colors[i] ?? colors[colors.length - 1])
    padded.push([c.r, c.g, c.b])
  }
  return padded
}

let renderer, program, glassProgram, renderTarget, animId
let onResize

onMounted(() => {
  const container = containerRef.value
  if (!container) return

  renderer = new Renderer({ alpha: true, premultipliedAlpha: true, antialias: true })
  const gl = renderer.gl
  gl.clearColor(0, 0, 0, 0)
  gl.enable(gl.BLEND)
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)
  gl.canvas.style.backgroundColor = 'transparent'

  const geometry = new Triangle(gl)
  if (geometry.attributes.uv) delete geometry.attributes.uv

  program = new Program(gl, {
    vertex: VERT,
    fragment: FRAG,
    uniforms: {
      uTime: { value: 0 },
      uResolution: { value: [container.offsetWidth, container.offsetHeight] },
      uColors: { value: buildPalette(emotionColors(0)) },
      uColorCount: { value: 3 },
      uStrandCount: { value: 4 },
      uSpeed: { value: 0.4 },
      uAmplitude: { value: 0.7 },
      uWaviness: { value: 1 },
      uThickness: { value: 0.85 },
      uGlow: { value: 2.2 },
      uTaper: { value: 3 },
      uSpread: { value: 1 },
      uHueShift: { value: 0 },
      uIntensity: { value: 0.6 },
      uOpacity: { value: 1 },
      uScale: { value: 1.4 },
      uSaturation: { value: 1.5 }
    }
  })
  const mesh = new Mesh(gl, { geometry, program })

  renderTarget = new RenderTarget(gl, { width: container.offsetWidth, height: container.offsetHeight })
  glassProgram = new Program(gl, {
    vertex: VERT,
    fragment: GLASS_FRAG,
    uniforms: {
      uScene: { value: renderTarget.texture },
      uResolution: { value: [container.offsetWidth, container.offsetHeight] },
      uRadius: { value: 0.375 },
      uRefraction: { value: 1.1 },
      uDispersion: { value: 1.25 },
      uLight: { value: 1 },
      uTint: { value: hexToRgb01(emotionColors(0)[1]) }
    }
  })
  const glassMesh = new Mesh(gl, { geometry, program: glassProgram })
  container.appendChild(gl.canvas)

  const resize = () => {
    const w = container.offsetWidth, h = container.offsetHeight
    if (!w || !h) return
    renderer.setSize(w, h)
    program.uniforms.uResolution.value = [w, h]
    glassProgram.uniforms.uResolution.value = [w, h]
    renderTarget.setSize(w, h)
  }
  onResize = resize
  window.addEventListener('resize', onResize)
  resize()

  const frame = (time) => {
    animId = requestAnimationFrame(frame)
    const v = clamp(props.value, -1, 1)
    const e = emotionEnergy(v)
    program.uniforms.uTime.value = time * 0.001
    program.uniforms.uColors.value = buildPalette(emotionColors(v))
    program.uniforms.uSpeed.value = 0.4 + 0.6 * e
    program.uniforms.uAmplitude.value = 0.7 + 0.7 * e
    program.uniforms.uGlow.value = 1.9 + 1.2 * e
    program.uniforms.uIntensity.value = 0.5 + 0.35 * e
    renderer.render({ scene: mesh, target: renderTarget })
    glassProgram.uniforms.uScene.value = renderTarget.texture
    // 微脉动：平静 ±1%，极端 ±2.5%（呼吸感）
    const pulse = 1 + (0.01 + 0.015 * e) * Math.sin(time * 0.001 * (1.5 + 2.5 * e))
    glassProgram.uniforms.uRadius.value = 0.375 * emotionGlassSize(v) * pulse
    glassProgram.uniforms.uTint.value = hexToRgb01(emotionColors(v)[1])
    renderer.render({ scene: glassMesh })
  }
  animId = requestAnimationFrame(frame)
})

onBeforeUnmount(() => {
  if (animId) cancelAnimationFrame(animId)
  if (onResize) window.removeEventListener('resize', onResize)
  if (renderer) {
    const gl = renderer.gl
    gl.getExtension('WEBGL_lose_context')?.loseContext()
    if (gl.canvas && gl.canvas.parentNode) gl.canvas.parentNode.removeChild(gl.canvas)
  }
})
</script>

<style scoped>
.emotion-orb {
  width: 180px;
  height: 180px;
  flex-shrink: 0;
  border-radius: 12px;
  overflow: hidden;
  background: transparent;
}
.emotion-orb :deep(canvas),
.emotion-orb canvas {
  display: block;
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 6px 16px rgba(40, 40, 80, 0.2));
}
</style>
