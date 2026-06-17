"""拦截闲鱼网页版API请求，找出行情数据接口"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

COOKIES_FILE = "data/xianyu_cookies.json"
OUTPUT_FILE = "data/intercepted_apis.jsonl"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        # Load cookies
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            valid = [c for c in cookies if c.get('name') and c.get('value')]
            if valid:
                await context.add_cookies(valid)
                print(f"Loaded {len(valid)} cookies")
        
        page = await context.new_page()
        
        # Intercept all API responses
        intercepted = []
        async def on_response(response):
            url = response.url
            # Filter for Xianyu API calls
            if any(k in url for k in ['mtop', 'h5api', 'acs.m', 'goofish.com/api', 'detail']):
                try:
                    ct = response.headers.get('content-type', '')
                    if 'json' in ct or 'javascript' in ct:
                        text = await response.text()
                        # Try parse JSONP
                        body = None
                        try:
                            body = json.loads(text)
                        except:
                            start = text.find('{')
                            end = text.rfind('}') + 1
                            if start >= 0 and end > start:
                                body = json.loads(text[start:end])
                        
                        record = {
                            'url': url[:200],
                            'status': response.status,
                            'content_type': ct,
                            'body_preview': str(body)[:500] if body else text[:500]
                        }
                        intercepted.append(record)
                        print(f"[API] {url[:100]} -> {response.status}")
                        
                        # Save full response
                        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                            f.write(json.dumps({
                                'url': url,
                                'status': response.status,
                                'body': body if body else text[:2000]
                            }, ensure_ascii=False) + '\n')
                except Exception as e:
                    pass
        
        page.on('response', on_response)
        
        # Visit a known item page with market data
        # NF800PRO example
        print("\n=== Visiting NF800PRO detail page ===")
        await page.goto("https://www.goofish.com/item?id=907070044498", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        # Look for "行情" tab and click it
        market_tab = page.locator('text=行情').first
        if await market_tab.count() > 0:
            print("Found 行情 tab, clicking...")
            await market_tab.click()
            await asyncio.sleep(5)
        else:
            print("No 行情 tab found, scrolling down...")
            for _ in range(3):
                await page.mouse.wheel(0, 500)
                await asyncio.sleep(1)
        
        # Also try searching
        print("\n=== Searching for NF800PRO ===")
        await page.goto("https://www.goofish.com/search?q=疾光800pro", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        # Scroll to trigger more API calls
        for _ in range(3):
            await page.mouse.wheel(0, 800)
            await asyncio.sleep(1)
        
        print(f"\n=== Results: {len(intercepted)} API calls intercepted ===")
        for i, rec in enumerate(intercepted):
            print(f"\n--- Call {i+1} ---")
            print(f"URL: {rec['url']}")
            print(f"Status: {rec['status']}")
            print(f"Preview: {rec['body_preview'][:300]}")
        
        await browser.close()

asyncio.run(main())
