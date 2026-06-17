# -*- coding: utf-8 -*-
"""
mitmproxy 插件 — 捕获闲鱼 App 的 mtop API 请求
专门查找成交记录相关的API

使用方法：
  mitmdump -s xianyu_capture.py -p 8888

手机配置代理后，打开闲鱼搜索某个型号，切到"已成交"标签。
脚本会自动捕获并保存所有 mtop API 响应。
"""

import json
import re
import time
from pathlib import Path
from mitmproxy import http

OUTPUT_DIR = Path(r"D:\AI共享文件夹\xianyu-market\data\captured")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 成交相关关键词
SOLD_KEYWORDS = [
    'sold', 'Sold', 'soldCnt', 'soldCount', 'soldPrice', 'soldTime',
    'deal', 'Deal', 'trade', 'Trade', 'transaction',
    '已售', '已卖出', '成交', '卖出',
    'wantNum', 'wantCount', 'browseCnt', 'viewCount',
    'recentSold', 'sellCount', 'tradeCount',
]

capture_count = 0


def response(flow: http.HTTPFlow) -> None:
    global capture_count

    url = flow.request.pretty_url

    # 只关注 mtop/h5api 请求
    if 'mtop' not in url and 'h5api' not in url:
        return

    # 提取API名称
    api_match = re.search(r'mtop\.[a-zA-Z0-9._]+', url)
    api_name = api_match.group(0) if api_match else 'unknown'

    try:
        body = flow.response.get_text(strict=False)
        if not body:
            return

        body_lower = body.lower()

        # 检查是否包含成交相关关键词
        found_keywords = [kw for kw in SOLD_KEYWORDS if kw.lower() in body_lower]

        capture_count += 1
        ts = time.strftime('%H%M%S')

        # 保存所有 mtop 响应（不限于成交相关）
        filename = f"{ts}_{api_name.split('.')[-1]}_{capture_count}.json"
        filepath = OUTPUT_DIR / filename

        save_data = {
            'api': api_name,
            'url': url[:300],
            'method': flow.request.method,
            'status': flow.response.status_code,
            'size': len(body),
            'keywords': found_keywords,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'request_headers': dict(flow.request.headers),
            'request_content': flow.request.get_text(strict=False)[:5000] if flow.request.get_text(strict=False) else '',
            'response_body': body[:50000],  # 保存前50KB
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        # 打印摘要
        kw_str = f" ★{found_keywords}" if found_keywords else ""
        size_kb = len(body) / 1024
        print(f"[{ts}] {api_name} ({size_kb:.1f}KB){kw_str}")

        # 如果发现成交相关API，特别标记
        if found_keywords:
            special_file = OUTPUT_DIR / f"SOLD_{ts}_{api_name.split('.')[-1]}_{capture_count}.json"
            with open(special_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            print(f"  >>> 成交相关API已保存: {special_file.name}")

    except Exception as e:
        print(f"[ERROR] {api_name}: {e}")
