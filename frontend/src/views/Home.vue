<template>
  <div class="home">
    <!-- 顶部装饰区域 -->
    <div class="hero-section">
      <div class="ink-wash-bg"></div>
      <div class="hero-content">
        <div class="seal-mark">印</div>
        <h1 class="main-title">
          <span class="vertical-text">中国画</span>
          <span class="vertical-text">书法AI</span>
        </h1>
        <p class="subtitle">基于人工智能的书画研究工具</p>
        <div class="divider"></div>
      </div>
    </div>

    <!-- 功能入口区域 -->
    <div class="features-section">
      <div class="section-header">
        <span class="section-number">壹</span>
        <h2 class="section-title">核心功能</h2>
        <span class="section-line"></span>
      </div>

      <div class="feature-cards">
        <!-- 题跋分析功能 -->
        <div class="feature-card" @click="$router.push('/tubi')">
          <div class="card-icon">
            <div class="icon-circle">
              <el-icon size="32"><DataAnalysis /></el-icon>
            </div>
          </div>
          <div class="card-content">
            <h3 class="card-title">题跋空间分析</h3>
            <p class="card-desc">AI自动识别画作中的题跋、绘画、留白区域</p>
            <div class="card-features">
              <span class="feature-tag">区域识别</span>
              <span class="feature-tag">比例统计</span>
              <span class="feature-tag">热力图</span>
            </div>
          </div>
          <div class="card-arrow">
            <el-icon><ArrowRight /></el-icon>
          </div>
          <div class="card-seal">分析</div>
        </div>

        <!-- 字体识别功能 -->
        <div class="feature-card" @click="$router.push('/recognize')">
          <div class="card-icon">
            <div class="icon-circle secondary">
              <el-icon size="32"><Camera /></el-icon>
            </div>
          </div>
          <div class="card-content">
            <h3 class="card-title">书法字体识别</h3>
            <p class="card-desc">上传书法单字，智能匹配碑帖来源</p>
            <div class="card-features">
              <span class="feature-tag">单字识别</span>
              <span class="feature-tag">碑帖匹配</span>
              <span class="feature-tag">相似度</span>
            </div>
          </div>
          <div class="card-arrow">
            <el-icon><ArrowRight /></el-icon>
          </div>
          <div class="card-seal secondary">识别</div>
        </div>
      </div>
    </div>

    <!-- 简介区域 -->
    <div class="about-section">
      <div class="section-header">
        <span class="section-number">贰</span>
        <h2 class="section-title">关于系统</h2>
        <span class="section-line"></span>
      </div>

      <div class="about-content">
        <div class="about-text">
          <p class="poem-text">
            笔墨丹青，千年传承<br>
            智能分析，古法新研
          </p>
          <p class="description">
            本系统融合传统书画艺术与现代人工智能技术，为研究者提供精准的题跋区域分析和字体识别服务。
            支持李鱓等明清画家作品的空间布局研究，以及历代碑帖的字体溯源。
          </p>
        </div>
        <div class="about-image">
          <div class="image-frame">
            <div class="placeholder-image">
              <el-icon size="48"><Document /></el-icon>
              <span>书画艺术</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 简化的名家对比 - 放在关于系统区域底部 -->
      <div class="simple-comparison">
        <div class="simple-comparison-title">研究对象</div>
        <div class="simple-comparison-content">
          <div class="simple-artist">
            <div class="simple-avatar li">李</div>
            <div class="simple-info">
              <div class="simple-name">李鱓</div>
              <div class="simple-years">1686 - 1756</div>
            </div>
          </div>
          <div class="simple-vs">vs</div>
          <div class="simple-artist">
            <div class="simple-avatar zheng">郑</div>
            <div class="simple-info">
              <div class="simple-name">郑燮</div>
              <div class="simple-years">1693 - 1766</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 使用流程 -->
    <div class="process-section">
      <div class="section-header">
        <span class="section-number">叁</span>
        <h2 class="section-title">使用流程</h2>
        <span class="section-line"></span>
      </div>

      <div class="process-steps">
        <div class="step-item">
          <div class="step-number">一</div>
          <div class="step-content">
            <h4>上传图像</h4>
            <p>选择书法或绘画作品</p>
          </div>
        </div>
        <div class="step-arrow">→</div>
        <div class="step-item">
          <div class="step-number">二</div>
          <div class="step-content">
            <h4>AI分析</h4>
            <p>智能识别与匹配</p>
          </div>
        </div>
        <div class="step-arrow">→</div>
        <div class="step-item">
          <div class="step-number">三</div>
          <div class="step-content">
            <h4>查看结果</h4>
            <p>获取分析报告</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部引用 -->
    <div class="quote-section">
      <div class="quote-content">
        <p class="quote-text">"书之妙道，神采为上，形质次之"</p>
        <p class="quote-author">—— 王僧虔 《笔意赞》</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { DataAnalysis, Camera, ArrowRight, Document } from '@element-plus/icons-vue'
