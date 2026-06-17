# -*- coding: utf-8 -*-
"""
批量API采集脚本
"""

import json
import time
import random
from pathlib import Path
from typing import Dict, List
from loguru import logger

from crawler.api_client import XianyuAPIClient
from storage.db import insert_records, init_db, migrate_db


# 球拍型号配置
RACKET_KEYWORDS = {
    "天斧88D PRO": ["天斧88D PRO", "88D PRO", "88dpro"],
    "天斧100ZZ": ["天斧100ZZ", "100ZZ", "100zz"],
    "天斧77PRO": ["天斧77PRO", "77PRO", "77pro"],
    "弓箭11PRO": ["弓箭11PRO", "11PRO", "11pro"],
    "疾光NF800PRO": ["疾光NF800PRO", "NF800PRO", "nf800pro"],
    "雷霆80": ["雷霆80", "雷霆80"],
    "战戟8000": ["战戟8000", "战戟8000"],
    "风刃900": ["风刃900", "风刃900"],
    "风刃900i": ["风刃900i", "风刃900i"],
    "神速100X": ["神速100X", "100X", "100x"],
    "龙牙之刃": ["龙牙之刃", "龙牙"],
    "极速10": ["极速10", "极速10"],
}


class BatchCrawler:
    """批量采集器"""
    
    def __init__(self, cookies_file: str = None):
        self.client = XianyuAPIClient(cookies_file)
        self.stats = {
            'total_crawled': 0,
            'total_inserted': 0,
            'errors': 0,
        }
    
    def crawl_model(self, model_name: str, keywords: List[str], max_pages: int = 5) -> List[Dict]:
        """
        采集单个型号
        
        Args:
            model_name: 型号名称
            keywords: 搜索关键词列表
            max_pages: 最大页数
        
        Returns:
            采集结果列表
        """
        all_records = []
        
        for keyword in keywords:
            logger.info(f"采集型号: {model_name}, 关键词: {keyword}")
            
            try:
                items = self.client.search_all(keyword, max_pages=max_pages)
                
                # 添加型号信息
                for item in items:
                    item['model'] = model_name
                    item['source'] = 'api'
                
                all_records.extend(items)
                self.stats['total_crawled'] += len(items)
                
            except Exception as e:
                logger.error(f"采集失败 {keyword}: {e}")
                self.stats['errors'] += 1
            
            # 随机延迟
            delay = random.uniform(3, 8)
            time.sleep(delay)
        
        return all_records
    
    def crawl_all(self, models: Dict[str, List[str]] = None, max_pages: int = 5) -> List[Dict]:
        """
        采集所有型号
        
        Args:
            models: 型号配置，默认使用RACKET_KEYWORDS
            max_pages: 每个关键词最大页数
        
        Returns:
            所有采集结果
        """
        if models is None:
            models = RACKET_KEYWORDS
        
        all_records = []
        
        for model_name, keywords in models.items():
            logger.info(f"开始采集: {model_name}")
            
            records = self.crawl_model(model_name, keywords, max_pages)
            all_records.extend(records)
            
            # 保存中间结果
            self.save_intermediate_results(model_name, records)
            
            # 型号间延迟
            delay = random.uniform(10, 20)
            time.sleep(delay)
        
        return all_records
    
    def save_intermediate_results(self, model_name: str, records: List[Dict]):
        """保存中间结果"""
        output_dir = Path(__file__).parent.parent / "data" / "api_results"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = output_dir / f"{model_name}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存中间结果: {filename} ({len(records)}条)")
    
    def save_to_database(self, records: List[Dict]):
        """保存到数据库"""
        if not records:
            logger.warning("没有数据需要保存")
            return
        
        # 初始化数据库
        init_db()
        migrate_db()
        
        # 插入数据
        inserted = insert_records(records)
        self.stats['total_inserted'] = inserted
        
        logger.info(f"数据库保存完成: {inserted}条新记录")
    
    def print_stats(self):
        """打印统计信息"""
        print("\n=== 采集统计 ===")
        print(f"总采集: {self.stats['total_crawled']}条")
        print(f"新增入库: {self.stats['total_inserted']}条")
        print(f"错误数: {self.stats['errors']}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='闲鱼批量采集脚本')
    parser.add_argument('--cookies', '-c', help='Cookie文件路径')
    parser.add_argument('--model', '-m', help='指定型号采集')
    parser.add_argument('--pages', '-p', type=int, default=5, help='每个关键词最大页数')
    parser.add_argument('--dry-run', action='store_true', help='试运行，不保存到数据库')
    
    args = parser.parse_args()
    
    # 创建采集器
    crawler = BatchCrawler(args.cookies)
    
    # 确定采集范围
    if args.model:
        # 单型号采集
        if args.model in RACKET_KEYWORDS:
            models = {args.model: RACKET_KEYWORDS[args.model]}
        else:
            logger.error(f"未知型号: {args.model}")
            return
    else:
        # 全量采集
        models = RACKET_KEYWORDS
    
    # 执行采集
    logger.info("开始批量采集...")
    records = crawler.crawl_all(models, max_pages=args.pages)
    
    # 保存到数据库
    if not args.dry_run:
        crawler.save_to_database(records)
    
    # 打印统计
    crawler.print_stats()


if __name__ == "__main__":
    main()
