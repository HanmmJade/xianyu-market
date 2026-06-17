"""用Playwright拦截闲鱼搜索API，批量获取结构化数据"""
import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright

COOKIES_FILE = "data/xianyu_cookies.json"
DB_PATH = "data/xianyu_data.db"

async def search_and_intercept(page, keyword, max_pages=3):
    """搜索并拦截API响应，返回结果列表"""
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
                    start = text.find('{')
                    end = text.rfind('}') + 1
                    if start >= 0 and end > start:
                        body = json.loads(text[start:end])
                if body and body.get('ret', [''])[0].startswith('SUCCESS'):
                    captured['data'] = body.get('data', {})
            except:
                pass
    
    page.on('response', on_response)
    
    for pg in range(1, max_pages + 1):
        captured.clear()
        url = f"https://www.goofish.com/search?q={keyword}&page={pg}"
        print(f"  Page {pg}: {url}")
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(6)
            
            # Scroll to trigger loading
            for _ in range(3):
                await page.mouse.wheel(0, 800)
                await asyncio.sleep(1)
            
            data = captured.get('data', {})
            result_list = data.get('resultList', [])
            
            if result_list:
                for item in result_list:
                    parsed = parse_item(item, keyword)
                    if parsed:
                        all_items.append(parsed)
                print(f"    -> {len(result_list)} items from API")
            else:
                # Fallback: parse from DOM
                dom_items = await parse_from_dom(page, keyword)
                all_items.extend(dom_items)
                print(f"    -> {len(dom_items)} items from DOM")
                
        except Exception as e:
            print(f"    -> Error: {e}")
    
    page.remove_listener('response', on_response)
    return all_items


def parse_item(item, keyword):
    """解析API返回的商品数据"""
    try:
        data = item.get('data', item)
        # Try different data structures
        title = data.get('title', '') or data.get('name', '')
        price = data.get('price', '') or data.get('soldPrice', '')
        item_id = data.get('id', '') or data.get('itemId', '')
        
        # Extract from nested structure
        if not title:
            for v in data.values():
                if isinstance(v, dict):
                    title = v.get('title', '') or v.get('name', '')
                    if title:
                        break
        
        if not title:
            return None
        
        return {
            'keyword': keyword,
            'title': title[:200],
            'price': str(price),
            'item_id': str(item_id),
            'source': 'api',
            'raw': json.dumps(data, ensure_ascii=False)[:500]
        }
    except:
        return None


async def parse_from_dom(page, keyword):
    """从DOM解析搜索结果"""
    items = await page.evaluate('''() => {
        const results = [];
        // Find all item links
        document.querySelectorAll('a[href*="/item"]').forEach(a => {
            const href = a.href || '';
            const idMatch = href.match(/id=(\d+)/);
            if (!idMatch) return;
            
            const text = a.textContent?.trim() || '';
            const priceEl = a.querySelector('[class*="price"], [class*="Price"]');
            const price = priceEl ? priceEl.textContent?.trim() : '';
            
            // Extract price from text
            const priceMatch = text.match(/¥\s*(\d+)/);
            const finalPrice = price || (priceMatch ? priceMatch[1] : '');
            
            results.push({
                item_id: idMatch[1],
                title: text.slice(0, 200).replace(/\s+/g, ' '),
                price: finalPrice,
                href: href
            });
        });
        return results;
    }''')
    
    parsed = []
    for item in items:
        if item.get('title') and item.get('item_id'):
            parsed.append({
                'keyword': keyword,
                'title': item['title'],
                'price': item.get('price', ''),
                'item_id': item['item_id'],
                'source': 'dom',
                'raw': ''
            })
    return parsed


async def main():
    import sys
    keyword = sys.argv[1] if len(sys.argv) > 1 else "疾光800pro"
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            valid = [c for c in cookies if c.get('name') and c.get('value')]
            if valid:
                await context.add_cookies(valid)
        
        page = await context.new_page()
        
        print(f"Searching: {keyword} ({max_pages} pages)")
        items = await search_and_intercept(page, keyword, max_pages)
        
        print(f"\nTotal: {len(items)} items")
        
        # Save to file
        output_file = f"data/search_{keyword.replace('/', '_')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"Saved to {output_file}")
        
        # Show samples
        for item in items[:5]:
            print(f"  ¥{item['price']} - {item['title'][:60]}")
        
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