</script>

<style scoped>
/* 基础样式 */
.home {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f6f1 0%, #f0ebe3 100%);
  font-family: "Noto Serif SC", "Source Han Serif SC", "SimSun", serif;
}

/* 顶部装饰区域 */
.hero-section {
  position: relative;
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.ink-wash-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: 
    radial-gradient(ellipse at 30% 20%, rgba(139, 115, 85, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 70% 80%, rgba(139, 115, 85, 0.06) 0%, transparent 50%),
    linear-gradient(180deg, #f8f6f1 0%, #f0ebe3 100%);
  opacity: 0.8;
}

.ink-wash-bg::before {
  content: '';
  position: absolute;
  top: 10%;
  right: 15%;
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(139, 115, 85, 0.1) 0%, transparent 70%);
  border-radius: 50%;
}

.hero-content {
  position: relative;
  text-align: center;
  z-index: 1;
}

.seal-mark {
  position: absolute;
  top: -40px;
  right: -60px;
  width: 60px;
  height: 60px;
  background: #c45c48;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
  border-radius: 4px;
  transform: rotate(-5deg);
  box-shadow: 2px 2px 8px rgba(196, 92, 72, 0.3);
}

.main-title {
  display: flex;
  justify-content: center;
  gap: 30px;
  margin-bottom: 20px;
}

.vertical-text {
  writing-mode: vertical-rl;
  text-orientation: upright;
  font-size: 48px;
  font-weight: 700;
  color: #3d3d3d;
  letter-spacing: 0.3em;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.05);
}

.subtitle {
  font-size: 18px;
  color: #8b7355;
  letter-spacing: 0.5em;
  margin-top: 20px;
}

.divider {
  width: 60px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #8b7355, transparent);
  margin: 30px auto 0;
}

/* 区块通用样式 */
.features-section,
.about-section,
.process-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 60px 40px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 50px;
  gap: 20px;
}

.section-number {
  font-size: 24px;
  color: #c45c48;
  font-weight: bold;
  font-family: "KaiTi", "STKaiti", serif;
}

.section-title {
  font-size: 28px;
  color: #3d3d3d;
  font-weight: 600;
  letter-spacing: 0.2em;
}

.section-line {
  width: 100px;
  height: 1px;
  background: linear-gradient(90deg, transparent, #8b7355, transparent);
}

/* 功能卡片 */
.feature-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 40px;
}

.feature-card {
  background: white;
  border-radius: 8px;
  padding: 40px;
  display: flex;
  align-items: flex-start;
  gap: 30px;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  border: 1px solid #e8e4dc;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.feature-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
  border-color: #c45c48;
}

.card-icon {
  flex-shrink: 0;
}

