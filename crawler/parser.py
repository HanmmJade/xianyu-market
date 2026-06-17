# -*- coding: utf-8 -*-
"""
数据解析 — 从标题和页面元素中提取型号、成色、价格
集成 cleaner 模块进行型号精准过滤 + 成色智能推断
"""

import re
from typing import Dict, Optional, List, Tuple
from loguru import logger

from crawler.cleaner import clean_record, clean_batch, classify_model, infer_condition, is_garbage


# 成色关键词映射
CONDITION_MAP = {
    '全新': '全新',
    '全新未拆': '全新',
    '未拆封': '全新',
    '99新': '99新',
    '99': '99新',
    '98新': '98新',
    '95新': '95新',
    '95': '95新',
    '9新': '9新',
    '9成新': '9新',
    '85新': '85新',
    '8新': '8新',
    '8成新': '8新',
    '7新': '7新',
    '7成新': '7新',
    '轻微使用': '95新',
    '正常使用': '9新',
    '明显使用': '8新',
    '充新': '99新',
    '准新': '99新',
    '几乎全新': '99新',
}

# 品牌关键词
BRAND_KEYWORDS = {
    'YONEX': ['yonex', '尤尼克斯', 'YY', '天斧', '弓箭', '疾光', 'DUORA', 'duora', 'NF', 'nf'],
    '李宁': ['李宁', 'lining', '风刃', '雷霆', '战戟', '能量', '突袭'],
    'VICTOR': ['victor', '威克多', '胜利', '神速', '龙牙', '极速', '挑战者'],
}


def extract_condition(title: str) -> str:
    """从标题提取成色"""
    title_lower = title.lower()

    # 先精确匹配
    for keyword, condition in CONDITION_MAP.items():
        if keyword in title:
            return condition

    # 正则匹配 "X成新"
    m = re.search(r'(\d)成新', title)
    if m:
        val = int(m.group(1))
        if val >= 9:
            return '9新'
        elif val >= 8:
            return '8新'
        elif val >= 7:
            return '7新'

    # 正则匹配 "X新"
    m = re.search(r'(\d{2})新', title)
    if m:
        val = int(m.group(1))
        if val >= 99:
            return '99新'
        elif val >= 95:
            return '95新'
        elif val >= 90:
            return '9新'
        elif val >= 85:
            return '85新'
        elif val >= 80:
            return '8新'

    return ''


def extract_brand(title: str) -> str:
    """从标题提取品牌"""
    title_lower = title.lower()
    for brand, keywords in BRAND_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title_lower:
                return brand
    return ''


def match_model(title: str, model_keywords: List[Dict]) -> Optional[str]:
    """匹配标题中的型号，返回标准型号名"""
    title_upper = title.upper()
    title_lower = title.lower()

    for kw_cfg in model_keywords:
        name = kw_cfg['name']
        aliases = kw_cfg.get('aliases', [])
        for alias in aliases:
            if alias.upper() in title_upper or alias.lower() in title_lower:
                return name
        # 也检查标准名
        if name.upper() in title_upper or name.lower() in title_lower:
            return name

    return None


def parse_price(price_str) -> float:
    """解析价格字符串为浮点数"""
    if isinstance(price_str, (int, float)):
        return float(price_str)
    if not price_str:
        return 0.0

    # 移除非数字字符（保留小数点）
    cleaned = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_listing_record(
    title: str,
    price,
    sold_time: str = '',
    listed_time: str = '',
    url: str = '',
    model_keywords: List[Dict] = None
) -> Optional[Dict]:
    """解析一条成交记录"""
    if not title or not price:
        return None

    price_val = parse_price(price)
    if price_val <= 0 or price_val > 100000:
        return None

    model = ''
    if model_keywords:
        model = match_model(title, model_keywords) or ''

    condition = extract_condition(title)

    days = None
    if listed_time and sold_time:
        try:
            from datetime import datetime
            fmt_candidates = ['%Y-%m-%d', '%Y.%m.%d', '%m-%d', '%m月%d日']
            lt, st = None, None
            for fmt in fmt_candidates:
                try:
                    lt = datetime.strptime(listed_time.strip(), fmt)
                    st = datetime.strptime(sold_time.strip(), fmt)
                    break
                except:
                    continue
            if lt and st:
                days = (st - lt).days
        except:
            pass

    return {
        'model': model,
        'title': title.strip(),
        'price': price_val,
        'condition': condition,
        'listed_time': listed_time,
        'sold_time': sold_time,
        'days_to_sell': days,
        'source_url': url,
    }


