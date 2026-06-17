# -*- coding: utf-8 -*-
"""
闲鱼球拍行情价监控系统 — 主入口
"""

import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger


def cmd_init_db(args):
    from storage.db import init_db, migrate_db
    init_db()
    migrate_db()


def cmd_crawl(args):
    from crawler.xianyu_spider import XianyuSpider
    from storage.db import insert_records, init_db, migrate_db

    init_db()
    migrate_db()

    keyword = args.keyword or ''
    login_mode = args.login or 'auto'
    spider = XianyuSpider(headless=args.headless, login_mode=login_mode)

    if keyword:
        records = asyncio.run(spider.crawl_all(keyword_filter=keyword))
    else:
        records = asyncio.run(spider.crawl_all())

    if records:
        inserted = insert_records(records)
        logger.info(f"完成: 抓取{len(records)}条, 新增{inserted}条")

        # 自动导出
        if args.export:
            from storage.export import export_all
            export_all()
            logger.info("JSON 导出完成")
    else:
        logger.warning("未抓取到数据")


def cmd_crawl_mtop(args):
    """使用 mtop API 爬虫采集数据"""
    from crawler.mtop_crawler import MtopCrawler
    from storage.db import insert_records, init_db, migrate_db

    init_db()
    migrate_db()

    keyword = args.keyword or ''
    crawler = MtopCrawler(headless=args.headless)

    async def run():
        await crawler.start()
        try:
            # 确保已登录
            if not await crawler.login_if_needed():
                logger.error("登录失败，无法继续")
                return []

            if keyword:
                return await crawler.crawl_all(keyword_filter=keyword)
            else:
                return await crawler.crawl_all()
        finally:
            await crawler.close()

    records = asyncio.run(run())

    if records:
        inserted = insert_records(records)
        logger.info(f"完成: 采集{len(records)}条, 新增{inserted}条")

        if args.export:
            from storage.export import export_all
            export_all()
            logger.info("JSON 导出完成")
    else:
        logger.warning("未采集到数据")


def cmd_pipeline(args):
    """一键执行完整管道: init-db → crawl → clean → export"""
    from storage.db import init_db, migrate_db, insert_records, get_stats
    from storage.export import export_all

    logger.info("=" * 50)
    logger.info("  开始执行完整数据管道")
    logger.info("=" * 50)

    # Step 1: 初始化数据库
    logger.info("[1/4] 初始化数据库...")
    init_db()
    migrate_db()

    # Step 2: 采集数据
    logger.info("[2/4] 采集数据...")
    keyword = args.keyword or ''

    if args.crawler == 'mtop':
        from crawler.mtop_crawler import MtopCrawler
        crawler = MtopCrawler(headless=args.headless)

        async def run_mtop():
            await crawler.start()
            try:
                if not await crawler.login_if_needed():
                    logger.error("登录失败")
                    return []
                if keyword:
                    return await crawler.crawl_all(keyword_filter=keyword)
                else:
                    return await crawler.crawl_all()
            finally:
                await crawler.close()

        records = asyncio.run(run_mtop())
    else:
        from crawler.xianyu_spider import XianyuSpider
        login_mode = args.login or 'auto'
        spider = XianyuSpider(headless=args.headless, login_mode=login_mode)
        if keyword:
            records = asyncio.run(spider.crawl_all(keyword_filter=keyword))
        else:
            records = asyncio.run(spider.crawl_all())

    # Step 3: 入库
    logger.info("[3/4] 数据入库...")
    if records:
        inserted = insert_records(records)
        logger.info(f"  采集 {len(records)} 条，新增 {inserted} 条")
    else:
        logger.warning("  未采集到数据")

    # Step 4: 导出
    logger.info("[4/4] 导出 JSON...")
    export_all()

    # 统计
    stats = get_stats()
    logger.info("=" * 50)
    logger.info(f"  管道执行完成")
    logger.info(f"  总记录: {stats['total_records']}")
    logger.info(f"  型号数: {stats['total_models']}")
    logger.info(f"  上次爬取: {stats['last_crawled'] or '-'}")
    logger.info("=" * 50)


def cmd_export(args):
    from storage.export import export_all
    export_all()


