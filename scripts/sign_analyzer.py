# -*- coding: utf-8 -*-
"""
签名算法分析器 — 分析抓包获取的签名数据
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger


class SignAnalyzer:
    """签名算法分析器"""
    
    def __init__(self, captured_dir: str = None):
        self.captured_dir = Path(captured_dir) if captured_dir else Path(__file__).parent.parent / "data" / "captured"
        self.signatures = []
    
    def load_captured_data(self) -> List[Dict]:
        """加载所有抓包数据"""
        data = []
        
        if not self.captured_dir.exists():
            logger.error(f"抓包目录不存在: {self.captured_dir}")
            return data
        
        for file in self.captured_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    if isinstance(content, list):
                        data.extend(content)
                    else:
                        data.append(content)
            except Exception as e:
                logger.warning(f"加载文件失败 {file}: {e}")
        
        logger.info(f"加载 {len(data)} 条抓包数据")
        return data
    
    def extract_sign_headers(self, data: List[Dict]) -> List[Dict]:
        """提取签名相关的请求头"""
        sign_headers = []
        
        for item in data:
            if 'request' not in item:
                continue
            
            headers = item['request'].get('headers', {})
            sign_info = {
                'url': item['request'].get('url', ''),
                'timestamp': item.get('timestamp', 0),
            }
            
            # 提取签名相关头
            for key, value in headers.items():
                key_lower = key.lower()
                if any(sign_key in key_lower for sign_key in ['sign', 'token', 'cookie', 'x-', 'mtop']):
                    sign_info[key] = value
            
            if len(sign_info) > 2:  # 除了url和timestamp外还有其他信息
                sign_headers.append(sign_info)
        
        logger.info(f"提取 {len(sign_headers)} 条签名数据")
        return sign_headers
    
    def analyze_sign_pattern(self, sign_headers: List[Dict]) -> Dict:
        """分析签名模式"""
        patterns = {
            'x-sign': [],
            'x-appkey': [],
            'x-t': [],
            'x-umt': [],
            'cookie': [],
        }
        
        for item in sign_headers:
            for key in patterns.keys():
                if key in item:
                    patterns[key].append(item[key])
        
        # 分析模式
        analysis = {}
        for key, values in patterns.items():
            if values:
                analysis[key] = {
                    'count': len(values),
                    'sample': values[0] if values else None,
                    'unique_count': len(set(values)),
                }
        
        return analysis
    
    def generate_sign_function(self, analysis: Dict) -> str:
        """生成签名函数代码"""
        code = '''
def generate_sign(params: Dict, token: str = None) -> str:
    """
    生成API签名
    
    Args:
        params: 请求参数
        token: 认证token
    
    Returns:
        签名字符串
    """
    # 排序参数
    sorted_params = sorted(params.items())
    sign_str = '&'.join(f'{k}={v}' for k, v in sorted_params)
    
    # 签名算法（根据抓包分析结果）
'''
        
        if 'x-sign' in analysis:
            sign_sample = analysis['x-sign'].get('sample', '')
            if sign_sample:
                code += f'    # 签名样本: {sign_sample[:50]}...\n'
        
        code += '''
    # 使用HMAC-MD5签名
    if token:
        return hmac.new(
            token.encode(),
            sign_str.encode(),
            hashlib.md5
        ).hexdigest()
    
    return ""
'''
        
        return code
    
    def save_analysis(self, analysis: Dict, output_file: str = None):
        """保存分析结果"""
        if not output_file:
            output_file = self.captured_dir / "sign_analysis.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        logger.info(f"分析结果已保存: {output_file}")


def main():
    """主函数"""
    analyzer = SignAnalyzer()
    
    # 加载数据
    data = analyzer.load_captured_data()
    if not data:
        logger.error("未找到抓包数据")
        return
    
    # 提取签名
    sign_headers = analyzer.extract_sign_headers(data)
    
    # 分析模式
    analysis = analyzer.analyze_sign_pattern(sign_headers)
    
    # 输出分析结果
    print("\n=== 签名分析结果 ===")
    for key, info in analysis.items():
        print(f"\n{key}:")
        print(f"  数量: {info['count']}")
        print(f"  唯一值: {info['unique_count']}")
        if info['sample']:
            print(f"  样本: {info['sample'][:100]}...")
    
    # 生成签名函数
    sign_func = analyzer.generate_sign_function(analysis)
    print("\n=== 生成的签名函数 ===")
    print(sign_func)
    
    # 保存分析结果
    analyzer.save_analysis(analysis)


if __name__ == "__main__":
    main()
