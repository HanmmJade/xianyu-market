"""点击详情页行情tab，捕获市场数据API"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

COOKIES_FILE = "data/xianyu_cookies.json"

async def main():
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
        
        all_api_data = {}
        async def on_response(response):
            url = response.url
            if 'h5api.m.goofish.com' not in url:
                return
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
                if body:
                    api = url.split('/h5/')[1].split('/')[0] if '/h5/' in url else 'unknown'
                    if body.get('ret', [''])[0].startswith('SUCCESS'):
                        all_api_data[api] = body.get('data', {})
            except:
                pass
        
        page.on('response', on_response)
        
        # Go to NF800PRO detail page
        item_id = "1055947258242"
        print(f"=== Detail page: {item_id} ===")
        await page.goto(f"https://www.goofish.com/item?id={item_id}", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)
        
        # Find 行情 element
        market_els = await page.evaluate('''() => {
            const results = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
                if (walker.currentNode.textContent.includes('行情')) {
                    const parent = walker.currentNode.parentElement;
                    results.push({
                        tag: parent.tagName,
                        class: parent.className?.slice(0, 80),
                        text: parent.textContent?.trim().slice(0, 100),
                        rect: parent.getBoundingClientRect()
                    });
                }
            }
            return results;
        }''')
        print(f"行情 elements: {len(market_els)}")
        for el in market_els:
            print(f"  {el['tag']}.{el['class'][:30]} -> '{el['text'][:60]}' rect={el['rect']}")
        
        # Click 行情 tab
        if market_els:
            # Click the first clickable 行情 element
            for el in market_els:
                tag = el['tag']
                cls = el['class']
                if tag in ('A', 'BUTTON', 'DIV', 'SPAN') and el['rect']['width'] > 0:
                    x = el['rect']['x'] + el['rect']['width'] / 2
                    y = el['rect']['y'] + el['rect']['height'] / 2
                    print(f"\nClicking 行情 at ({x}, {y})")
                    await page.mouse.click(x, y)
                    await asyncio.sleep(8)
                    
                    # Scroll to load more
                    for _ in range(3):
                        await page.mouse.wheel(0, 500)
                        await asyncio.sleep(2)
                    break
        
        # Save all captured API data
        with open("data/detail_apis.json", 'w', encoding='utf-8') as f:
            json.dump(all_api_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== Captured {len(all_api_data)} APIs ===")
        for api, data in all_api_data.items():
            print(f"  {api}: keys={list(data.keys())[:8]}")
        
        # Check detail API for market data
        detail = all_api_data.get('mtop.taobao.idle.pc.detail', {})
        if detail:
            print(f"\n=== Detail API keys ===")
            for k, v in detail.items():
                if isinstance(v, dict):
                    print(f"  {k}: {list(v.keys())[:8]}")
                elif isinstance(v, list):
                    print(f"  {k}: list[{len(v)}]")
                else:
                    print(f"  {k}: {str(v)[:80]}")
        
        # Check for market-specific data
        for api, data in all_api_data.items():
            data_str = json.dumps(data, ensure_ascii=False)
            if any(k in data_str for k in ['成交', 'deal', 'sold', 'trade', '行情', 'market', 'history']):
                print(f"\n[MARKET DATA FOUND] {api}")
                print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
        
        # Also get page content for 行情 section
        page_text = await page.evaluate('''() => {
            const text = document.body.innerText;
            const idx = text.indexOf('行情');
            if (idx >= 0) return text.slice(Math.max(0, idx - 100), idx + 500);
            return '行情 not found in page text';
        }''')
        print(f"\n=== Page text near 行情 ===\n{page_text}")
        
        await browser.close()

asyncio.run(main())
