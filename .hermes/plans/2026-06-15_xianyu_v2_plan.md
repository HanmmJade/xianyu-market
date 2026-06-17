# 闲鱼行情数据采集 V2 — 修订计划（含Root方案）

## 核心变更
- **废弃**：网页版爬虫（方案B: Playwright API拦截）——网页版没有真实成交记录
- **废弃**：纯ADB UI翻页方案 —— 速度太慢（3-5条/分钟）
- **主方案**：Root + Frida + mitmproxy 抓包 → 直接调用API（50-200条/秒）
- **备选**：ADB自动化（网络环境不允许抓包时降级使用）
- **新增**：数据清洗流水线 + 前端网站自动更新 + 全自动化定时任务

## 当前环境
- 手机：小米 2211133C，ADB连接（ee635a46），Android 6.0.1，**将root**
- 闲鱼App：已安装（com.taobao.idlefish），已登录
- 已有数据：12个型号（网页版抓的在售商品，非成交记录）
- 前端：`web/index.html` + `web/racket.html` + `web/data/*.json`

---

## 整体架构

```
┌─────────────────────────────────────────────────┐
│  全自动化流水线（定时任务 / 手动触发）            │
│                                                   │
│  Step 1: Root + Frida 绕过SSL Pinning            │
│      ↓                                            │
│  Step 2: mitmproxy 拦截闲鱼行情API请求            │
│      ↓                                            │
│  Step 3: 提取API签名算法（x-sign, wua等）         │
│      ↓                                            │
│  Step 4: Python批量调API获取成交记录              │
│      ↓                                            │
│  Step 5: 数据清洗（去重/标准化/异常过滤）         │
│      ↓                                            │
│  Step 6: 存入SQLite (market_records表)            │
│      ↓                                            │
│  Step 7: 导出JSON到 web/data/                    │
│      ↓                                            │
│  Step 8: 前端网站自动更新                         │
└─────────────────────────────────────────────────┘
```

---

## Phase 1：Root + 环境搭建

### 1.1 手机Root
- 小米 2211133C 解锁Bootloader
- 刷入Magisk获取root权限
- 验证：`adb shell su -c "id"` 返回 uid=0

### 1.2 安装Frida
```bash
# PC端
pip install frida-tools

# 手机端（push frida-server到手机）
adb push frida-server /data/local/tmp/
adb shell su -c "chmod 755 /data/local/tmp/frida-server"
adb shell su -c "/data/local/tmp/frida-server &"
```

### 1.3 安装mitmproxy
```bash
pip install mitmproxy
# 手机安装mitmproxy证书到系统级（需要root）
# 将证书安装到 /system/etc/security/cacerts/
```

### 关键文件
- `setup/root_setup.sh` — 新建，root环境搭建脚本
- `setup/frida_setup.sh` — 新建，frida安装脚本
- `setup/cert_install.sh` — 新建，mitmproxy证书安装脚本

---

## Phase 2：API抓取 + 签名分析

### 2.1 启动mitmproxy拦截
```bash
# 启动代理
mitmdump -s scripts/xianyu_intercept.py -p 8080

# 手机设置代理指向PC:8080
adb shell settings put global http_proxy <PC_IP>:8080
```

### 2.2 手动触发API请求
- ADB自动化打开闲鱼 → 搜索 → 行情tab
- mitmproxy捕获行情API请求：`h5api.m.goofish.com/h5/mtop.taobao.idlefish.search.item/`
- 记录：URL、Headers、Cookie、签名参数（x-sign, wua, x-umt等）

### 2.3 逆向签名算法
- 分析Frida hook日志，找到签名生成逻辑
- 提取关键参数：appKey、token、时间戳
- Python复现签名算法

### 关键文件
- `scripts/xianyu_intercept.py` — 新建，mitmproxy拦截脚本
- `scripts/sign_analyzer.py` — 新建，签名算法分析
- `crawler/api_client.py` — 新建，API直接调用客户端

---

## Phase 3：批量API采集

### 3.1 API调用流程
```python
import requests
import time
import random

for model_name, keywords in RACKET_KEYWORDS.items():
    for keyword in keywords:
        # 构造请求
        params = {
            'keyword': keyword,
            'sortType': 'sold_time',  # 按成交时间排序
            'pageNumber': 1,
            'pageSize': 20,
        }
        headers = generate_headers()  # 包含签名
        
        # 调用API
        resp = requests.get(API_URL, params=params, headers=headers)
        data = resp.json()
        
        # 解析成交记录
        for item in data['resultList']:
            save_to_db(item, model_name)
        
        # 随机延迟防限流
        time.sleep(random.uniform(2, 5))
```

### 3.2 数据字段
从API响应提取：
- `title` — 商品标题
- `soldPrice` — 成交价
- `price` — 发布价
- `soldTime` — 成交时间
- `area` — 地域（已去掉）
- `fishTags` — 成色/品牌标签
- `userNick` — 卖家昵称
- `itemId` — 商品ID

