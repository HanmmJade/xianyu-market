# -*- coding: utf-8 -*-
"""
SQLite 数据库操作 — v2: 支持推断成色字段
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

DB_PATH = Path(__file__).parent.parent / "data" / "xianyu.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT NOT NULL,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            condition TEXT,
            condition_inferred TEXT,
            condition_score INTEGER,
            condition_claimed TEXT,
            condition_evidence TEXT,
            condition_severe INTEGER DEFAULT 0,
            listed_time TEXT,
            sold_time TEXT,
            days_to_sell INTEGER,
            source_url TEXT,
            crawled_at TEXT NOT NULL,
            UNIQUE(title, price, sold_time)
        );

        CREATE INDEX IF NOT EXISTS idx_model ON records(model);
        CREATE INDEX IF NOT EXISTS idx_condition ON records(condition);
        CREATE INDEX IF NOT EXISTS idx_sold_time ON records(sold_time);
        CREATE INDEX IF NOT EXISTS idx_crawled_at ON records(crawled_at);
    """)
    conn.commit()
    conn.close()
    logger.info(f"数据库初始化完成: {DB_PATH}")


def migrate_db():
    """数据库迁移：添加新字段（如果不存在）"""
    conn = get_conn()
    cursor = conn.cursor()

    # 获取现有列
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(records)").fetchall()}

    migrations = [
        ("condition_inferred", "ALTER TABLE records ADD COLUMN condition_inferred TEXT"),
        ("condition_score", "ALTER TABLE records ADD COLUMN condition_score INTEGER"),
        ("condition_claimed", "ALTER TABLE records ADD COLUMN condition_claimed TEXT"),
        ("condition_evidence", "ALTER TABLE records ADD COLUMN condition_evidence TEXT"),
        ("condition_severe", "ALTER TABLE records ADD COLUMN condition_severe INTEGER DEFAULT 0"),
    ]

    migrated = 0
    for col_name, sql in migrations:
        if col_name not in columns:
            cursor.execute(sql)
            migrated += 1

    if migrated:
        conn.commit()
        logger.info(f"数据库迁移完成: 新增 {migrated} 个字段")

    conn.close()


def _record_to_params(r: Dict) -> tuple:
    """将记录字典转为SQL参数"""
    import json
    evidence = r.get('condition_evidence', [])
    if isinstance(evidence, list):
        evidence = json.dumps(evidence, ensure_ascii=False)

    return (
        r.get('model', ''),
        r.get('title', ''),
        r.get('price', 0),
        r.get('condition', ''),
        r.get('condition_inferred', ''),
        r.get('condition_score', 0),
        r.get('condition_claimed', ''),
        evidence,
        1 if r.get('condition_severe') else 0,
        r.get('listed_time', ''),
        r.get('sold_time', ''),
        r.get('days_to_sell'),
        r.get('source_url', ''),
        datetime.now().isoformat(),
    )


_INSERT_SQL = """
    INSERT OR IGNORE INTO records
    (model, title, price, condition, condition_inferred, condition_score,
     condition_claimed, condition_evidence, condition_severe,
     listed_time, sold_time, days_to_sell, source_url, crawled_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def insert_record(record: Dict) -> bool:
    """插入一条成交记录，返回是否成功（去重）"""
    conn = get_conn()
    try:
        conn.execute(_INSERT_SQL, _record_to_params(record))
        conn.commit()
        return conn.total_changes > 0
    except Exception as e:
        logger.error(f"插入记录失败: {e}")
        return False
    finally:
        conn.close()


def insert_records(records: List[Dict]) -> int:
    """批量插入，返回新增条数"""
    conn = get_conn()
    inserted = 0
    try:
        for r in records:
            try:
                conn.execute(_INSERT_SQL, _record_to_params(r))
                inserted += conn.total_changes
            except:
                pass
        conn.commit()
    except Exception as e:
        logger.error(f"批量插入失败: {e}")
    finally:
        conn.close()

    logger.info(f"批量插入: 尝试{len(records)}条, 新增{inserted}条")
    return inserted


def get_all_models() -> List[Dict]:
    """获取所有型号的摘要"""
    conn = get_conn()
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
    conn.close()
    return [dict(r) for r in rows]


def get_model_detail(model: str) -> Dict:
    """获取单个型号的详细数据"""
    conn = get_conn()

    records = conn.execute("""
        SELECT price, condition, condition_inferred, condition_score,
               condition_claimed, condition_evidence, condition_severe,
               sold_time, days_to_sell, title, source_url
        FROM records
        WHERE model = ?
        ORDER BY sold_time DESC
    """, (model,)).fetchall()

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
    """, (model,)).fetchall()

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
    """, (model,)).fetchall()

    conn.close()

    # 解析evidence JSON
    import json
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

    return {
        'records': records_list,
        'by_condition': [dict(r) for r in by_condition],
        'daily': [dict(r) for r in daily],
    }


def get_stats() -> Dict:
    """获取数据库统计"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM records").fetchone()['c']
    models = conn.execute("SELECT COUNT(DISTINCT model) as c FROM records").fetchone()['c']
    latest = conn.execute("SELECT MAX(crawled_at) as t FROM records").fetchone()['t']
    conn.close()
    return {'total_records': total, 'total_models': models, 'last_crawled': latest}
