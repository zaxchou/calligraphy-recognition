<template>
  <div class="analysis-container" :class="{ 'attachment-mode': currentImage?.page_role }">
    <!-- 左侧：原作图 + 作品信息（sticky） -->
    <div class="left-panel">
      <!-- 原作卡片 -->
      <el-card shadow="always" class="original-image-card" v-if="(analyzeStatus === 'analyzed' || currentImage?.page_role) && currentImage?.url">
        <template #header>
          <div class="card-header navigation-header">
            <el-button
              size="small"
              :disabled="!prevImage"
              @click="$emit('navigate', prevImage)"
              :icon="ArrowLeft"
            >
              {{ $t('nav.prev') }}
            </el-button>
            <span class="nav-title">{{ currentImage.title || $t('card.untitled') }}</span>
            <el-button
              size="small"
              :disabled="!nextImage"
              @click="$emit('navigate', nextImage)"
              :icon="ArrowRight"
            >
              {{ $t('nav.next') }}
            </el-button>
          </div>
        </template>
        <div class="original-image-wrapper">
          <img :src="currentImage.thumbnailUrl || currentImage.url" class="original-image" @click="openImagePreview(currentImage.url, currentImage.dzi_url)" :title="$t('nav.prev')" />
          <el-icon class="zoom-icon" @click="openImagePreview(currentImage.url, currentImage.dzi_url)" :title="$t('action.zoom')"><ZoomIn /></el-icon>
        </div>

        <!-- 册页导航 -->
        <div v-if="albumNavigation.is_in_album" class="album-navigation">
          <div class="album-nav-header">
            <span class="album-nav-title">「{{ albumNavigation.album_name }}」</span>
            <span class="album-nav-count">{{ $t('album.current', { n: albumNavigation.current_index + 1 }) }} / {{ $t('album.total', { n: albumNavigation.total_count }) }}</span>
          </div>
          <div class="album-nav-scroll">
            <button class="album-nav-arrow left" @click="scrollAlbumThumbs(-1)" :title="$t('action.scroll_left')">
              <el-icon><ArrowLeft /></el-icon>
            </button>
            <div class="album-nav-thumbnails" ref="albumThumbsRef" @wheel.prevent="onAlbumThumbnailsWheel">
              <div
                v-for="(item, idx) in albumNavigation.items"
                :key="item.id"
                :class="['album-nav-thumbnail', { active: item.is_current }]"
                @click="$emit('navigate-album', item)"
              >
                <img
                  v-if="item.thumbnail_url"
                  :src="item.thumbnail_url"
                  @error="e => e.target.style.display='none'"
                />
                <div v-else class="thumb-placeholder">{{ item.album_index || idx + 1 }}</div>
                <span v-if="item.page_role" class="thumb-role-badge" :class="'role-' + item.page_role">
                  {{ roleBadge(item.page_role) }}
                </span>
              </div>
            </div>
            <button class="album-nav-arrow right" @click="scrollAlbumThumbs(1)" :title="$t('action.scroll_right')">
              <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
      </el-card>

      <!-- 画作信息卡片（作者/年份/尺寸合并） -->
      <div class="artwork-info-card" v-if="!currentImage.page_role && (currentImage.artist || currentImage.year || (currentImage.artwork_width_cm && currentImage.artwork_height_cm))">
        <div class="info-card-row" v-if="currentImage.artist">
          <span class="info-card-label">{{ $t("info.author") }}</span>
          <span class="info-card-value">{{ $t(currentImage.artist) }}</span>
        </div>
        <div class="info-card-row" v-if="currentImage.year">
          <span class="info-card-label">{{ $t("info.year") }}</span>
          <span class="info-card-value">{{ currentImage.year }}{{ locale === 'en' ? '' : '年' }} {{ getDisplayAge(currentImage) !== null ? `(${getDisplayAge(currentImage)}${$t('info.age')})` : '' }}</span>
        </div>
        <div class="info-card-row" v-if="currentImage.artwork_width_cm && currentImage.artwork_height_cm">
          <span class="info-card-label">{{ $t("info.size") }}</span>
          <span class="info-card-value">{{ currentImage.artwork_height_cm }}cm × {{ currentImage.artwork_width_cm }}cm</span>
        </div>
        <div class="info-card-actions">
          <el-button v-if="authStore.isAdmin || (authStore.isEditor && currentImage.owner_id === authStore.userId)" plain size="small" class="btn-action" @click="$emit('edit-current')">
            <el-icon><Edit /></el-icon><span class="btn-label">{{ $t("btn.edit") }}</span>
          </el-button>
          <el-button v-if="authStore.isLoggedIn" plain size="small" class="btn-action" @click="openSuggestEdit">
            <el-icon><EditPen /></el-icon><span class="btn-label">{{ $t("btn.suggest") }}</span>
          </el-button>
          <el-button plain size="small" class="btn-action" @click="openRevisions">
            <el-icon><Clock /></el-icon><span class="btn-label">{{ $t("btn.history") }}</span>
          </el-button>
          <el-button plain size="small" class="btn-action" @click="$emit('back')">
            <el-icon><HomeFilled /></el-icon><span class="btn-label">{{ $t("btn.back") }}</span>
          </el-button>
        </div>
      </div>

      <!-- 附件页提示 -->
      <div v-if="currentImage.page_role" class="attachment-notice">
        {{ $t(roleLabel(currentImage.page_role)) }} — {{ $t("attachment.notice") }}
      </div>
    </div>

    <!-- 右侧：分析结果（附件页隐藏） -->
    <div class="right-panel" v-if="!currentImage.page_role">
      <el-card shadow="hover" class="upload-card" :body-style="{ padding: '0' }">
        <div class="image-display">
          <!-- 面积占比智能示意图 + 标签/款识/钤印 并排布局 -->
          <div v-if="analyzeStatus === 'analyzed'" class="analysis-result-layout">
            <div class="analysis-left-col">
              <!-- ===== Card 1: 情绪解读 ===== -->
              <div class="score-card" v-if="currentImage?.contentAnalysis">
                <h4 class="section-title"><el-icon><DataAnalysis /></el-icon> {{ $t("card.emotion") }}</h4>
                <!-- 有空间分析 → {{ $t("judgment.combined") }} -->
                <template v-if="combinedSentiment">
                  <div class="emotion-layout-v2">
                    <!-- VADER compound bar（融合版） -->
                    <div class="emotion-vader-bar" v-if="combinedSentiment?.vader_normalized != null">
                      <div class="vader-bar-header">
                        <span class="vader-polarity" :style="{ color: polarityLabelColor(combinedSentiment.polarity) }">
                          {{ $t(polarityKey(combinedSentiment.polarity)) }}
                        </span>
                        <span class="vader-score-big" :style="{ color: displayScore < 0 ? '#e07a5f' : displayScore > 0 ? '#3cb88b' : '#999' }">
                          {{ displayScore > 0 ? '+' : '' }}{{ displayScore.toFixed(4) }}
                        </span>
                        <el-tag v-if="conflictScore != null && conflictScore > 0.2" size="small" effect="plain"
                          :type="conflictScore > 0.6 ? 'warning' : 'info'">
                          复杂度 {{ (conflictScore * 100).toFixed(0) }}%
                        </el-tag>
                        <el-tag v-if="currentImage.contentAnalysis?.period_phase" size="small" type="info">{{ $t(currentImage.contentAnalysis.period_phase) }}</el-tag>
                        <el-tooltip :content="$t('method.vader_tip')" placement="top" effect="light">
                          <span class="score-method-badge">Molin Emotion</span>
                        </el-tooltip>
                      </div>
                      <div class="vader-track">
                        <div class="vader-gradient"></div>
                        <!-- 指示器 -->
                        <div class="vader-marker" :style="{ left: ((displayScore + 1) / 2 * 100) + '%' }">
                          <div class="vader-marker-pin"></div>
                          <div class="vader-marker-line"></div>
                        </div>
                        <span class="vader-axis vader-axis-neg">-1.0</span>
                        <span class="vader-axis vader-axis-zero">0</span>
                        <span class="vader-axis vader-axis-pos">+1.0</span>
                      </div>
                      <div class="vader-reasoning">{{ translateContent(combinedSentiment.reasoning) }}</div>
                      <!-- v3.1: 8维极性条 -->
                      <div class="dim-polarity-strip" v-if="Object.keys(dimensionPolarities).length">
                        <div class="polarity-strip-title">维度极性</div>
                        <div class="polarity-dots">
                          <el-tooltip v-for="dim in dimensionRows.filter(d => !d.placeholder)" :key="dim.nameKey"
                            :content="$t(dim.nameKey) + ': ' + (dim.raw > 0 ? '+' : '') + dim.raw.toFixed(2)" placement="top">
                            <span class="polarity-dot" :class="'pol-' + dim.polarity"></span>
                          </el-tooltip>
                        </div>
                      </div>
                    </div>
                    <!-- fallback：无 VADER 数据时用旧布局 -->
                    <div class="emotion-summary-row" v-else>
                      <div class="summary-left">
                        <span class="summary-polarity" :style="{ color: combinedSentiment.polarity === 'positive' ? '#3cb88b' : combinedSentiment.polarity === 'negative' ? '#f56c6c' : '#909399' }">
                          {{ combinedSentiment.polarity === 'positive' ? $t('polarity.positive') : combinedSentiment.polarity === 'negative' ? $t('polarity.negative') : combinedSentiment.polarity === 'ambiguous' ? $t('polarity.ambiguous') : $t('polarity.neutral') }}
                        </span>
                        <span class="summary-score" :style="{ color: displayScore < 0 ? '#f56c6c' : displayScore > 0 ? '#3cb88b' : '#999' }">
                          {{ displayScore > 0 ? '+' : '' }}{{ displayScore.toFixed(2) }}
                        </span>
                        <el-tag v-if="currentImage.contentAnalysis?.period_phase" size="small" type="info">{{ $t(currentImage.contentAnalysis.period_phase) }}</el-tag>
                      </div>
                      <div class="summary-reasoning">{{ translateContent(combinedSentiment.reasoning) }}</div>
                    </div>
                  </div>
                  <!-- 方法论说明（仅旧版无公式表格时显示） -->
                  <el-collapse v-if="combinedSentiment?.method === 'molin_v2'">
                    <el-collapse-item :title="$t('method.title')" name="methodology">
                      <div class="methodology-content">
                        <p><strong>{{ $t('method.formula') }}</strong></p>
                        <p class="method-formula">S = normalize(Σ wᵢ × cᵢ × sᵢ)</p>
                        <p>{{ $t('method.explanation') }}</p>
                        <ul>
                          <li>{{ $t('method.text_weight') }}: {{ (calibratedWeights.text * 100).toFixed(0) }}%</li>
                          <li>{{ $t('method.spatial_weight') }}: {{ (calibratedWeights.spatial * 100).toFixed(0) }}%</li>
                          <li>{{ $t('method.seal_weight') }}: {{ (calibratedWeights.seal * 100).toFixed(0) }}%</li>
                        </ul>
                        <p class="method-ref">{{ $t('method.reference') }}</p>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
                </template>
                <!-- 无空间分析 → 纯文字结论 -->
                <template v-else>
                  <div class="sentiment-card">
                    <div class="sentiment-header">
                      <span class="sentiment-dot" :style="{ background: currentImage.contentAnalysis.sentiment.polarity === 'positive'  ? '#4e8cff' : currentImage.contentAnalysis.sentiment.polarity === 'negative'  ? '#ff6b35' : '#b8a47e' }"></span>
                      <span class="sentiment-polarity-text" :style="{ color: currentImage.contentAnalysis.sentiment.polarity === 'positive' ? '#67c23a' : currentImage.contentAnalysis.sentiment.polarity === 'negative' ? '#f56c6c' : '#909399' }">{{ currentImage.contentAnalysis.sentiment.polarity === 'positive'  ? $t('polarity.positive') : currentImage.contentAnalysis.sentiment.polarity === 'negative'  ? $t('polarity.negative') : $t('polarity.neutral') }}</span>
                      <span class="sentiment-sep">·</span>
                      <span class="sentiment-score-text">{{ $t('sentiment.intensity') }} {{ Math.round(getSentimentIntensity(currentImage.contentAnalysis.sentiment) * 100) }}%</span>
                      <template v-if="currentImage.contentAnalysis.sentiment.emotion_score != null">
                        <span class="sentiment-sep">·</span>
                        <span class="sentiment-score-text">{{ $t('sentiment.score') }} {{ currentImage.contentAnalysis.sentiment.emotion_score > 0 ? '+' : '' }}{{ currentImage.contentAnalysis.sentiment.emotion_score }}</span>
                      </template>
                    </div>
                    <div class="sentiment-bar-track">
                      <div class="sentiment-bar-fill" :style="{ width: Math.round(getSentimentIntensity(currentImage.contentAnalysis.sentiment) * 100) + '%', background: currentImage.contentAnalysis.sentiment.polarity === 'positive'  ? '#4e8cff' : currentImage.contentAnalysis.sentiment.polarity === 'negative'  ? '#ff6b35' : '#b8a47e' }"></div>
                    </div>
                  </div>
                </template>
              </div>

              <!-- ===== Card 2: 主题判断 ===== -->
              <div class="theme-card" v-if="currentImage.contentAnalysis?.themes?.length">
                <h4 class="section-title"><el-icon><Collection /></el-icon> {{ $t("card.themes") }}</h4>
                <div ref="themeChartRef" class="theme-chart-small"></div>
              </div>

                            <!-- ===== Card 3: 空间情绪解读 ===== -->
              <!-- (kept in place - already above this block) -->

              <!-- 空间情绪解读（含布局类型，默认展开） -->
              <div class="spatial-emotion-card" v-if="spatialEmotion && spatialEmotion.signals?.length">
                <h4 class="section-title">
                  <el-icon><MagicStick /></el-icon> {{ $t("card.spatial") }}
                  <!-- 布局类型标签（始终可见） -->
                  <div class="form-types-inline" v-if="positionAnalysis?.form_types?.length">
                    <el-tooltip
                      v-for="ft in positionAnalysis.form_types.filter(f => f.matched)"
                      :key="ft.code"
                      :content="ft.description"
                      placement="bottom"
                      effect="dark"
                    >
                      <span class="form-type-tag" :class="`tag-code-${ft.code}`">
                        {{ $t(ft.name) }}
                      </span>
                    </el-tooltip>
                  </div>
                </h4>
                <div class="spatial-detail">
                    <div v-for="(sig, idx) in sortedSpatialSignals" :key="idx" class="spatial-item">
                      <span class="spatial-dot" :class="'emotion-' + sig.emotion_key"></span>
                      <span class="spatial-type">{{ $t(sig.type) }}</span>
                      <span class="spatial-emotion-tag">{{ $t(sig.emotion) }}</span>
                      <p class="spatial-desc">{{ translateContent(sig.desc) }}</p>
                    </div>
                    <div class="spatial-item">
                      <span class="spatial-dot blank-dot"></span>
                      <span class="spatial-type">{{ $t('spatial.blank') }} {{ spatialEmotion.blank_percent }}%</span>
                      <p class="spatial-desc">{{ translateContent(spatialEmotion.blank_analysis) }}</p>
                    </div>
                    <div v-if="spatialEmotion?.combined_spatial_sentiment" class="spatial-combined">
                      <span class="spatial-combined-label">{{ $t('spatial.combined') }}</span>
                      <span class="spatial-combined-text">{{ translateContent(spatialEmotion.combined_spatial_sentiment) }}</span>
                    </div>
                  </div>
              </div>
              <!-- 无空间情绪数据时，回退显示纯布局类型 -->
              <div class="spatial-analysis-card" v-else-if="analyzeStatus === 'analyzed' && positionAnalysis">
                <h4 class="section-title">
                  <el-icon><DataAnalysis /></el-icon> {{ $t("card.layout") }}
                  <div class="form-types-inline" v-if="positionAnalysis?.form_types?.length">
                    <el-tooltip
                      v-for="ft in positionAnalysis.form_types.filter(f => f.matched)"
                      :key="ft.code"
                      :content="ft.description"
                      placement="bottom"
                      effect="dark"
                    >
                      <span class="form-type-tag" :class="`tag-code-${ft.code}`">
                        {{ $t(ft.name) }}
                      </span>
                    </el-tooltip>
                    <span v-if="positionAnalysis.vl_overall_status === 'partial_timeout'" class="vl-timeout-badge">VL Timeout</span>
                  </div>
                </h4>
                <div class="spatial-description" v-if="positionAnalysis?.form_types?.length">
                  <div
                    v-for="ft in positionAnalysis.form_types.filter(f => f.matched)"
                    :key="ft.code"
                    class="form-type-desc-row"
                  >
                    <span class="desc-tag" :class="`desc-tag-${ft.code}`">{{ ft.code }}</span>
                    <span class="desc-text">{{ ft.description }}</span>
                  </div>
                </div>
                <div class="spatial-description" v-else>
                  {{ positionAnalysis.layout_description }}
                </div>
              </div>
              
