# -*- coding: utf-8 -*-
"""
统计API路由
"""

from fastapi import APIRouter
from server.database import get_db
from server.models import Stats

router = APIRouter()


@router.get("/", response_model=Stats)
async def get_stats():
    """获取数据库统计"""
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM records").fetchone()['c']
        models = conn.execute("SELECT COUNT(DISTINCT model) as c FROM records").fetchone()['c']
        latest = conn.execute("SELECT MAX(crawled_at) as t FROM records").fetchone()['t']

        return {
            "total_records": total,
            "total_models": models,
            "last_crawled": latest,
        }


@router.get("/brands")
async def get_brand_stats():
    """按品牌统计"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                CASE
                    WHEN model LIKE '%天斧%' OR model LIKE '%弓箭%' OR model LIKE '%疾光%'
                         OR model LIKE '%双刃%' OR model LIKE '%威力%' OR model LIKE '%锐速%'
                    THEN 'YONEX'
                    WHEN model LIKE '%雷霆%' OR model LIKE '%战戟%' OR model LIKE '%风刃%'
                         OR model LIKE '%能量%' OR model LIKE '%突袭%'
                    THEN '李宁'
                    WHEN model LIKE '%神速%' OR model LIKE '%龙牙%' OR model LIKE '%极速%'
                         OR model LIKE '%亮剑%' OR model LIKE '%挑战者%'
                    THEN 'VICTOR'
                    ELSE '其他'
                END as brand,
                COUNT(DISTINCT model) as model_count,
                COUNT(*) as record_count,
                ROUND(AVG(price), 0) as avg_price
            FROM records
            GROUP BY brand
            ORDER BY record_count DESC
        """).fetchall()

        return [dict(row) for row in rows]


@router.get("/conditions")
async def get_condition_stats():
    """按成色统计"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                COALESCE(condition_inferred, condition, '未知') as condition,
                COUNT(*) as count,
                ROUND(AVG(price), 0) as avg_price,
                ROUND(AVG(condition_score), 0) as avg_score
            FROM records
            GROUP BY COALESCE(condition_inferred, condition, '未知')
            ORDER BY count DESC
        """).fetchall()

        return [dict(row) for row in rows]
