# Vercel Serverless Function入口
import sys
from pathlib import Path

# 添加项目根目录到Python路径
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from server.main import app

# Vercel需要这个导出
handler = app
