"""专门拦截闲鱼行情(market)API"""
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
        
        market_apis = []
        all_apis = []
        
        async def on_response(response):
            url = response.url
            if 'h5api.m.goofish.com' not in url:
                return
            try:
                ct = response.headers.get('content-type', '')
                if 'json' not in ct and 'javascript' not in ct:
                    return
                text = await response.text()
                body = None
                try:
                    body = json.loads(text)
                except:
                    start = text.find('{')
                    end = text.rfind('}') + 1
                    if start >= 0 and end > start:
                        body = json.loads(text[start:end])
                
                if not body:
                    return
                
                api_name = url.split('/h5/')[1].split('/')[0] if '/h5/' in url else url
                
                record = {
                    'api': api_name,
                    'url': url[:300],
                    'status': response.status,
                    'ret': body.get('ret', []),
                    'data_keys': list(body.get('data', {}).keys())[:10] if isinstance(body.get('data'), dict) else [],
                    'data_preview': str(body.get('data', {}))[:300]
                }
                all_apis.append(record)
                
                # Look for market/行情 related APIs
                data_str = json.dumps(body, ensure_ascii=False)
                if any(k in data_str for k in ['行情', 'market', 'dealPrice', 'soldTime', '成交', 'traded']):
                    market_apis.append(record)
                    print(f"[MARKET?] {api_name}")
                
                print(f"  [{response.status}] {api_name} -> ret={body.get('ret', [])[:1]}")
            except:
                pass
        
        page.on('response', on_response)
        
        # Search for a racket and click into detail page
        print("=== Searching for NF800PRO ===")
        await page.goto("https://www.goofish.com/search?q=疾光800pro", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        # Click first item
        items = page.locator('a[href*="/item/"]')
        count = await items.count()
        print(f"Found {count} item links")
        
        if count > 0:
            href = await items.first.get_attribute('href')
            print(f"Clicking: {href}")
            await items.first.click()
            await asyncio.sleep(5)
            
            # Look for 行情 tab
            print("\n=== Looking for 行情 tab ===")
            market_tab = page.locator('text=行情')
            tab_count = await market_tab.count()
            print(f"Found {tab_count} '行情' elements")
            
            if tab_count > 0:
                for i in range(tab_count):
                    el = market_tab.nth(i)
                    text = await el.text_content()
                    tag = await el.evaluate('el => el.tagName')
                    print(f"  Tab {i}: {tag} -> '{text}'")
                
                print("\nClicking 行情 tab...")
                await market_tab.first.click()
                await asyncio.sleep(8)
                
                # Scroll to load more
                for _ in range(3):
                    await page.mouse.wheel(0, 500)
                    await asyncio.sleep(2)
        
        print(f"\n=== Summary ===")
        print(f"Total APIs: {len(all_apis)}")
        print(f"Market APIs: {len(market_apis)}")
        
        if market_apis:
            print("\n=== Market API Details ===")
            for rec in market_apis:
                print(json.dumps(rec, ensure_ascii=False, indent=2))
        
        # Save all APIs
        with open("data/market_apis.json", 'w', encoding='utf-8') as f:
            json.dump({'all': all_apis, 'market': market_apis}, f, ensure_ascii=False, indent=2)
        print("\nSaved to data/market_apis.json")
        
        await browser.close()

asyncio.run(main())
