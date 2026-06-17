# -*- coding: utf-8 -*-
"""
闲鱼行情全自动采集 v2 — ADB控制手机，无需人工操作

使用方法：
  python crawler/phone_auto_crawl.py                    # 爬取所有型号
  python crawler/phone_auto_crawl.py --models 3         # 只爬3个型号测试
  python crawler/phone_auto_crawl.py --keyword "88dpro" # 只爬指定关键词
"""

import json
import re
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from loguru import logger

import uiautomator2 as u2
import yaml
import xml.etree.ElementTree as ET

DEVICE_ID = "ee635a46"
ADB = r"C:\Users\奈奈\AppData\Local\Android\Sdk\platform-tools\adb.exe"
XIANYU_PKG = "com.taobao.idlefish"
OUTPUT_DIR = Path(__file__).parent.parent / "data"
MARKET_DB = OUTPUT_DIR / "market_records.json"


def adb(*args):
    return subprocess.run([ADB, '-s', DEVICE_ID] + list(args), capture_output=True)


def launch_xianyu(d):
    """启动闲鱼到首页"""
    adb('shell', 'am', 'force-stop', XIANYU_PKG)
    time.sleep(1)
    adb('shell', 'monkey', '-p', XIANYU_PKG, '-c', 'android.intent.category.LAUNCHER', '1')
    time.sleep(6)
    return d.app_current().get('package', '') in (XIANYU_PKG, 'com.quark.browser')


def search_and_open_market(d, keyword: str) -> bool:
    """搜索关键词并打开行情页"""
    # 点击搜索框
    search_bar = d(resourceId="com.taobao.idlefish:id/search_bar_layout")
    if not search_bar.exists(timeout=8):
        logger.warning("找不到搜索框")
        return False
    search_bar.click()
    time.sleep(2)

    # 输入关键词
    edit = d(className="android.widget.EditText")
    if edit.exists(timeout=3):
        edit.clear_text()
        edit.set_text(keyword)
    else:
        adb('shell', 'input', 'text', keyword)
    time.sleep(0.5)

    # 按回车搜索
    adb('shell', 'input', 'keyevent', '66')
    time.sleep(5)

    # 点击行情标签
    tab = d(text="行情")
    if not tab.exists(timeout=5):
        logger.warning("未找到行情标签")
        return False
    tab.click()
    time.sleep(3)
    return True


def extract_visible_records(d) -> list:
    """从当前屏幕提取成交记录"""
    hierarchy = d.dump_hierarchy()
    if not hierarchy:
        return []

    root = ET.fromstring(hierarchy)

    # 收集所有desc元素，带bounds用于排序
    items = []
    for elem in root.iter():
        desc = elem.get('content-desc', '').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').strip()
        bounds = elem.get('bounds', '')
        if not desc or len(desc) < 3:
            continue
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
        if m:
            y = int(m.group(2))
            items.append((y, desc))

    # 按Y坐标排序（从上到下）
    items.sort()

    # 解析：找 "发布价¥xxx"，然后往回找 成交价和时间
    records = []
    i = 0
    while i < len(items):
        y, desc = items[i]

        list_match = re.match(r'发布价[¥￥]\s*(\d+)', desc)
        if not list_match:
            i += 1
            continue

        list_price = float(list_match.group(1))
        sold_price = 0.0
        sold_after = ''

        # 往回找（Y坐标更小或相等的元素，最多4个）
        for j in range(i - 1, max(0, i - 5), -1):
            _, prev_desc = items[j]

            # 成交时间
            if not sold_after:
                tm = re.search(r'发布(\d+[天小时]+)后成交', prev_desc)
                if tm:
                    sold_after = tm.group(1)
                elif '发布当天成交' in prev_desc:
                    sold_after = '当天'

            # 成交价（独立的¥xxx，不是发布价）
            if sold_price == 0 and not prev_desc.startswith('发布价'):
                pm = re.match(r'^[¥￥]\s*(\d+(?:\.\d+)?)$', prev_desc)
                if pm:
                    sold_price = float(pm.group(1))

        # 也检查同行的元素（same Y）
        if not sold_after:
            for j in range(i + 1, min(len(items), i + 3)):
                _, next_desc = items[j]
                if '发布当天成交' in next_desc:
                    sold_after = '当天'
                    break
                tm = re.search(r'发布(\d+[天小时]+)后成交', next_desc)
                if tm:
                    sold_after = tm.group(1)
                    break

        if sold_price > 0 and list_price > 0:
            records.append({
                'sold_price': sold_price,
                'list_price': list_price,
                'sold_after': sold_after,
            })

        i += 1

    return records


