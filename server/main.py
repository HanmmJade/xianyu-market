# -*- coding: utf-8 -*-
"""
闲鱼行情监控API服务器
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.config import CORS_ORIGINS
from server.routers import records, models, stats, database

app = FastAPI(
    title="闲鱼行情监控API",
    description="羽毛球拍二手市场价格监控系统",
    version="1.0.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(records.router, prefix="/api/records", tags=["records"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(database.router, prefix="/api/database", tags=["database"])


@app.get("/")
async def root():
    """API根路径"""
    return {
        "name": "闲鱼行情监控API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok"}