<!-- ===== Card 4: 推导过程 ===== -->
              <div class="steps-card" v-if="currentImage.contentAnalysis?.sentiment?.reasoning_steps?.length || combinedSentiment">
                <h4 class="section-title"><el-icon><MagicStick /></el-icon> {{ $t("card.steps") }}</h4>

                <!-- v2/v3 八维度公式推导（有 combined_sentiment 时显示） -->
                <div v-if="combinedSentiment" class="formula-breakdown">
                  <div class="formula-box">
                    <div class="formula-title">{{ $t('derivation.formula') }}</div>
                    <div class="formula-expr">S = normalize( Σ wᵢ × cᵢ × sᵢ )</div>
                    <div class="formula-legend">
                      <span><b>wᵢ</b> {{ $t('derivation.legendWeight') }}</span>
                      <span><b>cᵢ</b> {{ $t('derivation.legendConf') }}</span>
                      <span><b>sᵢ</b> {{ $t('derivation.legendScore') }}</span>
                      <span><b>Σ</b> {{ $t('derivation.legendSum') }}</span>
                      <span><b>normalize</b> {{ $t('derivation.legendNorm') }}</span>
                    </div>
                  </div>

                  <table class="formula-table">
                    <thead>
                      <tr>
                        <th>{{ $t('derivation.dimension') }}</th>
                        <th>{{ $t('derivation.normalized') }}</th>
                        <th>{{ $t('derivation.weight') }}</th>
                        <th>{{ $t('derivation.confidence') }}</th>
                        <th>{{ $t('derivation.contribution') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <template v-for="dim in dimensionRows" :key="dim.nameKey">
                        <tr :class="{ 'dim-active': dim.hasData || dim.placeholder, 'dim-conflict': dim.conflicted }"
                          @click="(dim.hasData || dim.placeholder) && toggleDimDetail(dim.nameKey)"
                          :style="{ cursor: (dim.hasData || dim.placeholder) ? 'pointer' : 'default' }">
                          <td class="dim-name">
                            <span v-if="dim.hasData || dim.placeholder" class="dim-expand">{{ expandedDims.has(dim.nameKey) ? '▼' : '▶' }}</span>
                            <span class="dim-pol-dot" :class="'pol-' + dim.polarity" :title="dim.polarity"></span>
                            {{ $t(dim.nameKey) }}
                          </td>
                          <td class="dim-score" :class="{ 'score-pos': dim.normalized > 0, 'score-neg': dim.normalized < 0 }">
                            {{ dim.normalized > 0 ? '+' : '' }}{{ dim.normalized.toFixed(2) }}
                          </td>
                          <td class="dim-weight">{{ (dim.weight * 100).toFixed(0) }}%</td>
                          <td class="dim-conf" :class="{ 'conf-high': dim.confidence >= 0.7, 'conf-mid': dim.confidence >= 0.4 && dim.confidence < 0.7, 'conf-low': dim.confidence < 0.4 }">
                          {{ (dim.confidence * 100).toFixed(0) }}%
                        </td>
                          <td class="dim-contrib" :class="{ 'score-pos': dim.contribution > 0, 'score-neg': dim.contribution < 0 }">
                            {{ dim.contribution > 0 ? '+' : '' }}{{ dim.contribution.toFixed(3) }}
                          </td>
                        </tr>
                        <!-- 展开详情 -->
                        <tr v-if="expandedDims.has(dim.nameKey) && (dim.hasData || dim.placeholder)" class="dim-detail-row">
                          <td colspan="5" class="dim-detail-cell">
                            <div class="dim-detail-content" v-if="dim.placeholder">
                              <div class="detail-item dim-placeholder">{{ $t('derivation.underResearch') }}</div>
                            </div>
                            <div class="dim-detail-content" v-else>
                              <template v-for="(item, i) in getDimDetail(dim.nameKey)" :key="i">
                                <div class="detail-item">
                                  <span class="detail-label">{{ item.label }}</span>
                                  <span class="detail-value" :class="{ 'score-pos': item.score > 0, 'score-neg': item.score < 0 }">
                                    {{ item.score > 0 ? '+' : '' }}{{ item.score }}
                                  </span>
                                  <span class="detail-desc" v-if="item.desc">{{ item.desc }}</span>
                                </div>
                              </template>
                            </div>
                          </td>
                        </tr>
                      </template>
                    </tbody>
                  </table>

                  <div class="formula-result">
                    <span class="result-label">{{ $t('derivation.normalized') }}</span>
                    <span class="result-score" :class="{ 'score-pos': combinedSentiment.vader_normalized > 0, 'score-neg': combinedSentiment.vader_normalized < 0 }">
                      {{ combinedSentiment.vader_normalized > 0 ? '+' : '' }}{{ combinedSentiment.vader_normalized }}
                    </span>
                    <span class="result-polarity" :style="{ color: polarityColor(combinedSentiment.polarity) }">
                      → {{ $t(polarityKey(combinedSentiment.polarity)) }}
                    </span>
                  </div>

                  <!-- v3.1: 冲突分数条 -->
                  <div class="conflict-bar" v-if="conflictScore != null && conflictScore > 0">
                    <div class="conflict-bar-label">情感复杂度</div>
                    <div class="conflict-bar-track">
                      <div class="conflict-bar-fill" :style="{ width: (conflictScore * 100) + '%' }"></div>
                    </div>
                    <span class="conflict-bar-value">{{ (conflictScore * 100).toFixed(0) }}%{{ conflictScore > 0.6 ? ' 矛盾较强' : conflictScore > 0.3 ? ' 有张力' : ' 较一致' }}</span>
                  </div>
                </div>

                <!-- v3.1: LLM 分析叙述（DeepSeek 解读原文） -->
                <div v-if="llmNarrativeSections" class="llm-narrative-section">
                  <div class="llm-narrative-header">
                    <el-icon><MagicStick /></el-icon>
                    <span>AI 解读</span>
                  </div>
                  <div class="llm-narrative-grid">
                    <div class="narrative-card narrative-positive" v-if="llmNarrativeSections.positive">
                      <div class="narrative-card-header">积极面</div>
                      <div class="narrative-card-body">{{ llmNarrativeSections.positive }}</div>
                    </div>
                    <div class="narrative-card narrative-negative" v-if="llmNarrativeSections.negative">
                      <div class="narrative-card-header">消极面</div>
                      <div class="narrative-card-body">{{ llmNarrativeSections.negative }}</div>
                    </div>
                    <div class="narrative-card narrative-verdict" v-if="llmNarrativeSections.verdict">
                      <div class="narrative-card-header">综合判断</div>
                      <div class="narrative-card-body">{{ llmNarrativeSections.verdict }}</div>
                    </div>
                  </div>
                </div>
                <!-- fallback: old format plain text -->
                <div v-else-if="currentImage.contentAnalysis?.llm_analysis?.combined?.summary" class="llm-narrative-section">
                  <div class="llm-narrative-header">
                    <el-icon><MagicStick /></el-icon>
                    <span>AI 解读</span>
                  </div>
                  <div class="llm-narrative-body">
                    {{ currentImage.contentAnalysis.llm_analysis.combined.summary }}
                  </div>
                </div>

                <!-- v3 LLM 校正详情 -->
                <div v-if="currentImage.contentAnalysis?.llm_analysis?.corrections" class="llm-correction-section">
                  <div class="llm-section-header">
                    <el-icon><MagicStick /></el-icon>
                    <span>{{ $t('derivation.llm_correction') }}</span>
                  </div>
                  <!-- 逐维度校正 -->
                  <table class="llm-table">
                    <thead>
                      <tr>
                        <th>{{ $t('derivation.dimension') }}</th>
                        <th>{{ $t('derivation.llm_delta') }}</th>
                        <th>{{ $t('derivation.confidence') }}</th>
                        <th>{{ $t('derivation.llm_reasoning') }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(corr, dimKey) in currentImage.contentAnalysis.llm_analysis.corrections" :key="dimKey">
                        <td class="dim-name">{{ $t(`factor.${dimKey}`) }}</td>
                        <td class="dim-delta" :class="{ 'score-pos': corr.delta > 0, 'score-neg': corr.delta < 0 }">
                          {{ corr.delta > 0 ? '+' : '' }}{{ corr.delta.toFixed(2) }}
                        </td>
                        <td class="dim-conf" :class="{ 'conf-high': corr.confidence >= 0.7, 'conf-mid': corr.confidence >= 0.4 && corr.confidence < 0.7 }">
                          {{ (corr.confidence * 100).toFixed(0) }}%
                        </td>
                        <td class="llm-reasoning-cell">{{ corr.reasoning }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <!-- 元信息 -->
                  <div class="llm-meta" v-if="currentImage.contentAnalysis.llm_analysis.meta">
                    <span class="llm-model">{{ currentImage.contentAnalysis.llm_analysis.meta.model }}</span>
                    <span v-if="currentImage.contentAnalysis.llm_analysis.meta.token_count" class="llm-tokens">
                      · {{ currentImage.contentAnalysis.llm_analysis.meta.token_count }} tokens
                    </span>
                    <span v-if="currentImage.contentAnalysis.llm_analysis.meta.time_ms" class="llm-time">
                      · {{ (currentImage.contentAnalysis.llm_analysis.meta.time_ms / 1000).toFixed(1) }}s
                    </span>
                  </div>
                </div>

              </div>
              <div class="ts-empty" v-if="!currentImage.contentAnalysis?.themes?.length && !currentImage.contentAnalysis?.sentiment">
                {{ $t("analysis.empty") }}
              </div>

            </div>
            <div class="analysis-right-col">
              <div class="annotated-image-section">
                <h4 class="section-title">
                  <el-icon><DataAnalysis /></el-icon> {{ $t("card.diagram") }}
                  <el-button
                    v-if="authStore.isAdmin || (authStore.isEditor && currentImage.owner_id === authStore.userId)"
                    size="small" text
                    class="btn-annotate"
                    @click="$emit('open-annotator')"
                  >{{ $t("btn.manual_annotate") }}</el-button>
                </h4>
                <div class="annotated-image-wrapper" @mouseenter="showDiagramOverlay = false" @mouseleave="showDiagramOverlay = true">
                  <img :src="currentImage.annotatedImageUrl" class="annotated-image" />
                  <div v-if="currentImage.isManualAnnotated" class="manual-annotated-badge" :title="$t('btn.manual_annotate')">
                    <el-icon><Check /></el-icon>
                  </div>
                  <!-- 悬浮布局示意图 -->
                  <transition name="fade">
                    <div v-if="showDiagramOverlay && diagramRegions.inscription_regions?.length" class="diagram-hover-overlay">
                      <svg
                        class="diagram-svg"
                        :viewBox="`0 0 100 ${(100 * (currentImage?.height || 1) / (currentImage?.width || 1)).toFixed(1)}`"
                        preserveAspectRatio="xMidYMid meet"
                      >
                        <polygon
                          v-for="(reg, idx) in diagramRegions.margin_regions"
                          :key="'m'+idx"
                          :points="toDiagramPoints(reg)"
                          class="diagram-margin-poly"
                        />
                        <polygon
                          v-for="(reg, idx) in diagramRegions.painting_regions"
                          :key="'p'+idx"
                          :points="toDiagramPoints(reg)"
                          class="diagram-painting-poly"
                        />
                        <polygon
                          v-for="(reg, idx) in diagramRegions.inscription_regions"
                          :key="'i'+idx"
                          :points="toDiagramPoints(reg)"
                          class="diagram-inscription-poly"
                        />
                        <polygon
                          v-for="(reg, idx) in diagramRegions.blank_regions"
                          :key="'b'+idx"
                          :points="toDiagramPoints(reg)"
                          class="diagram-blank-poly"
                        />
                      </svg>
                      <div class="diagram-legend-overlay">
                        <span class="legend-item"><span class="legend-dot inscription"></span>{{ $t("area.inscription") }}</span>
                        <span class="legend-item"><span class="legend-dot painting"></span>{{ $t("area.painting") }}</span>
                        <span class="legend-item"><span class="legend-dot blank"></span>{{ $t("area.blank") }}</span>
                        <span class="legend-item"><span class="legend-dot margin"></span>{{ $t("area.margin") }}</span>
                      </div>
                    </div>
                  </transition>
                </div>
              </div>
              <!-- 题跋占比分析 -->
              <div class="stats-section">
                <h4 class="section-title"><el-icon><PieChart /></el-icon> {{ $t("card.area") }}</h4>
                <div class="stats-content">
                  <div ref="pieChartRef" class="pie-chart-small"></div>
                </div>
                <div class="stats-list">
                  <div class="stat-item inscription">
                    <span class="stat-dot" style="background: #d4846a;"></span>
                    <span class="stat-name">{{ $t("area.inscription") }}</span>
                    <span class="stat-percentile" v-if="areaPercentile !== null">{{ $t('area.percentile', { artist: $t(currentImage.artist) || $t('area.this_artist'), pct: areaPercentile }) }}</span>
                    <span class="stat-percent">{{ areaStats.inscriptionPercent }}%</span>
                  </div>
                  <div class="stat-item painting" v-if="areaStats.paintingPercent > 0">
                    <span class="stat-dot" style="background: #7ba3c4;"></span>
                    <span class="stat-name">{{ $t("area.painting") }}</span>
                    <span class="stat-percent">{{ areaStats.paintingPercent }}%</span>
                  </div>
                  <div class="stat-item blank" v-if="areaStats.blankPercent > 0">
                    <span class="stat-dot" style="background: #a8c97a;"></span>
                    <span class="stat-name">{{ $t("area.blank") }}</span>
                    <span class="stat-percent">{{ areaStats.blankPercent }}%</span>
                  </div>
                </div>
              </div>
              <div class="inscription-note-main">
                <h4>
                  <el-icon><Edit /></el-icon> {{ $t('card.inscription') }}
                  <span class="inscription-mode-btns">
                    <el-button size="small" text :class="{ active: inscriptionMode === 'original' }" @click="inscriptionMode = 'original'">{{ $t('btn.original') }}</el-button>
                    <el-button v-if="currentImage.inscriptionModern && currentImage.inscriptionModern !== currentImage.inscriptionContent" size="small" text :class="{ active: inscriptionMode === 'modern' }" @click="inscriptionMode = 'modern'">{{ $t('btn.vernacular') }}</el-button>
                    <el-button v-if="currentImage.inscriptionEn" size="small" text :class="{ active: inscriptionMode === 'english' }" @click="inscriptionMode = 'english'">{{ $t('btn.english') }}</el-button>
                  </span>
                </h4>
                <div class="inscription-switch">
                  <transition name="el-fade-in" mode="out-in">
                    <div v-if="inscriptionMode === 'original' && currentImage.inscriptionContent" key="orig" class="inscription-content">
                      {{ currentImage.inscriptionContent }}
                    </div>
                    <div v-else-if="inscriptionMode === 'modern' && currentImage.inscriptionModern" key="modern" class="inscription-content modern">
                      {{ currentImage.inscriptionModern }}
                    </div>
                    <div v-else-if="inscriptionMode === 'english' && currentImage.inscriptionEn" key="en" class="inscription-content english">
                      {{ currentImage.inscriptionEn }}
                    </div>
                    <div v-else key="empty" class="inscription-empty">
                      <p>{{ $t('inscription.empty') }}</p>
                      <p class="empty-tip">{{ $t('inscription.tip') }}</p>
                    </div>
                  </transition>
                </div>
              </div>
              <div class="seal-note-main">
                <h4><el-icon><Collection /></el-icon> {{ $t("card.seals") }}</h4>
                <div v-if="currentImage.sealContent" class="seal-content">
                  <div class="seal-tags-display">
                    <span v-for="(seal, idx) in detailSealTags" :key="idx"
                      class="seal-display-tag"
                      :class="{ 'has-image': detailSealImageMap[seal.name] }"
                      @click="openSealLightbox(seal.name)">
                      {{ seal.name }}
                      <span v-if="seal.seal_type" class="seal-display-type">{{ seal.seal_type }}</span>
                    </span>
                  </div>
                </div>
                <div v-else class="seal-empty"><p>{{ $t("seal.none") }}</p></div>
                <!-- 印章情绪解读 -->
                <div v-if="sealEmotion?.total_seals" class="seal-interp">
                  <div class="seal-interp-header">{{ $t("seal.emotion") }}</div>
                  <div class="seal-interp-signals">
                    <template v-for="sig in sealEmotion.signals.filter(s => s.raw_score !== 0)" :key="sig.seal">
                      <span class="seal-interp-tag">{{ sig.seal }}：{{ translateContent(sig.desc) }}（{{ sig.raw_score > 0 ? '+' : '' }}{{ sig.raw_score }}）</span>
                    </template>
                    <span v-if="!sealEmotion.signals.filter(s => s.raw_score !== 0).length" class="seal-interp-neutral">
                      {{ $t("seal.neutral") }}
                    </span>
                  </div>
                </div>
                <div v-else-if="currentImage.sealContent && !sealEmotion" class="seal-interp">
                  <span class="seal-interp-neutral">{{ $t("seal.no_data") }}</span>
                </div>
              </div>
              <div v-if="currentImage && getDetailAllTags().length > 0" class="detail-tags-section">
                <div class="detail-tags-list">
                  <span v-for="(tag, idx) in getDetailAllTags()" :key="idx" class="detail-tag" @click="$emit('filter-by-tag', tag)">{{ $t(tag) }}</span>
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
            <p class="analyzing-subtext">{{ $t('analysis.analyzing') }}</p>
          </div>

          <div class="image-meta">
            <el-tag>{{ currentImage.name }}</el-tag>
            <el-tag type="info">{{ currentImage.width }} × {{ currentImage.height }}</el-tag>
            <el-tag v-if="analyzeStatus === 'analyzed'" type="success">{{ $t('analysis.complete_tag') }}</el-tag>
            <el-button
              v-if="analyzeStatus !== 'analyzing' && analyzeStatus !== 'analyzed' && !currentImage.page_role"
              type="primary"
              size="small"
              @click="$emit('auto-analyze')"
            >
              {{ $t('analysis.start') }}
            </el-button>
          </div>
        </div>
      </el-card>

      <!-- {{ $t('gallery.title') }} -->
      <el-card shadow="hover" class="history-card">
        <template #header>
          <div class="card-header">
            <span>{{ $t('gallery.title') }}</span>
            <el-button type="primary" size="small" @click="openRanking" :icon="Clock">
              {{ $t('gallery.view_all') }}
            </el-button>
          </div>
        </template>
        <div class="history-grid" v-if="relatedWorks.length > 0">
          <div
            v-for="item in relatedWorks"
            :key="item.id"
            class="history-grid-item"
            :class="{ 'is-current': item.id === currentImage.id }"
            @click="$emit('history-item-click', item)"
          >
            <img v-if="item.thumbnailUrl || item.url" :src="item.thumbnailUrl || item.url" class="history-grid-thumb" loading="lazy" />
            <div v-else class="history-grid-thumb-placeholder">
              <el-icon size="16"><Picture /></el-icon>
            </div>
            <div v-if="item.id === currentImage.id" class="history-grid-thumb-overlay">
              <el-icon><Check /></el-icon>
            </div>
            <div class="history-grid-title">{{ item.title || $t('card.untitled') }}</div>
          </div>
        </div>
        <div class="history-summary empty" v-else>
          <p>{{ $t('gallery.no_same_artist') }}</p>
        </div>
      </el-card>
    </div>

    <!-- 深度缩放查看器（覆盖整个浏览器窗口） -->
    <TubiDeepZoomDialog
      v-if="imagePreviewVisible"
      :image-url="currentPreviewImage"
      :dzi-url="currentPreviewDzi"
      @close="imagePreviewVisible = false"
    />

    <!-- 印章 Lightbox（OpenSeadragon 缩放/翻页） -->
    <SealLightbox
      v-if="sealLightboxVisible"
      :visible="sealLightboxVisible"
      :seal="selectedSealForLightbox"
      @close="sealLightboxVisible = false"
    />

    <!-- 我的意见对话框 -->
    <el-dialog v-model="showSuggestDialog" :title="$t('suggest.title')" width="560px" destroy-on-close @closed="suggestDialogClosed">
      <p style="margin-bottom:16px;color:var(--stone-gray)" v-html="$t('suggest.intro', { title: currentImage.title || $t('card.untitled') })">
      </p>
      <el-form :model="suggestForm" label-position="top">
        <el-form-item :label="$t('suggest.field')">
          <el-select v-model="suggestForm.field_name" style="width:100%">
            <el-option :label="$t('suggest.field_title')" value="title" />
            <el-option :label="$t('suggest.field_artist')" value="artist" />
            <el-option :label="$t('suggest.field_year')" value="year" />
            <el-option :label="$t('suggest.field_period')" value="period" />
            <el-option :label="$t('suggest.field_notes')" value="notes" />
            <el-option :label="$t('suggest.field_inscription')" value="inscription_content" />
            <el-option :label="$t('suggest.field_annotation')" value="annotation_regions" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('suggest.old_value')">
          <div class="old-value-display">{{ suggestForm.old_value }}</div>
        </el-form-item>
        <template v-if="suggestForm.field_name === 'annotation_regions'">
          <el-form-item :label="$t('suggest.field_annotation')">
            <div style="font-size:13px;color:#666;margin-bottom:12px;">
              {{ $t('suggest.annotation_hint', { area: $t('area.inscription') }) }}
            </div>
            <el-button type="primary" @click="openAnnotatorSuggest">
              <el-icon><EditPen /></el-icon> {{ $t('suggest.open_annotator') }}
            </el-button>
            <div v-if="suggestAnnotationSaved" style="margin-top:10px;color:#67c23a;font-size:13px;">
              <el-icon><CircleCheckFilled /></el-icon> {{ $t('suggest.annotation_saved') }}
            </div>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item :label="$t('suggest.new_value')" required>
            <el-input v-model="suggestForm.new_value" type="textarea" :autosize="{ minRows: 2, maxRows: 8 }" :placeholder="$t('suggest.new_value_ph')" />
          </el-form-item>
          <el-form-item :label="$t('suggest.change_desc')" required>
            <el-input v-model="suggestForm.change_summary" type="textarea" :rows="3" :placeholder="$t('suggest.change_desc_ph')" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showSuggestDialog = false">{{ $t('suggest.cancel') }}</el-button>
        <el-button v-if="suggestForm.field_name !== 'annotation_regions'" type="primary" @click="handleSubmitChange" :loading="submitting">{{ $t('suggest.submit') }}</el-button>
      </template>
    </el-dialog>

    <!-- 版本历史对话框 -->
    <el-dialog v-model="showRevisionsDialog" :title="$t('revision.title')" width="700px" destroy-on-close>
      <div v-if="revisionsLoading" style="text-align:center;padding:40px;">
        <el-icon class="is-loading" size="24"><Loading /></el-icon>
        <p style="margin-top:12px;color:#999;">{{ $t('revision.loading') }}</p>
      </div>
      <template v-else>
        <el-empty v-if="revisions.length === 0" :description="$t('revision.empty')" />
        <el-timeline v-else>
          <el-timeline-item
            v-for="rev in revisions"
            :key="rev.id"
            :timestamp="rev.created_at"
            placement="top"
          >
            <div class="rev-header">
              <span class="rev-number">#{{ rev.revision_number }}</span>
              <el-tag :type="rev.operation_type === 'rollback' ? 'warning' : rev.operation_type === 'approve' ? 'success' : 'info'" size="small">
                {{ rev.operation_type === 'rollback' ? $t('revision.rollback') : rev.operation_type === 'approve' ? $t('revision.approve') : $t('revision.edit') }}
              </el-tag>
            </div>
            <div class="rev-summary">{{ rev.change_summary || $t('revision.no_summary') }}</div>
            <el-button v-if="rev.revision_number > 1" text size="small" type="primary" @click="handleRollback(rev)">
              {{ $t('revision.rollback_btn') }}
            </el-button>
          </el-timeline-item>
        </el-timeline>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
const { t, locale } = useI18n()

// 内容文本翻译：对中文分词逐个查字典翻译
function translateContent(text) {
  if (!text) return ''
  // 新格式：i18n key 用 | 分隔
  if (text.includes('|') && text.startsWith('reasoning.')) {
    return text.split('|').map(key => {
      key = key.trim()
      // reasoning.theme.咏物寄兴 → 翻译主题名
      if (key.startsWith('reasoning.theme.')) {
        const themeName = key.replace('reasoning.theme.', '')
        return t('reasoning.theme') + t(themeName)
      }
      return t(key)
    }).join('、')
  }
  // 旧格式：先查完整匹配
  const full = t(text)
  if (full !== text) return full
  // 逐词替换
  return text.replace(/[一-鿿]+/g, (word) => {
    const translated = t(word)
    return translated !== word ? translated : word
  })
}
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Picture, Edit, EditPen, HomeFilled, Clock, ArrowLeft, ArrowRight, ArrowDown, ArrowUp, Collection, Check, DataAnalysis, PieChart, ZoomIn, CircleCheckFilled, MagicStick
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getDisplayAge } from '../tubi/utils'
import { sealsApi } from '../api'
import api from '../api'
import TubiDeepZoomDialog from '../components/tubi/TubiDeepZoomDialog.vue'
import SealLightbox from '../components/seal/SealLightbox.vue'
import { useAuthStore } from '../stores/authStore'

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const authStore = useAuthStore()

function canEditItem(item) {
  return authStore.isAdmin || (authStore.isEditor && item.owner_id === authStore.userId)
}

// page_role
function roleLabel(role) { return t('role.' + (role || 'other')) }
function roleBadge(role) { return { cover: t('role.cover')[0], back_cover: t('role.back_cover')[0], inscription: t('role.inscription')[0], accessory: t('role.accessory')[0], other: t('role.other')[0] }[role] || '?' }

// 我的意见
const showSuggestDialog = ref(false)
const suggestForm = reactive({
  field_name: 'title',
  old_value: '',
  new_value: '',
  change_summary: ''
})
const submitting = ref(false)
const suggestAnnotationSaved = ref(false)

function getSuggestFieldValue(fieldName) {
  if (!props.currentImage) return ''
  if (fieldName === 'inscription_content') {
    return props.currentImage.inscriptionContent || ''
  }
  if (fieldName === 'annotation_regions') {
    return t('suggest.annotation_view')
  }
  const val = props.currentImage[fieldName]
  return val !== null && val !== undefined ? String(val) : ''
}

function updateSuggestOldValue() {
  suggestForm.old_value = getSuggestFieldValue(suggestForm.field_name)
  suggestForm.new_value = suggestForm.old_value
}

watch(() => suggestForm.field_name, updateSuggestOldValue)

const ANNOTATE_SUGGEST_FLAG = 'suggest_annotation_done_'

function openSuggestEdit() {
  if (!props.currentImage) return
  if (!props.currentImage.library_id) {
    ElMessage.warning(t('suggest.no_library'))
    return
  }
  // 检查先前打开的标注审阅是否已保存
  const id = props.currentImage.id || props.currentImage.image_id
  suggestAnnotationSaved.value = !!localStorage.getItem(ANNOTATE_SUGGEST_FLAG + id)
  suggestForm.field_name = 'title'
  suggestForm.old_value = getSuggestFieldValue('title')
  suggestForm.new_value = suggestForm.old_value
  suggestForm.change_summary = ''
  showSuggestDialog.value = true
}

function openAnnotatorSuggest() {
  if (!props.currentImage) return
  const imageId = props.currentImage.image_id || props.currentImage.id
  if (!imageId) {
    ElMessage.warning(t('suggest.no_artwork_id'))
    return
  }
  const libId = props.currentImage.library_id
  const artworkDbId = props.currentImage.id || props.currentImage.db_id
  const role = authStore.userInfo?.role || 'guest'
  // 同时存入 sessionStorage 和 URL 参数（sessionStorage 在部分浏览器跨 window.open 不可靠）
  sessionStorage.setItem('suggest_library_id', String(libId))
  sessionStorage.setItem('suggest_artwork_id', String(artworkDbId))
  window.open(`/#/annotate/${imageId}?mode=suggest&role=${role}&lib=${libId}&artwork=${artworkDbId}`, '_blank')
}

function suggestDialogClosed() {
  // 关闭对话框时检查标注保存标志
  const id = props.currentImage?.id || props.currentImage?.image_id
  if (id && localStorage.getItem(ANNOTATE_SUGGEST_FLAG + id)) {
    suggestAnnotationSaved.value = true
    localStorage.removeItem(ANNOTATE_SUGGEST_FLAG + id)
  }
}

async function handleSubmitChange() {
  if (!suggestForm.new_value) {
    ElMessage.warning(t('suggest.enter_new_value'))
    return
  }
  if (!suggestForm.change_summary || !suggestForm.change_summary.trim()) {
    ElMessage.warning(t('suggest.enter_desc'))
    return
  }
  const libId = props.currentImage.library_id
  if (!libId) {
    ElMessage.error(t('suggest.no_library_detail'))
    return
  }
  submitting.value = true
  try {
    const data = {
      artwork_id: props.currentImage.id || props.currentImage.db_id,
      field_name: suggestForm.field_name,
      old_value: suggestForm.old_value,
      new_value: suggestForm.new_value,
      change_summary: suggestForm.change_summary,
      request_type: suggestForm.field_name === 'inscription_content' ? 'edit_inscription' : 'edit_field'
    }
    await api.post(`/libraries/${libId}/requests`, data)
    ElMessage.success(t('suggest.submitted'))
    showSuggestDialog.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('suggest.submit_fail'))
  } finally {
    submitting.value = false
  }
}

// 版本历史
const showRevisionsDialog = ref(false)
const revisions = ref([])
const revisionsLoading = ref(false)

async function openRevisions() {
  if (!props.currentImage) return
  showRevisionsDialog.value = true
  revisionsLoading.value = true
  try {
    const resp = await api.get(`/artworks/${props.currentImage.id}/revisions`)
    revisions.value = resp.revisions || []
  } catch (e) {
    ElMessage.error(t('revision.load_fail'))
    revisions.value = []
  } finally {
    revisionsLoading.value = false
  }
}

async function handleRollback(rev) {
  try {
    await ElMessageBox.confirm(
      t('revision.confirm_msg', { num: rev.revision_number }),
      t('revision.confirm_title'),
      { confirmButtonText: t('revision.confirm_btn'), cancelButtonText: t('suggest.cancel'), type: 'warning' }
    )
    await api.post(`/artworks/${props.currentImage.id}/rollback/${rev.id}`)
    ElMessage.success(t('revision.success'))
    showRevisionsDialog.value = false
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.detail || t('revision.fail'))
    }
  }
}

