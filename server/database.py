# -*- coding: utf-8 -*-
"""
数据库连接管理
"""

import sqlite3
from contextlib import contextmanager
from server.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def get_db():
    """数据库上下文管理器"""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def dict_from_row(row: sqlite3.Row) -> dict:
    """将sqlite3.Row转换为字典"""
    return dict(row) if row else None


def dicts_from_rows(rows: list) -> list:
    """将sqlite3.Row列表转换为字典列表"""
    return [dict(row) for row in rows] if rows else []
