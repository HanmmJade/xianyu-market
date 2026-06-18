"""
闲鱼 mtop API 爬虫 v4 — 基于页面内置签名，主动调用API获取数据
核心思路：打开闲鱼页面 → 用 window.lib.mtop.request() 调用API → 提取成交数据
v4: 修复crawl_keyword bug，集成cleaner+storage，支持完整采集流程
"""
import sys, asyncio, json, re, random, yaml
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))
from playwright.async_api import async_playwright
from loguru import logger
from crawler.cleaner import clean_record, classify_model, infer_condition, is_garbage

CONFIG_DIR = Path(__file__).parent.parent / "config"
COOKIES_PATH = Path(__file__).parent.parent / "data" / "xianyu_cookies.json"


def load_keywords():
    kw_path = CONFIG_DIR / "keywords.yaml"
    if not kw_path.exists():
        logger.error(f"关键词配置不存在: {kw_path}")
        return []
    with open(kw_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data.get('keywords', [])


def load_settings():
    cfg_path = CONFIG_DIR / "settings.yaml"
    defaults = {
        'headless': False,
        'max_pages_per_keyword': 3,
        'min_delay': 3,
        'max_delay': 8,
        'timeout': 30000,
    }
    if cfg_path.exists():
        with open(cfg_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        defaults.update(data.get('crawler', {}))
    return defaults


class MtopCrawler:
    """基于 mtop API 的闲鱼爬虫 v4"""

    def __init__(self, headless=None):
        settings = load_settings()
        self.headless = headless if headless is not None else settings.get('headless', False)
        self.max_pages = settings.get('max_pages_per_keyword', 3)
        self.min_delay = settings.get('min_delay', 3)
        self.max_delay = settings.get('max_delay', 8)
        self.timeout = settings.get('timeout', 30000)
        self.keywords = load_keywords()
        self.browser = None
        self.ctx = None
        self.page = None
        self._pw = None

    async def start(self):
        """启动浏览器并初始化 mtop"""
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
            ]
        )
        self.ctx = await self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"
        )

        # 加载 Cookie
        if COOKIES_PATH.exists():
            try:
                with open(COOKIES_PATH) as f:
                    cookies = json.load(f)
                if cookies:
                    await self.ctx.add_cookies(cookies)
                    logger.info(f"已加载 {len(cookies)} 个 Cookie")
            except Exception as e:
                logger.warning(f"Cookie 加载失败: {e}")

        self.page = await self.ctx.new_page()
        await self.page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};"
        )

        # 打开首页让 mtop 初始化
        await self.page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=self.timeout)

        # 等待 mtop 库加载完成（最多等 15 秒）
        for i in range(15):
            mtop_ready = await self.page.evaluate("() => !!window.lib?.mtop")
            if mtop_ready:
                break
            await asyncio.sleep(1)

        if not mtop_ready:
            logger.warning("mtop 库未加载，尝试刷新页面...")
            await self.page.reload(wait_until="domcontentloaded", timeout=self.timeout)
            await asyncio.sleep(5)
            mtop_ready = await self.page.evaluate("() => !!window.lib?.mtop")

        if mtop_ready:
            logger.info("浏览器已启动，mtop 已就绪")
        else:
            logger.error("mtop 库加载失败，请检查登录状态")

    async def save_cookies(self):
        """保存 Cookie"""
        if self.ctx:
            cookies = await self.ctx.cookies()
            COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(COOKIES_PATH, "w") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"Cookie 已保存 ({len(cookies)} 个)")

    async def close(self):
        """关闭浏览器"""
        await self.save_cookies()
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("浏览器已关闭")

    # ── 登录模块 ────────────────────────────────────────────

    async def check_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            page_text = await self.page.evaluate("() => document.body?.innerText || ''")
            logged_in_keywords = ['退出', '我的订单', '我买到的', '个人中心', '消息']
            for kw in logged_in_keywords:
                if kw in page_text:
                    return True

            cookies = await self.ctx.cookies()
            login_cookies = [c for c in cookies if 'xianyu' in c.get('domain', '') or 'goofish' in c.get('domain', '')]
            return len(login_cookies) >= 5
        except Exception as e:
            logger.warning(f"登录检查异常: {e}")
            return False

    async def login_qrcode(self) -> bool:
        """扫码登录"""
        logger.info("打开闲鱼登录页，请用手机淘宝/支付宝扫码...")
        await self.page.goto("https://www.goofish.com/login", wait_until="domcontentloaded", timeout=self.timeout)
        await asyncio.sleep(3)

        qr_path = Path(__file__).parent.parent / "data" / "qrcode.png"
        qr_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            qr_el = await self.page.query_selector(
                '[class*="qrcode"], [class*="qr-code"], img[src*="qr"], '
                '[class*="login-qrcode"], canvas'
            )
            if qr_el:
                await qr_el.screenshot(path=str(qr_path))
                logger.info(f"二维码已保存: {qr_path}")
            else:
                await self.page.screenshot(path=str(qr_path))
                logger.info(f"登录页截图: {qr_path}")
        except Exception as e:
            logger.debug(f"截图失败: {e}")

        print()
        print("=" * 50)
        print("  请用手机淘宝/支付宝 扫描浏览器中的二维码登录")
        print("  或打开 data/qrcode.png 查看截图")
        print("=" * 50)
        print()

        for i in range(600):
            await asyncio.sleep(1)
            if "login" not in self.page.url.lower():
                logger.info("扫码登录成功!")
                await self.save_cookies()
                return True
            if i > 0 and i % 30 == 0:
                logger.info(f"仍在等待扫码... ({i}秒)")

        logger.error("扫码登录超时(600秒)")
        return False

    async def login_if_needed(self) -> bool:
        """登录入口：先试 Cookie，失败则扫码"""
        if await self.check_logged_in():
            logger.info("Cookie 登录成功")
            return True

        logger.info("Cookie 已失效，切换扫码登录")
        return await self.login_qrcode()

    # ── mtop API 调用 ──────────────────────────────────────

    async def search_items(self, keyword: str, page_num: int = 1, page_size: int = 20) -> list:
        """搜索商品（直接调用 mtop API）"""
        result = await self.page.evaluate("""async ([keyword, pageNum, pageSize]) => {
            const mtop = window.lib?.mtop;
            if (!mtop) return {error: "no mtop"};
            return new Promise((resolve) => {
                const timeout = setTimeout(() => resolve({error: "timeout"}), 15000);
                mtop.request({
                    api: "mtop.taobao.idlemtopsearch.pc.search",
                    v: "1.0",
                    data: JSON.stringify({
                        keyword: keyword,
                        pageNumber: pageNum,
                        pageSize: pageSize,
                    }),
                    type: "POST",
                    dataType: "json",
                    timeout: 10000,
                }, (success) => {
                    clearTimeout(timeout);
                    resolve({
                        ok: true,
                        data: success?.data,
                    });
                }, (error) => {
                    clearTimeout(timeout);
                    resolve({
                        ok: false,
                        ret: JSON.stringify(error?.ret || ""),
                        error: JSON.stringify(error).substring(0, 300),
                    });
                });
            });
        }""", [keyword, page_num, page_size])

        items = []
        if not result.get("ok"):
            logger.warning(f"搜索API失败: {result.get('error', result.get('ret', ''))}")
            return items

        result_list = result.get("data", {}).get("resultList", [])
        for entry in result_list:
            try:
                main = entry["data"]["item"]["main"]
                ex = main.get("exContent", {})
                dp = ex.get("detailParams", {})
                args = main.get("clickParam", {}).get("args", {})

                item_id = str(dp.get("itemId", ex.get("itemId", args.get("id", ""))))
                title = dp.get("title", ex.get("title", ""))
                sold_price = str(dp.get("soldPrice", args.get("price", "")))
                want = args.get("wantNum", "")
                user_nick = dp.get("userNick", "")

                if title and item_id:
                    items.append({
                        "item_id": item_id,
                        "title": title,
                        "price": sold_price,
                        "want_num": want,
                        "user_nick": user_nick,
                        "url": f"https://www.goofish.com/item?id={item_id}",
                    })
            except (KeyError, TypeError):
                continue

        return items

    async def get_item_detail(self, item_id: str) -> dict:
        """获取商品详情（通过 mtop API）"""
        result = await self.page.evaluate("""async ([itemId]) => {
            const mtop = window.lib?.mtop;
            if (!mtop) return {error: "no mtop"};
            return new Promise((resolve) => {
                const timeout = setTimeout(() => resolve({error: "timeout"}), 15000);
                mtop.request({
                    api: "mtop.taobao.idle.pc.detail",
                    v: "1.0",
                    data: JSON.stringify({
                        itemId: itemId,
                        detailParams: "{}",
                    }),
                    type: "POST",
                    dataType: "json",
                    timeout: 10000,
                }, (success) => {
                    clearTimeout(timeout);
                    resolve({ok: true, data: success?.data});
                }, (error) => {
                    clearTimeout(timeout);
                    resolve({ok: false, error: JSON.stringify(error).substring(0, 300)});
                });
            });
        }""", [item_id])
        return result

    # ── 采集逻辑 ────────────────────────────────────────────

    async def crawl_keyword(self, keyword: str, model_name: str = "",
                            max_pages: int = None) -> list:
        """
        爬取单个关键词的搜索结果，集成实时清洗。

        参数:
            keyword: 搜索词
            model_name: 标准型号名
            max_pages: 最大页数（默认用配置值）
        """
        if max_pages is None:
            max_pages = self.max_pages

        all_records = []

        for page_num in range(1, max_pages + 1):
            logger.info(f"搜索 '{keyword}' 第{page_num}页...")
            items = await self.search_items(keyword, page_num=page_num)

            if not items:
                logger.info(f"  第{page_num}页无结果，停止翻页")
                break

            logger.info(f"  找到 {len(items)} 个商品")

            for item in items:
                title = item.get("title", "")
                price_str = item.get("price", "0")

                # 价格转换
                try:
                    price = float(price_str)
                except (ValueError, TypeError):
                    continue

                # 构造记录
                record = {
                    "model": model_name or keyword,
                    "title": title,
                    "price": price,
                    "source_url": item.get("url", ""),
                    "sold_time": "",
                    "listed_time": "",
                }

                # 实时清洗
                cleaned = clean_record(record, target_model=model_name or keyword)
                if not cleaned.get("_clean_pass", False):
                    reject = cleaned.get("_clean_reject", "")
                    logger.debug(f"[清洗拒绝] ¥{price} {title[:30]}... 原因: {reject}")
                    continue

                # 应用推断成色
                inferred = cleaned.get("_inferred_condition", {})
                if inferred.get("label"):
                    record["condition"] = inferred["label"]
                    record["condition_inferred"] = inferred["label"]
                    record["condition_score"] = inferred.get("score", 0)
                    record["condition_claimed"] = inferred.get("claimed", "")
                    record["condition_evidence"] = inferred.get("evidence", [])
                    record["condition_severe"] = inferred.get("has_severe_issue", False)

                all_records.append(record)

            # 翻页延迟
            if page_num < max_pages:
                delay = random.uniform(self.min_delay, self.max_delay)
                await asyncio.sleep(delay)

        logger.info(f"关键词 '{keyword}' 共采集 {len(all_records)} 条（已清洗）")
        return all_records

    async def crawl_all(self, keyword_filter: str = '') -> list:
        """
        爬取所有配置的关键词，返回清洗后的记录列表。

        参数:
            keyword_filter: 可选，只爬取包含此关键词的型号
        """
        all_records = []

        kw_list = self.keywords
        if keyword_filter:
            kw_list = [k for k in self.keywords if keyword_filter.lower() in k['name'].lower()]
            if not kw_list:
                kw_list = [{'name': keyword_filter, 'aliases': [keyword_filter], 'brand': ''}]

        for kw_cfg in kw_list:
            model_name = kw_cfg['name']
            aliases = kw_cfg.get('aliases', [model_name])

            for alias in aliases:
                records = await self.crawl_keyword(alias, model_name=model_name)
                all_records.extend(records)
                await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

        logger.info(f"总计采集 {len(all_records)} 条记录（已清洗）")
        return all_records


async def test_mtop():
    """测试 mtop API 调用"""
    crawler = MtopCrawler(headless=False)
    await crawler.start()

    try:
        # 确保已登录
        if not await crawler.login_if_needed():
            print("登录失败，无法继续")
            return

        # 测试搜索
        print("\n" + "=" * 60)
        print("  测试: 搜索 '天斧88D PRO'")
        print("=" * 60)
        records = await crawler.crawl_keyword("天斧88D PRO", model_name="天斧88D PRO")
        print(f"  采集到 {len(records)} 条记录")
        for r in records[:5]:
            cond = r.get('condition_inferred', r.get('condition', ''))
            print(f"  ¥{r['price']:>8.0f} | {cond:>6} | {r['title'][:40]}")

    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(test_mtop())
