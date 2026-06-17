# -*- coding: utf-8 -*-
"""
简单导入脚本 - 直接操作数据库
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime


def main():
    # 数据库路径
    db_path = Path(__file__).parent.parent / "data" / "xianyu.db"
    data_file = Path(__file__).parent.parent / "data" / "market_records.json"
    
    print(f"数据库路径: {db_path}")
    print(f"数据文件: {data_file}")
    
    # 检查文件
    if not data_file.exists():
        print("错误: 数据文件不存在")
        return
    
    # 加载数据
    with open(data_file, 'r', encoding='utf-8') as f:
        records = json.load(f)
    
    print(f"加载 {len(records)} 条记录")
    
    # 连接数据库
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # 检查当前记录数
    cursor.execute("SELECT COUNT(*) FROM records")
    count_before = cursor.fetchone()[0]
    print(f"导入前记录数: {count_before}")
    
    # 插入数据
    inserted = 0
    for record in records:
        model = record.get('model', '')
        if not model:
            continue
        
        price = record.get('sold_price', 0)
        title = f"{model} 二手球拍"
        crawled_at = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO records (model, title, price, crawled_at)
                VALUES (?, ?, ?, ?)
            """, (model, title, price, crawled_at))
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"插入失败: {e}")
    
    # 提交
    conn.commit()
    
    # 检查记录数
    cursor.execute("SELECT COUNT(*) FROM records")
    count_after = cursor.fetchone()[0]
    print(f"导入后记录数: {count_after}")
    print(f"新增记录: {count_after - count_before}")
    
    # 关闭连接
    conn.close()


if __name__ == "__main__":
    main()