.icon-circle {
  width: 70px;
  height: 70px;
  background: linear-gradient(135deg, #c45c48 0%, #a84838 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 4px 15px rgba(196, 92, 72, 0.3);
}

.icon-circle.secondary {
  background: linear-gradient(135deg, #8b7355 0%, #6b5a45 100%);
  box-shadow: 0 4px 15px rgba(139, 115, 85, 0.3);
}

.card-content {
  flex: 1;
}

.card-title {
  font-size: 24px;
  color: #3d3d3d;
  margin-bottom: 12px;
  font-weight: 600;
}

.card-desc {
  font-size: 15px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 20px;
}

.card-features {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.feature-tag {
  padding: 4px 12px;
  background: #f5f3ef;
  border: 1px solid #e0dcd4;
  border-radius: 20px;
  font-size: 13px;
  color: #8b7355;
}

.card-arrow {
  color: #ccc;
  transition: all 0.3 ease;
}

.feature-card:hover .card-arrow {
  color: #c45c48;
  transform: translateX(5px);
}

.card-seal {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 40px;
  height: 40px;
  background: #c45c48;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;
  border-radius: 4px;
  transform: rotate(8deg);
  opacity: 0.9;
}

.card-seal.secondary {
  background: #8b7355;
}

/* 关于区域 */
.about-section {
  background: white;
  border-top: 1px solid #e8e4dc;
  border-bottom: 1px solid #e8e4dc;
}

.about-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 60px;
  align-items: center;
}

.about-text {
  padding-right: 40px;
}

.poem-text {
  font-size: 24px;
  color: #3d3d3d;
  line-height: 2;
  margin-bottom: 30px;
  font-family: "KaiTi", "STKaiti", serif;
  letter-spacing: 0.1em;
}

.description {
  font-size: 15px;
  color: #666;
  line-height: 2;
  text-align: justify;
}

.about-image {
  display: flex;
  justify-content: center;
}

.image-frame {
  width: 300px;
  height: 300px;
  border: 2px solid #e0dcd4;
  padding: 20px;
  background: white;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
}

.placeholder-image {
  width: 100%;
  height: 100%;
  background: #f8f6f1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #8b7355;
  gap: 10px;
}

/* 简化版名家对比 */
.simple-comparison {
  margin-top: 50px;
  padding-top: 40px;
  border-top: 1px dashed #e0dcd4;
}

.simple-comparison-title {
  text-align: center;
  font-size: 16px;
  color: #8b7355;
  margin-bottom: 24px;
  letter-spacing: 0.2em;
}

.simple-comparison-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 40px;
}

.simple-artist {
  display: flex;
  align-items: center;
  gap: 16px;
}

.simple-avatar {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: bold;
  color: white;
  font-family: "KaiTi", "STKaiti", serif;
}

.simple-avatar.li {
  background: linear-gradient(135deg, #c45c48 0%, #a84838 100%);
}

.simple-avatar.zheng {
  background: linear-gradient(135deg, #2c5f7c 0%, #1a3a4d 100%);
}

.simple-info {
  text-align: left;
}

.simple-name {
  font-size: 18px;
  font-weight: 600;
  color: #3d3d3d;
  margin-bottom: 4px;
}

.simple-years {
  font-size: 13px;
  color: #8b7355;
}

.simple-vs {
  font-size: 14px;
  color: #999;
  font-weight: 500;
  padding: 4px 12px;
  background: #f5f3ef;
  border-radius: 20px;
}

/* 流程区域 */
.process-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 30px;
}

.step-item {
  text-align: center;
  padding: 30px 40px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e8e4dc;
  min-width: 180px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.03);
}

.step-number {
  width: 50px;
  height: 50px;
  background: #c45c48;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-family: "KaiTi", "STKaiti", serif;
  margin: 0 auto 20px;
}

.step-content h4 {
  font-size: 18px;
  color: #3d3d3d;
  margin-bottom: 8px;
}

.step-content p {
  font-size: 14px;
  color: #8b7355;
}

.step-arrow {
  font-size: 24px;
  color: #c45c48;
  font-weight: bold;
}

/* 引用区域 */
.quote-section {
  background: #3d3d3d;
  padding: 60px 40px;
  text-align: center;
}

.quote-content {
  max-width: 800px;
  margin: 0 auto;
}

.quote-text {
  font-size: 28px;
  color: #f0ebe3;
  font-family: "KaiTi", "STKaiti", serif;
  line-height: 1.8;
  margin-bottom: 20px;
  letter-spacing: 0.1em;
}

.quote-author {
  font-size: 16px;
  color: #8b7355;
  letter-spacing: 0.2em;
}

/* 响应式 */
@media (max-width: 968px) {
  .feature-cards {
    grid-template-columns: 1fr;
  }

  .about-content {
    grid-template-columns: 1fr;
  }

  .process-steps {
    flex-direction: column;
  }

  .step-arrow {
    transform: rotate(90deg);
  }

  .vertical-text {
    font-size: 36px;
  }

  .simple-comparison-content {
    flex-direction: column;
    gap: 20px;
  }
}
</style>
