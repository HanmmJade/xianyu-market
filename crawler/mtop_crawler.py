"""
闲鱼 mtop API 爬虫 v3 — 基于页面内置签名，主动调用API获取数据
核心思路：打开闲鱼页面 → 用 window.lib.mtop.request() 调用API → 提取成交数据
"""
import sys, asyncio, json, re
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent))
from playwright.async_api import async_playwright
from loguru import logger
from crawler.parser import parse_listing_record, match_model

OUTPUT_DIR = Path(__file__).parent / "data"
COOKIES_PATH = OUTPUT_DIR / "xianyu_cookies.json"


class MtopCrawler:
    """基于 mtop API 的闲鱼爬虫"""

    def __init__(self, headless=False):
        self.headless = headless
        self.browser = None
        self.ctx = None
        self.page = None
        self._pw = None

    async def start(self):
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.ctx = await self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"
        )
        if COOKIES_PATH.exists():
            with open(COOKIES_PATH) as f:
                cookies = json.load(f)
            if cookies:
                await self.ctx.add_cookies(cookies)

        self.page = await self.ctx.new_page()
        await self.page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};"
        )
        # 先打开首页让 mtop 初始化
        await self.page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        logger.info("浏览器已启动，mtop已初始化")

    async def close(self):
        if self.ctx:
            cookies = await self.ctx.cookies()
            COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(COOKIES_PATH, "w") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()

    async def call_mtop(self, api: str, data: dict, v: str = "1.0") -> dict:
        """调用 mtop API"""
        data_json = json.dumps(data, ensure_ascii=False)
        result = await self.page.evaluate("""async ([api, v, dataJson]) => {
            const mtop = window.lib?.mtop;
            if (!mtop) return {error: "mtop not available"};
            return new Promise((resolve) => {
                const timeout = setTimeout(() => resolve({error: "timeout"}), 15000);
                mtop.request({
                    api: api,
                    v: v,
                    data: dataJson,
                    type: "POST",
                    dataType: "json",
                    timeout: 10000,
                }, (success) => {
                    clearTimeout(timeout);
                    resolve({
                        ok: true,
                        ret: JSON.stringify(success?.ret || ""),
                        data: success?.data,
                    });
                }, (error) => {
                    clearTimeout(timeout);
                    resolve({
                        ok: false,
                        ret: JSON.stringify(error?.ret || ""),
                        error: JSON.stringify(error).substring(0, 500),
                    });
                });
            });
        }""", [api, v, data_json])

        return result

    async def search_items(self, keyword: str, page_num: int = 1, page_size: int = 20) -> list:
        """搜索商品（直接调用 mtop API）"""
        # 用JS直接调用，和成功的测试脚本一致
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
        result = await self.call_mtop("mtop.taobao.idle.pc.detail", {
            "itemId": item_id,
            "detailParams": "{}",
        })
        return result

    async def get_feed(self, page_num: int = 1) -> dict:
        """获取首页Feed数据"""
        result = await self.call_mtop("mtop.taobao.idlehome.home.webpc.feed", {
            "indexParams": "{}",
            "topicId": "",
            "pageNumber": page_num,
            "pageSize": 20,
        })
        return result

    async def crawl_keyword(self, keyword: str, model_name: str = "", max_pages: int = 3) -> list:
        """爬取关键词的搜索结果"""
        all_items = []

        for page_num in range(1, max_pages + 1):
            logger.info(f"搜索 '{keyword}' 第{page_num}页...")
            result = await self.search_items(keyword, page_num=page_num)

            if isinstance(result, dict) and result.get("source") == "dom":
                items = result.get("data", [])
            else:
                items = []

            logger.info(f"  找到 {len(items)} 个商品")

            for item in items:
                # 尝试获取详情
                item_id = item.get("item_id", "")
                if item_id:
                    try:
                        detail = await self.get_item_detail(item_id)
                        if detail.get("ok") and detail.get("data"):
                            item["detail"] = detail["data"]
                    except:
                        pass
                    await asyncio.sleep(1)

                all_items.append(item)

            await asyncio.sleep(2)

        return all_items


async def test_mtop():
    """测试 mtop API 调用"""
    crawler = MtopCrawler(headless=False)
    await crawler.start()

    try:
        # 测试1: 调用 Feed API
        print("\n" + "=" * 60)
        print("  测试1: mtop.taobao.idlehome.home.webpc.feed")
        print("=" * 60)
        feed = await crawler.get_feed()
        if feed.get("ok"):
            data = feed.get("data", {})
            cards = data.get("cardList", [])
            print(f"  [OK] 返回 {len(cards)} 个卡片")
            for i, card in enumerate(cards[:3]):
                cd = card.get("cardData", {})
                attrs = cd.get("attributeMap", {})
                title = cd.get("detailParams", {}).get("title", cd.get("title", ""))
                price = attrs.get("firstPrice", "")
                sold_time = attrs.get("recentSoldTime", "")
                if sold_time:
                    sold_time = datetime.fromtimestamp(int(sold_time) / 1000).strftime("%Y-%m-%d %H:%M")
                print(f"  [{i+1}] {title[:50]}  价格:{price}  最近售出:{sold_time}")
        else:
            print(f"  [FAIL] {feed.get('error', feed.get('ret', ''))}")

        # 测试2: 搜索商品
        print("\n" + "=" * 60)
        print("  测试2: 搜索 '天斧88D PRO'")
        print("=" * 60)
        search = await crawler.search_items("天斧88D PRO")
        if isinstance(search, list):
            print(f"  找到 {len(search)} 个商品")
            for item in search[:8]:
                print(f"  ¥{item.get('price',''):>6} | {item.get('title','')[:45]} | {item.get('user_nick','')}")
        else:
            print(f"  结果: {str(search)[:300]}")

        # 测试3: 获取商品详情
        if isinstance(search, list) and search:
                item_id = search[0].get("item_id", "")
                if item_id:
                    print(f"\n{'='*60}")
                    print(f"  测试3: 商品详情 {item_id}")
                    print(f"{'='*60}")
                    detail = await crawler.get_item_detail(item_id)
                    if detail.get("ok"):
                        data = detail.get("data", {})
                        print(f"  [OK] 数据键: {list(data.keys())[:15]}")
                        print(f"  预览: {json.dumps(data, ensure_ascii=False)[:500]}")
                    else:
                        print(f"  [FAIL] {detail.get('error','')}")

    finally:
        await crawler.close()

asyncio.run(test_mtop())
