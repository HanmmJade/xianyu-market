"""提取搜索API的resultList结构"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

COOKIES_FILE = "data/xianyu_cookies.json"

async def main():
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
        
        search_result = {}
        
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
                    if body:
                        search_result.update(body)
                        print(f"[CAPTURED] search API response")
                except:
                    pass
        
        page.on('response', on_response)
        
        await page.goto("https://www.goofish.com/search?q=疾光800pro", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(8)
        
        # Save full result
        with open("data/search_full_response.json", 'w', encoding='utf-8') as f:
            json.dump(search_result, f, ensure_ascii=False, indent=2)
        
        # Analyze resultList
        data = search_result.get('data', {})
        result_list = data.get('resultList', [])
        print(f"\nresultList count: {len(result_list)}")
        
        if result_list:
            # Print first item structure
            first = result_list[0]
            print(f"\nFirst item keys: {list(first.keys())}")
            print(f"\nFirst item full:")
            print(json.dumps(first, ensure_ascii=False, indent=2)[:3000])
        
        await browser.close()

asyncio.run(main())