def parse_and_clean_record(
    title: str,
    price,
    sold_time: str = '',
    listed_time: str = '',
    url: str = '',
    model_keywords: List[Dict] = None
) -> Optional[Dict]:
    """
    解析 + 清洗一条记录（推荐入口）。

    流程：
    1. 基础解析（价格、型号匹配、卖家自标成色）
    2. 脏数据拦截（非球拍商品）
    3. 型号精准过滤（排除同系列不同型号）
    4. 成色智能推断（基于描述关键词，不信任卖家自标）
    5. 价格异常检测

    返回清洗后的记录，未通过清洗返回 None。
    """
    # Step 1: 基础解析
    parsed = parse_listing_record(title, price, sold_time, listed_time, url, model_keywords)
    if not parsed:
        return None

    # Step 2-5: 清洗管线
    result = clean_record(parsed, target_model=parsed.get('model', ''))

    # 未通过清洗 → 返回 None
    if not result.get('_clean_pass', False):
        reason = result.get('_clean_reject', 'unknown')
        logger.debug(f"[解析清洗] 拒绝: ¥{price} - {title[:30]}... 原因: {reason}")
        return None

    # 用推断成色替换卖家自标成色
    inferred = result.get('_inferred_condition', {})
    if inferred.get('label'):
        result['condition'] = inferred['label']

    # 清理内部字段（不存入数据库）
    for key in ['_clean_pass', '_clean_reject', '_real_model',
                '_inferred_condition', '_price_anomaly']:
        result.pop(key, None)

    # 保留推断成色的详细信息
    if inferred:
        result['condition_inferred'] = inferred.get('label', '')
        result['condition_score'] = inferred.get('score', 0)
        result['condition_claimed'] = inferred.get('claimed', '')
        result['condition_evidence'] = inferred.get('evidence', [])
        result['condition_severe'] = inferred.get('has_severe_issue', False)

    return result


def parse_and_clean_batch(
    records: List[Dict],
    target_model: str = None,
    model_keywords: List[Dict] = None
) -> Tuple[List[Dict], Dict]:
    """
    批量解析 + 清洗（推荐批量入口）。

    输入: 原始记录列表（每条含 title, price 等）
    输出: (清洗后记录列表, 清洗报告)
    """
    parsed_records = []

    for r in records:
        title = r.get('title', '')
        price = r.get('price', 0)
        sold_time = r.get('sold_time', '')
        listed_time = r.get('listed_time', '')
        url = r.get('source_url', '')

        parsed = parse_listing_record(title, price, sold_time, listed_time, url, model_keywords)
        if parsed:
            parsed_records.append(parsed)

    # 批量清洗
    cleaned, report = clean_batch(
        parsed_records,
        target_model=target_model,
        remove_garbage=True,
        remove_wrong_model=True,
        remove_price_anomaly=False,
    )

    # 后处理：用推断成色替换
    final = []
    for r in cleaned:
        inferred = r.pop('_inferred_condition', {})
        r.pop('_clean_pass', None)
        r.pop('_clean_reject', None)
        r.pop('_real_model', None)
        r.pop('_price_anomaly', None)

        if inferred.get('label'):
            r['condition'] = inferred['label']
            r['condition_inferred'] = inferred['label']
            r['condition_score'] = inferred['score']
            r['condition_claimed'] = inferred.get('claimed', '')
            r['condition_evidence'] = inferred.get('evidence', [])
            r['condition_severe'] = inferred.get('has_severe_issue', False)

        final.append(r)

    return final, report
