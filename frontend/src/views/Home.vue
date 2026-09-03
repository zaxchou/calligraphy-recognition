<template>
  <div class="home">
    <!-- ==================== 暗色区 ==================== -->
    <div class="dark-section">
      <!-- Hero -->
      <div class="hero-section">
        <div v-show="showVideoBg" class="hero-video">
          <video autoplay muted loop playsinline :src="VIDEO_SRC" />
        </div>
        <div v-show="!showVideoBg" class="hero-gallery">
          <div class="gallery-row gallery-row--top">
            <div class="gallery-track gallery-track--left">
              <div v-for="(img, i) in heroImages" :key="`t1-${i}`" class="gallery-frame">
                <img :src="img" alt="" loading="lazy" />
              </div>
              <div v-for="(img, i) in heroImages" :key="`t2-${i}`" class="gallery-frame">
                <img :src="img" alt="" loading="lazy" />
              </div>
            </div>
          </div>
          <div class="gallery-row gallery-row--bottom">
            <div class="gallery-track gallery-track--right">
              <div v-for="(img, i) in heroImagesReversed" :key="`b1-${i}`" class="gallery-frame">
                <img :src="img" alt="" loading="lazy" />
              </div>
              <div v-for="(img, i) in heroImagesReversed" :key="`b2-${i}`" class="gallery-frame">
                <img :src="img" alt="" loading="lazy" />
              </div>
            </div>
          </div>
        </div>

        <button class="bg-toggle" @click="showVideoBg = !showVideoBg">
          <el-icon v-if="showVideoBg"><Picture /></el-icon>
          <el-icon v-else><VideoPlay /></el-icon>
          <span>{{ showVideoBg ? '画廊背景' : '视频背景' }}</span>
        </button>

        <div class="hero-overlay"></div>
        <div class="hero-vignette"></div>

        <div class="hero-content t-stagger is-shown">
          <h1 class="hero-title t-stagger-line">{{ siteConfig.title }}<br/><span class="hero-title-accent">{{ siteConfig.subtitle }}</span></h1>
          <p class="hero-subtitle t-stagger-line t-stagger-line--2">题跋识别 · 字体溯源 · 构图分析 · 知识检索</p>
          <div class="hero-actions t-stagger-line t-stagger-line--3">
            <button class="btn-primary" @click="$router.push('/tiba')">
              <span>开始分析</span>
              <el-icon><ArrowRight /></el-icon>
            </button>
            <button class="btn-secondary" @click="scrollToFeatures">
              <span>了解功能</span>
            </button>
          </div>
          <div v-if="!loading && stats.total > 0" class="hero-trust t-stagger-line t-stagger-line--4">
            已收录 <strong>{{ stats.total }}</strong> 幅画作 · <strong>{{ artists.length }}</strong> 位艺术家
          </div>
        </div>
      </div>

      <!-- Stats Wall -->
      <div class="stats-wall">
        <div class="stats-wall-inner">
          <div class="stat-item">
            <div class="stat-num">{{ formatNumber(stats.total) }}</div>
            <div class="stat-label">收录画作</div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-num">{{ formatNumber(artists.length) }}</div>
            <div class="stat-label">艺术家</div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-num">{{ formatNumber(stats.albums?.count || 0) }}</div>
            <div class="stat-label">册页套数</div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-num">{{ formatNumber(stats.tags?.count || 0) }}</div>
            <div class="stat-label">标签类别</div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-num">{{ formatNumber(stats.albums?.item_count || 0) }}</div>
            <div class="stat-label">册页作品</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 淡色区 — 核心功能（硬切） ==================== -->
    <div class="features-section-light" ref="featuresRef">
      <div class="section-header-light">
        <div class="section-accent-bar"></div>
        <h2 class="section-title-light">核心功能</h2>
        <span class="section-line-light"></span>
      </div>
      <div class="feature-cards-light">
        <div 
          v-for="(feature, index) in features" 
          :key="feature.path" 
          class="feature-card-light"
          :class="feature.bgClass"
          @click="$router.push(feature.path)"
        >
          <div class="feature-card-preview">
            <div class="preview-placeholder" :class="'preview-' + index">
              <div class="preview-shape"></div>
            </div>
          </div>
          
          <div class="feature-card-content">
            <div class="feature-card-header">
              <div class="icon-wrapper">
                <div class="icon-circle-light" :class="feature.iconClass">
                  <el-icon size="22"><component :is="feature.icon" /></el-icon>
                </div>
                <div class="icon-decoration"></div>
              </div>
              <el-icon class="card-arrow-light" size="20"><ArrowRight /></el-icon>
            </div>
            
            <div class="feature-card-body">
              <div class="card-title-row">
                <span class="feature-tag">{{ feature.tag }}</span>
                <h3 class="card-title-light">{{ feature.title }}</h3>
              </div>
              <p class="card-desc-light">{{ feature.desc }}</p>
            </div>
          </div>
          
          <div class="feature-card-footer">
            <div class="gold-line"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部引用 -->
    <div class="quote-section">
      <div class="quote-content">
        <div class="quote-ornament">&#10077;</div>
        <p class="quote-text">书之妙道，神采为上，形质次之</p>
        <p class="quote-author">—— 王僧虔 《笔意赞》</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { siteConfig } from '../config'
