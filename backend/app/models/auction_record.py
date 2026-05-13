"""
拍卖记录模型 — auction_records 表
Phase 2: 作品拍卖记录
"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, func
from app.core.database import Base


class AuctionRecord(Base):
    __tablename__ = "auction_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artwork_id = Column(Integer, nullable=False, index=True, comment="关联作品ID (tubi_analyses.id)")
    auction_house = Column(String(255), nullable=True, comment="拍卖行")
    sale_date = Column(String(100), nullable=True, comment="拍卖日期")
    lot_number = Column(String(100), nullable=True, comment="拍品编号")
    estimate_low = Column(Float, nullable=True, comment="估价低值")
    estimate_high = Column(Float, nullable=True, comment="估价高值")
    hammer_price = Column(Float, nullable=True, comment="成交价")
    currency = Column(String(10), default="CNY", comment="币种: CNY/USD/HKD等")
    notes = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
