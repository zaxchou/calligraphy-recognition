from sqlalchemy import Column, Integer, String, Text, DateTime, Float, JSON, func
from app.core.database import Base


class TubiAnalysis(Base):
    """题跋分析结果数据库模型"""
    __tablename__ = "tubi_analyses"
    
    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(String(100), unique=True, nullable=False, comment="图片唯一标识")
    filename = Column(String(255), nullable=False, comment="原始文件名")
    filepath = Column(String(500), nullable=False, comment="文件存储路径")
    
    # 画作信息
    title = Column(String(255), comment="画作标题")
    artist = Column(String(100), comment="画家/作者")
    year = Column(Integer, comment="创作年份")
    period = Column(String(50), comment="时期（早期/中期/晚期）")
    notes = Column(Text, comment="备注说明")
    
    # 图片尺寸
    image_width = Column(Integer, default=0)
    image_height = Column(Integer, default=0)
    
    # 区域统计数据
    inscription_percent = Column(Float, default=0.0, comment="题跋区域百分比")
    painting_percent = Column(Float, default=0.0, comment="绘画区域百分比")
    blank_percent = Column(Float, default=0.0, comment="留白区域百分比")
    
    # 区域坐标数据（JSON格式）
    regions = Column(JSON, default=dict, comment="区域坐标数据")
    
    # 题跋位置分析数据
    position_analysis = Column(JSON, default=dict, comment="题跋位置分析结果")
    
    # 分析说明
    analysis_note = Column(Text, comment="AI分析说明")
    
    # 款识题跋内容
    inscription_content = Column(Text, nullable=True, default=None, comment="款识题跋内容")
    
    # 款识题跋现代文翻译
    inscription_modern = Column(Text, nullable=True, default=None, comment="题跋现代文翻译")
    
    # 标注图片路径
    annotated_image_path = Column(String(500), comment="标注后的图片路径")
    
    # 缩略图路径
    thumbnail_path = Column(String(500), comment="缩略图路径")
    
    # 状态
    status = Column(String(20), default="uploaded", comment="状态：uploaded/analyzed/error")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ── 李鱓题跋学术分析新增字段 ───────────────────────────────────────────
    period_phase = Column(String(10), comment="艺术分期：早期/中期/晚期")
    char_count = Column(Integer, comment="题跋字符数（不含标点）")
    word_count = Column(Integer, comment="题跋词数（jieba分词）")
    theme_tags = Column(String(200), comment="主题标签，逗号分隔")
    content_analysis = Column(Text, comment="LLM分析结果JSON")
    inscription_verified = Column(Integer, default=0, comment="是否已校对：0未校/1已校")
    inscription_verified_at = Column(DateTime(timezone=True), comment="校对时间")

    # ── 印章内容 ───────────────────────────────────────────
    seal_content = Column(Text, nullable=True, default=None, comment="印章内容文本")
    seal_verified = Column(Integer, default=0, comment="印章是否已校对：0未校/1已校")
    seal_verified_at = Column(DateTime(timezone=True), comment="印章校对时间")
    
    # ── 画材标签 ───────────────────────────────────────────
    material_tags = Column(String(500), nullable=True, default=None, comment="画材/题材标签，逗号分隔")

    # ── 结构化错误码 ───────────────────────────────────────────
    error_code = Column(String(50), nullable=True, default=None, comment="结构化错误码：REDIS_UNAVAILABLE/VL_TIMEOUT/OCR_FAILED/WORKER_CRASHED等")

    # ── 画作实际尺寸（厘米）──────────────────────────────────────────
    artwork_width_cm = Column(Float, nullable=True, default=None, comment="画作实际宽度（厘米），1位小数")
    artwork_height_cm = Column(Float, nullable=True, default=None, comment="画作实际高度（厘米），1位小数")

    # ── 手动标注标记──────────────────────────────────────────
    is_manual_annotated = Column(Integer, default=0, comment="是否手动标注区域：0否/1是")

    # ── 册页分组 ───────────────────────────────────────────
    album_name = Column(String(200), nullable=True, default=None, comment="册页名称，如花鸟册")
    album_index = Column(Integer, nullable=True, default=None, comment="册页页码，如1表示第一开")
    
    # ── 标签 ───────────────────────────────────────────
    tags = Column(Text, nullable=True, default=None, comment="标签，JSON数组格式，如[\"花鸟\",\"册页\"]")
