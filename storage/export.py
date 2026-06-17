# -*- coding: utf-8 -*-
"""
数据导出 — SQLite → JSON 文件（供前端使用）
v2: 支持推断成色字段
"""

import json
from pathlib import Path
from datetime import datetime
from loguru import logger

from storage.db import get_all_models, get_model_detail, get_stats

OUTPUT_DIR = Path(__file__).parent.parent / "web" / "data"


def export_index():
    """导出型号摘要 index.json"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    models = get_all_models()

    # 为每个型号获取最新价格趋势（简化版）
    index_data = []
    for m in models:
        detail = get_model_detail(m['model'])

        # 构建价格趋势
        daily = detail.get('daily', [])
        trend_dates = []
        trend_prices = []
        for d in daily:
            if d.get('date') and d.get('avg_price'):
                trend_dates.append(d['date'])
                trend_prices.append(d['avg_price'])

        # 计算推断成色统计
        records = detail.get('records', [])
        inferred_count = sum(1 for r in records if r.get('condition_inferred'))
        severe_count = sum(1 for r in records if r.get('condition_severe'))

        index_data.append({
            'model': m['model'],
            'total_sales': m['total_sales'],
            'avg_price': m['avg_price'],
            'min_price': m['min_price'],
            'max_price': m['max_price'],
            'latest_sold': m.get('latest_sold', ''),
            'last_crawled': m.get('last_crawled', ''),
            'trend_dates': trend_dates[-30:],  # 最近30天
            'trend_prices': trend_prices[-30:],
            'inferred_count': inferred_count,
            'severe_count': severe_count,
        })

    out_path = OUTPUT_DIR / "index.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    logger.info(f"导出 index.json: {len(index_data)} 个型号")
    return len(index_data)


def export_model(model: str):
    """导出单个型号的详细数据"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    detail = get_model_detail(model)
    records = detail['records']
    by_condition = detail['by_condition']
    daily = detail['daily']

    # 按成色构建价格趋势（优先使用推断成色）
    condition_trends = {}
    for d in daily:
        cond = d.get('condition', '未知') or '未知'
        if cond not in condition_trends:
            condition_trends[cond] = {'dates': [], 'prices': [], 'counts': []}
        condition_trends[cond]['dates'].append(d.get('date', ''))
        condition_trends[cond]['prices'].append(d.get('avg_price', 0))
        condition_trends[cond]['counts'].append(d.get('count', 0))

    # 最近成交记录
    recent = []
    for r in records[:50]:
        entry = {
            'price': r['price'],
            'condition': r.get('condition_inferred') or r['condition'] or '',
            'condition_claimed': r.get('condition_claimed', ''),
            'condition_score': r.get('condition_score', 0),
            'condition_severe': bool(r.get('condition_severe')),
            'sold_time': r['sold_time'],
            'days_to_sell': r['days_to_sell'],
            'title': r['title'],
        }
        # 成色证据
        evidence = r.get('condition_evidence', [])
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except:
                evidence = []
        entry['condition_evidence'] = evidence if evidence else []

        recent.append(entry)

    model_data = {
        'model': model,
        'total_sales': len(records),
        'by_condition': by_condition,
        'condition_trends': condition_trends,
        'recent_records': recent,
        'exported_at': datetime.now().isoformat(),
    }

    # 文件名：移除特殊字符
    safe_name = model.replace(' ', '_').replace('/', '_')
    out_path = OUTPUT_DIR / f"{safe_name}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(model_data, f, ensure_ascii=False, indent=2)

    logger.info(f"导出 {model}.json: {len(records)} 条记录")


def export_all():
    """导出所有数据"""
    models = get_all_models()

    if not models:
        logger.warning("数据库无数据，跳过导出")
        return

    count = export_index()
    for m in models:
        export_model(m['model'])

    # 导出统计信息
    stats = get_stats()
    stats_path = OUTPUT_DIR / "stats.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    logger.info(f"全部导出完成: {count} 个型号")
