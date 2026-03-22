<template>
  <div class="tubi-analysis">
    <h1 class="page-title">中国画题跋空间分析</h1>
    <p class="page-subtitle">AI自动识别画作中的题跋、绘画、留白区域</p>

    <!-- 首页概览视图 - 当没有选择画作时显示 -->
    <div v-if="!currentImage" class="home-dashboard">
      <!-- 作品库列表 -->
      <el-card shadow="hover" class="gallery-card">
        <template #header>
          <div class="card-header">
            <span>作品库</span>
            <div class="header-actions">
              <el-tag type="info" size="small">共 {{ historyList.length }} 幅作品</el-tag>
              <el-button type="primary" size="small" @click="showUploadDialog" :icon="Plus">
                添加画作
              </el-button>
            </div>
          </div>
        </template>
        <div class="gallery-grid" v-if="displayedHistoryList.length > 0">
          <div
            v-for="item in displayedHistoryList"
            :key="item.id"
            class="gallery-item"
            @click="loadHistoryItem(item)"
          >
            <div class="gallery-image-wrapper">
              <img v-if="item.url" :src="item.url" class="gallery-image" loading="lazy" />
              <div v-else class="gallery-image-placeholder">
                <el-icon size="32"><Picture /></el-icon>
              </div>
              <div class="gallery-overlay">
                <el-button type="primary" size="small" circle @click.stop="editImageInfo(item)">
                  <el-icon><Edit /></el-icon>
                </el-button>
                <el-button type="danger" size="small" circle @click.stop="deleteImage(item)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
            <div class="gallery-info">
              <div class="gallery-title">{{ item.title || '未命名' }}</div>
              <div class="gallery-meta">
                <span v-if="item.artist">{{ item.artist }}</span>
                <span v-if="item.year">{{ item.year }}年</span>
              </div>
              <div class="gallery-stats" v-if="item.inscriptionPercent !== undefined">
                <el-tag size="small" type="primary">题跋 {{ item.inscriptionPercent?.toFixed(1) }}%</el-tag>
              </div>
            </div>
          </div>
        </div>
        <div v-if="historyList.length > displayLimit" class="gallery-load-more">
          <el-button type="primary" link @click="loadMoreGallery">
            加载更多 ({{ historyList.length - displayLimit }} 剩余)
          </el-button>
        </div>
        <div class="gallery-empty" v-else>
          <el-icon size="64" color="#dcdfe6"><Picture /></el-icon>
          <p>暂无作品</p>
          <el-button type="primary" @click="showUploadDialog">上传第一幅画作</el-button>
        </div>
      </el-card>

      <!-- 名家对比区域 - 对比条设计 -->
      <el-card shadow="hover" class="comparison-dashboard-card">
        <template #header>
          <div class="card-header">
            <span>名家对比</span>
            <el-tag type="info">李鱓 vs 郑燮</el-tag>
          </div>
        </template>
        <div class="comparison-bars-container">
          <!-- 头部信息 -->
          <div class="comparison-header">
            <div class="artist-header">
              <div class="artist-avatar li">李</div>
              <div class="artist-name-section">
                <h3>李鱓</h3>
                <p class="years">1686 - 1756</p>
              </div>
            </div>
            <div class="vs-divider">VS</div>
            <div class="artist-header">
              <div class="artist-name-section" style="text-align: right;">
                <h3>郑燮</h3>
                <p class="years">1693 - 1766</p>
              </div>
              <div class="artist-avatar zheng">郑</div>
            </div>
          </div>

          <!-- 对比条 -->
          <div class="comparison-bars">
            <!-- 画作数量 -->
            <div class="comparison-row">
              <div class="bar-side left-side">
                <div class="bar-track-full">
                  <div class="bar-bg"></div>
                  <div class="bar-progress li-bar" :style="{ width: calculateBarWidthPercent(artistStats.liShan.count, artistStats.zhengXie.count, 'left') }">
                    <span class="bar-value-text">{{ artistStats.liShan.count }}幅</span>
                  </div>
                </div>
              </div>
              <div class="bar-label-center">画作数量</div>
              <div class="bar-side right-side">
                <div class="bar-track-full">
                  <div class="bar-bg"></div>
                  <div class="bar-progress zheng-bar" :style="{ width: calculateBarWidthPercent(artistStats.liShan.count, artistStats.zhengXie.count, 'right') }">
                    <span class="bar-value-text">{{ artistStats.zhengXie.count }}幅</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 平均题跋占比 -->
            <div class="comparison-row">
              <div class="bar-side left-side">
                <div class="bar-track-full">
                  <div class="bar-bg"></div>
                  <div class="bar-progress li-bar" :style="{ width: calculatePercentBarWidthPercent(artistStats.liShan.avgPercent, artistStats.zhengXie.avgPercent, 'left') }">
                    <span class="bar-value-text">{{ artistStats.liShan.avgPercent }}%</span>
                  </div>
                </div>
              </div>
              <div class="bar-label-center">平均题跋占比</div>
              <div class="bar-side right-side">
                <div class="bar-track-full">
                  <div class="bar-bg"></div>
                  <div class="bar-progress zheng-bar" :style="{ width: calculatePercentBarWidthPercent(artistStats.liShan.avgPercent, artistStats.zhengXie.avgPercent, 'right') }">
                    <span class="bar-value-text">{{ artistStats.zhengXie.avgPercent }}%</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 偏爱形式 -->
            <div class="comparison-row layout-row">
              <div class="layout-value left-layout">{{ artistStats.liShan.favoriteLayout }}</div>
              <div class="bar-label-center">偏爱形式</div>
              <div class="layout-value right-layout">{{ artistStats.zhengXie.favoriteLayout }}</div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 趋势图卡片 -->
      <el-card shadow="hover" class="trend-card" v-if="filteredTrendChartData.length > 0">
        <template #header>
          <div class="card-header">
            <span>题跋占比趋势</span>
            <div class="trend-stats">
              <el-select v-model="trendArtistFilter" size="small" style="width: 120px; margin-right: 10px;" @change="onTrendArtistChange">
                <el-option label="全部作者" value="all" />
                <el-option label="李鱓" value="李鱓" />
                <el-option label="郑燮" value="郑燮" />
              </el-select>
              <el-tag type="info" size="small">共 {{ filteredTrendChartData.length }} 幅作品</el-tag>
              <el-tag type="success" size="small" v-if="trendStats.avgPercent">平均占比 {{ trendStats.avgPercent }}%</el-tag>
            </div>
          </div>
        </template>
        <div ref="trendChartRef" class="trend-chart"></div>
      </el-card>

      <!-- 快速开始 -->
      <el-card shadow="hover" class="quick-start-card">
        <template #header>
          <div class="card-header">
            <span>快速开始</span>
          </div>
        </template>
        <div class="quick-start-content">
          <p>上传画作进行AI分析，系统将自动识别题跋、绘画、留白区域</p>
          <div class="quick-start-buttons">
            <el-button type="primary" size="large" @click="showUploadDialog">
              <el-icon><Plus /></el-icon> 添加画作
            </el-button>
            <el-button type="success" size="large" @click="showBatchUploadDialog">
              <el-icon><Upload /></el-icon> 批量上传
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <div class="analysis-container" v-if="currentImage">
      <!-- 左侧：图片上传和显示 -->
      <div class="left-panel">
        <el-card shadow="hover" class="upload-card">
          <template #header>
            <div class="card-header">
              <span>画作上传</span>
              <div class="header-buttons">
                <el-button type="success" size="small" @click="showBatchUploadDialog">
                  <el-icon><Upload /></el-icon> 批量上传
                </el-button>
                <el-button type="primary" size="small" @click="showUploadDialog">
                  <el-icon><Plus /></el-icon> 添加画作
                </el-button>
                <el-button type="info" size="small" @click="backToHome" :icon="HomeFilled">
                  返回首页
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="!currentImage" class="empty-state">
            <el-icon size="60" color="#dcdfe6"><Picture /></el-icon>
            <p>请上传画作图片</p>
            <el-button type="primary" @click="showUploadDialog">选择图片</el-button>
          </div>

          <div v-else class="image-display">
            <!-- 画作标题信息 -->
            <div class="image-info-header" v-if="currentImage.title || currentImage.artist">
              <div class="header-left">
                <h3>{{ currentImage.title || '未命名' }}</h3>
                <p v-if="currentImage.artist">作者: {{ currentImage.artist }}</p>
                <p v-if="currentImage.year">{{ currentImage.year }}年 {{ currentImage.period ? `(时年${currentImage.period})` : '' }}</p>
              </div>
            </div>

            <!-- AI分析说明 -->
            <div v-if="analyzeStatus === 'analyzed' && analysisNote" class="analysis-note-main">
              <h4><el-icon><InfoFilled /></el-icon> AI分析说明</h4>
              <p>{{ analysisNote }}</p>
            </div>

            <!-- 分析完成后的左右布局：左面积占比智能示意图，右面积占比 -->
            <div v-if="analyzeStatus === 'analyzed'" class="analysis-result-layout">
              <!-- 左侧：面积占比智能示意图 -->
              <div class="annotated-image-section">
                <div class="section-title">面积占比智能示意图</div>
                <img :src="currentImage.annotatedImageUrl" class="annotated-image" />
              </div>
              
              <!-- 右侧：面积占比分析 -->
              <div class="stats-section">
                <div class="section-title">面积占比分析</div>
                <div class="stats-content">
                  <div ref="pieChartRef" class="pie-chart-small"></div>
                </div>
                <div class="stats-list">
                  <div class="stat-item inscription">
                    <span class="stat-dot" style="background: #ff6b6b;"></span>
                    <span class="stat-name">题跋区域</span>
                    <span class="stat-percent">{{ areaStats.inscriptionPercent }}%</span>
                  </div>
                  <div class="stat-item painting">
                    <span class="stat-dot" style="background: #4ecdc4;"></span>
                    <span class="stat-name">绘画区域</span>
                    <span class="stat-percent">{{ areaStats.paintingPercent }}%</span>
                  </div>
                  <div class="stat-item blank">
                    <span class="stat-dot" style="background: #667eea;"></span>
                    <span class="stat-name">留白区域</span>
                    <span class="stat-percent">{{ areaStats.blankPercent }}%</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 未分析时显示Canvas -->
            <div class="canvas-wrapper" v-else>
              <canvas ref="canvasRef" class="annotation-canvas"></canvas>
            </div>

            <!-- AI分析进度显示 -->
            <div v-if="analyzeStatus === 'analyzing'" class="analyzing-progress">
              <div class="glow-progress-container">
                <div class="glow-progress-bar">
                  <div class="glow-progress-fill" :style="{ width: analyzeProgress + '%' }"></div>
                </div>
                <span class="glow-progress-text">{{ analyzeProgress }}%</span>
              </div>
              <p class="analyzing-text">{{ analyzingStep }}</p>
              <p class="analyzing-subtext">书画AI智能系统正在分析中...</p>
            </div>

            <div class="image-meta">
              <el-tag>{{ currentImage.name }}</el-tag>
              <el-tag type="info">{{ currentImage.width }} × {{ currentImage.height }}</el-tag>
              <el-tag v-if="analyzeStatus === 'analyzed'" type="success">分析完成</el-tag>
              <el-button
                v-if="analyzeStatus !== 'analyzing' && analyzeStatus !== 'analyzed'"
                type="primary"
                size="small"
                @click="autoAnalyze"
              >
                开始AI分析
              </el-button>
            </div>
          </div>
        </el-card>

        <!-- 作品库（移到左侧）-->
        <el-card shadow="hover" class="history-card">
          <template #header>
            <div class="card-header">
              <span>作品库</span>
              <el-button type="primary" size="small" @click="showHistoryDialog" :icon="Clock">
                查看全部
              </el-button>
            </div>
          </template>
          <div class="history-list" v-if="historyList.length > 0">
            <div
              v-for="(item, index) in historyList.slice(0, 5)"
              :key="item.id"
              class="history-item"
              @click="loadHistoryItem(item)"
            >
              <img v-if="item.url" :src="item.url" class="history-item-thumb" />
              <div v-else class="history-item-thumb-placeholder">
                <el-icon size="20"><Picture /></el-icon>
              </div>
              <div class="history-item-info">
                <div class="history-item-title">{{ item.title || '未命名' }}</div>
                <div class="history-item-meta">
                  <span v-if="item.artist">{{ item.artist }}</span>
                  <span v-if="item.year">{{ item.year }}年</span>
                </div>
                <div class="history-item-stats" v-if="item.inscriptionPercent !== undefined">
                  <el-tag size="small" type="primary">题跋 {{ item.inscriptionPercent?.toFixed(1) }}%</el-tag>
                  <el-tag size="small" type="success">绘画 {{ item.paintingPercent?.toFixed(1) }}%</el-tag>
                </div>
              </div>
            </div>
            <div v-if="historyList.length > 5" class="history-more" @click="showHistoryDialog">
              <el-link type="primary">查看全部 {{ historyList.length }} 条记录</el-link>
            </div>
          </div>
          <div class="history-summary empty" v-else>
            <p>暂无历史记录</p>
          </div>
        </el-card>
      </div>

      <!-- 右侧：分析结果 -->
      <div class="right-panel">


        <!-- 原作卡片（右2）-->
        <el-card shadow="hover" class="original-image-card" v-if="analyzeStatus === 'analyzed' && currentImage?.url">
          <template #header>
            <div class="card-header">
              <span>原作</span>
            </div>
          </template>
          <div class="original-image-wrapper">
            <img :src="currentImage.url" class="original-image" />
          </div>
        </el-card>

        <!-- 区域分析与位置分析融合卡片（右3）-->
        <el-card shadow="hover" class="chart-card integrated-analysis-card" v-if="analyzeStatus === 'analyzed'">
          <template #header>
            <div class="card-header">
              <span>题跋空间分布分析</span>
              <el-tag type="success" size="small" v-if="positionAnalysis">{{ positionAnalysis.layout_type }}</el-tag>
            </div>
          </template>

          <!-- 融合式布局：热力图 + 位置分析平面图 -->
          <div class="integrated-analysis-container">
            <!-- 左侧：热力图（作为主视觉） -->
            <div class="heatmap-wrapper">
              <div class="heatmap-container" ref="heatmapContainerRef"></div>
              <!-- 位置标签叠加层 -->
              <div v-if="positionAnalysis" class="position-labels-overlay">
                <div class="position-main-label" :class="getPositionLabelClass()">
                  <div class="layout-type">{{ positionAnalysis.layout_type }}</div>
                  <div class="position-name">{{ positionAnalysis.position }}</div>
                </div>
              </div>
            </div>

            <!-- 右侧：分析图例与指标（平面图风格） -->
            <div v-if="positionAnalysis" class="analysis-legend-panel">
              <!-- 布局示意图 -->
              <div class="layout-diagram">
                <div class="diagram-title">布局示意图</div>
                <div class="diagram-canvas">
                  <div class="canvas-frame">
                    <div class="canvas-painting-area">绘画</div>
                    <div 
                      class="canvas-inscription-area" 
                      :class="getInscriptionAreaClass()"
                      :style="getInscriptionAreaStyle()"
                    >
                      题跋
                    </div>
                  </div>
                </div>
              </div>

              <!-- 指标列表 -->
              <div class="metrics-list">
                <div class="metric-row">
                  <div class="metric-icon coverage"></div>
                  <span class="metric-name">覆盖率</span>
                  <span class="metric-value">{{ (positionAnalysis.coverage_ratio * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-row">
                  <div class="metric-icon overlap"></div>
                  <span class="metric-name">重叠率</span>
                  <span class="metric-value">{{ (positionAnalysis.overlap_ratio * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-row">
                  <div class="metric-icon margin"></div>
                  <span class="metric-name">边距</span>
                  <span class="metric-value">{{ getEdgeDistanceShortText() }}</span>
                </div>
              </div>

              <!-- 描述文本 -->
              <div class="layout-description-box">
                {{ positionAnalysis.layout_description }}
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 历史记录对话框 -->
    <el-dialog
      v-model="historyDialogVisible"
      title="题跋分析历史记录"
      width="85%"
      :close-on-click-modal="false"
      class="history-dialog-wide"
    >
      <div class="history-dialog-content">
        <el-table :data="historyList" style="width: 100%" v-loading="historyLoading">
          <el-table-column label="图片" width="100">
            <template #default="scope">
              <img v-if="scope.row.url" :src="scope.row.url" class="history-thumb" @click="previewHistoryImage(scope.row)" />
              <div v-else class="history-thumb-placeholder">
                <el-icon size="24"><Picture /></el-icon>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="200">
            <template #default="scope">
              {{ scope.row.title || '未命名' }}
            </template>
          </el-table-column>
          <el-table-column prop="artist" label="作者" width="120">
            <template #default="scope">
              {{ scope.row.artist || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="题跋占比" width="100">
            <template #default="scope">
              <el-tag v-if="scope.row.inscriptionPercent !== undefined" type="danger">
                {{ scope.row.inscriptionPercent }}%
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="分析时间" width="160">
            <template #default="scope">
              {{ formatDate(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="scope">
              <div class="action-buttons">
                <el-button type="primary" size="small" @click="loadHistoryItem(scope.row)">
                  查看
                </el-button>
                <el-button type="warning" size="small" @click="editHistoryItem(scope.row)">
                  编辑
                </el-button>
                <el-button type="danger" size="small" @click="deleteHistoryItem(scope.row)">
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>

    <!-- 图片预览对话框 -->
    <el-dialog
      v-model="previewDialogVisible"
      title="图片预览"
      width="600px"
      :close-on-click-modal="true"
    >
      <img :src="previewImageUrl" style="width: 100%;" />
    </el-dialog>

    <!-- 编辑历史记录对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑画作信息"
      width="600px"
      :close-on-click-modal="false"
      class="modern-form-dialog"
    >
      <div class="form-section">
        <h4 class="form-section-title">基本信息</h4>
        <el-form :model="editForm" label-position="top" class="modern-form">
          <div class="form-row">
            <el-form-item label="画作标题" class="form-item-half">
              <el-input v-model="editForm.title" placeholder="请输入画作标题" />
            </el-form-item>
            <el-form-item label="作者姓名" class="form-item-half">
              <el-select v-model="editForm.artist" placeholder="请选择作者" style="width: 100%" @change="onEditArtistChange">
                <el-option label="李鱓" value="李鱓" />
                <el-option label="郑燮" value="郑燮" />
              </el-select>
            </el-form-item>
          </div>
          <div class="form-row">
            <el-form-item label="创作年代" class="form-item-half">
              <el-input v-model.number="editForm.year" placeholder="如：1725" @change="onEditYearChange" />
            </el-form-item>
            <el-form-item label="作者年龄" class="form-item-half">
              <el-input v-model.number="editForm.age" placeholder="如：39" @change="onEditAgeChange">
                <template #append>岁</template>
              </el-input>
            </el-form-item>
          </div>
        </el-form>
      </div>

      <div class="form-section">
        <h4 class="form-section-title">区域占比数据 (%)</h4>
        <el-form :model="editForm" label-position="top" class="modern-form">
          <div class="form-row">
            <el-form-item label="题跋区域" class="form-item-third">
              <el-input-number 
                v-model="editForm.inscriptionPercent" 
                :min="0" 
                :max="100" 
                :precision="1"
                placeholder="0.0"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="绘画区域" class="form-item-third">
              <el-input-number 
                v-model="editForm.paintingPercent" 
                :min="0" 
                :max="100" 
                :precision="1"
                placeholder="0.0"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="留白区域" class="form-item-third">
              <el-input-number 
                v-model="editForm.blankPercent" 
                :min="0" 
                :max="100" 
                :precision="1"
                placeholder="0.0"
                style="width: 100%"
              />
            </el-form-item>
          </div>
        </el-form>
      </div>

      <div class="form-section">
        <h4 class="form-section-title">分析说明</h4>
        <el-form :model="editForm" label-position="top" class="modern-form">
          <el-form-item label="AI分析说明">
            <el-input 
              v-model="editForm.analysisNote" 
              type="textarea" 
              :rows="4" 
              placeholder="请输入AI分析说明内容"
              class="modern-textarea"
            />
          </el-form-item>
          <el-form-item label="备注信息">
            <el-input 
              v-model="editForm.notes" 
              type="textarea" 
              :rows="3" 
              placeholder="请输入备注信息"
              class="modern-textarea"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <div class="dialog-footer modern-footer">
          <el-button @click="editDialogVisible = false" class="btn-cancel">取消</el-button>
          <el-button type="primary" @click="saveEdit" class="btn-submit">保存</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 上传对话框 -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="上传画作"
      width="550px"
      :close-on-click-modal="false"
      class="modern-form-dialog"
    >
      <div class="form-section">
        <h4 class="form-section-title">选择图片</h4>
        <el-upload
          class="upload-dialog-area modern-upload"
          drag
          action="#"
          :auto-upload="false"
          :on-change="handleFileChange"
          :show-file-list="false"
          accept="image/*"
        >
          <el-icon class="el-icon--upload" size="48"><Upload /></el-icon>
          <div class="el-upload__text">
            拖拽图片到此处或 <em>点击上传</em>
          </div>
          <div class="el-upload__tip">
            支持 JPG、PNG 格式，文件大小不超过 10MB
          </div>
        </el-upload>
      </div>

      <div class="form-section">
        <h4 class="form-section-title">画作信息</h4>
        <el-form :model="uploadForm" label-position="top" class="modern-form">
          <div class="form-row">
            <el-form-item label="画作标题" class="form-item-half">
              <el-input v-model="uploadForm.title" placeholder="请输入画作标题" />
            </el-form-item>
            <el-form-item label="作者姓名" class="form-item-half">
              <el-select v-model="uploadForm.artist" placeholder="请选择作者" style="width: 100%">
                <el-option label="李鱓" value="李鱓" />
                <el-option label="郑燮" value="郑燮" />
              </el-select>
            </el-form-item>
          </div>
          <div class="form-row">
            <el-form-item label="创作年份" class="form-item-half">
              <el-input v-model.number="uploadForm.year" placeholder="如：1725" @change="onYearChange" />
            </el-form-item>
            <el-form-item label="作者年龄" class="form-item-half">
              <el-input v-model.number="uploadForm.age" placeholder="如：39" @change="onAgeChange">
                <template #append>岁</template>
              </el-input>
            </el-form-item>
          </div>
        </el-form>
      </div>

      <template #footer>
        <div class="dialog-footer modern-footer">
          <el-button @click="uploadDialogVisible = false" class="btn-cancel">取消</el-button>
          <el-button type="primary" @click="confirmUpload" class="btn-submit">确定上传</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 批量上传对话框 -->
    <el-dialog
      v-model="batchUploadDialogVisible"
      title="批量上传画作"
      width="650px"
      :close-on-click-modal="false"
      class="modern-form-dialog batch-upload-dialog"
      :before-close="handleBatchDialogClose"
    >
      <div class="form-section" v-if="batchUploadStatus === 'selecting'">
        <h4 class="form-section-title">选择图片</h4>
        <el-upload
          class="batch-upload-area"
          drag
          action="#"
          :auto-upload="false"
          :on-change="handleBatchFileChange"
          :on-remove="handleBatchFileRemove"
          v-model:file-list="batchFileList"
          multiple
          accept="image/*"
        >
          <el-icon class="el-icon--upload" size="56"><Upload /></el-icon>
          <div class="el-upload__text">
            拖拽图片到此处或 <em>点击选择</em>
          </div>
          <div class="el-upload__tip">
            支持批量选择多张图片，支持 JPG、PNG 格式
          </div>
        </el-upload>

        <div v-if="batchFileList.length > 0" class="batch-file-preview">
          <div class="batch-file-count">已选择 {{ batchFileList.length }} 张图片</div>
          <div class="batch-file-list">
            <div v-for="(file, index) in batchFileList.slice(0, 6)" :key="file.uid" class="batch-file-item">
              <img v-if="file.url" :src="file.url" class="batch-file-thumb" />
              <div v-else class="batch-file-icon">
                <el-icon><Picture /></el-icon>
              </div>
              <span class="batch-file-name">{{ file.name }}</span>
            </div>
            <div v-if="batchFileList.length > 6" class="batch-file-more">
              +{{ batchFileList.length - 6 }} 更多
            </div>
          </div>
        </div>
      </div>

      <!-- 批量上传进度 -->
      <div v-else-if="batchUploadStatus === 'uploading'" class="batch-upload-progress-section">
        <div class="batch-progress-header">
          <h4 class="form-section-title">正在上传分析</h4>
          <span class="batch-progress-count">{{ batchCurrentIndex }} / {{ batchTotalCount }}</span>
        </div>
        
        <div class="batch-current-file">
          <img 
            v-if="batchCurrentImage?.url" 
            :src="batchCurrentImage.url" 
            class="batch-current-thumb" 
          />
          <img 
            v-else-if="batchCurrentFile?.url" 
            :src="batchCurrentFile.url" 
            class="batch-current-thumb" 
          />
          <div v-else class="batch-current-thumb-placeholder">
            <el-icon size="32"><Picture /></el-icon>
          </div>
          <div class="batch-current-info">
            <div class="batch-current-name">{{ batchCurrentImage?.name || batchCurrentFile?.name || '未知文件' }}</div>
            <div class="batch-current-status">{{ batchCurrentStatus }}</div>
          </div>
        </div>

        <div class="glow-progress-container batch-progress-bar">
          <div class="glow-progress-bar">
            <div class="glow-progress-fill" :style="{ width: batchUploadProgress + '%' }"></div>
          </div>
          <span class="glow-progress-text">{{ batchUploadProgress }}%</span>
        </div>

        <div class="batch-overall-progress">
          <span>总体进度: {{ batchCurrentIndex }} / {{ batchTotalCount }} 张</span>
          <span v-if="batchSuccessCount > 0" class="batch-success-count">成功: {{ batchSuccessCount }}</span>
          <span v-if="batchFailCount > 0" class="batch-fail-count">失败: {{ batchFailCount }}</span>
        </div>
      </div>

      <!-- 上传完成 -->
      <div v-else-if="batchUploadStatus === 'completed'" class="batch-upload-complete">
        <div class="batch-complete-icon">
          <el-icon size="64" color="#67C23A"><CircleCheck /></el-icon>
        </div>
        <h4 class="batch-complete-title">批量上传完成</h4>
        <div class="batch-complete-stats">
          <div class="batch-stat-item">
            <span class="batch-stat-label">成功</span>
            <span class="batch-stat-value success">{{ batchSuccessCount }}</span>
          </div>
          <div class="batch-stat-item">
            <span class="batch-stat-label">失败</span>
            <span class="batch-stat-value fail">{{ batchFailCount }}</span>
          </div>
          <div class="batch-stat-item">
            <span class="batch-stat-label">总计</span>
            <span class="batch-stat-value">{{ batchTotalCount }}</span>
          </div>
        </div>
        <p class="batch-complete-tip">画作信息可在作品库中编辑</p>
      </div>

      <template #footer>
        <div class="dialog-footer modern-footer">
          <el-button 
            v-if="batchUploadStatus === 'selecting'" 
            @click="batchUploadDialogVisible = false" 
            class="btn-cancel"
          >
            取消
          </el-button>
          <el-button 
            v-if="batchUploadStatus === 'selecting' && batchFileList.length > 0" 
            type="primary" 
            @click="startBatchUpload"
            class="btn-submit"
          >
            开始上传 ({{ batchFileList.length }}张)
          </el-button>
          <el-button 
            v-if="batchUploadStatus === 'uploading'" 
            type="danger" 
            @click="cancelBatchUpload"
            class="btn-cancel"
          >
            取消上传
          </el-button>
          <el-button 
            v-if="batchUploadStatus === 'completed'" 
            type="primary" 
            @click="closeBatchUploadDialog"
            class="btn-submit"
          >
            完成
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import {
  Plus, Picture, Loading, Upload, Delete, Document, Brush, FullScreen, InfoFilled, Clock, CircleCheck, Location, Edit, HomeFilled
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import { tubiApi } from '../api'

// 图片数据
const uploadedImages = ref([])
const currentImage = ref(null)
const canvasRef = ref(null)
let canvas = null
let ctx = null

// 画家信息配置
const ARTISTS = {
  '李鱓': { birth: 1686, death: 1756, defaultYear: 1725 },
  '郑燮': { birth: 1693, death: 1766, defaultYear: 1730 }
}

// 当前选中的画家
const currentArtist = ref('李鱓')

// 上传对话框
const uploadDialogVisible = ref(false)
const uploadForm = reactive({
  title: '',
  artist: '李鱓',
  year: ARTISTS['李鱓'].defaultYear,
  age: null
})

// 根据画家和年份计算年龄
function calculateAge(year, artistName = currentArtist.value) {
  if (!year || isNaN(parseInt(year))) return null
  const artist = ARTISTS[artistName]
  if (!artist) return null
  return parseInt(year) - artist.birth
}

// 根据画家和年龄计算年份
function calculateYear(age, artistName = currentArtist.value) {
  if (!age || isNaN(parseInt(age))) return null
  const artist = ARTISTS[artistName]
  if (!artist) return null
  return artist.birth + parseInt(age)
}

// 监听画家变化，更新年份和年龄
watch(() => uploadForm.artist, (newArtist) => {
  currentArtist.value = newArtist
  const artist = ARTISTS[newArtist]
  if (artist) {
    uploadForm.year = artist.defaultYear
    uploadForm.age = calculateAge(artist.defaultYear, newArtist)
  }
})

// 监听年份变化，自动计算年龄
watch(() => uploadForm.year, (newYear) => {
  if (newYear) {
    uploadForm.age = calculateAge(newYear, uploadForm.artist)
  }
})

// 监听年龄变化，自动计算年份
watch(() => uploadForm.age, (newAge) => {
  if (newAge) {
    uploadForm.year = calculateYear(newAge, uploadForm.artist)
  }
})

// 年份变化时自动计算年龄
function onYearChange(year) {
  if (year && !isNaN(parseInt(year))) {
    uploadForm.age = calculateAge(year, uploadForm.artist)
  }
}

// 年龄变化时自动计算年份
function onAgeChange(age) {
  if (age && !isNaN(parseInt(age))) {
    uploadForm.year = calculateYear(age, uploadForm.artist)
  }
}

// 编辑表单：作者变化时更新年份和年龄
function onEditArtistChange(artist) {
  const artistInfo = ARTISTS[artist]
  if (artistInfo) {
    editForm.year = artistInfo.defaultYear
    editForm.age = calculateAge(artistInfo.defaultYear, artist)
  }
}

// 编辑表单：年份变化时自动计算年龄
function onEditYearChange(year) {
  if (year && !isNaN(parseInt(year))) {
    editForm.age = calculateAge(year, editForm.artist)
  }
}

// 编辑表单：年龄变化时自动计算年份
function onEditAgeChange(age) {
  if (age && !isNaN(parseInt(age))) {
    editForm.year = calculateYear(age, editForm.artist)
  }
}

// 批量上传相关
const batchUploadDialogVisible = ref(false)
const batchFileList = ref([])
const batchUploadStatus = ref('selecting') // selecting, uploading, completed
const batchUploadProgress = ref(0)
const batchCurrentIndex = ref(0)
const batchTotalCount = ref(0)
const batchCurrentFile = ref(null)
const batchCurrentStatus = ref('')
const batchSuccessCount = ref(0)
const batchFailCount = ref(0)
const batchCurrentImage = ref(null)
let batchUploadCancelled = false

// 历史记录相关
const historyDialogVisible = ref(false)
const historyList = ref([])
const historyLoading = ref(false)
const previewDialogVisible = ref(false)
const previewImageUrl = ref('')

// 作品库分页显示
const displayLimit = ref(12)
const displayedHistoryList = computed(() => {
  return historyList.value.slice(0, displayLimit.value)
})

// 加载更多作品
function loadMoreGallery() {
  displayLimit.value += 12
}
const editDialogVisible = ref(false)
const editForm = reactive({
  id: '',
  title: '',
  artist: '',
  year: '',
  age: '',
  notes: '',
  analysisNote: '',
  inscriptionPercent: 0,
  paintingPercent: 0,
  blankPercent: 0
})
let tempFile = null

// 分析状态
const analyzeStatus = ref('pending')
const analyzeProgress = ref(0)
const analyzingStep = ref('准备分析...')

// 区域统计
const areaStats = reactive({
  inscriptionPercent: 0,
  paintingPercent: 0,
  blankPercent: 0
})

// 区域数据
let regions = {
  inscription_regions: [],
  painting_regions: [],
  blank_regions: []
}

// 视图切换
// 分析说明
const analysisNote = ref('')

// 题跋位置分析
const positionAnalysis = ref(null)

// 图表引用
const pieChartRef = ref(null)
const heatmapContainerRef = ref(null)
const trendChartRef = ref(null)
let pieChart = null
let heatmapChart = null
let trendChart = null

// 趋势图数据
const trendChartData = ref([])
const trendArtistFilter = ref('all')
const trendStats = reactive({
  avgPercent: 0,
  maxPercent: 0,
  minPercent: 0
})

// 根据作者筛选的趋势图数据
const filteredTrendChartData = computed(() => {
  if (trendArtistFilter.value === 'all') {
    return trendChartData.value
  }
  return trendChartData.value.filter(item => item.artist === trendArtistFilter.value)
})

// 艺术家统计数据
const artistStats = computed(() => {
  const liShanData = historyList.value.filter(item => item.artist === '李鱓')
  const zhengXieData = historyList.value.filter(item => item.artist === '郑燮')

  // 计算李鱓统计
  const liShanPercents = liShanData.map(item => item.inscriptionPercent).filter(p => p !== undefined && p !== null)
  const liShanAvg = liShanPercents.length > 0
    ? (liShanPercents.reduce((a, b) => a + b, 0) / liShanPercents.length).toFixed(1)
    : '19.4'

  // 计算郑燮统计
  const zhengXiePercents = zhengXieData.map(item => item.inscriptionPercent).filter(p => p !== undefined && p !== null)
  const zhengXieAvg = zhengXiePercents.length > 0
    ? (zhengXiePercents.reduce((a, b) => a + b, 0) / zhengXiePercents.length).toFixed(1)
    : '--'

  return {
    liShan: {
      count: liShanData.length || 8,
      avgPercent: liShanAvg,
      favoriteLayout: '边角式'
    },
    zhengXie: {
      count: zhengXieData.length || 0,
      avgPercent: zhengXieAvg,
      favoriteLayout: zhengXieData.length > 0 ? '待分析' : '待添加'
    }
  }
})

// 趋势图作者筛选变化
function onTrendArtistChange() {
  updateTrendChart()
}

// 计算对比条宽度（用于数量对比）
function calculateBarWidth(leftValue, rightValue, side) {
  const left = parseFloat(leftValue) || 0
  const right = parseFloat(rightValue) || 0
  const max = Math.max(left, right, 1)
  const minWidth = 30 // 最小宽度百分比
  
  if (side === 'left') {
    const percentage = (left / max) * 100
    return Math.max(percentage, minWidth) + '%'
  } else {
    const percentage = (right / max) * 100
    return Math.max(percentage, minWidth) + '%'
  }
}

// 计算百分比对比条宽度
function calculatePercentBarWidth(leftValue, rightValue, side) {
  const left = parseFloat(leftValue) || 0
  const right = parseFloat(rightValue) || 0
  const max = Math.max(left, right, 1)
  const minWidth = 30
  
  if (side === 'left') {
    const percentage = (left / max) * 100
    return Math.max(percentage, minWidth) + '%'
  } else {
    const percentage = (right / max) * 100
    return Math.max(percentage, minWidth) + '%'
  }
}

// 计算百分比宽度（新设计用）
function calculateBarWidthPercent(leftValue, rightValue, side) {
  const left = parseFloat(leftValue) || 0
  const right = parseFloat(rightValue) || 0
  const max = Math.max(left, right, 1)
  const minWidth = 15 // 最小15%
  
  if (side === 'left') {
    const percentage = (left / max) * 100
    return Math.max(percentage, minWidth) + '%'
  } else {
    const percentage = (right / max) * 100
    return Math.max(percentage, minWidth) + '%'
  }
}

// 计算百分比对比条宽度（新设计用）
function calculatePercentBarWidthPercent(leftValue, rightValue, side) {
  const left = parseFloat(leftValue) || 0
  const right = parseFloat(rightValue) || 0
  const max = Math.max(left, right, 1)
  const minWidth = 15
  
  if (side === 'left') {
    const percentage = (left / max) * 100
    return Math.max(percentage, minWidth) + '%'
  } else {
    const percentage = (right / max) * 100
    return Math.max(percentage, minWidth) + '%'
  }
}

// 显示上传对话框
function showUploadDialog() {
  uploadDialogVisible.value = true
  tempFile = null
  uploadForm.title = ''
  uploadForm.artist = '李鱓'
  uploadForm.year = ARTISTS['李鱓'].defaultYear
  uploadForm.age = calculateAge(ARTISTS['李鱓'].defaultYear, '李鱓')
}

// 返回首页
function backToHome() {
  currentImage.value = null
  analyzeStatus.value = 'idle'
  analysisNote.value = ''
  positionAnalysis.value = null
  areaStats.value = {
    inscriptionPercent: 0,
    paintingPercent: 0,
    blankPercent: 0
  }
  // 清空图表
  if (pieChart) {
    pieChart.dispose()
    pieChart = null
  }
  if (heatmapChart) {
    heatmapChart.dispose()
    heatmapChart = null
  }
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
  
  // 返回首页后重新更新趋势图数据
  nextTick(() => {
    updateTrendChart()
  })
}

// 处理文件选择
function handleFileChange(file) {
  if (!file) return
  const isImage = file.raw.type.startsWith('image/')
  if (!isImage) {
    ElMessage.error('请上传图片文件')
    return
  }
  const isLt10M = file.raw.size / 1024 / 1024 < 10
  if (!isLt10M) {
    ElMessage.error('图片大小不能超过10MB')
    return
  }
  tempFile = file.raw
  if (!uploadForm.title) {
    uploadForm.title = file.name.replace(/\.[^/.]+$/, '')
  }
}

// 确认上传
async function confirmUpload() {
  if (!tempFile) {
    ElMessage.warning('请先选择图片')
    return
  }

  const formData = new FormData()
  formData.append('file', tempFile)
  if (uploadForm.title) formData.append('title', uploadForm.title)
  if (uploadForm.artist) formData.append('artist', uploadForm.artist)
  if (uploadForm.year) formData.append('year', uploadForm.year.toString())
  // 将年龄作为 period 传给后端，格式为 "39岁"
  if (uploadForm.age) formData.append('period', `${uploadForm.age}岁`)

  try {
    const response = await fetch('/api/v1/tubi/upload', {
      method: 'POST',
      body: formData
    })

    const result = await response.json()

    if (result.success) {
      const newImage = {
        id: result.data.id,
        name: tempFile.name,
        url: result.data.url,
        thumbnailUrl: result.data.thumbnail_url,
        width: result.data.width,
        height: result.data.height,
        title: uploadForm.title,
        artist: uploadForm.artist,
        year: uploadForm.year,
        period: `${uploadForm.age}岁`,
        inscriptionPercent: undefined,
        paintingPercent: undefined,
        blankPercent: undefined,
        regions: null,
        annotatedImageUrl: null
      }

      uploadedImages.value.push(newImage)
      selectImage(newImage)
      uploadDialogVisible.value = false
      ElMessage.success('上传成功')
    } else {
      throw new Error(result.detail || '上传失败')
    }
  } catch (error) {
    ElMessage.error(`上传失败: ${error.message}`)
  }
}

// ============ 批量上传功能 ============

// 显示批量上传对话框
function showBatchUploadDialog() {
  batchUploadDialogVisible.value = true
  batchUploadStatus.value = 'selecting'
  batchFileList.value = []
  batchUploadProgress.value = 0
  batchCurrentIndex.value = 0
  batchTotalCount.value = 0
  batchSuccessCount.value = 0
  batchFailCount.value = 0
  batchCurrentImage.value = null
  batchUploadCancelled = false
}

// 处理批量文件选择
function handleBatchFileChange(uploadFile, uploadFiles) {
  console.log('文件选择变化:', uploadFile?.name, '总文件数:', uploadFiles.length)
  
  // 为新添加的文件生成预览URL
  // 注意：uploadFile 是当前变化的文件，uploadFiles 是完整列表
  if (uploadFile && uploadFile.raw && !uploadFile.url) {
    try {
      uploadFile.url = URL.createObjectURL(uploadFile.raw)
      console.log('生成预览URL:', uploadFile.name)
    } catch (e) {
      console.error('生成预览URL失败:', uploadFile.name, e)
    }
  }
  
  // 确保所有文件都有预览URL
  uploadFiles.forEach(file => {
    if (!file.url && file.raw) {
      try {
        file.url = URL.createObjectURL(file.raw)
        console.log('生成预览URL:', file.name)
      } catch (e) {
        console.error('生成预览URL失败:', file.name, e)
      }
    }
  })
  
  console.log('当前文件列表:', uploadFiles.map(f => ({ name: f.name, hasUrl: !!f.url })))
}

// 处理批量文件移除
function handleBatchFileRemove(uploadFile, uploadFiles) {
  batchFileList.value = uploadFiles
}

// 开始批量上传
async function startBatchUpload() {
  if (batchFileList.value.length === 0) {
    ElMessage.warning('请先选择图片')
    return
  }

  batchUploadStatus.value = 'uploading'
  batchTotalCount.value = batchFileList.value.length
  batchCurrentIndex.value = 0
  batchSuccessCount.value = 0
  batchFailCount.value = 0
  batchUploadCancelled = false

  for (let i = 0; i < batchFileList.value.length; i++) {
    if (batchUploadCancelled) {
      console.log('批量上传已取消')
      break
    }

    const file = batchFileList.value[i]
    batchCurrentIndex.value = i + 1
    batchCurrentFile.value = file
    batchCurrentImage.value = null  // 重置当前图片
    batchCurrentStatus.value = '正在上传...'
    // 初始进度基于已完成的图片
    const initialProgress = Math.round((i / batchFileList.value.length) * 100)
    batchUploadProgress.value = initialProgress
    
    // 强制UI更新
    await nextTick()
    
    console.log(`========== 开始处理第 ${i+1}/${batchFileList.value.length} 张图片，进度: ${initialProgress}% ==========`)

    try {
      console.log(`[${i+1}/${batchFileList.value.length}] 开始上传:`, file.name)
      
      const formData = new FormData()
      formData.append('file', file.raw)
      // 批量上传时，标题使用文件名（不含扩展名）
      const fileName = file.name.replace(/\.[^/.]+$/, '')
      formData.append('title', fileName)

      const response = await fetch('/api/v1/tubi/upload', {
        method: 'POST',
        body: formData
      })

      const result = await response.json()
      console.log(`[${i+1}/${batchFileList.value.length}] 上传响应:`, result)

      if (result.success) {
        batchSuccessCount.value++
        batchCurrentStatus.value = '上传成功，开始AI分析...'
        console.log(`[${i+1}/${batchFileList.value.length}] 上传成功，ID:`, result.data.id)
        
        // 添加到已上传列表
        const newImage = {
          id: result.data.id,
          name: file.name,
          url: result.data.url,
          thumbnailUrl: result.data.thumbnail_url,
          width: result.data.width,
          height: result.data.height,
          title: fileName,
          artist: '',
          year: null,
          period: '',
          inscriptionPercent: undefined,
          paintingPercent: undefined,
          blankPercent: undefined,
          regions: null,
          annotatedImageUrl: null
        }
        uploadedImages.value.push(newImage)
        
        // 更新当前显示的图片（使用服务器URL）
        batchCurrentImage.value = newImage
        
        // 自动进行AI分析
        try {
          batchCurrentStatus.value = 'AI分析中...'
          // AI分析期间进度显示为 10%-45%
          const progressBase = Math.round((i / batchFileList.value.length) * 100)
          batchUploadProgress.value = progressBase + 10
          await nextTick()
          
          console.log(`[${i+1}/${batchFileList.value.length}] 开始AI分析，图片ID:`, result.data.id)
          
          // 使用 AbortController 设置超时（5分钟）
          const controller = new AbortController()
          const timeoutId = setTimeout(() => controller.abort(), 300000) // 5分钟超时
          
          const analyzeResponse = await fetch(`/api/v1/tubi/auto-analyze/${result.data.id}`, {
            method: 'POST',
            signal: controller.signal
          })
          
          clearTimeout(timeoutId)
          console.log(`[${i+1}/${batchFileList.value.length}] AI分析响应状态:`, analyzeResponse.status)
          
          if (!analyzeResponse.ok) {
            const errorText = await analyzeResponse.text()
            console.error(`[${i+1}/${batchFileList.value.length}] AI分析HTTP错误:`, errorText)
            throw new Error(`HTTP ${analyzeResponse.status}: ${errorText}`)
          }
          
          const analyzeResult = await analyzeResponse.json()
          console.log(`[${i+1}/${batchFileList.value.length}] AI分析结果:`, analyzeResult)
          
          if (analyzeResult.success) {
            // 更新图片信息
            newImage.inscriptionPercent = analyzeResult.data.inscription_percent
            newImage.paintingPercent = analyzeResult.data.painting_percent
            newImage.blankPercent = analyzeResult.data.blank_percent
            newImage.regions = analyzeResult.data.regions
            newImage.annotatedImageUrl = analyzeResult.data.annotated_image_url
            newImage.analysisNote = analyzeResult.data.analysis_note
            batchCurrentStatus.value = 'AI分析完成'
            // AI分析完成，进度设为 45%
            batchUploadProgress.value = progressBase + 45
            await nextTick()
            console.log(`[${i+1}/${batchFileList.value.length}] AI分析成功完成`)
          } else {
            const errorMsg = analyzeResult.detail || analyzeResult.error || '未知错误'
            console.error(`[${i+1}/${batchFileList.value.length}] AI分析失败:`, errorMsg)
            batchCurrentStatus.value = 'AI分析失败: ' + errorMsg
          }
        } catch (analyzeError) {
          if (analyzeError.name === 'AbortError') {
            console.error(`[${i+1}/${batchFileList.value.length}] AI分析超时`)
            batchCurrentStatus.value = 'AI分析超时，请稍后重试'
          } else {
            console.error(`[${i+1}/${batchFileList.value.length}] AI分析异常:`, analyzeError)
            batchCurrentStatus.value = 'AI分析失败: ' + analyzeError.message
          }
        }
        
        // 短暂延迟，让用户看到AI分析完成状态
        await new Promise(resolve => setTimeout(resolve, 800))
      } else {
        batchFailCount.value++
        batchCurrentStatus.value = '上传失败: ' + (result.detail || '未知错误')
      }
    } catch (error) {
      batchFailCount.value++
      batchCurrentStatus.value = '上传失败: ' + error.message
      console.error(`[${i+1}/${batchFileList.value.length}] 上传异常:`, error)
    }

    // 更新进度
    const finalProgress = Math.round(((i + 1) / batchFileList.value.length) * 100)
    batchUploadProgress.value = finalProgress
    await nextTick()
    console.log(`[${i+1}/${batchFileList.value.length}] 进度更新为: ${finalProgress}%`)
    
    // 短暂延迟，让用户看到进度
    await new Promise(resolve => setTimeout(resolve, 500))
    
    console.log(`[${i+1}/${batchFileList.value.length}] 处理完成，准备下一张...`)
  }

  // 上传完成
  batchUploadStatus.value = 'completed'
  batchCurrentStatus.value = ''
  
  // 刷新历史记录
  await loadHistory()
  
  if (batchSuccessCount.value > 0) {
    ElMessage.success(`批量上传分析完成，成功 ${batchSuccessCount.value} 张`)
  }
}

// 取消批量上传
function cancelBatchUpload() {
  batchUploadCancelled = true
  batchCurrentStatus.value = '正在取消...'
}

// 关闭批量上传对话框
function closeBatchUploadDialog() {
  batchUploadDialogVisible.value = false
  batchUploadStatus.value = 'selecting'
  batchFileList.value = []
}

// 处理批量上传对话框关闭
function handleBatchDialogClose(done) {
  if (batchUploadStatus.value === 'uploading') {
    ElMessageBox.confirm('上传正在进行中，确定要关闭吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      batchUploadCancelled = true
      done()
    }).catch(() => {})
  } else {
    done()
  }
}

// 选择图片
async function selectImage(img) {
  currentImage.value = img
  analyzeStatus.value = img.regions ? 'analyzed' : 'pending'

  if (img.regions) {
    areaStats.inscriptionPercent = img.inscriptionPercent || 0
    areaStats.paintingPercent = img.paintingPercent || 0
    areaStats.blankPercent = img.blankPercent || 0
    regions = img.regions
    analysisNote.value = img.analysisNote || ''
    // 设置位置分析（优先使用后端返回的数据，否则前端计算）
    if (img.positionAnalysis) {
      positionAnalysis.value = img.positionAnalysis
    } else if (img.regions && img.width && img.height) {
      positionAnalysis.value = calculatePositionAnalysisByRules(img.regions, img.width, img.height)
    }
  } else {
    areaStats.inscriptionPercent = 0
    areaStats.paintingPercent = 0
    areaStats.blankPercent = 0
    regions = { inscription_regions: [], painting_regions: [], blank_regions: [] }
    analysisNote.value = ''
    positionAnalysis.value = null
  }

  // 等待DOM更新
  await nextTick()
  initCanvas()
  
  if (analyzeStatus.value === 'analyzed') {
    drawRegions()
    // 延迟执行图表更新，确保DOM已渲染
    setTimeout(() => {
      updatePieChart()
      updateHeatmap()
    }, 300)
  }
}

// 清空所有
async function clearAll() {
  try {
    await ElMessageBox.confirm('确定要清空所有图片吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    for (const img of uploadedImages.value) {
      try {
        await fetch(`/api/v1/tubi/image/${img.id}`, { method: 'DELETE' })
      } catch (e) {
        console.error('删除图片失败:', e)
      }
    }

    uploadedImages.value = []
    currentImage.value = null
    analyzeStatus.value = 'pending'
    ElMessage.success('已清空')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清空失败')
    }
  }
}

// 初始化画布
function initCanvas() {
  if (!canvasRef.value || !currentImage.value) return
  
  // 检查图片 URL 是否有效
  const imageUrl = currentImage.value.url || currentImage.value.annotatedImageUrl
  if (!imageUrl) {
    console.warn('No valid image URL for canvas')
    return
  }

  canvas = canvasRef.value
  ctx = canvas.getContext('2d')

  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    const containerWidth = canvas.parentElement.clientWidth - 40
    const scale = containerWidth / img.width
    const displayWidth = containerWidth
    const displayHeight = img.height * scale

    canvas.width = displayWidth
    canvas.height = displayHeight
    canvas.style.width = displayWidth + 'px'
    canvas.style.height = displayHeight + 'px'

    ctx.drawImage(img, 0, 0, displayWidth, displayHeight)

    if (analyzeStatus.value === 'analyzed') {
      drawRegions()
    }
  }
  img.onerror = () => {
    console.error('Failed to load image:', imageUrl)
  }
  img.src = imageUrl
}

// 绘制区域标注
function drawRegions() {
  if (!ctx || !canvas || !currentImage.value) return

  // 检查图片 URL 是否有效
  const imageUrl = currentImage.value.url || currentImage.value.annotatedImageUrl
  if (!imageUrl) {
    console.warn('No valid image URL for drawRegions')
    return
  }

  const scaleX = canvas.width / currentImage.value.width
  const scaleY = canvas.height / currentImage.value.height

  // 清空画布并重新绘制图片
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    // 绘制区域
    const colors = {
      inscription: 'rgba(255, 68, 68, 0.3)',
      painting: 'rgba(68, 255, 68, 0.3)',
      blank: 'rgba(68, 68, 255, 0.3)'
    }

    const borderColors = {
      inscription: '#FF4444',
      painting: '#44FF44',
      blank: '#4444FF'
    }

    // 绘制多边形区域的辅助函数
    function drawPolygonRegion(reg, color, borderColor) {
      // 检查是否是多边形（有points字段）
      if (reg.points && Array.isArray(reg.points) && reg.points.length >= 3) {
        // 绘制多边形
        ctx.beginPath()
        reg.points.forEach((point, index) => {
          const x = point.x * scaleX
          const y = point.y * scaleY
          if (index === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }
        })
        ctx.closePath()
        
        // 填充
        ctx.fillStyle = color
        ctx.fill()
        
        // 描边
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2
        ctx.stroke()
      } else if (reg.x1 !== undefined && reg.y1 !== undefined && reg.x2 !== undefined && reg.y2 !== undefined) {
        // 绘制矩形（兼容旧数据）
        ctx.fillStyle = color
        ctx.fillRect(reg.x1 * scaleX, reg.y1 * scaleY, (reg.x2 - reg.x1) * scaleX, (reg.y2 - reg.y1) * scaleY)
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2
        ctx.strokeRect(reg.x1 * scaleX, reg.y1 * scaleY, (reg.x2 - reg.x1) * scaleX, (reg.y2 - reg.y1) * scaleY)
      }
    }

    // 绘制题跋区域
    regions.inscription_regions?.forEach(reg => {
      drawPolygonRegion(reg, colors.inscription, borderColors.inscription)
    })

    // 绘制绘画区域
    regions.painting_regions?.forEach(reg => {
      drawPolygonRegion(reg, colors.painting, borderColors.painting)
    })

    // 绘制留白区域
    regions.blank_regions?.forEach(reg => {
      drawPolygonRegion(reg, colors.blank, borderColors.blank)
    })
  }
  img.onerror = () => {
    console.error('Failed to load image in drawRegions:', imageUrl)
  }
  img.src = imageUrl
}

// AI自动分析
async function autoAnalyze() {
  if (!currentImage.value || analyzeStatus.value === 'analyzing') return

  analyzeStatus.value = 'analyzing'
  analyzeProgress.value = 0
  analyzingStep.value = '正在上传图片...'

  // 启动进度模拟
  const progressInterval = startAnalyzeProgress()

  try {
    const response = await fetch(`/api/v1/tubi/auto-analyze/${currentImage.value.id}`, {
      method: 'POST'
    })

    const result = await response.json()

    clearInterval(progressInterval)

    if (result.success) {
      const data = result.data

      currentImage.value.inscriptionPercent = data.area_stats.inscription_percent
      currentImage.value.paintingPercent = data.area_stats.painting_percent
      currentImage.value.blankPercent = data.area_stats.blank_percent
      currentImage.value.regions = data.regions
      currentImage.value.annotatedImageUrl = data.annotated_image_url

      areaStats.inscriptionPercent = data.area_stats.inscription_percent
      areaStats.paintingPercent = data.area_stats.painting_percent
      areaStats.blankPercent = data.area_stats.blank_percent

      regions = data.regions
      analysisNote.value = data.analysis_note

      // 使用基于规则的位置分析计算（无需AI）
      const calculatedPositionAnalysis = calculatePositionAnalysisByRules(
        data.regions,
        currentImage.value.width,
        currentImage.value.height
      )
      positionAnalysis.value = calculatedPositionAnalysis
      currentImage.value.positionAnalysis = calculatedPositionAnalysis

      drawRegions()

      const idx = uploadedImages.value.findIndex(img => img.id === currentImage.value.id)
      if (idx > -1) {
        uploadedImages.value[idx] = { ...currentImage.value }
      }

      analyzeProgress.value = 100
      analyzingStep.value = '分析完成！'
      analyzeStatus.value = 'analyzed'

      // 等待DOM更新后再初始化图表
      await nextTick()
      updatePieChart()
      updateHeatmap()
      
      // 刷新历史记录和趋势图
      await loadHistory()

      ElMessage.success('AI分析完成')
    } else {
      throw new Error(result.detail || '分析失败')
    }
  } catch (error) {
    clearInterval(progressInterval)
    analyzeStatus.value = 'pending'
    ElMessage.error(`分析失败: ${error.message}`)
  }
}

// 模拟题跋分析进度
function startAnalyzeProgress() {
  analyzeProgress.value = 0
  analyzingStep.value = '正在上传图片...'

  const steps = [
    { percent: 10, text: '正在读取图像...' },
    { percent: 25, text: 'AI正在识别题跋区域...' },
    { percent: 40, text: 'AI正在识别绘画区域...' },
    { percent: 55, text: 'AI正在识别留白区域...' },
    { percent: 70, text: '正在计算面积占比...' },
    { percent: 85, text: '正在生成热力图...' },
    { percent: 95, text: '正在生成面积占比智能示意图...' }
  ]

  let stepIndex = 0
  const interval = setInterval(() => {
    if (analyzeStatus.value !== 'analyzing') {
      clearInterval(interval)
      return
    }

    if (stepIndex < steps.length) {
      const step = steps[stepIndex]
      analyzeProgress.value = step.percent
      analyzingStep.value = step.text
      stepIndex++
    }
  }, 8000)

  return interval
}

// 更新饼图 - 现代卡片式设计
function updatePieChart() {
  if (!pieChartRef.value) {
    console.warn('pieChartRef is not ready')
    return
  }

  // 确保容器有尺寸
  const container = pieChartRef.value
  if (container.clientWidth === 0 || container.clientHeight === 0) {
    console.warn('Pie chart container has no size:', container.clientWidth, container.clientHeight)
    // 设置默认尺寸
    container.style.width = '200px'
    container.style.height = '200px'
  }

  if (!pieChart) {
    pieChart = echarts.init(pieChartRef.value)
  }

  // 检查数据是否有效
  const data = [
    areaStats.inscriptionPercent || 0,
    areaStats.paintingPercent || 0,
    areaStats.blankPercent || 0
  ]
  console.log('Pie chart data:', data)

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}%',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e4e7ed',
      borderWidth: 1,
      textStyle: { color: '#333' }
    },
    series: [{
      type: 'pie',
      radius: ['30%', '55%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 6,
        borderColor: '#fff',
        borderWidth: 2
      },
      label: {
        show: true,
        position: 'outside',
        formatter: '{b}\n{d}%',
        fontSize: 12,
        fontWeight: 'bold',
        color: '#333',
        lineHeight: 18
      },
      labelLine: {
        show: true,
        length: 15,
        length2: 10,
        smooth: true
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 13,
          fontWeight: 'bold'
        },
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.2)'
        }
      },
      data: [
        {
          value: areaStats.inscriptionPercent || 0,
          name: '题跋',
          itemStyle: {
            color: '#4A90E2' // 蓝色
          }
        },
        {
          value: areaStats.paintingPercent || 0,
          name: '绘画',
          itemStyle: {
            color: '#FF6B6B' // 红色
          }
        },
        {
          value: areaStats.blankPercent || 0,
          name: '留白',
          itemStyle: {
            color: '#F5A623' // 橙色
          }
        }
      ]
    }]
  }
  pieChart.setOption(option)
}

// 更新热力图
function updateHeatmap() {
  if (!heatmapContainerRef.value || !currentImage.value) return
  
  // 使用当前图片的 regions，如果没有则使用全局 regions
  const currentRegions = currentImage.value.regions || regions
  if (!currentRegions || !currentRegions.inscription_regions) {
    console.warn('No regions data available for heatmap')
    return
  }

  const width = currentImage.value.width
  const height = currentImage.value.height
  
  // 检查尺寸是否有效
  if (!width || !height || width <= 0 || height <= 0) {
    console.warn('Invalid image dimensions for heatmap:', width, height)
    return
  }

  // 计算热力图尺寸，保持原图比例
  const parentWidth = heatmapContainerRef.value.parentElement.clientWidth - 40
  const aspectRatio = height / width
  
  // 如果图片很宽，限制最大宽度；如果图片很高，限制最大高度
  let heatmapWidth = parentWidth
  let heatmapHeight = heatmapWidth * aspectRatio
  
  // 限制最大高度为 400px
  if (heatmapHeight > 400) {
    heatmapHeight = 400
    heatmapWidth = heatmapHeight / aspectRatio
  }
  
  // 设置容器尺寸
  heatmapContainerRef.value.style.width = heatmapWidth + 'px'
  heatmapContainerRef.value.style.height = heatmapHeight + 'px'
  heatmapContainerRef.value.style.margin = '0 auto'
  
  // 如果已有图表，先销毁再重新创建（避免尺寸问题）
  if (heatmapChart) {
    heatmapChart.dispose()
    heatmapChart = null
  }
  heatmapChart = echarts.init(heatmapContainerRef.value)
  
  // 根据图片尺寸自适应网格大小，确保网格数不超过100
  const maxGrid = 100
  let gridSize = 20
  
  // 计算需要的网格大小
  const requiredGridX = Math.ceil(width / maxGrid)
  const requiredGridY = Math.ceil(height / maxGrid)
  gridSize = Math.max(gridSize, requiredGridX, requiredGridY)
  
  const cols = Math.ceil(width / gridSize)
  const rows = Math.ceil(height / gridSize)

  // 点是否在多边形内（射线法）
  function pointInPolygon(point, polygon) {
    let inside = false
    let j = polygon.length - 1
    for (let i = 0; i < polygon.length; i++) {
      const xi = polygon[i].x, yi = polygon[i].y
      const xj = polygon[j].x, yj = polygon[j].y
      if (((yi > point.y) !== (yj > point.y)) &&
          (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi)) {
        inside = !inside
      }
      j = i
    }
    return inside
  }

  const heatmapData = []
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      const x1 = j * gridSize
      const y1 = i * gridSize
      const x2 = Math.min(x1 + gridSize, width)
      const y2 = Math.min(y1 + gridSize, height)

      // 计算网格中心点
      const centerX = (x1 + x2) / 2
      const centerY = (y1 + y2) / 2
      const centerPoint = { x: centerX, y: centerY }

      let coverage = 0
      currentRegions.inscription_regions?.forEach(reg => {
        // 支持多边形格式
        if (reg.points && reg.points.length >= 3) {
          if (pointInPolygon(centerPoint, reg.points)) {
            coverage = 1.0
          }
        } else if (reg.x1 !== undefined && reg.y1 !== undefined && reg.x2 !== undefined && reg.y2 !== undefined) {
          // 兼容矩形格式
          const ox1 = Math.max(x1, reg.x1)
          const oy1 = Math.max(y1, reg.y1)
          const ox2 = Math.min(x2, reg.x2)
          const oy2 = Math.min(y2, reg.y2)
          if (ox2 > ox1 && oy2 > oy1) {
            coverage = Math.max(coverage, ((ox2 - ox1) * (oy2 - oy1)) / ((x2 - x1) * (y2 - y1)))
          }
        }
      })

      if (coverage > 0) {
        heatmapData.push([j, rows - 1 - i, coverage])
      }
    }
  }

  const option = {
    tooltip: {
      position: 'top',
      formatter: (p) => `文字密度: ${(p.value[2] * 100).toFixed(1)}%`,
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e4e7ed',
      borderWidth: 1
    },
    backgroundColor: '#f5f0e6', // 米白色背景
    grid: { top: 10, left: 10, right: 10, bottom: 40 },
    xAxis: { type: 'category', data: Array(cols).fill(''), show: false },
    yAxis: { type: 'category', data: Array(rows).fill(''), show: false },
    visualMap: {
      min: 0,
      max: 1,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: '2%',
      itemWidth: 20,
      itemHeight: 12,
      textStyle: {
        color: '#666'
      },
      inRange: {
        // 鲜艳配色：蓝色 -> 绿色 -> 黄色 -> 橙色 -> 红色 -> 紫色
        color: ['#3498db', '#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#9b59b6']
      }
    },
    series: [{
      type: 'heatmap',
      data: heatmapData,
      itemStyle: {
        borderWidth: 0,
        borderRadius: 2
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 15,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  }

  heatmapChart.setOption(option, true)
}

// 监听窗口大小变化
function handleResize() {
  pieChart?.resize()
  heatmapChart?.resize()
  trendChart?.resize()
  if (currentImage.value) {
    initCanvas()
    if (analyzeStatus.value === 'analyzed') {
      drawRegions()
    }
  }
}

// 更新趋势图
function updateTrendChart() {
  // 筛选有年代信息的历史记录
  const validData = historyList.value.filter(item => {
    const hasYear = item.year && !isNaN(parseInt(item.year))
    const hasPercent = item.inscriptionPercent !== undefined && item.inscriptionPercent !== null
    return hasYear && hasPercent
  }).sort((a, b) => parseInt(a.year) - parseInt(b.year))

  // 先设置数据，让 v-if 渲染卡片
  trendChartData.value = validData

  // 获取筛选后的数据
  const filteredData = filteredTrendChartData.value

  if (filteredData.length === 0) {
    return
  }

  // 计算统计数据（基于筛选后的数据）
  const percents = filteredData.map(item => item.inscriptionPercent)
  trendStats.avgPercent = (percents.reduce((a, b) => a + b, 0) / percents.length).toFixed(1)
  trendStats.maxPercent = Math.max(...percents).toFixed(1)
  trendStats.minPercent = Math.min(...percents).toFixed(1)

  // 等待 DOM 更新后再初始化图表
  nextTick(() => {
    if (!trendChartRef.value) return

    if (!trendChart) {
      trendChart = echarts.init(trendChartRef.value)
      
      // 添加点击事件 - 点击跳转到对应画作
      trendChart.on('click', function(params) {
        const dataIndex = params.dataIndex
        const item = validData[dataIndex]
        if (item && item.id) {
          // 查找对应的图片数据
          const targetImage = uploadedImages.value.find(img => img.id === item.id)
          if (targetImage) {
            selectImage(targetImage)
            ElMessage.success(`已切换到: ${item.title || '未命名'}`)
          } else {
            // 如果不在 uploadedImages 中，需要加载该图片
            loadAndSelectImage(item.id)
          }
        }
      })
    }

  // 准备数据（使用筛选后的数据）
  const xData = filteredData.map(item => {
    // 如果有年龄信息，显示为 "年龄 (年代)" 格式
    if (item.period) {
      return `${item.period}\n(${item.year})`
    }
    return item.year.toString()
  })
  const yData = filteredData.map(item => item.inscriptionPercent)

  const option = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.98)',
      borderColor: '#9B7ED8',
      borderWidth: 1,
      textStyle: { color: '#333' },
      formatter: function(params) {
        const dataIndex = params[0].dataIndex
        const item = filteredData[dataIndex]
        const thumb = item.url ? `<img src="${item.url}" style="width:80px;height:80px;object-fit:cover;border-radius:8px;margin-bottom:8px;" />` : ''
        return `
          <div style="padding:8px;cursor:pointer;">
            ${thumb}
            <div style="font-weight:600;margin-bottom:4px;color:#6B5B95;">${item.title || '未命名'}</div>
            <div style="color:#8B7CB3;font-size:12px;margin-bottom:4px;">${item.artist || '未知作者'} · ${item.year}年</div>
            <div style="color:#9B7ED8;font-weight:600;margin-bottom:4px;">题跋占比: ${item.inscriptionPercent}%</div>
            <div style="color:#9B7ED8;font-size:11px;border-top:1px solid #E8E3F0;padding-top:4px;margin-top:4px;">点击查看详情</div>
          </div>
        `
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xData,
      boundaryGap: false,
      axisLine: { show: false },
      axisLabel: {
        color: '#8B7CB3',
        fontSize: 11,
        interval: 0,
        rotate: xData.length > 8 ? 45 : 0
      },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '题跋占比 (%)',
      nameTextStyle: {
        color: '#8B7CB3',
        fontSize: 12
      },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#8B7CB3',
        fontSize: 11,
        formatter: '{value}%'
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(139, 124, 179, 0.15)',
          type: 'dashed'
        }
      }
    },
    series: [{
      name: '题跋占比',
      type: 'line',
      data: yData,
      smooth: 0.4,
      symbol: 'circle',
      symbolSize: 10,
      lineStyle: {
        width: 3,
        color: '#9B7ED8',
        shadowColor: 'rgba(155, 126, 216, 0.5)',
        shadowBlur: 10,
        shadowOffsetY: 5
      },
      itemStyle: {
        color: '#fff',
        borderColor: '#9B7ED8',
        borderWidth: 3,
        shadowBlur: 8,
        shadowColor: 'rgba(155, 126, 216, 0.6)'
      },
      emphasis: {
        scale: 1.5,
        itemStyle: {
          color: '#9B7ED8',
          borderColor: '#fff',
          borderWidth: 3,
          shadowBlur: 15,
          shadowColor: 'rgba(155, 126, 216, 0.8)'
        }
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(155, 126, 216, 0.6)' },
            { offset: 0.3, color: 'rgba(155, 126, 216, 0.4)' },
            { offset: 0.6, color: 'rgba(155, 126, 216, 0.2)' },
            { offset: 1, color: 'rgba(155, 126, 216, 0.05)' }
          ]
        }
      }
    }]
  }

    trendChart.setOption(option)
  })
}

