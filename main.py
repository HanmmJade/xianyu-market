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

    # 确保数据库结构是最新的
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
    else:
        logger.warning("未抓取到数据")


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
    from storage.db import get_all_models, get_model_detail, update_record_condition
    from crawler.cleaner import clean_record, is_garbage, classify_model, infer_condition

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
                print(f"  ❌ ¥{price} 垃圾数据: {title[:30]}... ({reason})")
                removed_count += 1
                continue

            # 型号过滤
            is_match, match_reason = classify_model(title, model_name)
            if not is_match:
                print(f"  ❌ ¥{price} 型号不符: {title[:30]}... ({match_reason})")
                removed_count += 1
                continue

            # 成色推断
            cond = infer_condition(title)
            new_condition = cond['label']

            if old_condition != new_condition:
                print(f"  🔄 ¥{price} 成色修正: {old_condition or '未标'} → {new_condition} ({cond['score']}分)")
                for e in cond['evidence']:
                    print(f"      └─ {e}")
                mismatch_count += 1

            # 更新数据库中的成色
            if hasattr(update_record_condition, '__call__'):
                try:
                    update_record_condition(r.get('id'), new_condition, cond)
                except:
                    pass  # 如果数据库不支持更新，跳过

            cleaned_count += 1

        print(f"\n  汇总: 保留{cleaned_count}条, 移除{removed_count}条, 成色修正{mismatch_count}条")
        total_cleaned += cleaned_count
        total_removed += removed_count
        total_mismatch += mismatch_count

    print(f"\n{'='*50}")
    print(f"全部清洗完成: 保留{total_cleaned}条, 移除{total_removed}条, 成色修正{total_mismatch}条")
    print(f"{'='*50}")

    # 重新导出
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

    # crawl
    p = sub.add_parser('crawl', help='爬取数据')
    p.add_argument('--keyword', '-k', help='指定关键词(如 "天斧88D PRO")')
    p.add_argument('--headless', action='store_true', help='无头模式')
    p.add_argument('--login', '-l', choices=['auto', 'cookie', 'qrcode'],
                   default='auto', help='登录方式: auto(先Cookie再扫码) / cookie / qrcode')

    # export
    sub.add_parser('export', help='导出JSON给前端')

    # serve
    p = sub.add_parser('serve', help='本地预览网站')
    p.add_argument('--host', default='0.0.0.0')
    p.add_argument('--port', type=int, default=8088)

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
        'export': cmd_export,
        'serve': cmd_serve,
        'schedule': cmd_schedule,
        'stats': cmd_stats,
        'clean': cmd_clean,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
