# -*- coding: utf-8 -*-
"""
闲鱼API客户端 — 使用缓存签名调用API
签名来源：sign_interceptor.py 拦截的页面请求
"""

import json
import time
import random
import requests
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


SIGN_CACHE_PATH = Path(__file__).parent.parent / "data" / "sign_cache.json"
COOKIES_PATH = Path(__file__).parent.parent / "data" / "xianyu_cookies.json"


class XianyuAPIClient:
    """闲鱼API客户端 — 使用缓存签名"""

    def __init__(self, cookies_file: str = None):
        self.session = requests.Session()
        self.base_url = "https://h5api.m.goofish.com"
        self.sign_cache = {}

        # 加载签名缓存
        self._load_sign_cache()

        # 加载 Cookie
        cookie_path = cookies_file or str(COOKIES_PATH)
        self._load_cookies(cookie_path)

        # 请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.goofish.com/",
        }

    def _load_sign_cache(self):
        """加载签名缓存"""
        if not SIGN_CACHE_PATH.exists():
            logger.warning("签名缓存不存在，请先运行 sign_interceptor.py")
            return

        try:
            with open(SIGN_CACHE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.sign_cache = {s["api"]: s for s in data}
            logger.info(f"加载签名缓存: {len(self.sign_cache)} 个 API")
        except Exception as e:
            logger.error(f"加载签名缓存失败: {e}")

    def _load_cookies(self, filepath: str):
        """加载 Cookie 文件"""
        try:
            with open(filepath, 'r') as f:
                cookies_list = json.load(f)
            # Playwright 格式转 requests 格式
            if isinstance(cookies_list, list):
                for c in cookies_list:
                    self.session.cookies.set(c.get('name', ''), c.get('value', ''),
                                             domain=c.get('domain', ''))
            logger.info(f"加载 Cookie: {len(cookies_list)} 个")
        except Exception as e:
            logger.warning(f"加载 Cookie 失败: {e}")

    def _get_sign(self, api_name: str) -> Optional[Dict]:
        """从缓存获取签名"""
        return self.sign_cache.get(api_name)

    def search(self, keyword: str, page: int = 1, page_size: int = 20) -> Optional[Dict]:
        """
        搜索商品（使用缓存签名）

        注意：签名有时效性，过期后需要重新捕获
        """
        api_name = "mtop.taobao.idlemtopsearch.pc.search"
        sign_info = self._get_sign(api_name)

        if not sign_info:
            logger.error(f"无可用签名: {api_name}，请先运行 sign_interceptor.py")
            return None

        # 构造请求 URL
        url = f"{self.base_url}/h5/{api_name}/1.0/"
        params = {
            "jsv": sign_info.get("jsv", "2.7.2"),
            "appKey": sign_info.get("appKey", "34839810"),
            "t": str(int(time.time() * 1000)),
            "sign": sign_info.get("sign", ""),
            "v": sign_info.get("v", "1.0"),
            "type": "originaljson",
            "accountSite": "xianyu",
        }

        # POST 数据
        post_data = {
            "keyword": keyword,
            "pageNumber": page,
            "pageSize": page_size,
        }

        try:
            response = self.session.post(
                url,
                params=params,
                data={"data": json.dumps(post_data)},
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API 请求失败: {e}")
            return None

    def parse_search_result(self, result: Dict) -> List[Dict]:
        """解析搜索结果"""
        items = []
        try:
            data = result.get("data", {})
            result_list = data.get("resultList", [])

            for entry in result_list:
                try:
                    main = entry["data"]["item"]["main"]
                    ex = main.get("exContent", {})
                    dp = ex.get("detailParams", {})
                    args = main.get("clickParam", {}).get("args", {})

                    item_id = str(dp.get("itemId", ex.get("itemId", args.get("id", ""))))
                    title = dp.get("title", ex.get("title", ""))
                    sold_price = str(dp.get("soldPrice", args.get("price", "")))

                    if title and item_id:
                        items.append({
                            "item_id": item_id,
                            "title": title,
                            "price": sold_price,
                            "url": f"https://www.goofish.com/item?id={item_id}",
                        })
                except (KeyError, TypeError):
                    continue
        except Exception as e:
            logger.error(f"解析结果失败: {e}")

        return items

    def search_all(self, keyword: str, max_pages: int = 5) -> List[Dict]:
        """搜索所有页面"""
        all_items = []

        for page in range(1, max_pages + 1):
            logger.info(f"搜索 '{keyword}' 第{page}页...")
            result = self.search(keyword, page=page)
            if not result:
                break

            items = self.parse_search_result(result)
            if not items:
                break

            all_items.extend(items)
            time.sleep(random.uniform(2, 5))

        logger.info(f"搜索完成: {keyword}, 共{len(all_items)}条")
        return all_items


if __name__ == "__main__":
    client = XianyuAPIClient()
    if client.sign_cache:
        print(f"可用签名 API: {list(client.sign_cache.keys())}")
    else:
        print("无签名缓存，请先运行: python crawler/sign_interceptor.py")