// 印章显示
const sealLibraryCache = ref([])
const detailSealImageMap = ref({})
const detailSealTypeMap = ref({})

const sealLightboxVisible = ref(false)
const selectedSealForLightbox = ref({ name: '', images: [] })

function openSealLightbox(name) {
  let found = sealLibraryCache.value.find(s => s.name === name)
  if (!found) {
    loadSealByName(name)
    return
  }
  selectedSealForLightbox.value = found
  sealLightboxVisible.value = true
}

async function loadSealByName(name) {
  try {
    const artist = props.currentImage?.artist || ''
    const res = await sealsApi.getByName(name, { artist })
    if (res.success && res.seal) {
      const s = res.seal
      sealLibraryCache.value.push(s)
      detailSealImageMap.value[s.name] = !!(s.images && s.images.length > 0)
      if (s.seal_type) detailSealTypeMap.value[s.name] = s.seal_type
      selectedSealForLightbox.value = s
      sealLightboxVisible.value = true
      return
    }
  } catch (e) { /* 静默 */ }
  ElMessage.info(t('seal.not_in_library', { name }))
}

const detailSealTags = computed(() => {
  const content = props.currentImage?.sealContent || ''
  if (!content) return []
  const cleaned = content.replace(/^作者印[：:]\s*/, '')
  return cleaned.split(/[、，,]/).map(n => n.trim()).filter(n => n).map(n => ({
    name: n,
    seal_type: detailSealTypeMap.value[n] || null
  }))
})