import api from '../api'
import {
  DataAnalysis, Camera, ArrowRight, Collection, PictureFilled,
  TrendCharts, VideoPlay, Histogram, UserFilled
} from '@element-plus/icons-vue'

const router = useRouter()
const featuresRef = ref(null)

// ── 常量 ──────────────────────────────────────────
const VIDEO_SRC = '/videos/hero_museum_li_shan.mp4'

const heroImages = [
  '/images/hero/lishan_01.jpg', '/images/hero/lishan_02.jpg',
  '/images/hero/lishan_03.jpg', '/images/hero/lishan_04.jpg',
  '/images/hero/lishan_05.jpg', '/images/hero/lishan_06.jpg',
  '/images/hero/lishan_07.jpg', '/images/hero/lishan_08.jpg',
  '/images/hero/lishan_09.jpg', '/images/hero/lishan_10.jpg',
  '/images/hero/lishan_11.jpg',
]
const heroImagesReversed = [...heroImages].reverse()

const showVideoBg = ref(true)

// ── 功能卡片配置 ──────────────────────────────────
const features = [
  { 
    title: '艺术家百科', 
    desc: '探索历代书画名家生平、作品与艺术风格', 
    path: '/artists', 
    icon: 'UserFilled', 
    iconClass: '',
    bgClass: 'bg-artist',
    tag: '百科',
  },
  { 
    title: '写意知识库', 
    desc: '潘天寿、黄宾虹等名家题跋印章与绘画作品语义检索', 
    path: '/knowledge', 
    icon: 'Collection', 
    iconClass: '',
    bgClass: 'bg-knowledge',
    tag: '知识检索',
  },
  { 
    title: '题跋空间分析', 
    desc: 'AI 自动识别画作中的题跋、绘画、留白区域', 
    path: '/tiba', 
    icon: 'DataAnalysis', 
    iconClass: 'secondary',
    bgClass: 'bg-tiba',
    tag: 'AI识别',
  },
  { 
    title: '书法字体识别', 
    desc: '上传书法单字，智能匹配碑帖来源与相似度', 
    path: '/recognize', 
    icon: 'Camera', 
    iconClass: 'tertiary',
    bgClass: 'bg-recognize',
    tag: '字体溯源',
  },
  { 
    title: '潘天寿构图体系', 
    desc: '基于潘天寿教学理论，AI 分析国画构图与起承转合', 
    path: '/composition', 
    icon: 'PictureFilled', 
    iconClass: 'dark',
    bgClass: 'bg-composition',
    tag: '构图分析',
  },
  { 
    title: '起承转合分析', 
    desc: '运用多模态 AI 对国画构图的起承转合进行深度解读', 
    path: '/qczh', 
    icon: 'TrendCharts', 
    iconClass: 'accent',
    bgClass: 'bg-qczh',
    tag: '多模态',
  },
]

// ── 响应式数据 ────────────────────────────────────
const loading = ref(true)
const stats = ref({ total: 0, albums: { count: 0, item_count: 0 }, tags: { count: 0 } })
const artists = ref([])

