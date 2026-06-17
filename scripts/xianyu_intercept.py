# -*- coding: utf-8 -*-
"""
mitmproxy拦截脚本 — 捕获闲鱼行情API
"""

import json
import time
from pathlib import Path
from mitmproxy import http

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "captured"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class XianyuInterceptor:
    """闲鱼API拦截器"""
    
    def __init__(self):
        self.captured_apis = []
        self.request_count = 0
    
    def request(self, flow: http.HTTPFlow):
        """记录请求"""
        # 只拦截闲鱼API
        if 'h5api.m.goofish.com' not in flow.request.url:
            return
        
        self.request_count += 1
        request_data = {
            'id': self.request_count,
            'timestamp': time.time(),
            'url': flow.request.url,
            'method': flow.request.method,
            'headers': dict(flow.request.headers),
            'body': flow.request.content.decode('utf-8', errors='ignore') if flow.request.content else '',
        }
        
        # 保存请求
        filename = OUTPUT_DIR / f"request_{self.request_count:04d}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(request_data, f, ensure_ascii=False, indent=2)
        
        print(f"[+] 捕获请求 #{self.request_count}: {flow.request.url[:80]}...")
    
    def response(self, flow: http.HTTPFlow):
        """记录响应"""
        # 只拦截闲鱼API
        if 'h5api.m.goofish.com' not in flow.request.url:
            return
        
        # 解析响应
        try:
            response_json = json.loads(flow.response.content)
        except:
            response_json = {'raw': flow.response.content.decode('utf-8', errors='ignore')}
        
        # 保存完整的请求-响应对
        capture_data = {
            'id': self.request_count,
            'timestamp': time.time(),
            'request': {
                'url': flow.request.url,
                'method': flow.request.method,
                'headers': dict(flow.request.headers),
                'body': flow.request.content.decode('utf-8', errors='ignore') if flow.request.content else '',
            },
            'response': {
                'status_code': flow.response.status_code,
                'headers': dict(flow.response.headers),
                'body': response_json,
            }
        }
        
        # 判断是否为搜索API
        if 'mtop.taobao.idlefish.search.item' in flow.request.url:
            self.capture_search_api(capture_data)
        elif 'mtop.taobao.idle.pc.detail' in flow.request.url:
            self.capture_detail_api(capture_data)
        
        # 保存到主文件
        self.captured_apis.append(capture_data)
        main_file = OUTPUT_DIR / "captured_all.json"
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(self.captured_apis, f, ensure_ascii=False, indent=2)
    
    def capture_search_api(self, data):
        """保存搜索API数据"""
        filename = OUTPUT_DIR / "search_api.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[+] 保存搜索API响应: {data['request']['url'][:60]}...")
    
    def capture_detail_api(self, data):
        """保存详情API数据"""
        filename = OUTPUT_DIR / "detail_api.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[+] 保存详情API响应: {data['request']['url'][:60]}...")


addons = [XianyuInterceptor()]