async function loadSealLibraryForDetail() {
  if (!props.currentImage?.sealContent) return
  try {
    const artist = props.currentImage.artist || ''
    const res = await sealsApi.list({ limit: 500, artist })
    if (res.success) {
      sealLibraryCache.value = res.seals || []
      const imgMap = {}, typeMap = {}
      for (const s of sealLibraryCache.value) {
        imgMap[s.name] = !!(s.images && s.images.length > 0)
        if (s.seal_type) typeMap[s.name] = s.seal_type
      }
      detailSealImageMap.value = imgMap
      detailSealTypeMap.value = typeMap
    }
  } catch (e) { console.error('加载印章库失败', e) }
}

onMounted(() => { loadSealLibraryForDetail() })

const props = defineProps({
  currentImage: { type: Object, required: true },
  analysis: {
    type: Object,
    default: () => ({
      status: 'pending',
      progress: 0,
      step: '准备分析...',
      areaStats: { inscriptionPercent: 0, paintingPercent: 0, blankPercent: 0 },
      note: '',
      positionAnalysis: null
    })
  },
  prevImage: { type: Object, default: null },
  nextImage: { type: Object, default: null },
  albumNavigation: { type: Object, default: () => ({ is_in_album: false, items: [] }) },
  historyList: { type: Array, default: () => [] },
  getDetailAllTags: { type: Function, default: () => [] }
})

watch(() => props.currentImage, (img) => {
  if (img && img.sealContent && !sealLibraryCache.value.length) {
    loadSealLibraryForDetail()
  }
})

// 兼容旧的 prop 访问方式（向后兼容）
const analyzeStatus = computed(() => props.analysis?.status || 'pending')
const analyzeProgress = computed(() => props.analysis?.progress || 0)
const analyzingStep = computed(() => props.analysis?.step || '准备分析...')
const areaStats = computed(() => props.analysis?.areaStats || { inscriptionPercent: 0, paintingPercent: 0, blankPercent: 0 })
const analysisNote = computed(() => props.analysis?.note || '')
const positionAnalysis = computed(() => props.analysis?.positionAnalysis || null)

const areaPercentile = computed(() => {
  const myPct = areaStats.value.inscriptionPercent
  if (!myPct || !props.currentImage?.artist || !props.historyList?.length) return null
  const sameArtist = props.historyList.filter(i => i.artist === props.currentImage.artist && i.inscriptionPercent != null && i.inscriptionPercent > 0)
  if (sameArtist.length < 5) return null
  const below = sameArtist.filter(i => i.inscriptionPercent < myPct).length
  return Math.round(below / sameArtist.length * 100)
})

const emit = defineEmits([
  'back', 'edit-current', 'open-upload', 'auto-analyze',
  'navigate', 'navigate-album', 'open-annotator',
  'filter-by-tag', 'history-item-click'
])

// ── 相关作品（同作者，前3 + 当前 + 后8 = 12条）──
const relatedWorks = computed(() => {
  if (!props.currentImage || !props.historyList?.length) return []
  const currentId = props.currentImage.id
  const currentArtist = props.currentImage.artist
  if (!currentId || !currentArtist) return []
  const sameArtist = props.historyList.filter(item => item.artist === currentArtist)
  const idx = sameArtist.findIndex(item => item.id === currentId)
  if (idx < 0) return sameArtist.slice(0, 12)
  const start = Math.max(0, idx - 3)
  return sameArtist.slice(start, start + 12)
})

function openRanking() {
  window.open('/#/tubi/list', '_blank')
}

// ── 册页缩略图滚轮横向滚动 ──────────────────────
const albumThumbsRef = ref(null)

function onAlbumThumbnailsWheel(e) {
  const el = albumThumbsRef.value || e.currentTarget
  if (e.deltaY !== 0) {
    el.scrollLeft += e.deltaY
  }
}

function scrollAlbumThumbs(direction) {
  const el = albumThumbsRef.value
  if (!el) return
  el.scrollBy({ left: direction * 120, behavior: 'smooth' })
}

// ── 悬浮示意图 ────────────────────────────────
const showDiagramOverlay = ref(true)
const showSpatialEmotion = ref(true)
const inscriptionMode = ref(locale.value === 'en' ? 'english' : 'original')

// 空间情绪数据
const contentAnalysis = computed(() => {
  const ca = props.currentImage?.contentAnalysis
  if (!ca) return null
  return typeof ca === 'string' ? (() => { try { return JSON.parse(ca) } catch { return null } })() : ca
})
const spatialEmotion = computed(() => contentAnalysis.value?.spatial_emotion || null)
const sortedSpatialSignals = computed(() => {
  const signals = spatialEmotion.value?.signals
  if (!signals) return []
  const priority = { negative_intense: 5, positive_unrestrained: 5, negative_controlled: 3, positive_defiant: 3, positive_resolved: 2, negative: 2, positive: 2, neutral_controlled: 1, neutral_balanced: 1, neutral: 0 }
  return [...signals].sort((a, b) => (priority[b.emotion_key] || 0) - (priority[a.emotion_key] || 0))
})
const combinedSentiment = computed(() => contentAnalysis.value?.combined_sentiment || null)
const dimensionPolarities = computed(() => combinedSentiment.value?.dimension_polarities || {})
const conflictScore = computed(() => combinedSentiment.value?.conflict_score ?? null)

// v3.2: 解析 LLM 三段式解读文本
const llmNarrativeSections = computed(() => {
  const summary = contentAnalysis.value?.llm_analysis?.combined?.summary
  if (!summary) return null
  const text = String(summary)
  // 匹配 "积极面：" 或 "消极面：" 或 "综合判断：" 或 "复杂面："
  const positive = text.match(/积极面[：:]\s*([\s\S]*?)(?=消极面[：:]|综合判断[：:]|复杂面[：:]|$)/)
  const negative = text.match(/消极面[：:]\s*([\s\S]*?)(?=积极面[：:]|综合判断[：:]|复杂面[：:]|$)/)
  const verdict = text.match(/(?:综合判断|复杂面)[：:]\s*([\s\S]*?)$/)
  if (!positive && !negative && !verdict) return null
  return {
    positive: positive ? positive[1].trim() : '',
    negative: negative ? negative[1].trim() : '',
    verdict: verdict ? verdict[1].trim() : '',
  }
})
const displayScore = computed(() => {
  const cs = combinedSentiment.value
  if (cs?.vader_normalized != null) return cs.vader_normalized
  if (cs?.combined_score != null) return cs.combined_score
  return contentAnalysis.value?.sentiment?.emotion_score ?? 0
})
const isVaderScore = computed(() => combinedSentiment.value?.vader_normalized != null)
const calibratedWeights = computed(() => combinedSentiment.value?.weights || { text: 0.05, spatial: 0.569, seal: 0.381 })

