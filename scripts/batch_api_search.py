"""方案B: Playwright拦截闲鱼搜索API，批量获取结构化数据"""
import asyncio
import json
import os
import sys
import sqlite3
from datetime import datetime
from playwright.async_api import async_playwright

COOKIES_FILE = "data/xianyu_cookies.json"
DB_PATH = "data/xianyu_data.db"

# 球拍型号配置
RACKET_KEYWORDS = {
    "疾光NF800PRO": ["疾光800pro", "nf800pro"],
    "天斧88D PRO": ["天斧88d pro", "88dpro"],
    "天斧100ZZ": ["天斧100zz", "100zz"],
    "天斧77PRO": ["天斧77pro", "77pro"],
    "弓箭11PRO": ["弓箭11pro"],
    "风刃900": ["风刃900"],
    "雷霆80": ["雷霆80"],
    "战戟8000": ["战戟8000"],
    "神速100X": ["神速100x"],
    "龙牙之刃": ["龙牙之刃"],
    "极速10": ["极速10"],
    "雷霆90龙": ["雷霆90龙"],
    "天斧88S PRO": ["天斧88s pro", "88spro"],
    "风动9000": ["风动9000"],
    "亮剑12": ["亮剑12"],
}


def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS xianyu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT,
            item_id TEXT UNIQUE,
            title TEXT,
            price REAL,
            tag TEXT,
            condition_text TEXT,
            brand TEXT,
            seller_credit TEXT,
            want_count INTEGER DEFAULT 0,
            source TEXT DEFAULT 'api',
            raw_data TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_item_model ON xianyu_items(model_name)
    """)
    conn.commit()
    return conn


def save_items(conn, model_name, items):
    """保存商品数据到数据库"""
    saved = 0
    for item in items:
        try:
            price = float(item.get('price', 0) or 0)
            want = int(item.get('want', 0) or 0)
            conn.execute("""
                INSERT OR REPLACE INTO xianyu_items 
                (model_name, item_id, title, price, tag, condition_text, brand, seller_credit, want_count, source, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                model_name,
                item.get('item_id', ''),
                item.get('title', ''),
                price,
                item.get('tag', ''),
                item.get('condition', ''),
                item.get('brand', ''),
                item.get('seller_credit', ''),
                want,
                item.get('source', 'api'),
                item.get('raw', '')
            ))
            saved += 1
        except Exception as e:
            print(f"  Save error: {e}")
    conn.commit()
    return saved


async def search_keyword(page, keyword, max_pages=2):
    """搜索关键词，拦截API获取结果"""
    all_items = []
    
    captured = {}
    async def on_response(response):
        url = response.url
        if 'mtop.taobao.idlemtopsearch.pc.search/' in url and 'shade' not in url and 'activate' not in url:
            try:
                text = await response.text()
                body = None
                try:
                    body = json.loads(text)
                except:
                    s = text.find('{')
                    e = text.rfind('}') + 1
                    if s >= 0 and e > s:
                        body = json.loads(text[s:e])
                if body and body.get('ret', [''])[0].startswith('SUCCESS'):
                    captured['data'] = body.get('data', {})
            except:
                pass
    
    page.on('response', on_response)
    
    for pg in range(1, max_pages + 1):
        captured.clear()
        url = f"https://www.goofish.com/search?q={keyword}&page={pg}"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)
            
            # Scroll to trigger more loading
            for _ in range(2):
                await page.mouse.wheel(0, 600)
                await asyncio.sleep(1)
            
            data = captured.get('data', {})
            result_list = data.get('resultList', [])
            
            for item in result_list:
                d = item.get('data', {})
                main = d.get('item', {}).get('main', {})
                cp = main.get('clickParam', {}).get('args', {})
                ex = main.get('exContent', {})
                dp = ex.get('detailParams', {})
                
                # Title from detailParams
                title = dp.get('title', '') or cp.get('keyword', '')
                title = title.replace('\n', ' ').strip()
                
                # Price
                price = cp.get('price', '') or dp.get('soldPrice', '')
                
                # Item ID
                item_id = cp.get('id', '') or dp.get('itemId', '')
                
                # Tags from clickParam
                tagname = cp.get('tagname', '')
                
                # Want count from serviceUtParams
                want = cp.get('wantNum', '0')
                if want == '0':
                    # Try to extract from serviceUtParams
                    sup = cp.get('serviceUtParams', '')
                    import re
                    want_match = re.search(r'(\d+)人想要', sup)
                    if want_match:
                        want = want_match.group(1)
                
                # Condition from fishTags
                condition = ''
                fish_tags = ex.get('fishTags', {})
                r2 = fish_tags.get('r2', {}).get('tagList', [])
                for tag in r2:
                    content = tag.get('data', {}).get('content', '')
                    if content in ('全新', '几乎全新', '轻微使用痕迹', '明显使用痕迹', '仅拆封未使用'):
                        condition = content
                        break
                
                # Brand from fishTags
                brand = ''
                for tag in r2:
                    content = tag.get('data', {}).get('content', '')
                    if '/' in content and len(content) < 30:
                        brand = content
                        break
                
                # Seller credit
                seller_credit = ''
                r4 = fish_tags.get('r4', {}).get('tagList', [])
                for tag in r4:
                    content = tag.get('data', {}).get('content', '')
                    if '信用' in content:
                        seller_credit = content
                        break
                
                if title and item_id:
                    all_items.append({
                        'item_id': item_id,
                        'title': title[:200],
                        'price': price,
                        'tag': tagname,
                        'want': want,
                        'condition': condition,
                        'brand': brand,
                        'seller_credit': seller_credit,
                        'source': 'api',
                        'raw': json.dumps(d, ensure_ascii=False)[:800]
                    })
            
            print(f"  [{keyword}] p{pg}: {len(result_list)} API results")
            
        except Exception as e:
            print(f"  [{keyword}] p{pg}: Error - {e}")
    
    page.remove_listener('response', on_response)
    return all_items


async def main():
    # Parse args
    keywords_config = RACKET_KEYWORDS
    max_pages = 2
    
    if len(sys.argv) > 1:
        # Single keyword mode
        kw = sys.argv[1]
        max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        keywords_config = {kw: [kw]}
    
    conn = init_db()
    total_saved = 0
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            valid = [c for c in cookies if c.get('name') and c.get('value')]
            if valid:
                await context.add_cookies(valid)
        
        page = await context.new_page()
        
        for model_name, aliases in keywords_config.items():
            print(f"\n=== {model_name} ===")
            model_items = []
            
            for alias in aliases:
                items = await search_keyword(page, alias, max_pages)
                model_items.extend(items)
            
            # Deduplicate by item_id
            seen = set()
            unique_items = []
            for item in model_items:
                if item['item_id'] not in seen:
                    seen.add(item['item_id'])
                    unique_items.append(item)
            
            saved = save_items(conn, model_name, unique_items)
            total_saved += saved
            
            prices = [float(i['price']) for i in unique_items if i.get('price')]
            if prices:
                avg = sum(prices) / len(prices)
                print(f"  -> {saved} saved, avg ¥{avg:.0f}, range ¥{min(prices):.0f}~¥{max(prices):.0f}")
            else:
                print(f"  -> {saved} saved, no prices")
        
        await browser.close()
    
    conn.close()
    print(f"\n=== Done: {total_saved} total items saved ===")


if __name__ == '__main__':
    asyncio.run(main())