def crawl_model(d, keyword: str, model_name: str, max_scrolls: int = 5) -> list:
    """爬取单个型号"""
    logger.info(f"[{model_name}] 搜索: {keyword}")

    if not search_and_open_market(d, keyword):
        logger.warning(f"[{model_name}] 搜索/行情页打开失败")
        return []

    all_records = []
    seen = set()

    for i in range(max_scrolls):
        records = extract_visible_records(d)
        new_count = 0
        for r in records:
            key = f"{r['sold_price']}_{r['list_price']}_{r.get('sold_after', '')}"
            if key not in seen:
                seen.add(key)
                r['model'] = model_name
                r['keyword'] = keyword
                r['crawled_at'] = datetime.now().isoformat()
                all_records.append(r)
                new_count += 1

        logger.info(f"  第{i+1}屏: +{new_count}条 (累计{len(all_records)}条)")

        if new_count == 0 and i > 1:
            break

        d.swipe(0.5, 0.75, 0.5, 0.4, duration=0.5)
        time.sleep(2)

    logger.info(f"[{model_name}] 完成: {len(all_records)}条")
    return all_records


def save_records(records: list):
    """保存（追加+去重）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = []
    if MARKET_DB.exists():
        with open(MARKET_DB, 'r', encoding='utf-8') as f:
            existing = json.load(f)

    seen = {(r['model'], r['sold_price'], r['list_price'], r.get('sold_after', '')) for r in existing}
    new_count = 0
    for r in records:
        key = (r['model'], r['sold_price'], r['list_price'], r.get('sold_after', ''))
        if key not in seen:
            seen.add(key)
            existing.append(r)
            new_count += 1

    with open(MARKET_DB, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    logger.info(f"保存: {new_count}条新增 (总计{len(existing)}条)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--keyword', '-k', default='')
    parser.add_argument('--models', '-m', type=int, default=0)
    parser.add_argument('--scrolls', '-s', type=int, default=5)
    parser.add_argument('--delay', '-d', type=int, default=8)
    args = parser.parse_args()

    # 加载关键词
    config_path = Path(__file__).parent.parent / "config" / "keywords.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        keywords = yaml.safe_load(f).get('keywords', [])

    if args.keyword:
        keywords = [{'name': args.keyword, 'aliases': [args.keyword], 'brand': ''}]
    elif args.models > 0:
        keywords = keywords[:args.models]

    logger.info(f"开始采集: {len(keywords)} 个型号")

    # 连接手机
    d = u2.connect(DEVICE_ID)
    logger.info(f"已连接: {d.device_info.get('model', '?')}")

    # 保持屏幕常亮
    adb('shell', 'settings', 'put', 'system', 'screen_off_timeout', '1800000')

    all_records = []
    for i, kw_cfg in enumerate(keywords):
        name = kw_cfg['name']
        alias = kw_cfg.get('aliases', [name])[0]

        try:
            # 启动App
            launch_xianyu(d)

            records = crawl_model(d, alias, name, args.scrolls)
            all_records.extend(records)

            if records:
                save_records(records)

            # 延迟
            if i < len(keywords) - 1:
                delay = args.delay + (hash(name) % 5)
                logger.info(f"等待{delay}秒...")
                time.sleep(delay)

            # 每20个型号重启App
            if (i + 1) % 20 == 0:
                adb('shell', 'am', 'force-stop', XIANYU_PKG)
                time.sleep(3)

        except Exception as e:
            logger.error(f"[{name}] 失败: {e}")
            adb('shell', 'am', 'force-stop', XIANYU_PKG)
            time.sleep(3)

    # 汇总
    from collections import defaultdict
    by_model = defaultdict(list)
    for r in all_records:
        by_model[r['model']].append(r)

    print(f"\n{'='*60}")
    print(f"  行情采集完成: {len(all_records)} 条")
    print(f"{'='*60}")
    for model, recs in by_model.items():
        prices = [r['sold_price'] for r in recs]
        print(f"  {model}: {len(recs)}条, 均价¥{sum(prices)/len(prices):.0f}, ¥{min(prices):.0f}~¥{max(prices):.0f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