// 八维度数据行（用于推导过程公式表格，兼容 v2/v3）
const dimensionRows = computed(() => {
  const cs = combinedSentiment.value
  if (!cs) return []
  const w = cs.weights || {}
  const hd = cs.has_data || {}
  const dims = [
    { nameKey: 'factor.text', raw: cs.text_score || 0, weight: w.text || 0.40, confidence: hd.text ? 1.0 : 0.3, hasData: hd.text ?? true },
    { nameKey: 'factor.spatial', raw: cs.spatial_score || 0, weight: w.spatial || 0.20, confidence: hd.spatial ? 0.8 : 0.3, hasData: hd.spatial ?? false },
    { nameKey: 'factor.painting', raw: cs.painting_score || 0, weight: w.painting || 0.10, confidence: hd.painting ? 0.7 : 0.2, hasData: hd.painting ?? false },
    { nameKey: 'factor.size', raw: cs.size_score || 0, weight: w.size || 0.05, confidence: hd.size ? 0.5 : 0.2, hasData: hd.size ?? false },
    { nameKey: 'factor.period', raw: cs.time_score || 0, weight: w.period || 0.10, confidence: hd.period ? 0.8 : 0.3, hasData: hd.period ?? false },
    { nameKey: 'factor.seal', raw: cs.seal_score || 0, weight: w.seal || 0.10, confidence: hd.seal ? 0.6 : 0.2, hasData: hd.seal ?? false },
    { nameKey: 'factor.theme', raw: cs.theme_score || 0, weight: w.theme || 0.05, confidence: hd.theme ? 0.9 : 0.2, hasData: hd.theme ?? false },
    { nameKey: 'factor.brush_ink', raw: cs.brush_ink_score || 0, weight: w.brush_ink || 0.00, confidence: 0, hasData: false, placeholder: true },
  ]
  const dp = cs.dimension_polarities || {}
  const combinedPol = cs.polarity || 'neutral'
  // 计算每个维度的贡献、归一化分数和极性
  const totalWeight = dims.reduce((sum, d) => sum + d.weight * (d.hasData ? 1.0 : 0.2), 0)
  return dims.map(d => {
    const dimKey = d.nameKey.replace('factor.', '')
    const dimPol = dp[dimKey] || 'neutral'
    return {
      ...d,
      normalized: vaderNorm(d.raw),
      contribution: totalWeight > 0 ? (d.weight * (d.hasData ? 1.0 : 0.2) * d.raw) / totalWeight : 0,
      polarity: dimPol,
      conflicted: d.hasData && dimPol !== 'neutral' && combinedPol !== 'neutral' &&
        ((dimPol === 'positive' && combinedPol.includes('negative')) ||
         (dimPol === 'negative' && combinedPol.includes('positive'))),
    }
  })
})

// 八维度展开状态
const expandedDims = ref(new Set())
function toggleDimDetail(key) {
  if (expandedDims.value.has(key)) {
    expandedDims.value.delete(key)
  } else {
    expandedDims.value.add(key)
  }
}

// 获取维度详情
function getDimDetail(dimKey) {
  const cs = combinedSentiment.value
  if (!cs?.dimension_details) return []
  const key = dimKey.replace('factor.', '') // text, spatial, painting, size, period, seal, theme
  const detail = cs.dimension_details[key] || {}

  // 文字维度：显示匹配的词和分数
  if (key === 'text' && detail.signals?.length) {
    return detail.signals.map(s => ({
      label: s.word,
      score: s.score,
      desc: s.source === 'lexicon' ? '词典' : '规则',
    }))
  }

  // 空间维度：显示布局类型
  if (key === 'spatial' && detail.signals?.length) {
    return detail.signals.map(s => ({
      label: s.type || s.emotion || '',
      score: s.score || 0,
      desc: s.desc || '',
    }))
  }

  // 画材维度
  if (key === 'painting' && detail.signals?.length) {
    return detail.signals.map(s => ({
      label: s.visual_emotion || '',
      score: s.emotion_offset || 0,
      desc: s.matched_keywords?.join('、') || '',
    }))
  }

  // 尺寸维度
  if (key === 'size') {
    return [{
      label: `${detail.width || '?'}×${detail.height || '?'}cm`,
      score: cs.size_score || 0,
      desc: detail.category || '',
    }]
  }

  // 时期维度
  if (key === 'period') {
    return [{
      label: `${detail.year || '?'}年`,
      score: cs.time_score || 0,
      desc: detail.period_phase || '',
    }]
  }

  // 印章维度
  if (key === 'seal' && detail.signals?.length) {
    return detail.signals.map(s => ({
      label: s.seal || '',
      score: s.raw_score || 0,
      desc: s.desc || '',
    }))
  }

  // 主题维度
  if (key === 'theme' && detail.signals?.length) {
    return detail.signals.map(s => ({
      label: s.theme || '',
      score: s.bonus || 0,
      desc: s.note || (s.has_override ? s.polarity : '无覆盖规则'),
    }))
  }

  return [{ label: '无详细数据', score: 0, desc: '' }]
}

// VADER 归一化函数（前端版本，α=8）
function vaderNorm(raw) {
  if (!raw || raw === 0) return 0
  return raw / Math.sqrt(raw * raw + 8)
}

// ── v3.1: 复杂极性辅助函数 ──
function polarityKey(polarity) {
  const map = {
    positive: 'polarity.positive', negative: 'polarity.negative', neutral: 'polarity.neutral',
    complex_positive: 'polarity.complex_positive', complex_negative: 'polarity.complex_negative',
    complex_balanced: 'polarity.complex_balanced', ambiguous: 'polarity.ambiguous',
  }
  return map[polarity] || 'polarity.neutral'
}
function polarityLabelColor(polarity) {
  if (polarity?.startsWith('complex_')) return '#e6a23c'
  if (polarity === 'positive') return '#3cb88b'
  if (polarity === 'negative') return '#e07a5f'
  if (polarity === 'ambiguous') return '#e6a23c'
  return '#999'
}

// 各维度归一化分数
const textNorm = computed(() => vaderNorm(combinedSentiment.value?.text_score ?? contentAnalysis.value?.sentiment?.emotion_score))
const spatialNorm = computed(() => vaderNorm(combinedSentiment.value?.spatial_score))
const sealNorm = computed(() => vaderNorm(combinedSentiment.value?.seal_score ?? sealEmotion.value?.composite_score))
const sealEmotion = computed(() => contentAnalysis.value?.seal_emotion || null)

// 文字情绪摘要
const textSentimentSummary = computed(() => {
  const s = contentAnalysis.value?.sentiment
  if (!s) return ''
  const themes = contentAnalysis.value?.themes
  const themeNames = themes?.slice(0, 2).map(theme => t(theme.name)).join(locale === 'en' ? ', ' : '、') || ''
  const phase = contentAnalysis.value?.period_phase || ''
  const parts = []
  if (phase) parts.push(t(phase))
  if (themeNames) parts.push(themeNames)
  return parts.join(' · ') || '—'
})

// ── 头脑 SVG 颜色计算 ──────────────────────────
// 统一色调：暖色系（红棕←消极）↔ 中性灰 ↔ 冷色系（蓝绿→积极）
const polarityColor = (polarity, intensity = 0.5) => {
  const s = Math.min(1, Math.abs(intensity))
  if (polarity === 'positive') return `hsl(160, ${50 + s * 30}%, ${50 - s * 10}%)`
  if (polarity === 'negative') return `hsl(10, ${40 + s * 35}%, ${52 - s * 8}%)`
  return 'hsl(40, 15%, 65%)'
}
const textBrainColor = computed(() => {
  const cs = combinedSentiment.value
  if (!cs?.vader_normalized) return 'hsl(40, 15%, 70%)'
  const score = cs.text_score || 0
  const norm = vaderNorm(score)
  return polarityColor(norm > 0 ? 'positive' : norm < 0 ? 'negative' : 'neutral', Math.abs(norm))
})
const spatialBrainColor = computed(() => {
  const cs = combinedSentiment.value
  if (!cs?.spatial_score) return 'hsl(40, 15%, 70%)'
  const norm = vaderNorm(cs.spatial_score)
  return polarityColor(norm > 0 ? 'positive' : norm < 0 ? 'negative' : 'neutral', Math.abs(norm))
})
const combinedBrainColor = computed(() => {
  const cs = combinedSentiment.value
  if (!cs?.vader_normalized) return 'hsl(40, 15%, 65%)'
  return polarityColor(cs.polarity || 'neutral', Math.abs(cs.vader_normalized))
})

// ── Canvas 相关 ────────────────────────────────
const canvasRef = ref(null)
let canvas = null
let ctx = null

// ── 饼图相关 ──────────────────────────────────
const pieChartRef = ref(null)
const themeChartRef = ref(null)
let themeChart = null
let pieChart = null
let pieChartUpdateRaf = 0

// ── 原图预览缩放 ──────────────────────────────
const imagePreviewVisible = ref(false)
const currentPreviewImage = ref('')
const currentPreviewDzi = ref('')

function openImagePreview(imageUrl, dziUrl) {
  currentPreviewImage.value = imageUrl
  currentPreviewDzi.value = dziUrl || ''
  imagePreviewVisible.value = true
}

// ── 解析 regions ──────────────────────────────
function parseRegions(regionsData) {
  if (!regionsData) return { inscription_regions: [], painting_regions: [], blank_regions: [], margin_regions: [] }
  let parsed = regionsData
  if (typeof parsed === 'string') {
    try { parsed = JSON.parse(parsed) } catch { return { inscription_regions: [], painting_regions: [], blank_regions: [], margin_regions: [] } }
  }
  return {
    inscription_regions: parsed.inscription_regions || [],
    painting_regions: parsed.painting_regions || [],
    blank_regions: parsed.blank_regions || [],
    margin_regions: parsed.margin_regions || []
  }
}

// ── 图表 computed ──────────────────────────────
const diagramRegions = computed(() => {
  const currentRegions = parseRegions(props.currentImage?.regions)
  if (!currentRegions.inscription_regions?.length) {
    return { inscription_regions: [], painting_regions: [], blank_regions: [], margin_regions: [] }
  }
  return currentRegions
})

function toDiagramPoints(reg) {
  if (!reg?.points || reg.points.length < 2) return ''
  const w = props.currentImage?.width || 1000
  const h = props.currentImage?.height || 1000
  const viewBoxH = 100 * h / w
  const pts = reg.points
  if (pts.length === 2) {
    const [p1, p2] = pts
    const rect = [
      { x: Math.min(p1.x, p2.x), y: Math.min(p1.y, p2.y) },
      { x: Math.max(p1.x, p2.x), y: Math.min(p1.y, p2.y) },
      { x: Math.max(p1.x, p2.x), y: Math.max(p1.y, p2.y) },
      { x: Math.min(p1.x, p2.x), y: Math.max(p1.y, p2.y) },
    ]
    return rect.map((p) => `${(p.x / w * 100).toFixed(1)},${(p.y / h * viewBoxH).toFixed(1)}`).join(' ')
  }
  return pts.map((p) => `${(p.x / w * 100).toFixed(1)},${(p.y / h * viewBoxH).toFixed(1)}`).join(' ')
}

// ── 情感强度计算（兼容新旧数据）──
function getSentimentIntensity(sentiment) {
  if (!sentiment) return 0
  if (sentiment.intensity != null) return sentiment.intensity
  // 旧数据兜底：用 emotion_score 绝对值估算（假设最大范围是2）
  return Math.min(Math.abs(sentiment.emotion_score || 0) / 2, 1)
}

// ── 情感文本映射（将英文极性映射为带样式的中文标签）──
function mapPolarityText(text) {
  if (!text) return ''
  return text
    .replace(/\bpositive\b/g, `<span class="pol-label pol-positive">${t('polarity.positive')}</span>`)
    .replace(/\bnegative\b/g, `<span class="pol-label pol-negative">${t('polarity.negative')}</span>`)
    .replace(/\bneutral\b/g, `<span class="pol-label pol-neutral">${t('polarity.neutral')}</span>`)
}

function getInscriptionAreaClass() {
  if (!positionAnalysis.value) return ''
  if (positionAnalysis.value.form_types?.length) {
    const matched = positionAnalysis.value.form_types.filter(f => f.matched)
    if (matched.length) return `area-code-${matched[0].code}`
  }
  const layoutType = positionAnalysis.value.layout_type
  if (layoutType === t('area.corner')) return 'area-corner'
  if (layoutType === t('area.frame')) return 'area-frame'
  if (layoutType === t('area.interleaved')) return 'area-interleaved'
  if (layoutType === t('area.full')) return 'area-full'
  if (layoutType === t('area.independent')) return 'area-independent'
  return ''
}

function getInscriptionAreaStyle() {
  if (!positionAnalysis.value) return {}
  const pos = positionAnalysis.value.position
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  const width = props.currentImage?.width || 1000
  const height = props.currentImage?.height || 1000

  const leftPct = (ml / width) * 100
  const rightPct = (mr / width) * 100
  const topPct = (mt / height) * 100
  const bottomPct = (mb / height) * 100
  const areaWidth = 100 - leftPct - rightPct
  const areaHeight = 100 - topPct - bottomPct

  if (areaWidth > 3 && areaHeight > 3 && areaWidth < 95 && areaHeight < 95) {
    return {
      left: leftPct.toFixed(1) + '%',
      top: topPct.toFixed(1) + '%',
      width: areaWidth.toFixed(1) + '%',
      height: areaHeight.toFixed(1) + '%'
    }
  }

  const fallbacks = {
    '左上': { left: '5%', top: '5%', width: '30%', height: '25%' },
    '右上': { right: '5%', top: '5%', width: '30%', height: '25%' },
    '左下': { left: '5%', bottom: '5%', width: '30%', height: '25%' },
    '右下': { right: '5%', bottom: '5%', width: '30%', height: '25%' },
    '左侧': { left: '5%', top: '20%', width: '25%', height: '60%' },
    '右侧': { right: '5%', top: '20%', width: '25%', height: '60%' },
    '上方': { left: '20%', top: '5%', width: '60%', height: '20%' },
    '底部': { left: '20%', bottom: '5%', width: '60%', height: '20%' },
  }
  return fallbacks[pos] || { left: '35%', top: '35%', width: '30%', height: '30%' }
}

