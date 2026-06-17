# -*- coding: utf-8 -*-
"""
闲鱼行情自动提取 — 通过ADB从手机屏幕提取成交记录
用户在手机上翻页，脚本自动抓取每页数据

使用方法：
  python crawler/phone_extractor.py           # 抓取当前屏幕
  python crawler/phone_extractor.py --auto    # 自动翻页抓取
  python crawler/phone_extractor.py --model "疾光NF800PRO"  # 指定型号
"""

import json
import re
import time
import argparse
from pathlib import Path
from datetime import datetime
from loguru import logger

import uiautomator2 as u2
import xml.etree.ElementTree as ET

DEVICE_ID = "ee635a46"
OUTPUT_DIR = Path(__file__).parent.parent / "data"


def extract_current_screen(d, model_name: str = "") -> list:
    """从当前屏幕提取成交记录"""
    hierarchy = d.dump_hierarchy()
    if not hierarchy:
        return []

    root = ET.fromstring(hierarchy)

    # 收集所有content-desc和text
    all_items = []
    for elem in root.iter():
        desc = elem.get('content-desc', '').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
        text = elem.get('text', '').strip()
        if desc:
            all_items.append(desc)
        if text:
            all_items.append(text)

    # 合并所有文本进行解析
    records = []

    # 策略：找所有 "发布价¥xxx" + "成交价" + "¥xxx" 的组合
    full_text = '\n'.join(all_items)

    # 按"成交记录"分割各条记录
    # 每条记录的模式：发布价¥xxx ... 发布X天后成交 ... 成交价 ... ¥xxx
    price_blocks = re.split(r'(?=发布价[¥￥])', full_text)

    for block in price_blocks:
        record = {}

        # 提取发布价
        list_match = re.search(r'发布价[¥￥]\s*(\d+)', block)
        if not list_match:
            continue
        record['list_price'] = float(list_match.group(1))

        # 提取成交时间
        time_match = re.search(r'发布(\d+[天小时]+)后成交', block)
        if time_match:
            record['sold_after'] = time_match.group(1)
        elif '发布当天成交' in block:
            record['sold_after'] = '当天'

        # 提取成交价（成交价后面的独立¥数字）
        sold_match = re.search(r'成交价\s*[¥￥]\s*(\d+)', block)
        if sold_match:
            record['sold_price'] = float(sold_match.group(1))
        else:
            # 成交价和¥可能在不同元素里，找block中的独立¥数字
            prices = re.findall(r'[¥￥]\s*(\d+)', block)
            if len(prices) >= 2:
                # 第二个价格通常是成交价
                record['sold_price'] = float(prices[1])

        if record.get('sold_price') and record.get('list_price'):
            record['model'] = model_name
            record['crawled_at'] = datetime.now().isoformat()
            records.append(record)

    # 去重
    seen = set()
    unique = []
    for r in records:
        key = f"{r['sold_price']}_{r['list_price']}_{r.get('sold_after', '')}"
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


def extract_titles(d) -> list:
    """提取当前屏幕的商品标题"""
    hierarchy = d.dump_hierarchy()
    if not hierarchy:
        return []

    root = ET.fromstring(hierarchy)
    titles = []

    for elem in root.iter():
        desc = elem.get('content-desc', '').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
        # 标题通常是较长的content-desc，包含球拍关键词
        if len(desc) > 20 and any(kw in desc for kw in ['pro', 'PRO', 'Pro', '800', '88', '100', '弓箭', '天斧', '疾光', '风刃', '雷霆', '龙牙', '神速', '极速']):
            # 取第一行作为标题
            first_line = desc.split('\n')[0].strip()
            if first_line and len(first_line) > 5:
                titles.append(first_line[:100])

    return titles


def auto_extract(model_name: str = "", max_scrolls: int = 10) -> list:
    """自动翻页提取"""
    d = u2.connect(DEVICE_ID)
    logger.info(f"已连接: {d.device_info.get('model', '?')}")

    # 设置屏幕常亮
    import subprocess
    adb = 'C:/Users/奈奈/AppData/Local/Android/Sdk/platform-tools/adb.exe'
    subprocess.run([adb, '-s', DEVICE_ID, 'shell', 'settings', 'put', 'system', 'screen_off_timeout', '1800000'],
                   capture_output=True)

    all_records = []
    seen = set()

    for i in range(max_scrolls):
        records = extract_current_screen(d, model_name)
        new_count = 0
        for r in records:
            key = f"{r['sold_price']}_{r['list_price']}_{r.get('sold_after', '')}"
            if key not in seen:
                seen.add(key)
                all_records.append(r)
                new_count += 1

        logger.info(f"第{i+1}屏: {new_count}条新增 (累计{len(all_records)}条)")

        if new_count == 0 and i > 0:
            logger.info("无新数据，停止")
            break

        # 向下滚动
        d.swipe(0.5, 0.75, 0.5, 0.35, duration=0.5)
        time.sleep(2)

    return all_records


def save_records(records: list, model_name: str = ""):
    """保存记录"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / "market_records.json"

    # 追加到已有数据
    existing = []
    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)

    existing.extend(records)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    logger.info(f"保存 {len(records)} 条 → {output_path} (总计{len(existing)}条)")


def main():
    parser = argparse.ArgumentParser(description='闲鱼行情数据提取')
    parser.add_argument('--model', '-m', default='', help='型号名称')
    parser.add_argument('--auto', '-a', action='store_true', help='自动翻页模式')
    parser.add_argument('--scrolls', '-s', type=int, default=10, help='最大翻页数')
    args = parser.parse_args()

    if args.auto:
        records = auto_extract(args.model, args.scrolls)
    else:
        d = u2.connect(DEVICE_ID)
        records = extract_current_screen(d, args.model)

    if records:
        save_records(records, args.model)
        print(f"\n抓取结果: {len(records)} 条")
        for r in records:
            print(f"  ¥{r['sold_price']:>6} (发布¥{r['list_price']:>6}) {r.get('sold_after', ''):>4}")
    else:
        print("未抓取到数据，请确认手机在闲鱼行情页")


if __name__ == "__main__":
    main()