// 显示历史记录对话框
async function showHistoryDialog() {
  historyDialogVisible.value = true
  await loadHistory()
}

// 加载历史记录
async function loadHistory() {
  historyLoading.value = true
  try {
    const response = await tubiApi.getAllResults()
    console.log('历史记录API响应:', response)
    if (response.success) {
      // 转换字段名（下划线转驼峰）
      historyList.value = (response.data || []).map(item => ({
        ...item,
        inscriptionPercent: item.inscription_percent,
        paintingPercent: item.painting_percent,
        blankPercent: item.blank_percent,
        annotatedImageUrl: item.annotated_image_url,
        thumbnailUrl: item.thumbnail_url,
        analysisNote: item.analysis_note
      }))
      console.log('历史记录加载成功:', historyList.value.length, '条')
      // 加载完成后更新趋势图
      await nextTick()
      updateTrendChart()
    } else {
      console.error('历史记录API返回失败:', response)
      ElMessage.error(response.message || '加载历史记录失败')
    }
  } catch (error) {
    console.error('加载历史记录失败:', error)
    ElMessage.error('加载历史记录失败: ' + (error.message || '网络错误'))
  } finally {
    historyLoading.value = false
  }
}

// 预览历史图片
function previewHistoryImage(row) {
  previewImageUrl.value = row.url
  previewDialogVisible.value = true
}

