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
    
    # 热力图数据
    heatmap_data = Column(JSON, default=list, comment="热力图数据")
    
    # 题跋位置分析数据
    position_analysis = Column(JSON, default=dict, comment="题跋位置分析结果")
    
    # 分析说明
    analysis_note = Column(Text, comment="AI分析说明")
    
    # 标注图片路径
    annotated_image_path = Column(String(500), comment="标注后的图片路径")
    
    # 缩略图路径
    thumbnail_path = Column(String(500), comment="缩略图路径")
    
    # 状态
    status = Column(String(20), default="uploaded", comment="状态：uploaded/analyzed/error")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