// ── 计算属性 ──────────────────────────────────────

// ── 方法 ──────────────────────────────────────────
function formatNumber(n) {
  if (n === undefined || n === null) return '0'
  return n.toLocaleString('zh-CN')
}

function scrollToFeatures() {
  featuresRef.value?.scrollIntoView({ behavior: 'smooth' })
}

async function fetchDashboardData() {
  loading.value = true
  try {
    const [extRes, artistsRes] = await Promise.all([
      api.get('/tiba/stats/extended'),
      api.get('/content-analysis/artists'),
    ])

    if (extRes.success) stats.value = extRes.data
    if (artistsRes.success) artists.value = artistsRes.artists || []
  } catch (e) {
    console.error('首页数据加载失败', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboardData()
})
</script>

<style scoped>
/* ============================================
   全局
   ============================================ */
.home { min-height: 100vh; }

/* ============================================
   暗色区 — Hero + Stats
   ============================================ */
.dark-section { background: #0a0a0a; }

/* ── Hero ── */
.hero-section {
  position: relative; height: 78vh; min-height: 520px; max-height: 720px;
  overflow: hidden; display: flex; align-items: center; justify-content: center;
}
.hero-video { position: absolute; inset: 0; background: #0a0a0a; }
.hero-video video { width: 100%; height: 100%; object-fit: cover; }
.hero-gallery {
  position: absolute; inset: 0; display: flex; flex-direction: column;
  gap: 14px; padding: 14px 0; background: #0a0a0a;
}
.bg-toggle {
  position: absolute; top: 20px; right: 20px; z-index: 10;
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 14px; background: rgba(20,20,19,0.7);
  border: 1px solid rgba(255,255,255,0.12); border-radius: 999px;
  color: rgba(255,255,255,0.85); font-size: 13px; font-weight: 500;
  cursor: pointer; backdrop-filter: blur(8px); transition: all 0.2s ease;
}
.bg-toggle:hover { background: rgba(20,20,19,0.85); border-color: rgba(255,255,255,0.2); color: #fff; }
.gallery-row { flex: 1; overflow: hidden; position: relative; }
.gallery-track { display: flex; gap: 14px; height: 100%; width: max-content; }
.gallery-track--left { animation: scrollLeft 55s linear infinite; }
.gallery-track--right { animation: scrollRight 70s linear infinite; }
.gallery-frame {
  flex-shrink: 0; height: 100%; aspect-ratio: 4/3; border-radius: 8px;
  overflow: hidden; box-shadow: 0 4px 28px rgba(0,0,0,0.5);
  border: 1px solid rgba(255,255,255,0.06);
}
.gallery-frame img {
  width: 100%; height: 100%; object-fit: cover;
  filter: brightness(0.72) saturate(0.82);
  transition: filter 0.6s ease, transform 0.8s cubic-bezier(0.25,0.46,0.45,0.94);
}
.gallery-frame:hover img { filter: brightness(0.92) saturate(0.92); transform: scale(1.04); }

.hero-overlay {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(10,10,10,0.5) 0%, rgba(10,10,10,0.2) 35%, rgba(10,10,10,0.4) 65%, rgba(10,10,10,0.92) 100%);
  z-index: 1;
}
.hero-vignette {
  position: absolute; inset: 0;
  background: radial-gradient(ellipse 70% 50% at 50% 50%, rgba(10,10,10,0.3) 0%, transparent 60%);
  z-index: 1;
}
.hero-content { position: relative; z-index: 2; text-align: center; max-width: 640px; padding: 0 24px; }
.hero-title {
  font-family: 'Noto Serif SC','KaiTi','STKaiti',serif;
  font-size: 3.25rem; font-weight: 500; color: #fff;
  letter-spacing: 0.08em; line-height: 1.15; margin-bottom: 20px;
}
.hero-title-accent { font-size: 2.5rem; opacity: 0.9; }
.hero-subtitle {
  font-family: var(--font-sans); font-size: 1.05rem;
  color: rgba(255,255,255,0.65); letter-spacing: 0.3em; margin-bottom: 36px;
}
.hero-actions {
  display: flex; align-items: center; justify-content: center;
  gap: 16px; margin-bottom: 28px;
}
.btn-primary {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 28px; background: #c96442; border: none;
  border-radius: 8px; color: #fff; font-size: 15px; font-weight: 500;
  cursor: pointer; transition: all 0.2s ease;
}
.btn-primary:hover { background: #a8503a; transform: translateY(-1px); }
.btn-secondary {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 12px 28px; background: transparent;
  border: 1px solid rgba(255,255,255,0.25); border-radius: 8px;
  color: rgba(255,255,255,0.9); font-size: 15px; font-weight: 500;
  cursor: pointer; transition: all 0.2s ease;
}
.btn-secondary:hover { border-color: rgba(255,255,255,0.5); background: rgba(255,255,255,0.06); }
.hero-trust {
  font-size: 13px; color: rgba(255,255,255,0.45); letter-spacing: 0.08em;
}
.hero-trust strong { color: #b8a47e; font-weight: 600; }

/* ── Stats Wall ── */
.stats-wall {
  border-top: 1px solid rgba(255,255,255,0.06);
  border-bottom: 1px solid rgba(255,255,255,0.06);
  padding: 48px 24px;
}
.stats-wall-inner {
  max-width: 1000px; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between;
}
.stat-item { text-align: center; flex: 1; }
.stat-num {
  font-family: 'Noto Serif SC',serif; font-size: 2.5rem; font-weight: 500;
  color: #fff; line-height: 1.1; margin-bottom: 8px;
}
.stat-label { font-size: 13px; color: rgba(255,255,255,0.45); letter-spacing: 0.1em; }
.stat-divider { width: 1px; height: 40px; background: rgba(255,255,255,0.08); }

/* ============================================
   淡色区 — 核心功能（Claude 风格）
   ============================================ */
.features-section-light {
  background: var(--parchment, #f5f4ed);
  padding: 80px 24px;
}
.section-header-light {
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 56px; gap: 20px;
}
.section-accent-bar { width: 4px; height: 28px; background: #c96442; border-radius: 2px; }
.section-title-light {
  font-family: 'Noto Serif SC',serif; font-size: 1.6rem;
  color: var(--near-black, #141413); font-weight: 500; letter-spacing: 0.2em;
}
.section-line-light {
  width: 80px; height: 1px;
  background: linear-gradient(90deg, transparent, var(--gold, #b8a47e), transparent);
}
.feature-cards-light {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;
  max-width: 1100px; margin: 0 auto;
}

/* 各卡片专属渐变色背景（方案3） */
.feature-card-light.bg-knowledge {
  background: linear-gradient(135deg, rgba(201,100,66,0.06) 0%, rgba(245,244,237,1) 60%);
}
.feature-card-light.bg-artist {
  background: linear-gradient(135deg, rgba(196,90,60,0.08) 0%, rgba(245,244,237,1) 60%);
}
.feature-card-light.bg-tiba {
  background: linear-gradient(135deg, rgba(184,164,126,0.08) 0%, rgba(245,244,237,1) 60%);
}
.feature-card-light.bg-recognize {
  background: linear-gradient(135deg, rgba(77,76,72,0.06) 0%, rgba(245,244,237,1) 60%);
}
.feature-card-light.bg-composition {
  background: linear-gradient(135deg, rgba(61,61,58,0.06) 0%, rgba(245,244,237,1) 60%);
}
.feature-card-light.bg-qczh {
  background: linear-gradient(135deg, rgba(168,80,58,0.06) 0%, rgba(245,244,237,1) 60%);
}
.feature-card-light.bg-analytics {
  background: linear-gradient(135deg, rgba(90,122,150,0.06) 0%, rgba(245,244,237,1) 60%);
}

.feature-card-light {
  position: relative;
  border-radius: 12px; padding: 0;
  cursor: pointer; transition: all 0.3s ease;
  border: 1px solid var(--border-warm, #e8e6dc);
  box-shadow: 0 4px 20px rgba(0,0,0,0.04);
  overflow: hidden;
}
.feature-card-light:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(0,0,0,0.1);
  border-color: var(--cinnabar-light, #d97757);
}

/* 右上角低饱和功能预览图占位（方案2） */
.feature-card-preview {
  position: absolute; top: 0; right: 0;
  width: 80px; height: 70px;
  opacity: 0.6; transition: all 0.3s ease;
}
.feature-card-light:hover .feature-card-preview {
  opacity: 0.8; transform: scale(1.05);
}
.preview-placeholder {
  width: 100%; height: 100%;
  display: flex; align-items: center; justify-content: center;
}
.preview-shape {
  width: 50px; height: 50px;
  border-radius: 16px;
  opacity: 0.2;
}
.preview-0 .preview-shape { background: #c96442; transform: rotate(12deg); }
.preview-1 .preview-shape { background: #b8a47e; border-radius: 50%; }
.preview-2 .preview-shape { background: #4d4c48; border-radius: 50% 50% 0 50%; }
.preview-3 .preview-shape { background: #3d3d3a; transform: rotate(-6deg); }
.preview-4 .preview-shape { background: #a8503a; clip-path: polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%); }
.preview-5 .preview-shape { background: #5a7a96; border-radius: 16px 4px 16px 4px; }

/* 内容区域（不对称布局：左图标+右内容）（方案2） */
.feature-card-content {
  padding: 24px;
  display: flex; flex-direction: column; gap: 16px;
}

.feature-card-header {
  display: flex; align-items: flex-start; justify-content: space-between;
}

/* 图标装饰化背景（方案1） */
.icon-wrapper {
  position: relative;
}
.icon-circle-light {
  position: relative; z-index: 2;
  width: 48px; height: 48px;
  background: #c96442; border-radius: 12px;
  display: flex; align-items: center; justify-content: center; color: #fff;
  transition: all 0.3s ease;
  box-shadow: 0 6px 20px rgba(201,100,66,0.2);
}
.feature-card-light:hover .icon-circle-light {
  transform: scale(1.08);
  box-shadow: 0 10px 28px rgba(201,100,66,0.28);
}
.icon-decoration {
  position: absolute; z-index: 1;
  left: -4px; top: -4px;
  width: 56px; height: 56px;
  border-radius: 14px;
  border: 2px solid rgba(201,100,66,0.12);
  transition: all 0.3s ease;
}
.feature-card-light:hover .icon-decoration {
  transform: scale(1.15);
  border-color: rgba(201,100,66,0.3);
}
.icon-circle-light.secondary { background: #b8a47e; box-shadow: 0 6px 20px rgba(184,164,126,0.2); }
.icon-circle-light.secondary + .icon-decoration { border-color: rgba(184,164,126,0.12); }
.feature-card-light:hover .icon-circle-light.secondary { box-shadow: 0 10px 28px rgba(184,164,126,0.28); }
.feature-card-light:hover .icon-circle-light.secondary + .icon-decoration { border-color: rgba(184,164,126,0.3); }
.icon-circle-light.tertiary { background: #4d4c48; box-shadow: 0 6px 20px rgba(77,76,72,0.2); }
.icon-circle-light.tertiary + .icon-decoration { border-color: rgba(77,76,72,0.12); }
.feature-card-light:hover .icon-circle-light.tertiary { box-shadow: 0 10px 28px rgba(77,76,72,0.28); }
.feature-card-light:hover .icon-circle-light.tertiary + .icon-decoration { border-color: rgba(77,76,72,0.3); }
.icon-circle-light.dark { background: #3d3d3a; box-shadow: 0 6px 20px rgba(61,61,58,0.2); }
.icon-circle-light.dark + .icon-decoration { border-color: rgba(61,61,58,0.12); }
.feature-card-light:hover .icon-circle-light.dark { box-shadow: 0 10px 28px rgba(61,61,58,0.28); }
.feature-card-light:hover .icon-circle-light.dark + .icon-decoration { border-color: rgba(61,61,58,0.3); }
.icon-circle-light.accent { background: linear-gradient(135deg, #a8503a, #3d3d3a); box-shadow: 0 6px 20px rgba(168,80,58,0.2); }
.icon-circle-light.accent + .icon-decoration { border-color: rgba(168,80,58,0.12); }
.feature-card-light:hover .icon-circle-light.accent { box-shadow: 0 10px 28px rgba(168,80,58,0.28); }
.feature-card-light:hover .icon-circle-light.accent + .icon-decoration { border-color: rgba(168,80,58,0.3); }
.icon-circle-light.analytics { background: linear-gradient(135deg, #5a7a96, #3d5a73); box-shadow: 0 6px 20px rgba(90,122,150,0.2); }
.icon-circle-light.analytics + .icon-decoration { border-color: rgba(90,122,150,0.12); }
.feature-card-light:hover .icon-circle-light.analytics { box-shadow: 0 10px 28px rgba(90,122,150,0.28); }
.feature-card-light:hover .icon-circle-light.analytics + .icon-decoration { border-color: rgba(90,122,150,0.3); }

.card-arrow-light {
  color: var(--warm-silver, #b0aea5);
  transition: all 0.3s ease;
  margin-top: 4px;
}
.feature-card-light:hover .card-arrow-light {
  color: #c96442;
  transform: translateX(4px);
}

.card-title-row {
  display: flex; flex-direction: column; gap: 8px;
}
.feature-tag {
  display: inline-flex; align-items: center;
  font-size: 11px; font-weight: 500;
  color: #c96442;
  background: rgba(201,100,66,0.08);
  padding: 2px 10px;
  border-radius: 999px;
  letter-spacing: 0.06em;
  width: fit-content;
}
.card-title-light {
  font-family: 'Noto Serif SC',serif; font-size: 1.15rem;
  color: var(--near-black, #141413); font-weight: 500; letter-spacing: 0.04em;
}
.card-desc-light {
  font-family: var(--font-sans); font-size: 13px;
  color: var(--stone-gray, #87867f); line-height: 1.6;
}

/* 底部装饰金线（方案1） */
.feature-card-footer {
  position: relative;
  height: 3px;
  background: linear-gradient(90deg, transparent 0%, rgba(184,164,126,0.4) 30%, rgba(184,164,126,0.6) 50%, rgba(184,164,126,0.4) 70%, transparent 100%);
}
.feature-card-light:hover .feature-card-footer {
  background: linear-gradient(90deg, transparent 0%, rgba(201,100,66,0.6) 30%, rgba(201,100,66,0.8) 50%, rgba(201,100,66,0.6) 70%, transparent 100%);
}
.gold-line {
  width: 100%; height: 100%;
}

/* ============================================
   底部引用 — 暗色收尾
   ============================================ */
.quote-section {
  background: var(--deep-dark, #141413); padding: 80px 24px; text-align: center;
}
.quote-content { max-width: 600px; margin: 0 auto; }
.quote-ornament { font-size: 2rem; color: #c96442; opacity: 0.45; margin-bottom: 16px; font-family: Georgia,serif; line-height: 1; }
.quote-text { font-family: 'KaiTi','STKaiti',serif; font-size: 1.6rem; color: var(--parchment, #f5f4ed); line-height: 1.6; margin-bottom: 20px; letter-spacing: 0.12em; }
.quote-author { font-size: 13px; color: #b8a47e; letter-spacing: 0.2em; }

/* ============================================
   动画
   ============================================ */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes scrollLeft { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
@keyframes scrollRight { 0% { transform: translateX(-50%); } 100% { transform: translateX(0); } }

/* ============================================
   响应式
   ============================================ */
@media (max-width: 968px) {
  .hero-title { font-size: 2.5rem; }
  .hero-title-accent { font-size: 2rem; }
  .feature-cards-light { grid-template-columns: repeat(2, 1fr); }
  .stats-wall-inner { flex-wrap: wrap; gap: 24px; }
  .stat-divider { display: none; }
  .stat-item { min-width: 100px; }
}

@media (max-width: 640px) {
  .hero-section { height: 70vh; min-height: 400px; }
  .hero-content { padding: 0 20px; }
  .hero-title { font-size: 2rem; }
  .hero-title-accent { font-size: 1.6rem; }
  .hero-actions { flex-direction: column; gap: 12px; }
  .btn-primary, .btn-secondary { width: 100%; justify-content: center; }
  .feature-cards-light { grid-template-columns: 1fr; }
  .stats-wall { padding: 32px 16px; }
  .stat-num { font-size: 1.8rem; }
  .features-section-light { padding: 48px 16px; }
}
</style>