// 加载历史记录项
async function loadHistoryItem(row) {
  try {
    const response = await tubiApi.getAnalysisResult(row.id)
    if (response.success) {
      const data = response.data

      // 创建图片对象
      const historyImage = {
        id: data.id,
        name: data.name || '历史记录',
        url: data.url,
        thumbnailUrl: data.thumbnail_url || data.url,
        width: data.width,
        height: data.height,
        title: data.title,
        artist: data.artist,
        year: data.year,
        period: data.period,
        inscriptionPercent: data.inscription_percent,
        paintingPercent: data.painting_percent,
        blankPercent: data.blank_percent,
        regions: data.regions,
        positionAnalysis: data.position_analysis,
        annotatedImageUrl: data.annotated_image_url,
        analysisNote: data.analysis_note
      }

      // 添加到当前会话
      const exists = uploadedImages.value.find(img => img.id === historyImage.id)
      if (!exists) {
        uploadedImages.value.push(historyImage)
      }

      // 选中该图片
      selectImage(historyImage)
      historyDialogVisible.value = false
      
      // 滚动到页面顶部
      window.scrollTo({ top: 0, behavior: 'smooth' })
      
      ElMessage.success('已加载历史记录')
    } else {
      ElMessage.error(response.message || '加载失败')
    }
  } catch (error) {
    console.error('加载历史记录项失败:', error)
    ElMessage.error('加载失败')
  }
}