function getEdgeDistanceShortText() {
  if (!positionAnalysis.value) return ''
  const ml = positionAnalysis.value.margin_left || 0
  const mr = positionAnalysis.value.margin_right || 0
  const mt = positionAnalysis.value.margin_top || 0
  const mb = positionAnalysis.value.margin_bottom || 0
  const margins = [
    { name: '左', val: ml }, { name: '右', val: mr },
    { name: '上', val: mt }, { name: '下', val: mb }
  ]
  const minMargin = margins.reduce((min, cur) => cur.val < min.val ? cur : min)
  return `${minMargin.name}${Math.round(minMargin.val)}`
}

// ── Canvas 初始化和绘制 ───────────────────────
function initCanvas() {
  if (!canvasRef.value || !props.currentImage) return

  const imageUrl = props.currentImage.url || props.currentImage.annotatedImageUrl
  if (!imageUrl) return

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
  img.onerror = () => console.error('Failed to load image:', imageUrl)
  img.src = imageUrl
}

function drawRegions() {
  if (!ctx || !canvas || !props.currentImage) return

  const imageUrl = props.currentImage.url || props.currentImage.annotatedImageUrl
  if (!imageUrl) return

  const regions = parseRegions(props.currentImage.regions)
  const scaleX = canvas.width / props.currentImage.width
  const scaleY = canvas.height / props.currentImage.height

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    const colors = {
      inscription: 'rgba(220, 92, 92, 0.3)',
      painting: 'rgba(74, 144, 217, 0.28)',
      blank: 'rgba(90, 184, 112, 0.25)'
    }
    const borderColors = {
      inscription: '#dc5c5c',
      painting: '#4a90d9',
      blank: '#5ab870'
    }

    function drawPolygonRegion(reg, color, borderColor) {
      if (reg.points && Array.isArray(reg.points) && reg.points.length >= 3) {
        ctx.beginPath()
        reg.points.forEach((point, index) => {
          const x = point.x * scaleX
          const y = point.y * scaleY
          if (index === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        })
        ctx.closePath()
        ctx.fillStyle = color
        ctx.fill()
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2
        ctx.stroke()
      } else if (reg.x1 !== undefined && reg.y1 !== undefined && reg.x2 !== undefined && reg.y2 !== undefined) {
        ctx.fillStyle = color
        ctx.fillRect(reg.x1 * scaleX, reg.y1 * scaleY, (reg.x2 - reg.x1) * scaleX, (reg.y2 - reg.y1) * scaleY)
        ctx.strokeStyle = borderColor
        ctx.lineWidth = 2
        ctx.strokeRect(reg.x1 * scaleX, reg.y1 * scaleY, (reg.x2 - reg.x1) * scaleX, (reg.y2 - reg.y1) * scaleY)
      }
    }

    regions.inscription_regions?.forEach(reg => drawPolygonRegion(reg, colors.inscription, borderColors.inscription))
    regions.painting_regions?.forEach(reg => drawPolygonRegion(reg, colors.painting, borderColors.painting))
    regions.blank_regions?.forEach(reg => drawPolygonRegion(reg, colors.blank, borderColors.blank))
  }
  img.onerror = () => console.error('Failed to load image in drawRegions:', imageUrl)
  img.src = imageUrl
}

// ── 饼图更新 ─────────────────────────────────
function updatePieChart() {
  if (!pieChartRef.value) {
    if (pieChartUpdateRaf) cancelAnimationFrame(pieChartUpdateRaf)
    pieChartUpdateRaf = requestAnimationFrame(() => {
      pieChartUpdateRaf = 0
      updatePieChart()
    })
    return
  }

  const container = pieChartRef.value
  if (container.clientWidth === 0 || container.clientHeight === 0) {
    if (pieChartUpdateRaf) cancelAnimationFrame(pieChartUpdateRaf)
    pieChartUpdateRaf = requestAnimationFrame(() => {
      pieChartUpdateRaf = 0
      updatePieChart()
    })
    return
  }

  if (!pieChart) {
    pieChart = echarts.init(pieChartRef.value)
  }

  const insc = areaStats.value.inscriptionPercent || 0
  const paint = areaStats.value.paintingPercent || 0
  const blank = areaStats.value.blankPercent || 0

  const rawItems = [
    { name: t('area.inscription'), value: insc, color: '#d4846a' },
    { name: t('area.painting'), value: paint, color: '#7ba3c4' },
    { name: t('area.blank'), value: blank, color: '#a8c97a' },
  ].filter(i => i.value > 0)

  rawItems.sort((a, b) => b.value - a.value)

  const rankConfigs = [
    { offset: 30, percentSize: 20, nameSize: 13 },
    { offset: 18, percentSize: 16, nameSize: 10 },
    { offset: 6,  percentSize: 12, nameSize: 9 },
  ]

  const data = rawItems.map((item, idx) => {
    const cfg = rankConfigs[idx] || rankConfigs[rankConfigs.length - 1]
    const percentText = `${item.value.toFixed(2).replace(/\.00$/, '')}%`
    // 文字小于9px 或 扇区小于12% 时外置黑字（14%以上内显）
    const isTooSmall = cfg.nameSize < 9 || item.value < 10

    return {
      value: item.value,
      name: item.name,
      selected: true,
      selectedOffset: cfg.offset,
      label: isTooSmall
        ? {
            position: 'outside',
            formatter: `{percentOut|${percentText}}\n{nameOut|${item.name}}`,
            color: '#333',
            rich: {
              percentOut: { fontSize: 10, fontWeight: 700, color: '#333', lineHeight: 12 },
              nameOut: { fontSize: 9, fontWeight: 500, color: '#555', lineHeight: 11 },
            }
          }
        : {
            position: 'inside',
            formatter: `{percent|${percentText}}\n{name|${item.name}}`,
            rich: {
              percent: { fontSize: cfg.percentSize, fontWeight: 700, color: '#fff', lineHeight: cfg.percentSize + 2 },
              name: { fontSize: cfg.nameSize, fontWeight: 500, color: 'rgba(255,255,255,0.92)', lineHeight: cfg.nameSize + 2 },
            }
          },
      labelLine: isTooSmall ? { show: true, length: 6, length2: 3, smooth: true } : { show: false },
      itemStyle: {
        color: item.color,
        borderRadius: 6,
        borderColor: item.color,
        borderWidth: 1
      }
    }
  })

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (p) => `${p.name}: ${p.value.toFixed(2).replace(/\.00$/, '')}%`
    },
    series: [{
      type: 'pie',
      radius: ['20%', '68%'],
      center: ['50%', '50%'],
      roseType: 'area',
      selectedMode: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: {
        formatter: '{b}\n{d}%',
        fontSize: 11,
        color: '#555'
      },
      data: rawItems.map(item => ({
        value: item.value,
        name: item.name,
        itemStyle: { color: item.color }
      }))
    }]
  }

  pieChart.setOption(option, true)
}

// ── 监听 currentImage 变化 ─────────────────────
watch(() => props.currentImage, async (newVal) => {
  if (!newVal) return
  await nextTick()
  initCanvas()
  if (analyzeStatus.value === 'analyzed') {
    drawRegions()
    setTimeout(() => { updatePieChart(); updateThemeChart() }, 300)
  }
}, { immediate: true })

// 监听 areaStats 变化更新饼图
watch(() => areaStats.value, () => {
  if (analyzeStatus.value === 'analyzed') {
    nextTick(() => updatePieChart())
  }
}, { deep: true })

// ── 主题柱状图 ─────────────────────────────────
function updateThemeChart() {
  if (!themeChartRef.value) return
  if (!themeChart) {
    themeChart = echarts.init(themeChartRef.value)
  }
  const themes = props.currentImage?.contentAnalysis?.themes
  if (!themes?.length) return

  const data = themes.map(theme => ({
    name: t(theme.name),
    value: Math.round(theme.confidence * 100)
  })).sort((a, b) => b.value - a.value)

  themeChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 0, right: 80, top: 2, bottom: 0, containLabel: true },
    xAxis: { show: false },
    yAxis: {
      type: 'category',
      data: data.map(d => d.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { fontSize: 12, color: '#555' }
    },
    series: [{
      type: 'bar',
      data: data.map((d, i) => ({
        value: d.value,
        itemStyle: {
          color: ['#d4846a', '#7ba3c4', '#a8c97a', '#b8a47e', '#c4a87a'][i % 5],
          borderRadius: [0, 4, 4, 0]
        }
      })),
      barWidth: 16,
      label: {
        show: true,
        position: 'right',
        fontSize: 11,
        color: '#888',
        formatter: (params) => `${t('theme.confidence')} ${params.value}%`
      }
    }]
  }, true)
}

// Watch for theme changes
watch(() => props.currentImage?.contentAnalysis?.themes, (themes) => {
  if (themes?.length) {
    nextTick(() => updateThemeChart())
  }
}, { deep: true, immediate: true })



function handleResize() {
  pieChart?.resize()
  themeChart?.resize()
  if (props.currentImage) {
    initCanvas()
    if (analyzeStatus.value === 'analyzed') drawRegions()
  }
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  pieChart?.dispose()
  themeChart?.dispose()
  pieChart = null
})

defineExpose({
  updatePieChart,
  initCanvas
})
</script>

<style src="../tubi/TubiAnalysis.css" scoped></style>

<style scoped>
/* upload-card 去背景/边框/阴影，避免双层卡片感 */
:deep(.upload-card) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
:deep(.upload-card .el-card__body) {
  padding: 0 !important;
  overflow: visible;
}
:deep(.upload-card) {
  overflow: visible;
}
:deep(.upload-card .image-display) {
  padding: 0;
}
:deep(.upload-card .analysis-result-layout) {
  margin: 0;
}

/* 卡片背景调亮，与页面背景拉开层次 */
:deep(.annotated-image-section) {
  background: #faf9f7;
}
:deep(.analysis-right-col .inscription-note-main),
:deep(.analysis-right-col .seal-note-main),
:deep(.analysis-right-col .stats-section),
:deep(.analysis-right-col .detail-tags-section) {
  background: #fff;
}
.artwork-info-card,
.spatial-analysis-card {
  background: #fff;
}

/* 所有卡片统一默认阴影，hover 加深 */
:deep(.annotated-image-section),
:deep(.analysis-right-col .inscription-note-main),
:deep(.analysis-right-col .seal-note-main),
:deep(.analysis-right-col .stats-section),
:deep(.analysis-right-col .detail-tags-section),
.artwork-info-card,
.spatial-analysis-card {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s ease;
}
:deep(.annotated-image-section:hover),
:deep(.analysis-right-col .inscription-note-main:hover),
:deep(.analysis-right-col .seal-note-main:hover),
:deep(.analysis-right-col .stats-section:hover),
:deep(.analysis-right-col .detail-tags-section:hover),
.artwork-info-card:hover,
.spatial-analysis-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}
:deep(.theme-sentiment-card) {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}
:deep(.theme-sentiment-card:hover) {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

/* 现代文翻译样式 */
.inscription-translation {
  margin-top: 10px;
  padding-top: 10px;
}
.translation-divider {
  height: 1px;
  background: linear-gradient(to right, transparent, #e8e6dc 20%, #e8e6dc 80%, transparent);
  margin-bottom: 8px;
}
.translation-label {
  margin-bottom: 8px;
}
/* 画作信息卡片（合并作者/年份/尺寸 + 操作按钮） */
.artwork-info-card {
  padding: 10px 12px;
  background: #faf9f7;
  border-radius: 8px;
  border: 1px solid #e8e4da;
}
.info-card-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 0;
}
.info-card-row + .info-card-row {
  border-top: 1px solid #ede9de;
}
.info-card-label {
  font-size: 11px;
  color: #8a7a5e;
  font-weight: 600;
  flex-shrink: 0;
  min-width: 28px;
}
.info-card-value {
  font-size: 13px;
  color: #333;
  font-weight: 500;
}
.info-card-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 8px;
  border-top: 1px solid #ede9de;
}

/* 我的意见对话框 */
.old-value-display {
  width: 100%;
  padding: 10px 12px;
  background: #f5f5f5;
  border: 1px solid #e8e4dc;
  border-radius: 6px;
  font-size: 13px;
  color: #888;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
  user-select: text;
  cursor: text;
}

/* 版本历史对话框 */
.rev-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.rev-number {
  font-weight: 700;
  font-size: 15px;
  color: #333;
}
.rev-summary {
  font-size: 13px;
  color: #666;
  margin: 4px 0;
}

.btn-action {
  flex: 1 1 0;
  min-width: 0;
  width: 0;
  font-size: 12px !important;
  box-shadow: none !important;
}
:deep(.btn-action .el-button__content) {
  font-size: 12px;
  justify-content: center;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}
:deep(.btn-action .el-button__content .el-icon) {
  flex-shrink: 0;
  font-size: 14px;
}
/* 作品信息表格 */
.image-info-header {
  justify-content: flex-start !important;
  display: flex !important;
}
.artwork-info-table { width: 100%; }
.info-row-horizontal {
  display: flex;
  gap: 8px;
  width: 100%;
}
.info-item {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px 10px;
  background: #f8f9fa;
  border-radius: 6px;
  transition: all 0.2s ease;
}
.info-item:nth-child(1) { flex: 0 0 30%; }
.info-item:nth-child(2) { flex: 0 0 35%; }
.info-item:nth-child(3) { flex: 0 0 35%; }
.info-item:hover {
  background: #f1f3f5;
  transform: translateY(-1px);
}
.info-label {
  font-size: 10px;
  color: #6b7280;
  font-weight: 500;
  letter-spacing: 0.02em;
}
.info-value {
  font-size: 11px;
  color: #111827;
  font-weight: 500;
  line-height: 1.3;
}
.translation-content {
  font-size: 13px;
  line-height: 1.8;
  color: #3d3d3a;
  font-style: italic;
  white-space: pre-wrap;
}

