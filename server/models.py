# -*- coding: utf-8 -*-
"""
Pydantic数据模型
"""

from typing import Optional, List
from pydantic import BaseModel


class RecordBase(BaseModel):
    """记录基础模型"""
    model: str
    title: str
    price: float
    condition: Optional[str] = None
    condition_inferred: Optional[str] = None
    condition_score: Optional[int] = None
    condition_claimed: Optional[str] = None
    condition_evidence: Optional[str] = None
    condition_severe: Optional[int] = 0
    listed_time: Optional[str] = None
    sold_time: Optional[str] = None
    days_to_sell: Optional[int] = None
    source_url: Optional[str] = None


class RecordCreate(RecordBase):
    """创建记录"""
    pass


class Record(RecordBase):
    """完整记录"""
    id: int
    crawled_at: str

    class Config:
        from_attributes = True


class ModelSummary(BaseModel):
    """型号汇总"""
    model: str
    total_sales: int
    avg_price: float
    min_price: float
    max_price: float
    latest_sold: Optional[str] = None
    last_crawled: Optional[str] = None


class ConditionStats(BaseModel):
    """成色统计"""
    condition: str
    count: int
    avg_price: float
    min_price: float
    max_price: float
    avg_days: Optional[float] = None


class DailyTrend(BaseModel):
    """每日趋势"""
    date: str
    avg_price: float
    condition: str
    count: int


class ModelDetail(BaseModel):
    """型号详情"""
    records: List[Record]
    by_condition: List[ConditionStats]
    daily: List[DailyTrend]


class Stats(BaseModel):
    """数据库统计"""
    total_records: int
    total_models: int
    last_crawled: Optional[str] = None


class CrawlerStatus(BaseModel):
    """爬虫状态"""
    is_running: bool
    last_run: Optional[str] = None
    records_crawled: int = 0
    current_task: Optional[str] = None