def cmd_serve(args):
    import http.server
    import functools

    web_dir = Path(__file__).parent / "web"
    if not web_dir.exists():
        logger.error("web目录不存在")
        return

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(web_dir))
    host = args.host or "0.0.0.0"
    port = args.port or 8088

    logger.info(f"本地预览: http://localhost:{port}")
    with http.server.HTTPServer((host, port), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def cmd_serve_api(args):
    """启动 FastAPI 后端服务"""
    import uvicorn
    host = args.host or "0.0.0.0"
    port = args.port or 8000
    logger.info(f"FastAPI 服务: http://{host}:{port}")
    uvicorn.run("server.main:app", host=host, port=port, reload=args.reload)


def cmd_schedule(args):
    from scheduler.runner import start_scheduler
    start_scheduler()


def cmd_stats(args):
    from storage.db import get_stats, get_all_models
    stats = get_stats()
    print(f"\n数据库统计:")
    print(f"  总记录: {stats['total_records']}")
    print(f"  型号数: {stats['total_models']}")
    print(f"  上次爬取: {stats['last_crawled'] or '-'}")

    models = get_all_models()
    if models:
        print(f"\n型号列表:")
        for m in models:
            print(f"  {m['model']}: {m['total_sales']}笔, 均价{m['avg_price']}元")
    print()


def cmd_clean(args):
    """对已有数据执行清洗（不重新爬取）"""
    from storage.db import get_all_models, get_model_detail
    from crawler.cleaner import is_garbage, classify_model, infer_condition

    models = get_all_models()
    if not models:
        print("数据库无数据，请先 crawl")
        return

    total_cleaned = 0
    total_removed = 0
    total_mismatch = 0

    for m in models:
        model_name = m['model']
        detail = get_model_detail(model_name)
        records = detail['records']

        print(f"\n{'='*50}")
        print(f"清洗: {model_name} ({len(records)}条记录)")
        print(f"{'='*50}")

        cleaned_count = 0
        removed_count = 0
        mismatch_count = 0

        for r in records:
            title = r.get('title', '')
            price = r.get('price', 0)
            old_condition = r.get('condition', '')

            # 脏数据检测
            is_bad, reason = is_garbage(title)
            if is_bad:
                print(f"  X ¥{price} 垃圾数据: {title[:30]}... ({reason})")
                removed_count += 1
                continue

            # 型号过滤
            is_match, match_reason = classify_model(title, model_name)
            if not is_match:
                print(f"  X ¥{price} 型号不符: {title[:30]}... ({match_reason})")
                removed_count += 1
                continue

            # 成色推断
            cond = infer_condition(title)
            new_condition = cond['label']

            if old_condition != new_condition:
                print(f"  ~ ¥{price} 成色修正: {old_condition or '未标'} -> {new_condition} ({cond['score']}分)")
                mismatch_count += 1

            cleaned_count += 1

        print(f"\n  汇总: 保留{cleaned_count}条, 移除{removed_count}条, 成色修正{mismatch_count}条")
        total_cleaned += cleaned_count
        total_removed += removed_count
        total_mismatch += mismatch_count

    print(f"\n{'='*50}")
    print(f"全部清洗完成: 保留{total_cleaned}条, 移除{total_removed}条, 成色修正{total_mismatch}条")
    print(f"{'='*50}")

    if args.export:
        print("\n重新导出JSON...")
        from storage.export import export_all
        export_all()
        print("导出完成")


def main():
    parser = argparse.ArgumentParser(description='闲鱼球拍行情价监控系统')
    sub = parser.add_subparsers(dest='command')

    # init-db
    sub.add_parser('init-db', help='初始化数据库')

    # crawl (Playwright 方案)
    p = sub.add_parser('crawl', help='使用 Playwright 爬虫采集数据')
    p.add_argument('--keyword', '-k', help='指定关键词(如 "天斧88D PRO")')
    p.add_argument('--headless', action='store_true', help='无头模式')
    p.add_argument('--login', '-l', choices=['auto', 'cookie', 'qrcode'],
                   default='auto', help='登录方式')
    p.add_argument('--no-export', dest='export', action='store_false',
                   help='不自动导出JSON')
    p.set_defaults(export=True)

    # crawl-mtop (mtop API 方案)
    p = sub.add_parser('crawl-mtop', help='使用 mtop API 爬虫采集数据')
    p.add_argument('--keyword', '-k', help='指定关键词')
    p.add_argument('--headless', action='store_true', help='无头模式')
    p.add_argument('--no-export', dest='export', action='store_false',
                   help='不自动导出JSON')
    p.set_defaults(export=True)

    # pipeline (一键完整管道)
    p = sub.add_parser('pipeline', help='一键执行: init-db -> crawl -> export')
    p.add_argument('--keyword', '-k', help='指定关键词')
    p.add_argument('--headless', action='store_true', help='无头模式')
    p.add_argument('--crawler', '-c', choices=['playwright', 'mtop'],
                   default='mtop', help='爬虫方案 (默认: mtop)')
    p.add_argument('--login', '-l', choices=['auto', 'cookie', 'qrcode'],
                   default='auto', help='登录方式 (Playwright方案)')

    # export
    sub.add_parser('export', help='导出JSON给前端')

    # serve (静态文件)
    p = sub.add_parser('serve', help='本地预览静态网站')
    p.add_argument('--host', default='0.0.0.0')
    p.add_argument('--port', type=int, default=8088)

    # serve-api (FastAPI)
    p = sub.add_parser('serve-api', help='启动 FastAPI 后端')
    p.add_argument('--host', default='0.0.0.0')
    p.add_argument('--port', type=int, default=8000)
    p.add_argument('--reload', action='store_true', help='开发模式热重载')

    # schedule
    sub.add_parser('schedule', help='启动定时调度')

    # stats
    sub.add_parser('stats', help='查看数据库统计')

    # clean
    p = sub.add_parser('clean', help='清洗已有数据（不重新爬取）')
    p.add_argument('--export', action='store_true', help='清洗后自动重新导出JSON')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    handlers = {
        'init-db': cmd_init_db,
        'crawl': cmd_crawl,
        'crawl-mtop': cmd_crawl_mtop,
        'pipeline': cmd_pipeline,
        'export': cmd_export,
        'serve': cmd_serve,
        'serve-api': cmd_serve_api,
        'schedule': cmd_schedule,
        'stats': cmd_stats,
        'clean': cmd_clean,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