// 加载并选择指定ID的图片（用于趋势图点击）
async function loadAndSelectImage(imageId) {
  try {
    const response = await tubiApi.getAnalysisResult(imageId)
    if (response.success) {
      const data = response.data

      // 创建图片对象
      const image = {
        id: data.id,
        name: data.name || '画作',
        url: data.url,
        thumbnailUrl: data.thumbnail_url || data.url,
        width: data.width,
        height: data.height,
        title: data.title,
        artist: data.artist,
        year: data.year,
        period: data.period,
        inscriptionPercent: data.inscription_percent,
        paintingPercent: data.painting_percent,
        blankPercent: data.blank_percent,
        regions: data.regions,
        annotatedImageUrl: data.annotated_image_url,
        analysisNote: data.analysis_note
      }

      // 添加到当前会话
      const exists = uploadedImages.value.find(img => img.id === image.id)
      if (!exists) {
        uploadedImages.value.push(image)
      }

      // 选中该图片
      selectImage(image)
      ElMessage.success(`已切换到: ${image.title || '未命名'}`)
    } else {
      ElMessage.error(response.message || '加载画作失败')
    }
  } catch (error) {
    console.error('加载画作失败:', error)
    ElMessage.error('加载画作失败')
  }
}

// 删除历史记录项
async function deleteHistoryItem(row) {
  try {
    await ElMessageBox.confirm('确定要删除这条历史记录吗？', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const response = await tubiApi.deleteImage(row.id)
    if (response.success) {
      ElMessage.success('删除成功')
      // 从列表中移除
      const idx = historyList.value.findIndex(item => item.id === row.id)
      if (idx > -1) {
        historyList.value.splice(idx, 1)
      }
      // 从当前会话中移除
      const sessionIdx = uploadedImages.value.findIndex(img => img.id === row.id)
      if (sessionIdx > -1) {
        uploadedImages.value.splice(sessionIdx, 1)
        if (currentImage.value?.id === row.id) {
          currentImage.value = uploadedImages.value[0] || null
          if (currentImage.value) {
            selectImage(currentImage.value)
          } else {
            analyzeStatus.value = 'pending'
          }
        }
      }
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 编辑历史记录
function editHistoryItem(row) {
  editForm.id = row.id
  editForm.title = row.title || ''
  editForm.artist = row.artist || ''
  editForm.year = row.year || ''
  editForm.age = row.age || row.period || ''
  editForm.notes = row.notes || ''
  editForm.analysisNote = row.analysisNote || row.analysis_note || ''
  editForm.inscriptionPercent = row.inscriptionPercent || row.inscription_percent || 0
  editForm.paintingPercent = row.paintingPercent || row.painting_percent || 0
  editForm.blankPercent = row.blankPercent || row.blank_percent || 0
  editDialogVisible.value = true
}

// 保存编辑
async function saveEdit() {
  try {
    const response = await tubiApi.updateImageInfo(editForm.id, {
      title: editForm.title,
      artist: editForm.artist,
      year: editForm.year ? parseInt(editForm.year) : null,
      age: editForm.age ? parseInt(editForm.age) : null,
      notes: editForm.notes,
      analysis_note: editForm.analysisNote,
      inscription_percent: parseFloat(editForm.inscriptionPercent) || 0,
      painting_percent: parseFloat(editForm.paintingPercent) || 0,
      blank_percent: parseFloat(editForm.blankPercent) || 0
    })

    if (response.success) {
      ElMessage.success('保存成功')
      editDialogVisible.value = false
      // 刷新历史记录列表
      await loadHistory()
      // 如果当前正在查看这张图片，也更新当前图片的信息
      if (currentImage.value?.id === editForm.id) {
        currentImage.value.title = editForm.title
        currentImage.value.artist = editForm.artist
        currentImage.value.year = editForm.year
        currentImage.value.age = editForm.age
        currentImage.value.analysisNote = editForm.analysisNote
        currentImage.value.inscriptionPercent = parseFloat(editForm.inscriptionPercent) || 0
        currentImage.value.paintingPercent = parseFloat(editForm.paintingPercent) || 0
        currentImage.value.blankPercent = parseFloat(editForm.blankPercent) || 0
        analysisNote.value = editForm.analysisNote
        // 更新区域统计
        areaStats.inscriptionPercent = parseFloat(editForm.inscriptionPercent) || 0
        areaStats.paintingPercent = parseFloat(editForm.paintingPercent) || 0
        areaStats.blankPercent = parseFloat(editForm.blankPercent) || 0
        // 更新饼图
        updatePieChart()
      }
    } else {
      ElMessage.error(response.message || '保存失败')
    }
  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error('保存失败')
  }
}

// 编辑图片信息（作品库用）
function editImageInfo(item) {
  editForm.id = item.id
  editForm.title = item.title || ''
  editForm.artist = item.artist || ''
  editForm.year = item.year || ''
  editForm.age = item.age || item.period || ''
  editForm.notes = item.notes || ''
  editForm.analysisNote = item.analysisNote || item.analysis_note || ''
  editForm.inscriptionPercent = item.inscriptionPercent || item.inscription_percent || 0
  editForm.paintingPercent = item.paintingPercent || item.painting_percent || 0
  editForm.blankPercent = item.blankPercent || item.blank_percent || 0
  editDialogVisible.value = true
}

// 删除图片（作品库用）
async function deleteImage(item) {
  try {
    await ElMessageBox.confirm(`确定要删除「${item.title || '未命名'}」吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const response = await tubiApi.deleteImage(item.id)
    if (response.success) {
      ElMessage.success('删除成功')
      // 从列表中移除
      const idx = historyList.value.findIndex(h => h.id === item.id)
      if (idx > -1) {
        historyList.value.splice(idx, 1)
      }
      // 从当前会话中移除
      const sessionIdx = uploadedImages.value.findIndex(img => img.id === item.id)
      if (sessionIdx > -1) {
        uploadedImages.value.splice(sessionIdx, 1)
      }
      // 如果删除的是当前选中的图片，清空当前选择
      if (currentImage.value?.id === item.id) {
        currentImage.value = null
        analyzeStatus.value = 'pending'
      }
    } else {
      ElMessage.error(response.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 基于规则计算题跋位置分析（无需AI）
function calculatePositionAnalysisByRules(regions, imageWidth, imageHeight) {
  if (!regions || !regions.inscription_regions || regions.inscription_regions.length === 0) {
    return null
  }

  const inscriptionRegs = regions.inscription_regions
  const paintingRegs = regions.painting_regions || []

  // 计算题跋区域的边界框
  let minX = imageWidth, minY = imageHeight, maxX = 0, maxY = 0
  let totalInscriptionArea = 0

  inscriptionRegs.forEach(reg => {
    let x1, y1, x2, y2
    if (reg.points && reg.points.length >= 3) {
      // 多边形，计算边界框
      const xs = reg.points.map(p => p.x)
      const ys = reg.points.map(p => p.y)
      x1 = Math.min(...xs)
      y1 = Math.min(...ys)
      x2 = Math.max(...xs)
      y2 = Math.max(...ys)
    } else if (reg.x1 !== undefined) {
      // 矩形
      x1 = reg.x1
      y1 = reg.y1
      x2 = reg.x2
      y2 = reg.y2
    } else {
      return
    }

    minX = Math.min(minX, x1)
    minY = Math.min(minY, y1)
    maxX = Math.max(maxX, x2)
    maxY = Math.max(maxY, y2)
    totalInscriptionArea += (x2 - x1) * (y2 - y1)
  })

  const inscriptionWidth = maxX - minX
  const inscriptionHeight = maxY - minY
  const inscriptionCenterX = (minX + maxX) / 2
  const inscriptionCenterY = (minY + maxY) / 2

  // 计算与画面边缘的距离
  const marginLeft = minX
  const marginRight = imageWidth - maxX
  const marginTop = minY
  const marginBottom = imageHeight - maxY

  // 计算与绘画区域的重叠
  let overlapWithPainting = 0
  paintingRegs.forEach(paintReg => {
    let px1, py1, px2, py2
    if (paintReg.points && paintReg.points.length >= 3) {
      const xs = paintReg.points.map(p => p.x)
      const ys = paintReg.points.map(p => p.y)
      px1 = Math.min(...xs)
      py1 = Math.min(...ys)
      px2 = Math.max(...xs)
      py2 = Math.max(...ys)
    } else if (paintReg.x1 !== undefined) {
      px1 = paintReg.x1
      py1 = paintReg.y1
      px2 = paintReg.x2
      py2 = paintReg.y2
    } else {
      return
    }

    // 计算重叠面积
    const ox1 = Math.max(minX, px1)
    const oy1 = Math.max(minY, py1)
    const ox2 = Math.min(maxX, px2)
    const oy2 = Math.min(maxY, py2)

    if (ox2 > ox1 && oy2 > oy1) {
      overlapWithPainting += (ox2 - ox1) * (oy2 - oy1)
    }
  })

  const overlapRatio = totalInscriptionArea > 0 ? overlapWithPainting / totalInscriptionArea : 0

  // 判断位置类型
  let layoutType = ''
  let layoutDescription = ''
  let position = ''

  // 计算覆盖率
  const coverageRatio = totalInscriptionArea / (imageWidth * imageHeight)

  // 判断位置（基于中心点）
  const isLeft = inscriptionCenterX < imageWidth * 0.33
  const isRight = inscriptionCenterX > imageWidth * 0.67
  const isTop = inscriptionCenterY < imageHeight * 0.33
  const isBottom = inscriptionCenterY > imageHeight * 0.67
  const isCenterX = !isLeft && !isRight
  const isCenterY = !isTop && !isBottom

  if (isLeft && isTop) position = '左上'
  else if (isRight && isTop) position = '右上'
  else if (isLeft && isBottom) position = '左下'
  else if (isRight && isBottom) position = '右下'
  else if (isLeft && isCenterY) position = '左侧'
  else if (isRight && isCenterY) position = '右侧'
  else if (isCenterX && isTop) position = '顶部'
  else if (isCenterX && isBottom) position = '底部'
  else position = '中部'

  // 判断布局类型
  if (coverageRatio > 0.3) {
    layoutType = '满布式'
    layoutDescription = '题跋遍布画面大部分区域，与绘画内容紧密融合，形成图文交织的视觉效果。'
  } else if (overlapRatio > 0.5) {
    layoutType = '穿插式'
    layoutDescription = '题跋与绘画区域相互穿插，文字与图像形成有机的整体，增强了画面的层次感。'
  } else if (marginLeft < 20 || marginRight < 20 || marginTop < 20 || marginBottom < 20) {
    if ((marginLeft < 20 && marginTop < 20) ||
        (marginLeft < 20 && marginBottom < 20) ||
        (marginRight < 20 && marginTop < 20) ||
        (marginRight < 20 && marginBottom < 20)) {
      layoutType = '拦边封角式'
      layoutDescription = '题跋沿画面边缘布置，并在角落处汇聚，形成框景效果，突出中心绘画内容。'
    } else {
      layoutType = '边角式'
      layoutDescription = '题跋位于画面边角位置，既不影响主体绘画的展示，又能提供必要的文字说明。'
    }
  } else {
    layoutType = '独立式'
    layoutDescription = '题跋独立于绘画区域之外，与图像形成清晰的分离，便于分别欣赏文字和图像。'
  }

  return {
    layout_type: layoutType,
    position: position,
    layout_description: layoutDescription,
    coverage_ratio: coverageRatio,
    margin_left: marginLeft,
    margin_right: marginRight,
    margin_top: marginTop,
    margin_bottom: marginBottom,
    overlap_ratio: overlapRatio
  }
}

// 格式化日期
function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

// 获取位置标签样式类
function getPositionLabelClass() {
  if (!positionAnalysis.value) return ''
  const layoutType = positionAnalysis.value.layout_type
  if (layoutType === '边角式') return 'label-corner'
  if (layoutType === '拦边封角式') return 'label-frame'
  if (layoutType === '穿插式') return 'label-interleaved'
  if (layoutType === '满布式') return 'label-full'
  if (layoutType === '独立式') return 'label-independent'
  return ''
}

// 获取题跋区域示意图样式类
function getInscriptionAreaClass() {
  if (!positionAnalysis.value) return ''
  const layoutType = positionAnalysis.value.layout_type
  if (layoutType === '边角式') return 'area-corner'
  if (layoutType === '拦边封角式') return 'area-frame'
  if (layoutType === '穿插式') return 'area-interleaved'
  if (layoutType === '满布式') return 'area-full'
  if (layoutType === '独立式') return 'area-independent'
  return ''
}

// 获取题跋区域示意图样式
function getInscriptionAreaStyle() {
  if (!positionAnalysis.value) return {}
  const pos = positionAnalysis.value.position
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  const width = currentImage.value?.width || 1000
  const height = currentImage.value?.height || 1000

  // 计算百分比位置
  const leftPct = (ml / width) * 100
  const rightPct = (mr / width) * 100
  const topPct = (mt / height) * 100
  const bottomPct = (mb / height) * 100

  // 根据位置类型调整显示
  if (pos === '左上') {
    return { left: '5%', top: '5%', width: '30%', height: '25%' }
  } else if (pos === '右上') {
    return { right: '5%', top: '5%', width: '30%', height: '25%' }
  } else if (pos === '左下') {
    return { left: '5%', bottom: '5%', width: '30%', height: '25%' }
  } else if (pos === '右下') {
    return { right: '5%', bottom: '5%', width: '30%', height: '25%' }
  } else if (pos === '左侧') {
    return { left: '5%', top: '20%', width: '25%', height: '60%' }
  } else if (pos === '右侧') {
    return { right: '5%', top: '20%', width: '25%', height: '60%' }
  } else if (pos === '上方') {
    return { left: '20%', top: '5%', width: '60%', height: '20%' }
  } else if (pos === '底部') {
    return { left: '20%', bottom: '5%', width: '60%', height: '20%' }
  } else {
    // 中部或其他
    return { left: '30%', top: '30%', width: '40%', height: '40%' }
  }
}

// 获取边缘距离文本（完整版）
function getEdgeDistanceText() {
  if (!positionAnalysis.value) return ''
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  return `左${Math.round(ml)} 右${Math.round(mr)} 上${Math.round(mt)} 下${Math.round(mb)}`
}

// 获取边缘距离文本（简化版）
function getEdgeDistanceShortText() {
  if (!positionAnalysis.value) return ''
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  // 找出最小的边距
  const margins = [
    { name: '左', val: ml },
    { name: '右', val: mr },
    { name: '上', val: mt },
    { name: '下', val: mb }
  ]
  const minMargin = margins.reduce((min, cur) => cur.val < min.val ? cur : min)
  return `${minMargin.name}${Math.round(minMargin.val)}`
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  // 页面加载时自动加载历史记录
  loadHistory()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  pieChart?.dispose()
  heatmapChart?.dispose()
  trendChart?.dispose()
})
</script>

<style scoped>
/* 页面整体样式 */
.tubi-analysis {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-title {
  text-align: center;
  font-size: 28px;
  margin-bottom: 8px;
  color: #333;
  font-weight: 600;
}

.page-subtitle {
  text-align: center;
  font-size: 14px;
  color: #666;
  margin-bottom: 24px;
}

/* 趋势图卡片 */
.trend-card {
  margin-bottom: 20px;
}

.trend-stats {
  display: flex;
  gap: 8px;
}

.trend-chart {
  width: 100%;
  height: 320px;
}

/* 响应式布局容器 */
.analysis-container {
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 20px;
}

/* 左侧面板 */
.left-panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 历史记录卡片 */
.history-card {
  margin-bottom: 0;
}

.history-summary {
  padding: 16px;
  text-align: center;
  color: #666;
  font-size: 14px;
}

.history-summary.empty {
  color: #999;
}

.history-summary p {
  margin: 0;
}

/* 历史记录列表样式 */
.history-list {
  padding: 8px 0;
}

.history-item {
  display: flex;
  align-items: center;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 12px;
  background: #f8f9fa;
  cursor: pointer;
  transition: all 0.3s ease;
}

.history-item:hover {
  background: #e8f4ff;
  transform: translateX(4px);
}

.history-item:last-child {
  margin-bottom: 0;
}

.history-item-thumb {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 8px;
  margin-right: 12px;
  border: 1px solid #e4e7ed;
}

.history-item-thumb-placeholder {
  width: 60px;
  height: 60px;
  border-radius: 8px;
  margin-right: 12px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  border: 1px dashed #dcdfe6;
}

.history-item-info {
  flex: 1;
  min-width: 0;
}

.history-item-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item-meta {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.history-item-meta span {
  margin-right: 8px;
}

.history-item-stats {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.history-more {
  text-align: center;
  padding: 12px;
  margin-top: 8px;
  border-top: 1px dashed #dcdfe6;
}

/* 历史记录对话框 */
.history-dialog-wide {
  max-width: 1400px;
}

.history-dialog-wide :deep(.el-dialog__body) {
  padding: 20px;
}

.history-dialog-content {
  max-height: 600px;
  overflow-y: auto;
}

.history-thumb {
  width: 80px;
  height: 80px;
  object-fit: cover;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid #e4e7ed;
  transition: all 0.3s ease;
}

.history-thumb:hover {
  border-color: #409EFF;
  transform: scale(1.05);
}

.history-thumb-placeholder {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  border: 1px dashed #dcdfe6;
}

/* 操作按钮容器 */
.action-buttons {
  display: flex;
  gap: 8px;
  white-space: nowrap;
}

.action-buttons .el-button {
  padding: 6px 16px;
  font-size: 12px;
}

/* 圆角胶囊按钮样式 */
:deep(.el-button) {
  border-radius: 50px;
  padding: 12px 32px;
  font-size: 14px;
  font-weight: 600;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #ffa726 0%, #ff9800 100%);
  color: white;
}

:deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #ffb74d 0%, #ffa726 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(255, 167, 38, 0.4);
}

:deep(.el-button--success) {
  background: linear-gradient(135deg, #cddc39 0%, #8bc34a 100%);
  color: #333;
}

:deep(.el-button--success:hover) {
  background: linear-gradient(135deg, #d4e157 0%, #9ccc65 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(139, 195, 74, 0.4);
}

:deep(.el-button--warning) {
  background: linear-gradient(135deg, #cddc39 0%, #8bc34a 100%);
  color: #333;
}

:deep(.el-button--warning:hover) {
  background: linear-gradient(135deg, #d4e157 0%, #9ccc65 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(139, 195, 74, 0.4);
}

:deep(.el-button--danger) {
  background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
  color: white;
}

:deep(.el-button--danger:hover) {
  background: linear-gradient(135deg, #e57373 0%, #ef5350 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(239, 83, 80, 0.4);
}

:deep(.el-button--default) {
  background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
  color: #666;
}

:deep(.el-button--default:hover) {
  background: linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
}

:deep(.el-button.is-small) {
  padding: 8px 20px;
  font-size: 13px;
}

/* 卡片通用样式 */
:deep(.el-card) {
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
  border: none;
}

:deep(.el-card__header) {
  border-bottom: 1px solid #f0f0f0;
  padding: 16px 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 16px;
}

/* 上传区域样式 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #999;
  gap: 16px;
}

.empty-state p {
  font-size: 14px;
}

/* 图片显示区域 */
.image-display {
  padding: 10px;
}

.image-info-header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.image-info-header .header-left {
  flex: 1;
}

.image-info-header h3 {
  font-size: 18px;
  color: #333;
  margin-bottom: 4px;
}

.image-info-header p {
  font-size: 13px;
  color: #666;
  margin: 2px 0;
}

.canvas-wrapper {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
  background: #f8f9fa;
  border-radius: 12px;
  padding: 16px;
}

.annotation-canvas {
  max-width: 100%;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.image-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

/* AI分析进度样式 - 发光效果 */
.analyzing-progress {
  margin: 20px 0;
  padding: 30px 24px;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 16px;
  text-align: center;
  color: white;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

/* 发光进度条容器 */
.glow-progress-container {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

/* 发光进度条背景 */
.glow-progress-bar {
  flex: 1;
  height: 24px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
  position: relative;
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.3);
}

/* 发光进度条填充 */
.glow-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #00d4ff 0%, #00a8ff 50%, #00d4ff 100%);
  border-radius: 12px;
  box-shadow:
    0 0 10px rgba(0, 212, 255, 0.5),
    0 0 20px rgba(0, 212, 255, 0.3),
    0 0 30px rgba(0, 212, 255, 0.2);
  transition: width 0.3s ease;
  position: relative;
}

/* 进度条光泽效果 */
.glow-progress-fill::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 50%;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.3) 0%, transparent 100%);
  border-radius: 12px 12px 0 0;
}

/* 进度百分比文字 */
.glow-progress-text {
  font-size: 16px;
  font-weight: 700;
  color: #00d4ff;
  text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
  min-width: 45px;
  text-align: right;
}

.analyzing-text {
  margin-top: 16px;
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.analyzing-subtext {
  margin-top: 8px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

/* 现代表单样式 */
.modern-form-dialog :deep(.el-dialog__header) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px 24px;
  margin: 0;
}

.modern-form-dialog :deep(.el-dialog__title) {
  color: white;
  font-size: 18px;
  font-weight: 600;
}

.modern-form-dialog :deep(.el-dialog__headerbtn .el-dialog__close) {
  color: white;
}

.modern-form-dialog :deep(.el-dialog__body) {
  padding: 0;
  background: #f8f9fa;
}

.form-section {
  background: white;
  margin: 16px;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.form-section-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0 0 20px 0;
  padding-bottom: 12px;
  border-bottom: 2px solid #e8e8e8;
  position: relative;
}

.form-section-title::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  width: 60px;
  height: 2px;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
}

.modern-form :deep(.el-form-item__label) {
  font-size: 14px;
  font-weight: 500;
  color: #555;
  padding-bottom: 8px;
  line-height: 1.4;
}

.modern-form :deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  border: 1px solid #e0e0e0;
  transition: all 0.3s ease;
}

.modern-form :deep(.el-input__wrapper:hover) {
  border-color: #667eea;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.1);
}

.modern-form :deep(.el-input__wrapper.is-focus) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.modern-form :deep(.el-textarea__inner) {
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  padding: 12px;
  font-size: 14px;
  resize: none;
  transition: all 0.3s ease;
}

.modern-form :deep(.el-textarea__inner:hover) {
  border-color: #667eea;
}

.modern-form :deep(.el-textarea__inner:focus) {
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-row {
  display: flex;
  gap: 20px;
}

.form-item-half {
  flex: 1;
  margin-bottom: 16px;
}

.form-item-half :deep(.el-form-item__content) {
  width: 100%;
}

.form-item-third {
  flex: 1;
  margin-bottom: 16px;
}

.form-item-third :deep(.el-form-item__content) {
  width: 100%;
}

/* 现代上传区域 */
.modern-upload :deep(.el-upload-dragger) {
  width: 100%;
  height: 160px;
  border: 2px dashed #d0d0d0;
  border-radius: 12px;
  background: #fafafa;
  transition: all 0.3s ease;
}

.modern-upload :deep(.el-upload-dragger:hover) {
  border-color: #667eea;
  background: #f5f3ff;
}

.modern-upload :deep(.el-upload__text) {
  font-size: 14px;
  color: #666;
  margin-top: 12px;
}

.modern-upload :deep(.el-upload__text em) {
  color: #667eea;
  font-weight: 600;
}

.modern-upload :deep(.el-upload__tip) {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}

/* 表单底部按钮 */
.modern-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  background: white;
  border-top: 1px solid #e8e8e8;
  margin: 0;
}

.btn-cancel {
  padding: 10px 24px;
  border-radius: 8px;
  border: 1px solid #d0d0d0;
  background: white;
  color: #666;
  font-weight: 500;
}

.btn-cancel:hover {
  border-color: #667eea;
  color: #667eea;
  background: #f5f3ff;
}

.btn-submit {
  padding: 10px 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.btn-submit:hover {
  background: linear-gradient(135deg, #7b8ce8 0%, #8a5cb8 100%);
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}

/* 头部按钮组 */
.header-buttons {
  display: flex;
  gap: 10px;
}

/* 批量上传样式 */
.batch-upload-area :deep(.el-upload-dragger) {
  width: 100%;
  height: 180px;
  border: 2px dashed #d0d0d0;
  border-radius: 12px;
  background: #fafafa;
  transition: all 0.3s ease;
}

.batch-upload-area :deep(.el-upload-dragger:hover) {
  border-color: #67c23a;
  background: #f0f9eb;
}

.batch-file-preview {
  margin-top: 20px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.batch-file-count {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.batch-file-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.batch-file-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 80px;
}

.batch-file-thumb {
  width: 60px;
  height: 60px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}

.batch-file-icon {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  border-radius: 6px;
  color: #999;
}

.batch-file-name {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
  text-align: center;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-file-more {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e8e8e8;
  border-radius: 6px;
  font-size: 12px;
  color: #666;
}

/* 批量上传进度 */
.batch-upload-progress-section {
  padding: 20px;
}

.batch-progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.batch-progress-header .form-section-title {
  margin: 0;
  border: none;
}

.batch-progress-header .form-section-title::after {
  display: none;
}

.batch-progress-count {
  font-size: 14px;
  color: #667eea;
  font-weight: 600;
}

.batch-current-file {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 12px;
}

.batch-current-thumb {
  width: 80px;
  height: 80px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
}

.batch-current-info {
  flex: 1;
}

.batch-current-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
  word-break: break-all;
}

.batch-current-status {
  font-size: 13px;
  color: #667eea;
}

.batch-current-thumb-placeholder {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  border-radius: 8px;
  border: 1px solid #e0e0e0;
  color: #999;
}

.batch-progress-bar {
  margin-bottom: 20px;
}

.batch-overall-progress {
  display: flex;
  justify-content: center;
  gap: 20px;
  font-size: 14px;
  color: #666;
}

.batch-success-count {
  color: #67c23a;
  font-weight: 600;
}

.batch-fail-count {
  color: #f56c6c;
  font-weight: 600;
}

/* 批量上传完成 */
.batch-upload-complete {
  text-align: center;
  padding: 40px 20px;
}

.batch-complete-icon {
  margin-bottom: 20px;
}

.batch-complete-title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin-bottom: 24px;
}

.batch-complete-stats {
  display: flex;
  justify-content: center;
  gap: 40px;
  margin-bottom: 24px;
}

.batch-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.batch-stat-label {
  font-size: 14px;
  color: #666;
}

.batch-stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #333;
}

.batch-stat-value.success {
  color: #67c23a;
}

.batch-stat-value.fail {
  color: #f56c6c;
}

.batch-complete-tip {
  font-size: 14px;
  color: #999;
}

/* 图表卡片样式 */
.chart-card,
.stats-card {
  overflow: hidden;
}

/* 统计网格布局 */
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: center;
}

.chart-container {
  display: flex;
  justify-content: center;
  align-items: center;
}

.pie-chart {
  width: 200px;
  height: 200px;
}

/* 统计卡片样式 - 现代设计 */
.stats-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.stat-card.inscription {
  background: linear-gradient(135deg, #ff6b6b20 0%, #ee5a6f20 100%);
  border-left: 4px solid #ff6b6b;
}

.stat-card.painting {
  background: linear-gradient(135deg, #4ecdc420 0%, #44a08d20 100%);
  border-left: 4px solid #4ecdc4;
}

.stat-card.blank {
  background: linear-gradient(135deg, #667eea20 0%, #764ba220 100%);
  border-left: 4px solid #667eea;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.stat-card.inscription .stat-icon {
  color: #ff6b6b;
}

.stat-card.painting .stat-icon {
  color: #4ecdc4;
}

.stat-card.blank .stat-icon {
  color: #667eea;
}

.stat-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: 13px;
  color: #666;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #333;
}

/* 分析说明 */
/* 主区域AI分析说明 */
.analysis-note-main {
  margin: 16px;
  padding: 16px;
  background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
  border-radius: 12px;
  border-left: 4px solid #667eea;
}

.analysis-note-main h4 {
  font-size: 15px;
  color: #333;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.analysis-note-main p {
  font-size: 14px;
  color: #555;
  line-height: 1.7;
}

/* 分析结果左右布局 */
.analysis-result-layout {
  display: flex;
  gap: 20px;
  margin: 0 16px 16px;
  min-height: 300px;
}

.annotated-image-section {
  flex: 1.2;
  display: flex;
  flex-direction: column;
}

.stats-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 200px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
  text-align: center;
}

.annotated-image {
  width: 100%;
  flex: 1;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  background: #f5f7fa;
}

.stats-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  min-height: 200px;
}

.pie-chart-small {
  width: 100%;
  height: 260px;
}

.stats-list {
  margin-top: 16px;
  width: 100%;
  padding: 0 10px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #e4e7ed;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}

.stat-name {
  flex: 1;
  font-size: 15px;
  color: #666;
  white-space: nowrap;
}

.stat-percent {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  white-space: nowrap;
}

/* 右侧原作卡片 */
.original-image-card {
  margin-bottom: 16px;
}

.original-image-wrapper {
  padding: 10px;
  display: flex;
  justify-content: center;
}

.original-image {
  max-width: 100%;
  max-height: 350px;
  object-fit: contain;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

/* 旧的analysis-note样式（保留用于兼容） */
.analysis-note {
  margin-top: 20px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 12px;
  border-left: 4px solid #667eea;
}

.analysis-note h4 {
  font-size: 14px;
  color: #333;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.analysis-note p {
  font-size: 13px;
  color: #666;
  line-height: 1.6;
}

/* 热力图容器 */
.heatmap-container {
  min-height: 200px;
  max-height: 400px;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
}

/* 主区域图片对比 */
.image-compare-container {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 12px;
  margin: 0 16px 16px;
}

.compare-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.compare-title {
  font-size: 14px;
  color: #333;
  margin-bottom: 10px;
  font-weight: 600;
}

.compare-img {
  width: 100%;
  max-height: 300px;
  object-fit: contain;
  border-radius: 8px;
  border: 2px solid #e4e7ed;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

/* 热力图区域 */
.heatmap-section {
  margin-top: 16px;
}

.section-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 500;
  text-align: center;
}

/* 首页概览仪表板 */
.home-dashboard {
  max-width: 1200px;
  margin: 0 auto 30px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 作品库卡片 - 简洁样式 */
.gallery-card {
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
}

.gallery-card :deep(.el-card__header) {
  background: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
}

.gallery-card .header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 20px;
  padding: 20px;
}

.gallery-item {
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 12px;
  overflow: hidden;
  background: white;
  border: 1px solid #e4e7ed;
}

.gallery-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  border-color: #409eff;
}

.gallery-image-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 4/3;
  overflow: hidden;
  background: #f5f7fa;
}

.gallery-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.gallery-item:hover .gallery-image {
  transform: scale(1.05);
}

.gallery-image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
}

.gallery-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.gallery-item:hover .gallery-overlay {
  opacity: 1;
}

.gallery-info {
  padding: 12px;
}

.gallery-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gallery-meta {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.gallery-meta span {
  margin-right: 8px;
}

.gallery-stats {
  display: flex;
  gap: 6px;
}

.gallery-load-more {
  text-align: center;
  padding: 20px 0;
  border-top: 1px solid #e4e7ed;
  margin-top: 10px;
}

.gallery-empty {
  padding: 60px 20px;
  text-align: center;
  color: #909399;
}

.gallery-empty .el-icon {
  margin-bottom: 16px;
}

.gallery-empty p {
  margin-bottom: 20px;
  font-size: 14px;
}

/* 名家对比仪表板卡片 - 简洁样式 */
.comparison-dashboard-card {
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
}

.comparison-dashboard-card :deep(.el-card__header) {
  background: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
}

/* 对比条设计 */
.comparison-bars-container {
  padding: 30px 40px;
}

.comparison-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 40px;
  padding: 0 20px;
}

.artist-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.artist-avatar {
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

.artist-avatar.li {
  background: linear-gradient(135deg, #20b2aa 0%, #008b8b 100%);
}

.artist-avatar.zheng {
  background: linear-gradient(135deg, #4a90d9 0%, #2c5f7c 100%);
}

.artist-name-section h3 {
  font-size: 20px;
  color: #333;
  margin: 0 0 4px 0;
  font-weight: 600;
}

.artist-name-section .years {
  font-size: 12px;
  color: #999;
  margin: 0;
}

.vs-divider {
  font-size: 24px;
  font-weight: bold;
  color: #ccc;
}

.comparison-bars {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.comparison-row {
  display: flex;
  align-items: center;
  gap: 20px;
}

.bar-side {
  flex: 1;
  display: flex;
}

.bar-side.left-side {
  justify-content: flex-end;
}

.bar-side.right-side {
  justify-content: flex-start;
}

.bar-track {
  width: 100%;
  height: 32px;
  background: #f0f0f0;
  border-radius: 16px;
  overflow: hidden;
  position: relative;
}

.progress-fill {
  height: 100%;
  border-radius: 16px;
  display: flex;
  align-items: center;
  transition: width 0.6s ease;
  min-width: 60px;
}

.progress-fill.li-fill {
  background: linear-gradient(90deg, #20b2aa 0%, #3db8a8 100%);
  justify-content: flex-end;
  padding-right: 12px;
}

.progress-fill.zheng-fill {
  background: linear-gradient(90deg, #4a90d9 0%, #5ba3d9 100%);
  justify-content: flex-start;
  padding-left: 12px;
}

.bar-text {
  color: white;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.bar-label-center {
  width: 100px;
  text-align: center;
  font-size: 14px;
  color: #666;
  font-weight: 500;
  flex-shrink: 0;
}

/* 偏爱形式行 */
.layout-row {
  margin-top: 10px;
}

.layout-value {
  flex: 1;
  font-size: 15px;
  color: #333;
  font-weight: 500;
}

.layout-value.left-layout {
  text-align: right;
  padding-right: 20px;
}

.layout-value.right-layout {
  text-align: left;
  padding-left: 20px;
}

/* 新对比条样式 - 根据设计图 */
.bar-track-full {
  width: 100%;
  height: 32px;
  position: relative;
  display: flex;
  align-items: center;
}

.bar-bg {
  position: absolute;
  width: 100%;
  height: 100%;
  background: #e8e8e8;
  border-radius: 16px;
}

.bar-progress {
  position: absolute;
  height: 100%;
  border-radius: 16px;
  display: flex;
  align-items: center;
  transition: width 0.6s ease;
}

/* 左侧李鱓 - 红色条，从右向左延伸 */
.bar-progress.li-bar {
  background: linear-gradient(90deg, #ff6b6b 0%, #ee5a5a 100%);
  right: 0;
  justify-content: flex-start;
  padding-left: 12px;
}

/* 右侧郑燮 - 蓝色条，从左向右延伸 */
.bar-progress.zheng-bar {
  background: linear-gradient(90deg, #4a90d9 0%, #5ba3d9 100%);
  left: 0;
  justify-content: flex-end;
  padding-right: 12px;
}

.bar-value-text {
  color: white;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
}

/* 旧样式兼容 */
.dashboard-comparison {
  display: none;
}

/* 快速开始卡片 */
.quick-start-card {
  text-align: center;
}

.quick-start-content {
  padding: 30px;
}

.quick-start-content p {
  color: #666;
  font-size: 15px;
  margin-bottom: 24px;
}

.quick-start-buttons {
  display: flex;
  justify-content: center;
  gap: 20px;
}

/* 题跋位置分析卡片 - 醒目样式 */
.position-analysis-card {
  border: 3px solid #e6a23c;
  box-shadow: 0 8px 32px rgba(230, 162, 60, 0.3) !important;
  animation: pulse-border 2s ease-in-out infinite;
}

.position-analysis-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #e6a23c 0%, #f5a623 100%);
  color: white;
  font-weight: 600;
  font-size: 16px;
  padding: 16px 20px;
}

@keyframes pulse-border {
  0%, 100% {
    box-shadow: 0 8px 32px rgba(230, 162, 60, 0.3);
  }
  50% {
    box-shadow: 0 8px 40px rgba(230, 162, 60, 0.6);
  }
}

.position-analysis-content {
  padding: 20px;
}

/* 位置分析空状态 */
.position-analysis-empty {
  padding: 40px 20px;
  text-align: center;
  color: #999;
}

.position-analysis-empty .el-icon {
  margin-bottom: 16px;
}

.position-analysis-empty p {
  margin: 4px 0;
  font-size: 14px;
}

.position-analysis-empty .layout-types-hint {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #e0e0e0;
  font-size: 12px;
  color: #bbb;
}

.position-main {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.position-type {
  font-size: 28px;
  font-weight: 700;
  color: #e6a23c;
  background: linear-gradient(135deg, #fff8e7 0%, #fff0cc 100%);
  padding: 12px 24px;
  border-radius: 12px;
  border: 2px solid #e6a23c;
  text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}

.position-location {
  font-size: 16px;
  color: #666;
  font-weight: 500;
}

.position-desc {
  font-size: 15px;
  line-height: 1.8;
  color: #555;
  margin-bottom: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
  border-left: 4px solid #e6a23c;
}

.position-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* 合并的位置分析样式 */
.position-analysis-merged {
  margin-top: 20px;
  padding: 20px;
  background: linear-gradient(135deg, #fff8e7 0%, #ffecd2 100%);
  border-radius: 12px;
  border: 2px solid #e6a23c;
}

.position-analysis-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.position-analysis-header .position-tag {
  font-size: 16px;
  font-weight: 600;
}

.position-analysis-header .position-location {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.position-metrics {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #e6a23c;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-label {
  font-size: 12px;
  color: #999;
}

.metric-value {
  font-size: 14px;
  font-weight: 600;
  color: #e6a23c;
}

/* 融合式分析布局 - 参考图书馆平面图风格 */
.integrated-analysis-card {
  background: #fafbfc;
}

.integrated-analysis-container {
  display: flex;
  gap: 16px;
  padding: 10px;
}

/* 左侧：热力图区域 */
.heatmap-wrapper {
  flex: 1;
  position: relative;
  background: #f0f2f5;
  border-radius: 12px;
  padding: 15px;
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.heatmap-container {
  width: 100%;
  height: 100%;
  min-height: 300px;
}

/* 位置标签叠加层 */
.position-labels-overlay {
  position: absolute;
  top: 15px;
  left: 15px;
  right: 15px;
  bottom: 15px;
  pointer-events: none;
}

.position-main-label {
  position: absolute;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  padding: 8px 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  text-align: center;
  pointer-events: auto;
}

.position-main-label .layout-type {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 2px;
}

.position-main-label .position-name {
  font-size: 12px;
  color: #666;
}

/* 不同布局类型的标签颜色 */
.label-corner { border-left: 4px solid #67c23a; }
.label-frame { border-left: 4px solid #409eff; }
.label-interleaved { border-left: 4px solid #e6a23c; }
.label-full { border-left: 4px solid #f56c6c; }
.label-independent { border-left: 4px solid #909399; }

/* 右侧：分析图例面板 */
.analysis-legend-panel {
  flex: 0 0 220px;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 布局示意图 */
.layout-diagram {
  background: white;
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.diagram-title {
  font-size: 13px;
  color: #666;
  margin-bottom: 10px;
  text-align: center;
  font-weight: 500;
}

.diagram-canvas {
  aspect-ratio: 4/3;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 8px;
}

.canvas-frame {
  width: 100%;
  height: 100%;
  background: white;
  border: 2px solid #dcdfe6;
  border-radius: 4px;
  position: relative;
  overflow: hidden;
}

.canvas-painting-area {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 50%;
  height: 50%;
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: #4caf50;
  font-weight: 500;
}

.canvas-inscription-area {
  position: absolute;
  background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: #f44336;
  font-weight: 500;
  border: 1px dashed #f44336;
}

/* 指标列表 */
.metrics-list {
  background: white;
  border-radius: 12px;
  padding: 12px 14px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.metric-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  white-space: nowrap;
}

.metric-row:last-child {
  border-bottom: none;
}

.metric-icon {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  flex-shrink: 0;
}

.metric-icon.coverage { background: #4caf50; }
.metric-icon.overlap { background: #ff9800; }
.metric-icon.margin { background: #2196f3; }

.metric-name {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}

.metric-value {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  white-space: nowrap;
  margin-left: auto;
  padding-left: 8px;
}

/* 描述文本框 */
.layout-description-box {
  background: white;
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  font-size: 12px;
  color: #666;
  line-height: 1.6;
  border-left: 3px solid #e6a23c;
  max-height: 100px;
  overflow-y: auto;
}

/* 视图容器 */
.view-container {
  width: 100%;
  text-align: center;
  padding: 10px;
}

.view-image {
  max-width: 100%;
  max-height: 350px;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

/* 已上传图片列表 */
.uploaded-list {
  max-height: 300px;
  overflow-y: auto;
}

.uploaded-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  cursor: pointer;
  border-radius: 10px;
  transition: all 0.3s ease;
}

.uploaded-item:hover {
  background: #f5f7fa;
}

.uploaded-item.active {
  background: #ecf5ff;
  border-left: 3px solid #409eff;
}

.thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.thumb-placeholder {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  border: 1px dashed #dcdfe6;
}

.item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.item-name {
  font-size: 14px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.item-percent {
  font-size: 13px;
  color: #ff6b6b;
  font-weight: 600;
}

.item-status {
  font-size: 12px;
  color: #999;
}

/* 上传对话框 */
.upload-dialog-area :deep(.el-upload-dragger) {
  width: 100%;
  height: 180px;
}

/* ========== 响应式设计 ========== */

/* iPad 平板 (768px - 1024px) */
@media screen and (max-width: 1024px) {
  .trend-chart {
    height: 280px;
  }

  .analysis-container {
    grid-template-columns: 1fr;
  }

  .right-panel {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .chart-card,
  .stats-card {
    flex: 1;
    min-width: 300px;
  }

  .uploaded-card {
    width: 100%;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .pie-chart {
    width: 180px;
    height: 180px;
  }
}

/* 手机 (小于 768px) */
@media screen and (max-width: 768px) {
  .tubi-analysis {
    padding: 12px;
  }

  .trend-card {
    margin-bottom: 16px;
  }

  .trend-chart {
    height: 240px;
  }

  .trend-stats {
    flex-wrap: wrap;
  }

  .page-title {
    font-size: 22px;
  }

  .page-subtitle {
    font-size: 12px;
  }

  .analysis-container {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .right-panel {
    flex-direction: column;
  }

  .chart-card,
  .stats-card,
  .uploaded-card {
    width: 100%;
    min-width: auto;
  }

  .stats-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .stats-cards {
    gap: 10px;
  }

  .stat-card {
    padding: 12px;
  }

  .stat-value {
    font-size: 20px;
  }

  /* 名家对比柱状图响应式 */
  .comparison-bars-container {
    padding: 20px 16px;
  }

  .comparison-header {
    flex-direction: column;
    gap: 16px;
    margin-bottom: 24px;
    padding: 0;
  }

  .artist-header {
    width: 100%;
    justify-content: center;
  }

  .artist-header:last-child {
    flex-direction: row-reverse;
  }

  .vs-divider {
    font-size: 18px;
    order: -1;
  }

  .comparison-bars {
    gap: 16px;
  }

  .comparison-row {
    gap: 12px;
  }

  .bar-track-full {
    height: 28px;
  }

  .bar-value-text {
    font-size: 12px;
  }

  .bar-label-center {
    width: 80px;
    font-size: 12px;
  }

  .layout-value {
    font-size: 13px;
  }

  .layout-value.left-layout,
  .layout-value.right-layout {
    padding: 0 10px;
  }

  .pie-chart {
    width: 160px;
    height: 160px;
  }

  .heatmap-container {
    min-height: 150px;
    max-height: 300px;
    margin: 0 auto;
  }

  .image-compare-container {
    flex-direction: column;
    gap: 12px;
  }

  .compare-img {
    max-height: 200px;
  }

  /* 新增布局的响应式 */
  .analysis-result-layout {
    flex-direction: column;
    gap: 16px;
  }

  .annotated-image {
    max-height: 250px;
  }

  .stats-content {
    padding: 16px;
  }

  .pie-chart-small {
    width: 100%;
    height: 200px;
  }

  .original-image {
    max-height: 280px;
  }

  .canvas-wrapper {
    padding: 10px;
  }

  .image-meta {
    flex-direction: column;
    align-items: flex-start;
  }

  .uploaded-item {
    padding: 10px;
  }

  .thumb {
    width: 48px;
    height: 48px;
  }
}

/* 小屏手机 (小于 480px) */
@media screen and (max-width: 480px) {
  .trend-chart {
    height: 200px;
  }

  .page-title {
    font-size: 20px;
  }

  .card-header {
    flex-direction: column;
    gap: 10px;
    align-items: flex-start;
  }

  .stats-grid {
    gap: 12px;
  }

  .stat-card {
    flex-direction: column;
    text-align: center;
    gap: 8px;
  }

  .stat-info {
    align-items: center;
  }

  .pie-chart {
    width: 140px;
    height: 140px;
  }

  .heatmap-container {
    height: 200px;
  }

  .image-compare-container {
    flex-direction: column;
    gap: 12px;
    padding: 12px;
    margin: 0 12px 12px;
  }

  .compare-img {
    max-height: 180px;
  }

  /* 小屏下的对比条 */
  .comparison-bars-container {
    padding: 16px 12px;
  }

  .comparison-header {
    margin-bottom: 20px;
  }

  .artist-avatar {
    width: 40px;
    height: 40px;
    font-size: 16px;
  }

  .artist-name-section h3 {
    font-size: 16px;
  }

  .artist-name-section .years {
    font-size: 11px;
  }

  .comparison-bars {
    gap: 12px;
  }

  .comparison-row {
    gap: 8px;
  }

  .bar-track-full {
    height: 24px;
  }

  .bar-progress.li-bar {
    padding-left: 8px;
  }

  .bar-progress.zheng-bar {
    padding-right: 8px;
  }

  .bar-value-text {
    font-size: 11px;
  }

  .bar-label-center {
    width: 60px;
    font-size: 11px;
  }
}

/* 大屏幕电脑 (大于 1400px) */
@media screen and (min-width: 1400px) {
  .trend-chart {
    height: 360px;
  }

  .analysis-container {
    grid-template-columns: 1fr 450px;
  }

  .pie-chart {
    width: 220px;
    height: 220px;
  }

  .heatmap-container {
    min-height: 250px;
    max-height: 450px;
    margin: 0 auto;
  }
}
</style>
