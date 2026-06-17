# -*- coding: utf-8 -*-
"""
导入ADB采集的数据到主数据库
"""

import json
from pathlib import Path
from loguru import logger
from storage.db import insert_records, init_db, migrate_db


def import_market_records():
    """导入market_records.json数据"""
    data_file = Path(__file__).parent.parent / "data" / "market_records.json"
    
    if not data_file.exists():
        logger.error(f"数据文件不存在: {data_file}")
        return
    
    # 加载数据
    with open(data_file, 'r', encoding='utf-8') as f:
        records = json.load(f)
    
    logger.info(f"加载 {len(records)} 条ADB数据")
    
    # 转换格式
    converted = []
    for record in records:
        # 直接使用model字段（数据中已有）
        model = record.get('model', '')
        
        if not model:
            continue
        
        # 构造标题
        title = f"{model} 二手球拍"
        
        converted_record = {
            'model': model,
            'title': title,
            'price': record.get('sold_price', 0),
            'condition': '',
            'sold_time': '',
            'listed_time': '',
            'source_url': '',
        }
        converted.append(converted_record)
    
    logger.info(f"转换 {len(converted)} 条记录")
    
    # 初始化数据库
    init_db()
    migrate_db()
    
    # 插入数据
    inserted = insert_records(converted)
    logger.info(f"导入完成: {inserted} 条新记录")


if __name__ == "__main__":
    import_market_records()
