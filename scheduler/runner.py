# -*- coding: utf-8 -*-
"""
定时调度器 v2 — 支持重试、多爬虫模式、完整管道
"""

import asyncio
import signal
from pathlib import Path
from datetime import datetime
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import yaml


SCHEDULE_YAML = Path(__file__).parent.parent / "config" / "settings.yaml"


def load_schedule_config() -> dict:
    if SCHEDULE_YAML.exists():
        with open(SCHEDULE_YAML, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return data.get('schedule', {})
    return {'enabled': True, 'cron': 'daily 2:00'}


def load_crawler_config() -> dict:
    if SCHEDULE_YAML.exists():
        with open(SCHEDULE_YAML, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return data.get('crawler', {})
    return {}


def parse_cron(expr: str) -> dict:
    """解析简化cron: 'daily 2:00' -> {'hour': 2, 'minute': 0}"""
    expr = expr.strip()
    parts = expr.split()

    if parts[0] == 'daily' and len(parts) == 2:
        h, m = parts[1].split(':')
        return {'hour': int(h), 'minute': int(m)}

    if parts[0] in ('weekdays', 'mon-fri') and len(parts) == 2:
        h, m = parts[1].split(':')
        return {'day_of_week': 'mon-fri', 'hour': int(h), 'minute': int(m)}

    # 标准5字段cron
    if len(parts) == 5:
        return CronTrigger.from_crontab(expr)

    return {'hour': 2, 'minute': 0}


async def _run_mtop_crawl(keyword_filter: str = '') -> list:
    """使用 mtop 爬虫采集"""
    from crawler.mtop_crawler import MtopCrawler

    crawler = MtopCrawler(headless=True)
    await crawler.start()
    try:
        if not await crawler.login_if_needed():
            logger.error("[调度] mtop 登录失败")
            return []
        if keyword_filter:
            return await crawler.crawl_all(keyword_filter=keyword_filter)
        else:
            return await crawler.crawl_all()
    finally:
        await crawler.close()


async def _run_playwright_crawl(keyword_filter: str = '') -> list:
    """使用 Playwright 爬虫采集"""
    from crawler.xianyu_spider import XianyuSpider

    spider = XianyuSpider(headless=True, login_mode='auto')
    if keyword_filter:
        return await spider.crawl_all(keyword_filter=keyword_filter)
    else:
        return await spider.crawl_all()


async def run_crawl_job():
    """执行完整管道: 采集 → 入库 → 导出"""
    from storage.db import insert_records, init_db, migrate_db, get_stats
    from storage.export import export_all

    cfg = load_crawler_config()
    crawler_type = cfg.get('scheduler_crawler', 'mtop')
    retry_count = cfg.get('retry_count', 2)
    retry_delay = cfg.get('retry_delay', 300)

    logger.info(f"[调度] 开始闲鱼行情爬取 (爬虫: {crawler_type})")

    # 初始化数据库
    init_db()
    migrate_db()

    records = []
    for attempt in range(1, retry_count + 1):
        try:
            if crawler_type == 'mtop':
                records = await _run_mtop_crawl()
            else:
                records = await _run_playwright_crawl()

            if records:
                break
            else:
                logger.warning(f"[调度] 第{attempt}次未采集到数据")
        except Exception as e:
            logger.error(f"[调度] 第{attempt}次采集失败: {e}")

        if attempt < retry_count:
            logger.info(f"[调度] {retry_delay}秒后重试...")
            await asyncio.sleep(retry_delay)

    # 入库
    if records:
        inserted = insert_records(records)
        logger.info(f"[调度] 入库 {inserted} 条 (共采集 {len(records)} 条)")

        # 导出
        export_all()
        logger.info("[调度] JSON 导出完成")

        # 统计
        stats = get_stats()
        logger.info(f"[调度] 数据库: {stats['total_records']} 条记录, {stats['total_models']} 个型号")
    else:
        logger.warning("[调度] 本次未采集到数据")


def start_scheduler():
    """启动调度器（前台运行）"""
    cfg = load_schedule_config()

    scheduler = AsyncIOScheduler()

    cron_expr = cfg.get('cron', 'daily 2:00')
    parsed = parse_cron(cron_expr)
    if isinstance(parsed, dict):
        trigger = CronTrigger(**parsed)
    else:
        trigger = parsed

    scheduler.add_job(run_crawl_job, trigger, id='xianyu_crawl', replace_existing=True)
    scheduler.start()

    logger.info(f"调度器启动: {cron_expr}")
    logger.info("按 Ctrl+C 停止")

    loop = asyncio.new_event_loop()

    def _shutdown(sig, frame):
        logger.info("收到停止信号，正在关闭...")
        scheduler.shutdown(wait=False)
        loop.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_forever()
    finally:
        loop.close()
        logger.info("调度器已停止")
