# 闲鱼球拍行情监控系统 V2

一个完整的羽毛球拍二手市场价格监控系统，包含数据采集、后端API、前端展示。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      数据采集层                              │
│  Root手机 + Frida + mitmproxy → 拦截闲鱼行情API             │
│  → 提取签名算法 → Python批量调API                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      后端服务层                              │
│  FastAPI服务器                                               │
│  ├── REST API (CRUD + 查询)                                 │
│  ├── SQLite数据库 (xianyu.db)                               │
│  ├── 数据清洗管道                                           │
│  └── 定时采集调度                                           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      前端展示层                              │
│  Vue3 + Vite + TailwindCSS + ECharts                        │
│  ├── 型号总览页 (品牌筛选/搜索/统计)                        │
│  ├── 型号详情页 (价格走势/成色分析/散点图)                  │
│  └── 实时数据从API获取                                      │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 启动后端API服务器

```bash
cd xianyu-market
pip install -r requirements.txt
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000/docs 查看API文档

### 2. 启动前端开发服务器

```bash
cd xianyu-market/web-app
npm install
npm run dev
```

访问 http://localhost:5173 查看前端页面

### 3. 数据采集（可选）

#### 方案A: 使用现有数据
```bash
# 导入ADB采集的数据
python scripts/import_adb_data.py

# 导出JSON给前端
python main.py export
```

#### 方案B: Root+Frida采集
```bash
# 1. Root手机（需要先解锁Bootloader）
bash setup/root_setup.sh

# 2. 安装Frida
bash setup/frida_setup.sh

# 3. 启动采集环境
bash scripts/start_capture.sh
# 或 Windows: start_capture.bat

# 4. 批量采集
python crawler/batch_crawler.py
```

## 项目结构

```
xianyu-market/
├── server/                  # FastAPI后端
│   ├── main.py              # 服务器入口
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库连接
│   ├── models.py            # Pydantic模型
│   └── routers/             # API路由
│       ├── records.py       # 记录CRUD
│       ├── models.py        # 型号查询
│       └── stats.py         # 统计数据
├── web-app/                 # Vue3前端
│   ├── src/
│   │   ├── api/             # API请求
│   │   ├── components/      # Vue组件
│   │   ├── views/           # 页面视图
│   │   └── router/          # 路由配置
│   └── package.json
├── crawler/                 # 数据采集
│   ├── api_client.py        # API客户端
│   ├── batch_crawler.py     # 批量采集
│   └── xianyu_spider.py     # 网页爬虫
├── storage/                 # 数据存储
│   ├── db.py                # SQLite操作
│   └── export.py            # JSON导出
├── scripts/                 # 工具脚本
│   ├── frida_ssl_bypass.js  # Frida Hook脚本
│   ├── xianyu_intercept.py  # mitmproxy拦截
│   └── sign_analyzer.py     # 签名分析
├── setup/                   # 环境搭建
│   ├── root_setup.sh        # Root脚本
│   └── frida_setup.sh       # Frida安装
├── config/                  # 配置文件
│   ├── keywords.yaml        # 关键词配置
│   └── racket_database.json # 球拍数据库
├── data/                    # 数据文件
│   ├── xianyu.db            # SQLite数据库
│   └── captured/            # 抓包数据
├── main.py                  # CLI入口
├── requirements.txt         # Python依赖
└── start_capture.bat        # Windows采集启动
```

## API接口

### 型号相关
- `GET /api/models/` - 获取所有型号汇总
- `GET /api/models/{name}` - 获取型号详情
- `GET /api/models/{name}/trend` - 获取价格趋势

### 记录相关
- `GET /api/records/` - 获取记录列表（支持筛选）
- `GET /api/records/{id}` - 获取单条记录
- `POST /api/records/` - 创建记录
- `DELETE /api/records/{id}` - 删除记录

### 统计相关
- `GET /api/stats/` - 获取数据库统计
- `GET /api/stats/brands` - 按品牌统计
- `GET /api/stats/conditions` - 按成色统计

## 配置说明

### 球拍型号配置
编辑 `config/keywords.yaml` 添加新的球拍型号：

```yaml
rackets:
  - name: "天斧88D PRO"
    keywords: ["天斧88D PRO", "88D PRO", "88dpro"]
  - name: "天斧100ZZ"
    keywords: ["天斧100ZZ", "100ZZ", "100zz"]
```

### 服务器配置
编辑 `server/config.py` 修改服务器配置：

```python
HOST = "0.0.0.0"
PORT = 8000
CORS_ORIGINS = ["http://localhost:5173"]
```

## 数据采集方案对比

| 方案 | 速度 | 稳定性 | 难度 | 适用场景 |
|------|------|--------|------|----------|
| 网页版爬虫 | 慢 | 中 | 低 | 小规模测试 |
| ADB手机爬虫 | 3-5条/分钟 | 低 | 中 | 中等规模 |
| Root+Frida | 50-200条/秒 | 高 | 高 | 大规模采集 |

## 常见问题

### Q: 如何添加新的球拍型号？
A: 编辑 `config/keywords.yaml`，添加型号名称和搜索关键词。

### Q: 如何查看采集的数据？
A: 启动前端服务器后访问 http://localhost:5173，或直接查看 `data/xianyu.db`。

### Q: 如何定时采集？
A: 使用 `python main.py schedule` 启动定时调度器，或配置系统定时任务。

### Q: 采集速度太慢怎么办？
A: 考虑使用Root+Frida方案，速度可提升100倍以上。

## 开发计划

- [x] FastAPI后端搭建
- [x] Vue3前端搭建
- [x] Root+Frida采集脚本
- [ ] 签名算法逆向
- [ ] 定时任务优化
- [ ] 数据清洗增强
- [ ] 前端功能完善

## 许可证

MIT License
