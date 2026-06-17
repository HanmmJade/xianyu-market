# -*- coding: utf-8 -*-
"""
签名拦截器 — 通过 Playwright 拦截闲鱼页面请求，提取 mtop API 签名
用途：缓存签名供 api_client.py 直接调用，避免逆向签名算法
"""

import asyncio
import json
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from loguru import logger

COOKIES_PATH = Path(__file__).parent.parent / "data" / "xianyu_cookies.json"
SIGN_CACHE_PATH = Path(__file__).parent.parent / "data" / "sign_cache.json"


class SignInterceptor:
    """通过 Playwright 拦截 mtop 请求，提取签名参数"""

    def __init__(self, headless=False):
        self.headless = headless
        self.browser = None
        self.ctx = None
        self.page = None
        self._pw = None
        self.captured_signs = []

    async def start(self):
        from playwright.async_api import async_playwright

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
            try:
                with open(COOKIES_PATH) as f:
                    cookies = json.load(f)
                if cookies:
                    await self.ctx.add_cookies(cookies)
            except Exception:
                pass

        self.page = await self.ctx.new_page()
        await self.page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};"
        )

        # 注册请求拦截
        self.page.on("request", self._on_request)

        logger.info("签名拦截器已启动")

    async def _on_request(self, request):
        """拦截 mtop API 请求，提取签名参数"""
        url = request.url
        if "h5api.m.goofish.com" not in url:
            return

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # 提取关键参数
        api_match = re.search(r'/h5/([^/]+)/', parsed.path)
        api_name = api_match.group(1) if api_match else ""

        sign_data = {
            "api": api_name,
            "sign": params.get("sign", [""])[0],
            "appKey": params.get("appKey", [""])[0],
            "t": params.get("t", [""])[0],
            "v": params.get("v", [""])[0],
            "jsv": params.get("jsv", [""])[0],
            "type": params.get("type", [""])[0],
            "accountSite": params.get("accountSite", [""])[0],
            "url": url,
            "captured_at": datetime.now().isoformat(),
        }

        # 只记录有签名的请求
        if sign_data["sign"]:
            self.captured_signs.append(sign_data)
            logger.debug(f"[签名捕获] {api_name} sign={sign_data['sign'][:16]}...")

    async def intercept_search(self, keyword: str, max_pages: int = 1) -> list:
        """
        触发搜索操作，拦截生成的签名。
        返回捕获的签名列表。
        """
        before_count = len(self.captured_signs)

        # 打开搜索页
        search_url = f"https://www.goofish.com/search?q={keyword}"
        await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        # 等待搜索结果加载
        try:
            await self.page.wait_for_selector('[class*="feeds-item-wrap"], a[href*="/item/"]', timeout=10000)
        except Exception:
            logger.warning("搜索结果未加载")

        # 翻页
        for i in range(max_pages - 1):
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(2)

        new_signs = self.captured_signs[before_count:]
        logger.info(f"搜索 '{keyword}' 捕获 {len(new_signs)} 个签名")
        return new_signs

    async def intercept_home(self) -> list:
        """打开首页，捕获首页相关 API 签名"""
        before_count = len(self.captured_signs)

        await self.page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        new_signs = self.captured_signs[before_count:]
        logger.info(f"首页捕获 {len(new_signs)} 个签名")
        return new_signs

    def get_sign_for_api(self, api_name: str) -> dict:
        """获取指定 API 的最新签名"""
        for sign in reversed(self.captured_signs):
            if api_name in sign.get("api", ""):
                return sign
        return None

    def save_cache(self):
        """保存签名缓存"""
        SIGN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 去重：同一 API 只保留最新的
        deduped = {}
        for sign in self.captured_signs:
            api = sign.get("api", "")
            deduped[api] = sign

        with open(SIGN_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(list(deduped.values()), f, ensure_ascii=False, indent=2)

        logger.info(f"签名缓存已保存: {len(deduped)} 个 API")

    def load_cache(self) -> dict:
        """加载签名缓存，返回 {api_name: sign_data}"""
        if not SIGN_CACHE_PATH.exists():
            return {}

        try:
            with open(SIGN_CACHE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {s["api"]: s for s in data}
        except Exception as e:
            logger.warning(f"加载签名缓存失败: {e}")
            return {}

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


async def capture_signs(keyword: str = "天斧88D PRO"):
    """交互式签名捕获"""
    interceptor = SignInterceptor(headless=False)
    await interceptor.start()

    try:
        # 确保已登录
        await interceptor.page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        page_text = await interceptor.page.evaluate("() => document.body?.innerText || ''")
        if '登录' in page_text and '退出' not in page_text:
            print("\n请先在浏览器中登录闲鱼，然后按 Enter 继续...")
            await interceptor.login_qrcode()

        # 捕获首页签名
        print("\n捕获首页 API 签名...")
        await interceptor.intercept_home()

        # 捕获搜索签名
        print(f"\n捕获搜索 '{keyword}' 的 API 签名...")
        await interceptor.intercept_search(keyword)

        # 保存
        interceptor.save_cache()

        # 打印结果
        print(f"\n{'='*60}")
        print(f"  捕获到 {len(interceptor.captured_signs)} 个签名")
        print(f"{'='*60}")
        seen = set()
        for sign in interceptor.captured_signs:
            api = sign["api"]
            if api not in seen:
                seen.add(api)
                print(f"  {api}")
                print(f"    sign: {sign['sign'][:32]}...")
                print(f"    appKey: {sign['appKey']}")
                print(f"    t: {sign['t']}")

    finally:
        await interceptor.close()


if __name__ == "__main__":
    asyncio.run(capture_signs())
