# -*- coding: utf-8 -*-
"""
闲鱼爬虫核心 — Playwright 自动化 goofish.com
支持：Cookie复用登录 / 扫码登录
v2: 集成cleaner实时清洗，使用全部aliases匹配
"""

import asyncio
import json
import yaml
import random
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from loguru import logger

from crawler.anti_detect import random_ua, random_viewport, random_delay
from crawler.parser import parse_listing_record
from crawler.cleaner import clean_record, classify_model, infer_condition, is_garbage

CONFIG_DIR = Path(__file__).parent.parent / "config"
COOKIES_PATH = Path(__file__).parent.parent / "data" / "xianyu_cookies.json"


def load_keywords() -> List[Dict]:
    kw_path = CONFIG_DIR / "keywords.yaml"
    if not kw_path.exists():
        logger.error(f"关键词配置不存在: {kw_path}")
        return []
    with open(kw_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data.get('keywords', [])


def load_settings() -> Dict:
    cfg_path = CONFIG_DIR / "settings.yaml"
    defaults = {
        'headless': False,
        'max_pages_per_keyword': 5,
        'min_delay': 3,
        'max_delay': 8,
        'timeout': 30000,
    }
    if cfg_path.exists():
        with open(cfg_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        defaults.update(data.get('crawler', {}))
    return defaults


class XianyuSpider:
    """闲鱼爬虫 v2 — 集成实时清洗"""

    def __init__(self, headless: bool = None, login_mode: str = 'auto'):
        settings = load_settings()
        self.headless = headless if headless is not None else settings.get('headless', False)
        self.max_pages = settings.get('max_pages_per_keyword', 5)
        self.min_delay = settings.get('min_delay', 3)
        self.max_delay = settings.get('max_delay', 8)
        self.timeout = settings.get('timeout', 30000)
        self.keywords = load_keywords()
        self.login_mode = login_mode  # auto / cookie / qrcode
        self.browser = None
        self.context = None
        self.page = None
        self._pw = None

    # ── 浏览器生命周期 ──────────────────────────────────────

    async def start(self):
        """启动浏览器"""
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
            ]
        )
        self.context = await self.browser.new_context(
            viewport=random_viewport(),
            user_agent=random_ua(),
        )
        self.page = await self.context.new_page()

        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
            window.chrome = {runtime: {}};
        """)

        logger.info("浏览器已启动")

    async def save_cookies(self):
        COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
        cookies = await self.context.cookies()
        with open(COOKIES_PATH, 'w') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info(f"Cookie已保存: {COOKIES_PATH}")

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()
        logger.info("浏览器已关闭")

    # ── 登录模块 ────────────────────────────────────────────

    async def _load_cookies(self) -> bool:
        """从文件加载Cookie"""
        if not COOKIES_PATH.exists():
            return False
        try:
            with open(COOKIES_PATH, 'r') as f:
                cookies = json.load(f)
            if not cookies:
                return False
            await self.context.add_cookies(cookies)
            logger.info(f"Cookie已加载 ({len(cookies)}条)")
            return True
        except Exception as e:
            logger.warning(f"Cookie加载失败: {e}")
            return False

    async def _check_logged_in(self) -> bool:
        """检查当前是否已登录"""
        try:
            await self.page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=self.timeout)
            await asyncio.sleep(5)  # 等待页面充分加载

            page_text = await self.page.evaluate("() => document.body?.innerText || ''")

            # 未登录标志：页面包含"登录"按钮文本
            if '登录' in page_text and '退出' not in page_text and '我的' not in page_text:
                # 再确认一下，可能是页面还没加载完
                await asyncio.sleep(3)
                page_text = await self.page.evaluate("() => document.body?.innerText || ''")
                if '登录' in page_text and '退出' not in page_text:
                    return False

            # 已登录标志：有退出/我的/订单等关键词
            logged_in_keywords = ['退出', '我的订单', '我买到的', '个人中心', '消息']
            for kw in logged_in_keywords:
                if kw in page_text:
                    return True

            # 检查cookie数量作为最后手段
            cookies = await self.context.cookies()
            login_cookies = [c for c in cookies if 'xianyu' in c.get('domain', '') or 'goofish' in c.get('domain', '')]
            if len(login_cookies) >= 5:
                return True

            return False
        except Exception as e:
            logger.warning(f"登录状态检查异常: {e}")
            return False

    async def _login_qrcode(self) -> bool:
        """扫码登录"""
        logger.info("打开闲鱼登录页，请用手机淘宝/支付宝扫码...")
        await self.page.goto("https://www.goofish.com/login", wait_until="domcontentloaded", timeout=self.timeout)
        await asyncio.sleep(3)

        # 截图保存二维码区域，方便用户查看
        qr_path = Path(__file__).parent.parent / "data" / "qrcode.png"
        qr_path.parent.mkdir(parents=True, exist_ok=True)

        # 等待二维码加载
        try:
            qr_el = await self.page.query_selector(
                '[class*="qrcode"], [class*="qr-code"], img[src*="qr"], '
                '[class*="login-qrcode"], canvas'
            )
            if qr_el:
                await qr_el.screenshot(path=str(qr_path))
                logger.info(f"二维码已保存到: {qr_path}")
            else:
                # 截整个页面
                await self.page.screenshot(path=str(qr_path))
                logger.info(f"登录页截图已保存: {qr_path}")
        except Exception as e:
            logger.debug(f"截图失败: {e}")

        print()
        print("=" * 50)
        print("  请用手机淘宝/支付宝 扫描浏览器中的二维码登录")
        print("  或者打开 data/qrcode.png 查看截图")
        print("  等待中...")
        print("=" * 50)
        print()

        # 等待用户扫码完成（最多600秒）
        for i in range(600):
            await asyncio.sleep(1)
            current_url = self.page.url
            # 登录成功后会跳转离开login页面
            if "login" not in current_url.lower():
                logger.info("扫码登录成功!")
                await self.save_cookies()
                return True
            # 每30秒提示一下
            if i > 0 and i % 30 == 0:
                logger.info(f"仍在等待扫码... ({i}秒)")

        logger.error("扫码登录超时(600秒)")
        return False

    async def login_if_needed(self) -> bool:
        """登录入口：auto模式先试Cookie再试扫码"""
        if self.login_mode == 'cookie':
            if await self._load_cookies():
                if await self._check_logged_in():
                    logger.info("Cookie登录成功")
                    return True
                else:
                    logger.warning("Cookie已失效")
                    return False
            else:
                logger.warning("无Cookie文件")
                return False

        if self.login_mode == 'qrcode':
            return await self._login_qrcode()

        # auto模式：先Cookie，失败则扫码
        logger.info("尝试Cookie登录...")
        if await self._load_cookies():
            if await self._check_logged_in():
                logger.info("Cookie登录成功")
                return True
            else:
                logger.info("Cookie已失效，切换扫码登录")

        return await self._login_qrcode()

    # ── 搜索与解析 ──────────────────────────────────────────

    async def search_keyword(self, keyword: str, model_name: str = '',
                              all_aliases: List[str] = None) -> List[Dict]:
        """
        搜索单个关键词，使用全部aliases进行型号匹配。

        参数:
            keyword: 搜索词（用于构造搜索URL）
            model_name: 标准型号名（用于数据库存储和清洗）
            all_aliases: 该型号的所有别名列表（用于匹配，不仅仅是keyword）
        """
        records = []
        search_url = f"https://www.goofish.com/search?q={keyword}"

        logger.info(f"搜索: {keyword} (型号: {model_name})")
        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=self.timeout)
            await asyncio.sleep(random_delay(4, 6))
        except Exception as e:
            logger.error(f"搜索页加载失败: {e}")
            return records

        # 尝试切换到"已卖出"筛选（如果有的话）
        try:
            sold_btn = await self.page.query_selector('text="已卖出"')
            if not sold_btn:
                sold_btn = await self.page.query_selector('text="已售出"')
            if sold_btn:
                await sold_btn.click()
                await asyncio.sleep(random_delay(2, 4))
                logger.info("已切换到已卖出筛选")
        except Exception as e:
            logger.debug(f"未找到已卖出筛选: {e}")

        # 使用全部aliases构建匹配配置
        if all_aliases:
            model_keywords = [{'name': model_name, 'aliases': all_aliases}]
        elif model_name:
            model_keywords = [{'name': model_name, 'aliases': [keyword]}]
        else:
            model_keywords = self.keywords

        # 使用JS提取商品数据
        for page_num in range(self.max_pages):
            page_records = await self._extract_items_js(keyword, model_name, model_keywords)
            records.extend(page_records)
            logger.info(f"  第{page_num+1}页: {len(page_records)}条")

            # 翻页
            has_next = await self._go_next_page()
            if not has_next:
                break
            await asyncio.sleep(random_delay(self.min_delay, self.max_delay))

        logger.info(f"关键词 '{keyword}' 共抓取 {len(records)} 条")
        return records

    async def _extract_items_js(self, keyword: str, model_name: str,
                                 model_keywords: List[Dict] = None) -> List[Dict]:
        """用JavaScript直接从DOM提取商品信息，并实时清洗"""
        items_data = await self.page.evaluate("""() => {
            const results = [];

            // 策略1: feeds商品流（闲鱼当前主力布局）
            const feedItems = document.querySelectorAll('[class*="feeds-item-wrap"]');
            if (feedItems.length > 0) {
                const seen = new Set();
                for (const item of feedItems) {
                    // 获取链接
                    const link = item.tagName === 'A' ? item : item.querySelector('a[href*="/item/"]');
                    const href = link?.href || '';
                    if (!href || seen.has(href)) continue;
                    seen.add(href);

                    const text = item.innerText || '';
                    const lines = text.split('\\n').map(s => s.trim()).filter(s => s);

                    // 提取价格
                    let price = '';
                    for (const line of lines) {
                        const m = line.match(/^[¥￥]?\\s*(\\d+(?:\\.\\d{1,2})?)\\s*$/);
                        if (m && parseFloat(m[1]) > 10 && parseFloat(m[1]) < 50000) {
                            price = m[1];
                            break;
                        }
                    }

                    // 提取标题（第一段长文本）
                    let title = '';
                    for (const line of lines) {
                        if (line.length > 15 && line.length < 300 &&
                            !line.match(/^[¥￥\\d.]+$/) &&
                            !line.match(/发布|想要|信用|降价|包邮|验货/)) {
                            title = line;
                            break;
                        }
                    }

                    if (title && price) {
                        results.push({
                            title: title.substring(0, 200),
                            price: price,
                            url: href,
                        });
                    }
                }
                return results;
            }

            // 策略2: 传统 /item/ 链接（兜底）
            const links = document.querySelectorAll('a[href*="/item/"]');
            const seen = new Set();
            for (const link of links) {
                const href = link.href;
                if (seen.has(href)) continue;
                seen.add(href);

                let card = link;
                for (let i = 0; i < 6; i++) {
                    if (card.parentElement) card = card.parentElement;
                    const rect = card.getBoundingClientRect();
                    if (rect.width > 150 && rect.height > 100) break;
                }

                const text = card.innerText || '';
                const lines = text.split('\\n').map(s => s.trim()).filter(s => s);

                let price = '';
                for (const line of lines) {
                    const m = line.match(/[¥￥]?\\s*(\\d+(?:\\.\\d{1,2})?)\\s*元?$/);
                    if (m && parseFloat(m[1]) > 5 && parseFloat(m[1]) < 50000) {
                        price = m[1];
                        break;
                    }
                }

                let title = link.innerText?.trim() || '';
                if (title.length < 5) {
                    for (const line of lines) {
                        if (line.length > title.length && line.length < 200 && !line.match(/^[¥￥\\d.]+$/)) {
                            title = line;
                        }
                    }
                }

                if (title && price) {
                    results.push({
                        title: title.substring(0, 200),
                        price: price,
                        url: href,
                    });
                }
            }

            return results;
        }""")

        records = []
        if not model_keywords:
            model_keywords = self.keywords

        for item in items_data:
            record = parse_listing_record(
                title=item.get('title', ''),
                price=item.get('price', ''),
                url=item.get('url', ''),
                model_keywords=model_keywords,
            )
            if record:
                if model_name:
                    record['model'] = model_name

                # 实时清洗：脏数据 + 型号过滤 + 成色推断
                cleaned = clean_record(record, target_model=record.get('model', ''))
                if not cleaned.get('_clean_pass', False):
                    reject_reason = cleaned.get('_clean_reject', '')
                    logger.debug(f"[清洗拒绝] ¥{record['price']} {record['title'][:30]}... 原因: {reject_reason}")
                    continue

                # 应用推断成色
                inferred = cleaned.get('_inferred_condition', {})
                if inferred.get('label'):
                    record['condition'] = inferred['label']
                    record['condition_inferred'] = inferred['label']
                    record['condition_score'] = inferred.get('score', 0)
                    record['condition_claimed'] = inferred.get('claimed', '')
                    record['condition_evidence'] = inferred.get('evidence', [])
                    record['condition_severe'] = inferred.get('has_severe_issue', False)

                records.append(record)

        return records

    async def _go_next_page(self) -> bool:
        """翻到下一页"""
        try:
            # 先滚动到页面底部
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(1)

            # 找下一页按钮
            next_btn = await self.page.query_selector(
                'button:has-text("下一页"), a:has-text("下一页"), '
                '[class*="next"]:not([disabled]), [aria-label="next"]'
            )
            if next_btn:
                disabled = await next_btn.get_attribute('disabled')
                if not disabled:
                    await next_btn.click()
                    await asyncio.sleep(3)
                    return True
            return False
        except:
            return False

    # ── 主入口 ──────────────────────────────────────────────

    async def crawl_all(self, keyword_filter: str = '') -> List[Dict]:
        """爬取所有配置的关键词"""
        all_records = []

        kw_list = self.keywords
        if keyword_filter:
            kw_list = [k for k in self.keywords if keyword_filter.lower() in k['name'].lower()]
            if not kw_list:
                kw_list = [{'name': keyword_filter, 'aliases': [keyword_filter], 'brand': ''}]

        await self.start()

        try:
            logged_in = await self.login_if_needed()
            if not logged_in:
                logger.error("登录失败，无法继续")
                return []

            for kw_cfg in kw_list:
                model_name = kw_cfg['name']
                aliases = kw_cfg.get('aliases', [model_name])

                for alias in aliases:
                    # 传入全部aliases，让匹配更精准
                    records = await self.search_keyword(
                        alias, model_name, all_aliases=aliases
                    )
                    all_records.extend(records)
                    await asyncio.sleep(random_delay(self.min_delay, self.max_delay))

        finally:
            await self.save_cookies()
            await self.close()

        logger.info(f"总计抓取 {len(all_records)} 条记录（已实时清洗）")
        return all_records