### 关键文件
- `crawler/batch_crawler.py` — 新建，批量API采集主脚本
- `config/keywords.yaml` — 新建，15个球拍型号配置

---

## Phase 4：数据清洗

### 4.1 清洗规则
| 规则 | 说明 |
|------|------|
| 去重 | 同一itemId → 保留1条 |
| 价格过滤 | <50元或>5000元标记异常 |
| 成色标准化 | "九成新"→9, "八成新"→8 |
| 日期标准化 | 统一为 YYYY-MM-DD |
| 型号归一化 | "天斧100zz"→"天斧100ZZ", "88dpro"→"天斧88D PRO" |
| 品牌提取 | YONEX/LI-NING/VICTOR |
| 异常检测 | 发布价与成交价差距>80%标记 |

### 4.2 数据质量标记
- `data_source`: "api"（抓包）或 "adb"（ADB降级）
- `confidence`: 数据可信度（高/中/低）

### 关键文件
- `crawler/data_cleaner.py` — 新建，清洗流水线

---

## Phase 5：前端网站更新

### 5.1 数据导出
从 SQLite 导出到 JSON：
- `web/data/index.json` — 汇总统计
- `web/data/<型号>.json` — 详细成交记录

### 5.2 前端页面
- 已有 `web/index.html`（型号总览）和 `web/racket.html`（单型号详情）
- JSON格式不变，兼容现有前端

### 关键文件
- `scripts/export_to_web.py` — 新建，SQLite → JSON导出

---

## Phase 6：全自动化定时任务

### 6.1 一键执行脚本
```bash
# run_all.sh — 全自动流水线
python crawler/batch_crawler.py      # API采集
python crawler/data_cleaner.py       # 数据清洗
python scripts/export_to_web.py      # 导出JSON
echo "Done! 数据已更新到前端"
```

### 6.2 Windows定时任务
```powershell
# 每天凌晨2点执行
schtasks /create /tn "XianyuCrawl" /tr "D:\AI共享文件夹\xianyu-market\run_all.bat" /sc daily /st 02:00
```

### 6.3 监控
- 采集日志：`logs/crawl_YYYYMMDD.log`
- 异常告警：采集失败/数据量异常 → 飞书通知

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `setup/root_setup.sh` | 新建 | Root环境搭建 |
| `setup/frida_setup.sh` | 新建 | Frida安装 |
| `setup/cert_install.sh` | 新建 | mitmproxy证书安装 |
| `scripts/xianyu_intercept.py` | 新建 | mitmproxy拦截脚本 |
| `scripts/sign_analyzer.py` | 新建 | 签名算法分析 |
| `crawler/api_client.py` | 新建 | API直接调用客户端 |
| `crawler/batch_crawler.py` | 新建 | 批量API采集主脚本 |
| `crawler/data_cleaner.py` | 新建 | 数据清洗流水线 |
| `scripts/export_to_web.py` | 新建 | SQLite → JSON导出 |
| `config/keywords.yaml` | 新建 | 15个球拍型号配置 |
| `run_all.bat` | 新建 | 一键执行脚本 |
| `storage/db.py` | 修改 | 新增 market_records 表 |
| `web/data/*.json` | 自动更新 | 前端数据文件 |

---

## 方案对比

| | ADB自动化 | Root+抓包+API |
|---|---|---|
| 速度 | 3-5条/分钟 | 50-200条/秒 |
| 15型号全量 | ~50分钟 | ~30秒 |
| 稳定性 | UI变动易崩 | 接口稳定 |
| 维护成本 | 低 | 需跟进签名变化 |
| 风险 | 低 | 高（封号/法律） |
| 自动化难度 | 中 | 低（API调用天然自动化） |

---

## 验证步骤

1. **Root验证**：确认 `su` 可用
2. **Frida验证**：hook闲鱼App SSL成功
3. **mitmproxy验证**：能看到行情API请求
4. **单型号API测试**：用提取的签名手动调一次API
5. **批量采集**：15个型号全量采集
6. **数据清洗**：检查去重/标准化结果
7. **前端展示**：打开 web/index.html 确认数据正确

---

## 风险与应对

| 风险 | 应对 |
|------|------|
| 封号风险 | 控制频率（2-5秒/请求），用小号 |
| 签名算法变化 | 自动检测失败 → 回退到Frida重新抓包 |
| Root后银行App不工作 | Magisk Hide隐藏root |
| 接口限流 | 代理池 + 随机延迟 |
| 法律风险 | 仅个人研究用途，不商用 |

---

## 开放问题

1. 前端网站是否需要新增功能（筛选/排序/图表）？
2. 部署到公网还是本地HTML？
3. 数据更新频率：每天/每周/手动触发？
4. 是否需要准备多个闲鱼账号防封？