/* 导航按钮左右分布，标题居中 */
.navigation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.navigation-header :deep(.el-button) {
  flex: 0 0 auto;
  padding: 5px 8px;
  font-size: 12px;
}
.nav-title {
  flex: 1;
  text-align: center;
  font-size: 15px;
  font-weight: 700;
  color: #333;
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 6px;
  min-width: 0;
}

/* ── 响应式 ── */

/* 强制导航栏不换行（父级 card-header 有 flex-wrap: wrap） */
.navigation-header {
  flex-wrap: nowrap;
}

/* 手机：导航按钮更紧凑 */
@media (max-width: 768px) {
  .navigation-header :deep(.el-button) {
    padding: 5px 6px !important;
    font-size: 11px !important;
  }
  .nav-title {
    font-size: 14px;
  }
}

@media (max-width: 480px) {
  .navigation-header {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
  }
  .navigation-header :deep(.el-button) {
    flex: 0 1 auto !important;
    min-width: 0 !important;
    padding: 8px 10px !important;
    font-size: 0 !important;
  }
  .navigation-header :deep(.el-button .el-icon) {
    font-size: 16px !important;
  }
  .nav-title {
    font-size: 12px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
  }
}

/* 面积占比智能示意图标题与按钮同行 */
.annotated-image-section .section-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: left;
}
.btn-annotate {
  font-size: 11px;
  padding: 3px 10px;
  box-shadow: none !important;
}
/* 面积示意图容器（用于定位打勾徽章） */
.annotated-image-wrapper {
  position: relative;
  display: inline-block;
  width: 100%;
  background: linear-gradient(180deg, #ede8dc 0%, #e2dcd0 100%);
  border-radius: 6px;
  padding: 4px;
}

/* 手动标注打勾徽章 */
.manual-annotated-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 24px;
  height: 24px;
  background: rgba(76, 175, 80, 0.9);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 10;
}

/* 册页导航样式 */
.album-navigation {
  margin-top: 8px;
  padding: 8px;
  background: #faf8f3;
  border-radius: 8px;
  border: 1px solid #ede9de;
}
.album-nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.album-nav-title {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}
.album-nav-count {
  font-size: 11px;
  color: #8a8a7a;
}
.album-nav-scroll {
  display: flex;
  align-items: center;
  gap: 4px;
}
.album-nav-arrow {
  flex-shrink: 0;
  width: 22px;
  height: 38px;
  border: 1px solid #d4cfc5;
  border-radius: 4px;
  background: #faf9f7;
  color: #8a8a7a;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
  padding: 0;
}
.album-nav-arrow:hover {
  background: #f0ece3;
  color: #333;
  border-color: #b8a47e;
}
.album-nav-arrow:active {
  transform: scale(0.92);
}
.album-nav-thumbnails {
  display: flex;
  gap: 5px;
  overflow-x: auto;
  padding: 3px 0;
  scroll-behavior: smooth;
  scroll-snap-type: x mandatory;
  scrollbar-width: none; /* Firefox */
}
.album-nav-thumbnails::-webkit-scrollbar { display: none; /* Chrome/Safari */ }
.album-nav-thumbnail {
  flex-shrink: 0;
  position: relative;
  width: 38px;
  height: 38px;
  border-radius: 5px;
  border: 2px solid transparent;
  cursor: pointer;
  overflow: visible;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0ece3;
  scroll-snap-align: start;
}
.album-nav-thumbnail:hover {
  border-color: #4A90D9;
  transform: translateY(-1px);
}
.album-nav-thumbnail.active {
  border-color: #4A90D9;
  box-shadow: 0 0 0 2px rgba(74, 144, 217, 0.25);
}
.album-nav-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 3px;
}
.album-nav-thumbnail .thumb-placeholder {
  font-size: 12px;
  color: #8a8a7a;
  font-weight: 500;
  border-radius: 3px;
  overflow: hidden;
}

/* ── 悬浮布局示意图覆盖层 ── */
.diagram-hover-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 253, 245, 0.88);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px;
  pointer-events: none;
  z-index: 5;
}
.diagram-hover-overlay .diagram-svg {
  width: 100%;
  max-height: 100%;
}
.diagram-legend-overlay {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  font-size: 11px;
  color: #666;
}
.diagram-legend-overlay .legend-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 3px;
  vertical-align: middle;
}
.diagram-legend-overlay .legend-dot.inscription { background: rgba(201, 100, 66, 0.7); }
.diagram-legend-overlay .legend-dot.painting { background: rgba(74, 144, 217, 0.7); }
.diagram-legend-overlay .legend-dot.blank { background: rgba(144, 164, 174, 0.5); }
.diagram-legend-overlay .legend-dot.margin { background: rgba(51, 51, 51, 0.8); }

/* 余边图例多边形 - 灰色半透明 */
.diagram-hover-overlay .diagram-margin-poly {
  fill: rgba(51, 51, 51, 0.3);
  stroke: #333;
  stroke-width: 0.5;
  vector-effect: non-scaling-stroke;
}
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* ── 情绪解读卡片 ── */
.score-card {
  background: linear-gradient(135deg, #fdfcf8 0%, #f7f3ea 100%);
  border: 1px solid #e0d8c8;
  border-radius: 10px;
  padding: 14px 16px;
}
.score-card .section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #4d3e2c;
  margin-bottom: 8px;
}

/* 头脑图 + 结论 并排 */
.emotion-layout {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
/* ── 情绪解读卡片 v2 布局 ── */
.emotion-layout-v2 {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.emotion-summary-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: #faf9f7;
  border-radius: 6px;
  border: 1px solid #e8e4da;
}
.summary-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.summary-polarity {
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
}
.summary-score {
  font-size: 13px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
}
.summary-reasoning {
  font-size: 12px;
  color: #5a5347;
  line-height: 1.5;
  flex: 1;
}
/* ── VADER compound bar（融合版）────────────────────── */
.emotion-vader-bar {
  padding: 10px 14px 8px;
  background: #faf9f7;
  border-radius: 8px;
  border: 1px solid #e8e4da;
}
.vader-bar-header {
  position: relative;
  display: flex;
  align-items: baseline;
  margin-bottom: 10px;
  height: 28px;
}
.vader-polarity {
  position: absolute;
  left: 0;
  font-size: 20px;
  font-weight: 800;
  line-height: 1;
}
.vader-score-big {
  width: 100%;
  text-align: center;
  font-size: 26px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.3px;
  line-height: 1;
}
.vader-bar-header .el-tag,
.vader-bar-header .score-method-badge {
  position: absolute;
  right: 0;
}
.vader-track {
  position: relative;
  height: 16px;
  border-radius: 8px;
  margin-bottom: 18px;
}
.vader-gradient {
  position: absolute;
  inset: 0;
  border-radius: 8px;
  background: linear-gradient(to right,
    #e07a5f 0%,
    #f2c4b3 25%,
    #faf8f3 50%,
    #b8dcc6 75%,
    #3cb88b 100%
  );
}
/* 指示器：圆点 + 竖线 */
.vader-marker {
  position: absolute;
  top: -4px;
  transform: translateX(-50%);
  z-index: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.vader-marker-pin {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #333;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,0.35);
  flex-shrink: 0;
}
.vader-marker-line {
  width: 2px;
  height: 20px;
  background: #333;
  margin-top: -1px;
  box-shadow: 0 0 2px rgba(0,0,0,0.2);
}
.vader-axis {
  position: absolute;
  bottom: -14px;
  font-size: 9px;
  color: #aaa;
  transform: translateX(-50%);
  font-variant-numeric: tabular-nums;
}
.vader-axis-neg { left: 0%; }
.vader-axis-zero { left: 50%; }
.vader-axis-pos { left: 100%; }
.vader-reasoning {
  font-size: 12px;
  color: #5a5347;
  line-height: 1.5;
  margin-top: 4px;
}
.dim-bar-score-h {
  font-size: 10px;
  font-family: 'Courier New', monospace;
  font-weight: 600;
  width: 36px;
  text-align: right;
  flex-shrink: 0;
}
.emotion-text-col {
  flex: 1;
  min-width: 0;
}
.emotion-text-col .final-judgment-card {
  padding: 8px 10px;
  margin-bottom: 4px;
}
.emotion-text-col .final-judgment-header {
  gap: 6px;
  margin-bottom: 3px;
}
.emotion-text-col .judgment-polarity {
  font-size: 15px;
}
.emotion-text-col .judgment-reasoning {
  font-size: 12px;
  line-height: 1.7;
  padding-left: 14px;
}
.emotion-text-col .factor-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 12px;
}
.factor-row + .factor-row { border-top: 1px solid #f0ede6; }
.factor-col-head {
  font-weight: 600;
  color: #5d4e37;
  padding: 4px 10px 6px;
  white-space: nowrap;
  text-align: center;
  font-size: 12px;
  border-bottom: 2px solid #d8d0c0;
}
.factor-table td {
  padding: 5px 10px;
  text-align: center;
  vertical-align: middle;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: break-word;
}
.factor-cell { word-break: break-word; }
.factor-value {
  color: #999;
  font-size: 11px;
}

/* ── 主题判断卡片 ── */
.theme-card {
  background: #faf9f7;
  border: 1px solid #e8e4da;
  border-radius: 8px;
  padding: 8px 12px 10px;
}
.theme-card .section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 6px;
}
.theme-chart-small {
  width: 100%;
  height: 100px;
}
.theme-card .theme-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* ── 推导过程卡片 ── */
.steps-card {
  background: #faf9f7;
  border: 1px solid #e8e4da;
  border-radius: 8px;
  padding: 10px 12px;
}
.steps-card .section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}
.steps-card .sentiment-reasoning {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e8e4da;
}
.steps-card .reasoning-text {
  font-size: 12px;
  color: #666;
  line-height: 1.6;
}
.steps-card .reasoning-label {
  font-size: 11px;
  color: #999;
  margin-bottom: 6px;
}

