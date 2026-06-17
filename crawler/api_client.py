# -*- coding: utf-8 -*-
"""
闲鱼API客户端 — 使用抓包获取的签名调用API
"""

import json
import time
import random
import hashlib
import hmac
import requests
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


class XianyuAPIClient:
    """闲鱼API客户端"""
    
    def __init__(self, cookies_file: str = None):
        self.session = requests.Session()
        self.base_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlefish.search.item/1.0/"
        self.app_key = "12574478"
        self.token = None
        self.cookies = {}
        
        # 加载Cookie
        if cookies_file:
            self.load_cookies(cookies_file)
        
        # 请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }
    
    def load_cookies(self, filepath: str):
        """加载Cookie文件"""
        try:
            with open(filepath, 'r') as f:
                self.cookies = json.load(f)
            logger.info(f"加载Cookie: {len(self.cookies)}个")
        except Exception as e:
            logger.error(f"加载Cookie失败: {e}")
    
    def generate_sign(self, params: Dict) -> str:
        """
        生成API签名
        注意: 这是一个示例实现，实际签名算法需要从Frida hook结果中提取
        """
        # 排序参数
        sorted_params = sorted(params.items())
        sign_str = '&'.join(f'{k}={v}' for k, v in sorted_params)
        
        # 使用token签名（如果有的话）
        if self.token:
            return hmac.new(
                self.token.encode(),
                sign_str.encode(),
                hashlib.md5
            ).hexdigest()
        
        # 否则返回空签名（需要从抓包结果中获取）
        return ""
    
    def search(self, keyword: str, page: int = 1, page_size: int = 20) -> Dict:
        """
        搜索商品
        
        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
        
        Returns:
            API响应
        """
        params = {
            "keyword": keyword,
            "pageNumber": page,
            "pageSize": page_size,
            "sortType": "sold_time",
        }
        
        # 生成签名
        sign = self.generate_sign(params)
        
        # 构造请求头
        request_headers = self.headers.copy()
        request_headers.update({
            "x-sign": sign,
            "x-appkey": self.app_key,
            "x-t": str(int(time.time() * 1000)),
        })
        
        try:
            response = self.session.get(
                self.base_url,
                params=params,
                headers=request_headers,
                cookies=self.cookies,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return None
    
    def search_all(self, keyword: str, max_pages: int = 5) -> List[Dict]:
        """
        搜索所有页面
        
        Args:
            keyword: 搜索关键词
            max_pages: 最大页数
        
        Returns:
            所有结果列表
        """
        all_items = []
        
        for page in range(1, max_pages + 1):
            logger.info(f"搜索 '{keyword}' 第{page}页...")
            
            result = self.search(keyword, page=page)
            if not result:
                break
            
            # 解析结果
            items = self.parse_search_result(result)
            if not items:
                break
            
            all_items.extend(items)
            
            # 随机延迟
            delay = random.uniform(2, 5)
            time.sleep(delay)
        
        logger.info(f"搜索完成: {keyword}, 共{len(all_items)}条")
        return all_items
    
    def parse_search_result(self, result: Dict) -> List[Dict]:
        """
        解析搜索结果
        
        Args:
            result: API响应
        
        Returns:
            解析后的商品列表
        """
        items = []
        
        try:
            # 根据实际API响应结构调整
            if 'data' in result and 'resultList' in result['data']:
                for item in result['data']['resultList']:
                    parsed = {
                        'title': item.get('title', ''),
                        'price': float(item.get('soldPrice', 0)),
                        'listed_price': float(item.get('price', 0)),
                        'sold_time': item.get('soldTime', ''),
                        'item_id': item.get('itemId', ''),
                        'seller': item.get('userNick', ''),
                        'location': item.get('area', ''),
                        'condition': item.get('fishTags', ''),
                    }
                    items.append(parsed)
        except Exception as e:
            logger.error(f"解析结果失败: {e}")
        
        return items


def load_captured_signatures(filepath: str) -> Dict:
    """
    加载抓包获取的签名数据
    
    Args:
        filepath: 抓包数据文件路径
    
    Returns:
        签名数据
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"加载签名数据失败: {e}")
        return None


if __name__ == "__main__":
    # 测试API客户端
    client = XianyuAPIClient()
    
    # 需要先通过抓包获取签名
    # result = client.search("天斧88D PRO")
    # print(json.dumps(result, ensure_ascii=False, indent=2))
