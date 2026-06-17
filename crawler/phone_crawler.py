# -*- coding: utf-8 -*-
"""
闲鱼手机行情爬虫 — 通过ADB操控夸克浏览器中的闲鱼网页
抓取"行情"标签下的成交记录（成交价、发布价、成交时间）

使用方法：
  python crawler/phone_crawler.py
"""

import asyncio
import json
import re
import time
from pathlib import Path
from datetime import datetime
from loguru import logger

import uiautomator2 as u2
import xml.etree.ElementTree as ET

DEVICE_ID = "ee635a46"
OUTPUT_DIR = Path(__file__).parent.parent / "data"


class PhoneCrawler:
    """通过ADB操控手机闲鱼网页抓取成交数据"""

    def __init__(self, device_id: str = DEVICE_ID):
        self.device_id = device_id
        self.d = None

    def connect(self):
        """连接手机"""
        self.d = u2.connect(self.device_id)
        info = self.d.device_info
        logger.info(f"已连接: {info.get('brand', '?')} {info.get('model', '?')}")

    def search_and_get_market(self, keyword: str) -> list:
        """
        在闲鱼搜索关键词，切到"行情"标签，抓取成交记录
        """
        records = []

        # 1. 点击搜索框
        logger.info(f"搜索: {keyword}")

        # 点击搜索栏的关键词区域
        kw_container = self.d(resourceId="keyword_container")
        if kw_container.exists(timeout=3):
            kw_container.click()
            time.sleep(1)
        else:
            # 尝试点击搜索文本
            kw_text = self.d(resourceId="keyword_text")
            if kw_text.exists(timeout=2):
                kw_text.click()
                time.sleep(1)

        # 2. 清除旧关键词，输入新关键词
        # 找到输入框
        input_field = self.d(className="android.widget.EditText")
        if not input_field.exists(timeout=3):
            # 可能需要重新点击搜索区域
            self.d(resourceId="keyword_container").click()
            time.sleep(1)
            input_field = self.d(className="android.widget.EditText")

        if input_field.exists(timeout=2):
            input_field.clear_text()
            input_field.set_text(keyword)
            time.sleep(0.5)
        else:
            logger.warning("找不到输入框")
            self._dump_ui()
            return records

        # 3. 按搜索/回车
        self.d.press("enter")
        time.sleep(3)

        # 4. 切换到"行情"标签
        market_tab = self.d(text="行情")
        if market_tab.exists(timeout=3):
            market_tab.click()
            time.sleep(2)
            logger.info("已切换到行情标签")
        else:
            logger.warning("未找到'行情'标签")
            # 打印当前可见标签
            self._dump_tabs()
            return records

        # 5. 滚动抓取成交记录
        seen = set()
        for scroll_round in range(8):  # 最多滚动8次
            page_items = self._extract_market_records()

            new_count = 0
            for item in page_items:
                key = f"{item.get('title', '')[:30]}_{item.get('sold_price', 0)}"
                if key not in seen:
                    seen.add(key)
                    records.append(item)
                    new_count += 1

            logger.info(f"  第{scroll_round+1}屏: {new_count}条新增 (累计{len(records)}条)")

            if new_count == 0 and scroll_round > 1:
                # 连续无新数据，可能到底了
                break

            # 向下滚动
            self.d.swipe(0.5, 0.8, 0.5, 0.3, duration=0.5)
            time.sleep(2)

        logger.info(f"'{keyword}' 共抓取 {len(records)} 条成交记录")
        return records

    def _extract_market_records(self) -> list:
        """从行情页当前屏幕提取成交记录"""
        items = []

        hierarchy = self.d.dump_hierarchy()
        if not hierarchy:
            return items

        try:
            root = ET.fromstring(hierarchy)
        except:
            return items

        # 收集所有文本和content-desc
        all_texts = []
        for elem in root.iter():
            text = elem.get('text', '').strip()
            desc = elem.get('content-desc', '').strip()
            if text:
                all_texts.append(('text', text))
            if desc and desc != text:
                all_texts.append(('desc', desc))

        # 合并所有文本
        full_text = '\n'.join(t[1] for t in all_texts)

        # 从content-desc中提取成交记录
        # 格式：标题\n品牌\n成色\n成交价\n发布价¥xxx\n发布X天后成交\n¥xxx
        desc_texts = [t[1] for t in all_texts if t[0] == 'desc']

        for desc in desc_texts:
            record = self._parse_market_desc(desc)
            if record:
                items.append(record)

        # 也从纯文本中提取
        text_only = [t[1] for t in all_texts if t[0] == 'text']
        items.extend(self._parse_market_texts(text_only))

        return items

    def _parse_market_desc(self, desc: str) -> dict:
        """解析行情页的content-desc文本"""
        # 去掉Unicode零宽字符
        desc = desc.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')

        record = {}

        # 提取标题（第一行）
        lines = [l.strip() for l in desc.split('\n') if l.strip()]
        if not lines:
            return {}

        record['title'] = lines[0][:200]

        for i, line in enumerate(lines):
            # 发布价
            m = re.match(r'发布价[¥￥]?\s*(\d+(?:\.\d{1,2})?)', line)
            if m:
                record['list_price'] = float(m.group(1))

            # 成交价标签后面，找独立的¥数字行
            if line == '成交价':
                for j in range(i+1, len(lines)):
                    m2 = re.match(r'^[¥￥]\s*(\d+(?:\.\d+)?)$', lines[j])
                    if m2:
                        record['sold_price'] = float(m2.group(1))
                        break

            # 成交时间
            m3 = re.search(r'发布(\d+[天小时]+)后成交', line)
            if m3:
                record['sold_after'] = m3.group(1)
            elif '发布当天成交' in line:
                record['sold_after'] = '当天'

            # 品牌
            for brand in ['YONEX/尤尼克斯', 'Lining/李宁', 'VICTOR/威克多', 'Victor']:
                if brand in line:
                    record['brand'] = brand
                    break

            # 成色
            for cond in ['全新', '几乎全新', '轻微使用痕迹', '明显使用痕迹', '95新', '9新']:
                if cond in line:
                    record['condition'] = cond
                    break

        return record if record.get('sold_price') else {}

    def _parse_market_texts(self, texts: list) -> list:
        """从纯文本行中解析成交记录"""
        items = []
        # 行情页的纯文本格式通常比较零散
        # 主要靠content-desc，这里做兜底
        return items

    def _dump_ui(self):
        """调试：保存UI结构"""
        try:
            hierarchy = self.d.dump_hierarchy()
            if hierarchy:
                path = OUTPUT_DIR / "ui_dump.xml"
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(hierarchy)
                logger.info(f"UI已保存: {path}")
        except:
            pass

    def _dump_tabs(self):
        """打印当前可见的标签/按钮"""
        try:
            root = ET.fromstring(self.d.dump_hierarchy())
            for elem in root.iter():
                text = elem.get('text', '').strip()
                if text and 1 < len(text) < 10:
                    logger.info(f"  标签: {text}")
        except:
            pass

    def crawl_keywords(self, keywords: list) -> list:
        """批量爬取多个型号的行情数据"""
        all_records = []

        for kw_cfg in keywords:
            name = kw_cfg['name']
            aliases = kw_cfg.get('aliases', [name])

            # 每个型号只用第一个alias搜索（行情页数据已经按型号聚合）
            alias = aliases[0]

            try:
                records = self.search_and_get_market(alias)
                for r in records:
                    r['model'] = name
                    r['keyword'] = alias
                    r['crawled_at'] = datetime.now().isoformat()
                all_records.extend(records)
                logger.info(f"[{name}] {len(records)}条成交记录")

                # 间隔避免被限流
                time.sleep(3)
            except Exception as e:
                logger.error(f"[{name}] 失败: {e}")

        # 保存结果
        output_path = OUTPUT_DIR / "phone_crawl_result.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)
        logger.info(f"全部完成: {len(all_records)}条 → {output_path}")

        return all_records


def main():
    """测试：搜索一个关键词"""
    import yaml

    config_path = Path(__file__).parent.parent / "config" / "keywords.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    keywords = config.get('keywords', [])[:1]  # 先测1个

    crawler = PhoneCrawler()
    crawler.connect()
    results = crawler.crawl_keywords(keywords)

    print(f"\n抓取结果: {len(results)} 条")
    for r in results[:10]:
        print(f"  ¥{r.get('sold_price', '?'):>6} (发布¥{r.get('list_price', '?')}) | {r.get('title', '')[:40]} | {r.get('sold_after', '')}")


if __name__ == "__main__":
    main()
