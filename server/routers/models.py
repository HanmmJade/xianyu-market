# -*- coding: utf-8 -*-
"""
型号API路由
"""

import json
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException
from server.database import get_db, dicts_from_rows
from server.models import ModelSummary, ModelDetail, ConditionStats, DailyTrend, Record

router = APIRouter()

# 加载图片映射
IMAGES_CONFIG = Path(__file__).parent.parent.parent / "config" / "racket_images.json"
_image_map = {}
if IMAGES_CONFIG.exists():
    with open(IMAGES_CONFIG, 'r', encoding='utf-8') as f:
        _image_map = json.load(f)


def get_model_image(model_name: str) -> str:
    """获取型号图片路径"""
    return _image_map.get(model_name, "")


@router.get("/")
async def get_models():
    """获取所有型号汇总"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                model,
                COUNT(*) as total_sales,
                ROUND(AVG(price), 0) as avg_price,
                ROUND(MIN(price), 0) as min_price,
                ROUND(MAX(price), 0) as max_price,
                MAX(sold_time) as latest_sold,
                MAX(crawled_at) as last_crawled
            FROM records
            GROUP BY model
            ORDER BY total_sales DESC
        """).fetchall()
        
        result = []
        for row in rows:
            d = dict(row)
            d['image'] = get_model_image(d['model'])
            result.append(d)
        return result


@router.get("/{model_name}")
async def get_model_detail(model_name: str):
    """获取型号详情"""
    with get_db() as conn:
        # 获取记录
        records = conn.execute("""
            SELECT *
            FROM records
            WHERE model = ?
            ORDER BY crawled_at DESC
        """, (model_name,)).fetchall()

        if not records:
            raise HTTPException(status_code=404, detail=f"型号 '{model_name}' 不存在")

        # 解析evidence JSON
        records_list = []
        for r in records:
            d = dict(r)
            ev = d.get('condition_evidence', '')
            if ev and isinstance(ev, str):
                try:
                    d['condition_evidence'] = json.loads(ev)
                except:
                    d['condition_evidence'] = []
            records_list.append(d)

        # 按成色统计
        by_condition = conn.execute("""
            SELECT
                COALESCE(condition_inferred, condition, '未知') as condition,
                COUNT(*) as count,
                ROUND(AVG(price), 0) as avg_price,
                ROUND(MIN(price), 0) as min_price,
                ROUND(MAX(price), 0) as max_price,
                ROUND(AVG(days_to_sell), 1) as avg_days
            FROM records
            WHERE model = ?
            GROUP BY COALESCE(condition_inferred, condition, '未知')
            ORDER BY avg_price DESC
        """, (model_name,)).fetchall()

        # 每日趋势
        daily = conn.execute("""
            SELECT
                sold_time as date,
                ROUND(AVG(price), 0) as avg_price,
                COALESCE(condition_inferred, condition, '未知') as condition,
                COUNT(*) as count
            FROM records
            WHERE model = ? AND sold_time != ''
            GROUP BY sold_time, COALESCE(condition_inferred, condition, '未知')
            ORDER BY sold_time
        """, (model_name,)).fetchall()

        return {
            "model": model_name,
            "image": get_model_image(model_name),
            "records": records_list,
            "by_condition": dicts_from_rows(by_condition),
            "daily": dicts_from_rows(daily),
        }


@router.get("/{model_name}/trend")
async def get_model_trend(model_name: str, days: int = 30):
    """获取型号价格趋势"""
    with get_db() as conn:
        # 检查型号是否存在
        exists = conn.execute(
            "SELECT COUNT(*) as c FROM records WHERE model = ?", (model_name,)
        ).fetchone()['c']

        if not exists:
            raise HTTPException(status_code=404, detail=f"型号 '{model_name}' 不存在")

        # 获取每日均价趋势
        trend = conn.execute("""
            SELECT
                DATE(crawled_at) as date,
                ROUND(AVG(price), 0) as avg_price,
                COUNT(*) as count,
                ROUND(MIN(price), 0) as min_price,
                ROUND(MAX(price), 0) as max_price
            FROM records
            WHERE model = ?
            GROUP BY DATE(crawled_at)
            ORDER BY date DESC
            LIMIT ?
        """, (model_name, days)).fetchall()

        return dicts_from_rows(trend)
