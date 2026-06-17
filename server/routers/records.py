# -*- coding: utf-8 -*-
"""
记录API路由
"""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from server.database import get_db, dicts_from_rows
from server.models import Record, RecordCreate

router = APIRouter()


@router.get("/", response_model=List[Record])
async def get_records(
    model: Optional[str] = Query(None, description="型号筛选"),
    condition: Optional[str] = Query(None, description="成色筛选"),
    min_price: Optional[float] = Query(None, description="最低价格"),
    max_price: Optional[float] = Query(None, description="最高价格"),
    limit: int = Query(100, le=1000, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    """获取记录列表，支持筛选"""
    with get_db() as conn:
        query = "SELECT * FROM records WHERE 1=1"
        params = []

        if model:
            query += " AND model = ?"
            params.append(model)
        if condition:
            query += " AND (condition_inferred = ? OR condition = ?)"
            params.extend([condition, condition])
        if min_price is not None:
            query += " AND price >= ?"
            params.append(min_price)
        if max_price is not None:
            query += " AND price <= ?"
            params.append(max_price)

        query += " ORDER BY crawled_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return dicts_from_rows(rows)


@router.get("/{record_id}", response_model=Record)
async def get_record(record_id: int):
    """获取单条记录"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="记录不存在")
        return dict(row)


@router.post("/", response_model=dict)
async def create_record(record: RecordCreate):
    """创建记录"""
    with get_db() as conn:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO records
                (model, title, price, condition, condition_inferred, condition_score,
                 condition_claimed, condition_evidence, condition_severe,
                 listed_time, sold_time, days_to_sell, source_url, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                record.model, record.title, record.price,
                record.condition, record.condition_inferred, record.condition_score,
                record.condition_claimed, record.condition_evidence, record.condition_severe,
                record.listed_time, record.sold_time, record.days_to_sell, record.source_url
            ))
            conn.commit()
            return {"message": "记录已创建", "id": conn.execute("SELECT last_insert_rowid()").fetchone()[0]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{record_id}")
async def delete_record(record_id: int):
    """删除记录"""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM records WHERE id = ?", (record_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"message": "记录已删除"}
