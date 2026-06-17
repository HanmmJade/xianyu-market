"""用Playwright抓取闲鱼详情页行情数据"""
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
        
        # Capture all API responses
        api_responses = []
        async def on_response(response):
            url = response.url
            if 'h5api.m.goofish.com' in url:
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
                        api_name = url.split('/h5/')[1].split('/')[0] if '/h5/' in url else 'unknown'
                        api_responses.append({'api': api_name, 'body': body, 'url': url[:200]})
                except:
                    pass
        
        page.on('response', on_response)
        
        # Search for NF800PRO
        print("=== Search ===")
        await page.goto("https://www.goofish.com/search?q=疾光800pro", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(5)
        
        # Find item links - try multiple selectors
        links = await page.evaluate('''() => {
            const results = [];
            // Try all links
            document.querySelectorAll('a').forEach(a => {
                const href = a.href || '';
                if (href.includes('/item/') || href.includes('item?id=')) {
                    results.push({href, text: a.textContent?.trim().slice(0, 50)});
                }
            });
            // Also try data attributes
            document.querySelectorAll('[data-id], [data-item-id]').forEach(el => {
                results.push({href: el.getAttribute('data-id') || el.getAttribute('data-item-id'), text: el.textContent?.trim().slice(0, 50), type: 'data-attr'});
            });
            return results;
        }''')
        print(f"Found {len(links)} item links")
        for l in links[:5]:
            print(f"  {l}")
        
        # Get page content to find items
        html_snippet = await page.evaluate('''() => {
            // Look for item cards
            const cards = document.querySelectorAll('[class*="item"], [class*="card"], [class*="feeds"]');
            return Array.from(cards).slice(0, 3).map(c => ({
                tag: c.tagName,
                class: c.className?.slice(0, 80),
                text: c.textContent?.trim().slice(0, 100)
            }));
        }''')
        print(f"\nCards: {len(html_snippet)}")
        for c in html_snippet:
            print(f"  {c}")
        
        # Try clicking on any item
        if links:
            first_href = links[0].get('href', '')
            if first_href and 'http' not in first_href:
                first_href = f"https://www.goofish.com{first_href}"
            print(f"\n=== Navigating to: {first_href} ===")
            await page.goto(first_href, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)
            
            # Look for 行情 on detail page
            content = await page.content()
            has_market = '行情' in content
            print(f"Has 行情: {has_market}")
            
            # Get page text
            page_text = await page.evaluate('() => document.body.innerText.slice(0, 2000)')
            print(f"\nPage text:\n{page_text[:1000]}")
        
        # Print all captured APIs
        print(f"\n=== All {len(api_responses)} API calls ===")
        for r in api_responses:
            ret = r['body'].get('ret', [])
            data = r['body'].get('data', {})
            keys = list(data.keys())[:5] if isinstance(data, dict) else []
            print(f"  {r['api']}: ret={ret[:1]}, keys={keys}")
        
        await browser.close()

asyncio.run(main())
