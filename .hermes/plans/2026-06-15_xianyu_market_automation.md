# 闲鱼行情数据自动化采集方案

## 目标
自动采集100+羽毛球拍型号在闲鱼的**成交记录**（成交价、发布价、成交时间、成色），不依赖人工截图/翻页。

## 当前状态
- 手机：小米 2211133C，已ADB连接（ee635a46）
- 闲鱼：原生App已安装（com.taobao.idlefish），用户已登录
- 已验证：uiautomator2可读取行情页ImageView的content-desc，包含完整成交数据
- 已验证：手动流程可提取5条/屏记录
- **阻塞**：原生App用自定义渲染，大部分UI元素uiautomator2读不到，只有ImageView的content-desc可用
- **阻塞**：mitmproxy证书被Android SSL pinning拦截，无法抓包

## 方案对比

### 方案A：ADB自动化 + uiautomator2（推荐）
**原理**：用ADB模拟点击/输入控制原生App，uiautomator2读取行情页数据
**优点**：
- 不需要截图/OCR，直接读content-desc
- 已验证可行
- 不需要网络代理
**缺点**：
- 原生App搜索框可能需要坐标点击（uiautomator2读不到EditText）
- 翻页需要模拟滑动
- 每个型号需要手动导航到行情页
**速度**：每个型号约30秒（搜索+切tab+3次翻页），100个型号约50分钟

### 方案B：API拦截（最快但最难）
**原理**：找到闲鱼App的行情数据API，直接HTTP调用
**步骤**：
1. 用frida hook闲鱼App的SSL，绕过证书pinning
2. 用mitmproxy抓取行情API请求
3. 分析API格式和签名
4. Python批量调用
**优点**：100个型号几分钟搞定
**缺点**：
- 需要root手机或用frida-gadget注入
- 签名机制可能很复杂
- 反爬风险高
**速度**：100个型号约5-10分钟

### 方案C：浏览器自动化（备选）
**原理**：用ADB打开夸克浏览器访问m.goofish.com，Playwright/ADB控制浏览器
**优点**：网页DOM完整可读
**缺点**：
- 网页版行情数据在canvas里，DOM读不到
- 需要登录态
- 已验证不可行（行情数据是canvas渲染）

### 方案D：ADB全自动化（方案A的增强版）
**原理**：完全用ADB脚本控制手机，无需用户操作
**步骤**：
1. ADB shell am start 打开闲鱼
2. ADB input tap 点击搜索框（坐标）
3. ADB input text 输入关键词
4. ADB input tap 点击搜索/行情tab（坐标）
5. 循环：dump_hierarchy → 解析 → swipe翻页
**优点**：完全无人值守
**缺点**：坐标可能因设备分辨率不同而变化
**速度**：每个型号约20秒，100个型号约35分钟

## 推荐方案：D（ADB全自动化）

### 实施步骤

#### 第1步：坐标校准（5分钟）
1. ADB截图当前界面
2. 识别搜索框、搜索按钮、行情tab的坐标
3. 硬编码坐标（1080x2400分辨率）

#### 第2步：单型号自动化流程（核心）
```
for keyword in keywords:
    1. am start -n com.taobao.idlefish/.home.activity.InitActivity  # 回到首页
    2. sleep 2
    3. input tap <搜索框坐标>              # 点击搜索框
    4. sleep 1
    5. input text <keyword>                # 输入关键词
    6. input keyevent 66                   # 按回车搜索
    7. sleep 3
    8. input tap <行情tab坐标>             # 点击行情标签
    9. sleep 3
    10. for i in range(5):                 # 翻页抓取
        a. dump_hierarchy → 解析content-desc
        b. input swipe <翻页坐标>
        c. sleep 2
```

#### 第3步：数据解析
- 从content-desc提取：发布价、成交价、成交时间、品牌、成色
- 去重（同一笔成交不重复记录）
- 存入SQLite

#### 第4步：批量执行
- 读取keywords.yaml中的100个型号
- 每个型号执行第2步
- 失败重试（网络超时等）
- 进度日志

#### 第5步：数据导出
- 更新JSON给前端
- 生成行情报告

### 需要修改的文件
- `crawler/phone_extractor.py` → 重写为全自动化版本
- `storage/db.py` → 添加market_records表
- `main.py` → 添加phone-crawl命令

### 验证步骤
1. 先用1个型号测试完整流程
2. 检查数据完整性（成交价、发布价都有）
3. 扩展到5个型号
4. 全量100个型号

### 风险
1. **坐标偏移**：不同App版本坐标可能变 → 用相对坐标（百分比）
2. **App弹窗**：广告/升级弹窗打断流程 → 加弹窗检测和关闭逻辑
3. **限流**：频繁搜索可能触发验证码 → 加随机延迟（5-15秒）
4. **内存**：长时间运行手机可能卡 → 每20个型号重启App
5. **屏幕锁定**：已设置30分钟超时 → 脚本内持续唤醒

### 开放问题
1. 手机是否需要保持USB连接？→ 是
2. 手机能否同时做其他事？→ 不能，自动化期间会持续操控屏幕
3. 能否后台运行？→ 不能，需要前台操作App
