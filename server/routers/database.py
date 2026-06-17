# -*- coding: utf-8 -*-
"""
球拍产品库API
"""

import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()

# 加载产品库
DB_PATH = Path(__file__).parent.parent.parent / "config" / "racket_images.json"
RACKET_DB_PATH = Path(__file__).parent.parent.parent / "config" / "racket_database.json"

_image_map = {}
_racket_db = {}

if DB_PATH.exists():
    with open(DB_PATH, 'r', encoding='utf-8') as f:
        _image_map = json.load(f)

if RACKET_DB_PATH.exists():
    with open(RACKET_DB_PATH, 'r', encoding='utf-8') as f:
        _racket_db = json.load(f)


@router.get("/")
async def get_all_rackets():
    """获取完整球拍产品库"""
    from server.database import get_db
    
    # 获取已有数据的型号统计
    with get_db() as conn:
        rows = conn.execute("""
            SELECT model, COUNT(*) as total_sales,
                   ROUND(AVG(price), 0) as avg_price,
                   ROUND(MIN(price), 0) as min_price,
                   ROUND(MAX(price), 0) as max_price
            FROM records
            GROUP BY model
        """).fetchall()
        existing_models = {row['model']: dict(row) for row in rows}
    
    # 构建完整产品库
    result = []
    for name, info in _racket_db.items():
        brand = info.get('brand', '未知')
        aliases = info.get('aliases', [])
        
        # 检查是否有数据（通过别名匹配）
        data = None
        for alias in aliases:
            if alias in existing_models:
                data = existing_models[alias]
                break
        
        result.append({
            'name': name,
            'brand': brand,
            'aliases': aliases,
            'image': _image_map.get(name, ''),
            'has_data': data is not None,
            'total_sales': data['total_sales'] if data else 0,
            'avg_price': data['avg_price'] if data else 0,
            'min_price': data['min_price'] if data else 0,
            'max_price': data['max_price'] if data else 0,
        })
    
    # 按品牌分组，有数据的排前面
    result.sort(key=lambda x: (x['brand'], -x['has_data'], -x['total_sales']))
    
    return result


@router.get("/brands")
async def get_brands():
    """获取品牌列表"""
    brands = {}
    for name, info in _racket_db.items():
        brand = info.get('brand', '未知')
        if brand not in brands:
            brands[brand] = 0
        brands[brand] += 1
    
    return [{'brand': b, 'count': c} for b, c in brands.items()]
