# 🏸 闲鱼球拍行情价监控系统

自动爬取闲鱼二手羽毛球拍成交数据，智能清洗分析，可视化展示行情走势。

## 功能特性

- **自动爬取** — Playwright自动化，支持Cookie/扫码登录
- **智能清洗** — 脏数据过滤、型号精准匹配、成色智能推断
- **成色评分** — 基于卖家描述关键词，0-100分量化成色，不信任卖家自标
- **虚标检测** — 自动发现卖家虚标成色（标"全新"实际有塌陷）
- **价格走势** — 按成色分层的价格趋势图
- **数据持久化** — SQLite存储，支持增量更新

## 快速开始

```bash
# 安装依赖
pip install playwright pyyaml loguru apscheduler
playwright install chromium

# 初始化数据库
python main.py init-db

# 爬取数据（首次需要扫码登录）
python main.py crawl

# 导出JSON给前端
python main.py export

# 本地预览
python main.py serve --port 8088
```

## 命令说明

| 命令 | 说明 |
|------|------|
| `init-db` | 初始化/迁移数据库 |
| `crawl` | 爬取所有关键词数据 |
| `crawl -k "疾光NF800PRO"` | 只爬指定型号 |
| `crawl --login cookie` | 只用Cookie登录 |
| `crawl --login qrcode` | 强制扫码登录 |
| `clean --export` | 对已有数据重新清洗 |
| `export` | 导出JSON给前端 |
| `serve` | 启动本地预览 |
| `schedule` | 启动定时调度 |
| `stats` | 查看数据库统计 |

## 项目结构

```
xianyu-market/
├── main.py                 # 主入口（CLI）
├── config/
│   ├── keywords.yaml       # 关键词配置（型号+搜索别名）
│   ├── racket_database.json # 球拍型号数据库（100+型号，278别名）
│   └── settings.yaml       # 运行参数配置
├── crawler/
│   ├── xianyu_spider.py    # 爬虫核心（Playwright）
│   ├── parser.py           # 数据解析
│   ├── cleaner.py          # 数据清洗（型号过滤+成色推断+脏数据检测）
│   ├── anti_detect.py      # 反检测
│   └── mtop_crawler.py     # API模式爬虫（实验性）
├── storage/
│   ├── db.py               # SQLite数据库操作
│   └── export.py           # JSON导出
├── scheduler/
│   └── runner.py           # 定时调度
└── web/
    ├── index.html           # 首页（型号列表）
    ├── racket.html          # 详情页（价格走势+成色分析）
    └── data/                # 导出的JSON数据
```

## 成色推断规则

系统不信任卖家自标的成色，而是基于描述中的关键词自动推断：

| 关键词 | 分数变化 | 说明 |
|--------|---------|------|
| 全新/未拆封 | →100分 | 直接设为全新 |
| 有质保/首线无暇 | +2~3分 | 正面加分 |
| 轻微磨损/划痕 | -3分 | 轻微瑕疵 |
| 掉漆/磕碰 | -5分 | 中等瑕疵 |
| 翻新/补漆 | -5~8分 | 翻新处理 |
| 有塌陷/修复 | -15~20分 | 严重问题 |

**分数映射：** ≥98全新 → ≥9095新 → ≥829新 → ≥7285新 → ≥608新

## 部署

### Vercel（静态前端）

```bash
# 导出数据后直接部署web/目录
python main.py export
cd web && vercel --prod
```

### 定时调度

```bash
# 配置 config/settings.yaml
schedule:
  enabled: true
  cron: "daily 2:00"

# 启动调度器
python main.py schedule
```
