# -*- coding: utf-8 -*-
"""
服务器配置
"""

import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 数据库路径
DB_PATH = BASE_DIR / "data" / "xianyu.db"

# 服务器配置
HOST = os.getenv("XIANYU_HOST", "0.0.0.0")
PORT = int(os.getenv("XIANYU_PORT", "8000"))

# CORS配置
CORS_ORIGINS = [
    "http://localhost:5173",  # Vue开发服务器
    "http://localhost:3000",  # 备用端口
    "http://127.0.0.1:5173",
]

# 爬虫配置
CRAWLER_DELAY_MIN = 2  # 最小延迟(秒)
CRAWLER_DELAY_MAX = 5  # 最大延迟(秒)
