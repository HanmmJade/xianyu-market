# -*- coding: utf-8 -*-
"""
定时调度器
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
        from apscheduler.triggers.cron import CronTrigger
        return CronTrigger.from_crontab(expr)

    return {'hour': 2, 'minute': 0}


async def run_crawl_job():
    """执行爬取+导出任务"""
    from crawler.xianyu_spider import XianyuSpider
    from storage.db import insert_records
    from storage.export import export_all

    logger.info("[调度] 开始闲鱼行情爬取")

    try:
        spider = XianyuSpider(headless=True)
        records = await spider.crawl_all()

        if records:
            inserted = insert_records(records)
            logger.info(f"[调度] 入库 {inserted} 条")
            export_all()
            logger.info("[调度] 数据导出完成")
        else:
            logger.warning("[调度] 未抓取到数据")

    except Exception as e:
        logger.error(f"[调度] 任务失败: {e}")


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

    loop = asyncio.new_event_loop()

    def _shutdown(sig, frame):
        logger.info("收到停止信号")
        scheduler.shutdown(wait=False)
        loop.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        loop.run_forever()
    finally:
        loop.close()