/* ── 七维度公式推导 ── */
.formula-breakdown {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e8e4da;
}
.formula-box {
  background: #fcfaf6;
  border: 1px solid #e8e4da;
  border-radius: 6px;
  padding: 12px 14px;
  margin-bottom: 10px;
}
.formula-title {
  font-size: 11px;
  color: #8a7e6b;
  font-weight: 600;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.formula-expr {
  font-family: 'Courier New', 'Consolas', monospace;
  font-size: 15px;
  font-weight: 600;
  color: #3a3530;
  background: #fff;
  border: 1px solid #ddd8cc;
  border-radius: 4px;
  padding: 8px 14px;
  display: block;
  text-align: center;
  letter-spacing: 1px;
  margin-bottom: 10px;
}
.formula-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 16px;
  font-size: 12px;
  color: #7a6b54;
  line-height: 1.7;
}
.formula-legend b {
  color: #5d4e37;
}
.formula-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin-bottom: 8px;
}
.formula-table th {
  text-align: left;
  font-weight: 600;
  color: #5d4e37;
  padding: 4px 8px;
  border-bottom: 2px solid #d8d0c0;
  font-size: 11px;
}
.formula-table td {
  padding: 4px 8px;
  border-bottom: 1px solid #f0ede6;
}
.formula-table tr.dim-active {
  background: rgba(196, 90, 60, 0.04);
}
.formula-table .dim-name {
  font-weight: 500;
  color: #333;
}
.formula-table .dim-score,
.formula-table .dim-weight,
.formula-table .dim-conf,
.formula-table .dim-contrib {
  text-align: right;
  font-family: 'Courier New', monospace;
}
.conf-high { color: #3d7a3d; font-weight: 600; }
.conf-mid { color: #b8860b; }
.conf-low { color: #999; }
.score-pos { color: #3d7a3d; }
.score-neg { color: #a13d3d; }
.formula-result {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 6px 10px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #e8e4da;
}
.result-label {
  font-weight: 500;
  color: #5d4e37;
}
.result-score {
  font-family: 'Courier New', monospace;
  font-weight: 700;
  font-size: 14px;
}
.result-polarity {
  font-weight: 600;
}

/* ── 维度展开详情 ── */
.dim-expand {
  font-size: 10px;
  color: #b8a47e;
  margin-right: 4px;
  display: inline-block;
  width: 10px;
}
.dim-detail-row {
  background: #faf9f7;
}
.dim-detail-cell {
  padding: 0 !important;
}
.dim-detail-content {
  padding: 6px 12px 8px 28px;
}
.dim-placeholder {
  color: #9b8a6e;
  font-style: italic;
  padding: 4px 0;
}
.detail-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 2px 0;
  font-size: 11px;
}
.detail-label {
  color: #333;
  font-weight: 500;
  min-width: 60px;
}
.detail-value {
  font-family: 'Courier New', monospace;
  font-weight: 600;
  min-width: 40px;
  text-align: right;
}
.detail-desc {
  color: #999;
  font-size: 10px;
  flex: 1;
}

/* ── 空间情绪解读卡片 ── */

.spatial-emotion-card {
  margin-top: 10px;
  padding: 10px 12px;
  background: #faf9f7;
  border-radius: 8px;
  border: 1px solid #e8e4da;
}
.spatial-emotion-card .section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #141413;
  margin-bottom: 0;
  user-select: none;
}
.spatial-summary {
  font-size: 11px;
  font-weight: 400;
  color: #999;
  margin-left: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}
.spatial-toggle-icon { margin-left: auto; font-size: 12px; color: #999; }
.spatial-detail { margin-top: 10px; }
.spatial-item { margin-bottom: 8px; }
.spatial-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.spatial-dot.emotion-negative_intense,
.spatial-dot.emotion-negative_controlled { background: #c45a3c; }
.spatial-dot.emotion-positive_resolved,
.spatial-dot.emotion-positive_unrestrained { background: #5a8a4a; }
.spatial-dot.emotion-neutral_controlled,
.spatial-dot.emotion-neutral_balanced,
.spatial-dot.emotion-neutral { background: #999; }
.spatial-dot.blank-dot { background: #a8c97a; }
.spatial-type { font-size: 12px; font-weight: 600; color: #4d4c48; }
.spatial-emotion-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 500;
}
.spatial-item:nth-child(1) .spatial-emotion-tag { background: rgba(196, 90, 60, 0.1); color: #c45a3c; }
.spatial-desc {
  margin: 4px 0 0 16px;
  font-size: 11px;
  color: #777;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: break-word;
}
.spatial-combined {
  margin-top: 8px;
  padding: 8px 10px;
  background: rgba(196, 90, 60, 0.06);
  border-radius: 6px;
  font-size: 11px;
  color: #4d4c48;
  line-height: 1.5;
  word-break: break-word;
  overflow-wrap: break-word;
}
.spatial-combined-label {
  font-weight: 600;
  margin-right: 6px;
  color: #c45a3c;
}

/* ── 综合判断（最终结论） ── */
.final-judgment-card {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  background: linear-gradient(135deg, #faf8f3 0%, #f5f0e8 100%);
  border-radius: 10px;
  border: 1px solid #e0d8c8;
}
.judgment-score-col {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 60px;
}
.judgment-score-col .judgment-polarity {
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
}
.judgment-score {
  font-size: 13px;
  font-weight: 700;
  margin-top: 2px;
}
.score-method-badge {
  display: inline-block;
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #8a7e6b;
  background: #f0ede6;
  border: 1px solid #d8d0c0;
  border-radius: 3px;
  padding: 1px 4px;
  margin-top: 3px;
  cursor: help;
  opacity: 0.7;
  transition: opacity 0.2s;
}
.score-method-badge:hover {
  opacity: 1;
}

/* ── 方法论折叠面板 ── */
.score-card :deep(.el-collapse) {
  border: none;
  margin-top: 8px;
}
.score-card :deep(.el-collapse-item__header) {
  background: transparent;
  border: none;
  font-size: 11px;
  color: #8a7e6b;
  font-weight: 500;
  height: 28px;
  line-height: 28px;
  padding: 0 4px;
  border-radius: 4px;
  transition: background 0.2s;
}
.score-card :deep(.el-collapse-item__header:hover) {
  background: #f5f3ef;
}
.score-card :deep(.el-collapse-item__header .el-collapse-item__arrow) {
  font-size: 10px;
  color: #b8a47e;
}
.score-card :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}
.score-card :deep(.el-collapse-item__content) {
  padding: 0;
}
.methodology-content {
  font-size: 12px;
  color: #5a5347;
  line-height: 1.7;
  padding: 8px 12px 12px;
  background: #faf9f7;
  border-radius: 6px;
  border: 1px dashed #e0dcd3;
}
.methodology-content p {
  margin: 6px 0;
}
.methodology-content ul {
  margin: 6px 0 6px 20px;
  padding: 0;
}
.methodology-content li {
  margin: 3px 0;
  list-style: disc;
}
.method-formula {
  font-family: 'Courier New', 'Consolas', monospace;
  background: #fff;
  border: 1px solid #e8e4da;
  padding: 6px 12px;
  border-radius: 4px;
  display: block;
  margin: 8px 0;
  font-size: 13px;
  color: #333;
  letter-spacing: 0.5px;
}
.method-ref {
  font-size: 11px;
  color: #999;
  font-style: italic;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}
.judgment-info-col {
  flex: 1;
  min-width: 0;
}
.judgment-info-col .judgment-reasoning {
  font-size: 12px;
  color: #6b6356;
  line-height: 1.6;
  word-break: break-word;
  overflow-wrap: break-word;
}

/* ── 推导因素 ── */
.derivation-factors {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 4px;
  padding: 6px 10px;
  background: #f9f8f6;
  border-radius: 6px;
  border: 1px dashed #e0dcd3;
}
.factor-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.factor-label {
  color: #5d4e37;
  font-weight: 500;
  min-width: 60px;
}
.factor-result {
  font-weight: 600;
  padding: 0 6px;
  border-radius: 3px;
  font-size: 11px;
}
.factor-result.positive { color: #3d7a3d; background: #e8f4e8; }
.factor-result.negative { color: #a13d3d; background: #fce8e8; }
.factor-result.neutral  { color: #7a7a7a; background: #f0f0f0; }
.factor-score {
  color: #999;
  font-size: 11px;
}
.factor-detail {
  color: #999;
  font-size: 11px;
  word-break: break-word;
  overflow-wrap: break-word;
}

/* ── 印章情绪解读 ── */
.seal-interp {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e8e4da;
}
.seal-interp-header {
  font-size: 11px;
  font-weight: 600;
  color: #8a7a5e;
  margin-bottom: 4px;
}
.seal-interp-signals {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.seal-interp-tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  background: #f5f0e8;
  color: #6b5d4a;
  line-height: 1.4;
}
.seal-interp-neutral {
  font-size: 11px;
  color: #999;
}

/* ── 款识题跋白话文切换 ── */
.inscription-note-main h4 {
  display: flex;
  align-items: center;
  gap: 6px;
}
.inscription-mode-btns {
  display: flex;
  gap: 2px;
  margin-left: auto;
}
.inscription-mode-btns .el-button {
  font-size: 10px;
  color: #b0a898;
  padding: 0 6px;
  height: 22px;
  border: 1px solid #e8e4da;
  border-radius: 4px;
  background: transparent;
  box-shadow: none;
}
.inscription-mode-btns .el-button.active {
  color: #c45a3c;
  border-color: #c45a3c;
  background: #fdf5f2;
}
.inscription-content.english {
  background: #f6f4f8;
  border-left: 3px solid #6b7db3;
  padding-left: 10px;
}

.inscription-switch {
  min-height: 60px;
}
.inscription-content.modern {
  background: #f8f6f0;
  border-left: 3px solid #c45a3c;
  padding-left: 10px;
}
.factor-arrow {
  text-align: center;
  margin-bottom: 8px;
}
.arrow-text {
  font-size: 11px;
  color: #b8a47e;
  letter-spacing: 2px;
}

/* ── 题跋布局类型（精简卡片） ── */

.spatial-analysis-card {
  margin-top: 10px;
  padding: 10px 12px;
  background: #faf9f7;
  border-radius: 8px;
  border: 1px solid #e8e4da;
}
.spatial-analysis-card .section-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #333;
  margin-bottom: 8px;
}
.form-types-inline {
  display: inline-flex;
  gap: 4px;
  margin-left: 6px;
}
.spatial-description {
  font-size: 12px;
  line-height: 1.7;
  color: #555;
}
.form-type-desc-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-bottom: 8px;
  line-height: 1.7;
}
.desc-tag {
  flex-shrink: 0;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  background: #ede9de;
  color: #8a7a5e;
  font-weight: 600;
}
.desc-text {
  color: #555;
}
.desc-none {
  color: #999;
  font-style: italic;
}

/* 印章标签显示 */
.seal-tags-display {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.seal-display-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 6px;
  background: #f5f3ee;
  border: 1px solid #e8e5de;
  font-size: 12px;
  color: #5a5a4e;
  cursor: default;
  transition: all 0.15s;
}

.seal-display-tag.has-image {
  cursor: pointer;
  border-color: #d0ccc2;
}

.seal-display-tag.has-image:hover {
  background: #ede9e0;
  border-color: #c96442;
  color: #c96442;
}

.seal-display-type {
  font-size: 10px;
  color: #aaa;
}

.stat-percentile {
  font-size: 11px;
  color: #c96442;
  margin-left: 6px;
  font-weight: 500;
}

/* ── 情感标签样式 ── */
:deep(.pol-label) {
  font-weight: 700;
}
:deep(.pol-positive) {
  color: #67c23a;
}
:deep(.pol-negative) {
  color: #f56c6c;
}
:deep(.pol-neutral) {
  color: #909399;
}

/* ── 页面角色角标 ── */
.thumb-role-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  font-size: 10px;
  line-height: 1;
  padding: 1px 3px;
  border-radius: 2px;
  color: #fff;
  pointer-events: none;
  z-index: 1;
}
.thumb-role-badge.role-cover {
  background: #8b6914;
}
.thumb-role-badge.role-back_cover {
  background: #666;
}
.thumb-role-badge.role-accessory {
  background: #2c6e8f;
}
.thumb-role-badge.role-inscription {
  background: #7b4a8b;
}
.thumb-role-badge.role-other {
  background: #999;
}

/* 附件模式下全宽图 */
.attachment-view .original-image-wrapper {
  max-width: 100%;
}
.attachment-notice {
  text-align: center;
  color: #999;
  font-size: 13px;
  padding: 12px 0;
  border-top: 1px solid #eee;
  margin-top: 8px;
}

/* ── v3.2: 三段式辩论卡片 ── */
.llm-narrative-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: #e8e4da;
  border: 1px solid #e8e4da;
  border-radius: 6px;
  overflow: hidden;
}
.narrative-card {
  padding: 18px 22px;
  background: #fefefe;
}
.narrative-positive {
  border-bottom: 2px solid #a3c9a1;
}
.narrative-negative {
  border-bottom: 2px solid #d4a899;
}
.narrative-verdict {
  grid-column: 1 / -1;
  background: #faf9f5;
  border-top: 1px solid #e8e4da;
  padding: 20px 24px;
}
.narrative-card-header {
  font-family: 'Noto Serif SC', 'KaiTi', serif;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.08em;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0ebe0;
}
.narrative-positive .narrative-card-header {
  color: #5a8a4a;
}
.narrative-negative .narrative-card-header {
  color: #b8634a;
}
.narrative-verdict .narrative-card-header {
  color: #8b6914;
  border-bottom-color: #e8d5b0;
}
.narrative-card-body {
  font-size: 13px;
  line-height: 1.85;
  color: #5c5346;
}

/* ── v3.1: LLM 分析叙述（旧格式 plain text fallback）── */
.llm-narrative-section {
  margin-top: 12px;
  border: 1px solid #e8e4da;
  border-radius: 6px;
  overflow: hidden;
}
.llm-narrative-header {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px;
  background: #fdf6ee;
  border-bottom: 1px solid #e8e4da;
  font-size: 13px; font-weight: 500; color: #c45a3c;
}
.llm-narrative-body {
  padding: 10px 12px;
  font-size: 13px; line-height: 1.7;
  color: #4a4438; background: #fefefe;
  white-space: pre-wrap;
}

/* ── v3.1: 维度极性条 ── */
.dim-polarity-strip {
  margin-top: 8px;
  display: flex; align-items: center; gap: 8px;
}
.polarity-strip-title {
  font-size: 11px; color: #999; white-space: nowrap;
}
.polarity-dots {
  display: flex; gap: 6px; align-items: center;
}
.polarity-dot {
  width: 10px; height: 10px; border-radius: 50%;
  cursor: pointer; transition: transform 0.15s;
}
.polarity-dot:hover { transform: scale(1.4); }
.pol-positive { background: #67c23a; }
.pol-negative { background: #f56c6c; }
.pol-neutral { background: #c0c4cc; }
.pol-complex_positive, .pol-complex_negative, .pol-complex_balanced { background: #e6a23c; }

/* ── v3.1: 推导表极性点 ── */
.dim-pol-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  margin-right: 4px; vertical-align: middle;
}

/* ── v3.1: 冲突高亮行 ── */
.dim-conflict {
  background: #fdf6ee !important;
}

/* ── v3.1: 冲突分数条 ── */
.conflict-bar {
  margin-top: 10px;
  display: flex; align-items: center; gap: 8px;
  font-size: 12px;
}
.conflict-bar-label { color: #999; white-space: nowrap; }
.conflict-bar-track {
  flex: 1; height: 6px; background: #f0ebe0;
  border-radius: 3px; overflow: hidden;
}
.conflict-bar-fill {
  height: 100%; background: linear-gradient(90deg, #67c23a, #e6a23c, #f56c6c);
  border-radius: 3px; transition: width 0.4s ease;
}
.conflict-bar-value { color: #666; white-space: nowrap; }

/* ── LLM 校正详情 ── */
.llm-correction-section {
  margin-top: 12px;
  border: 1px solid #e8e4da;
  border-radius: 6px;
  overflow: hidden;
}
.llm-section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #5d4e37;
  background: #f8f5ee;
  border-bottom: 1px solid #e8e4da;
}
.llm-section-header .el-icon {
  color: #9b7b4a;
}
.llm-summary {
  font-size: 13px;
  color: #5d4e37;
  padding: 10px 14px;
  background: #fcfaf6;
  line-height: 1.6;
  border-bottom: 1px solid #f0ede6;
}
.llm-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.llm-table th {
  text-align: left;
  padding: 8px 10px;
  background: #f8f5ee;
  color: #7a6b54;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid #e8e4da;
}
.llm-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #f5f2ea;
  vertical-align: top;
}
.llm-table tbody tr:last-child td {
  border-bottom: none;
}
.llm-table tbody tr:hover {
  background: #fcfaf6;
}
.llm-table .dim-name {
  font-weight: 500;
  color: #5d4e37;
  white-space: nowrap;
}
.llm-table .dim-delta {
  font-family: 'Courier New', monospace;
  font-weight: 600;
  font-size: 12px;
  white-space: nowrap;
}
.llm-table .dim-conf {
  font-family: 'Courier New', monospace;
  font-size: 11px;
  white-space: nowrap;
}
.conf-high { color: #4a7c59; }
.conf-mid { color: #b8953a; }
.llm-reasoning-cell {
  color: #6a5b44;
  font-size: 12px;
  line-height: 1.5;
  max-width: 320px;
}
.llm-meta {
  padding: 8px 14px;
  font-size: 11px;
  color: #b0a590;
  background: #fcfaf6;
  border-top: 1px solid #f0ede6;
  display: flex;
  align-items: center;
  gap: 2px;
}
.llm-model {
  font-family: 'Courier New', monospace;
  color: #9b8a6e;
}
</style>
