"""
闲鱼PC版 + 移动UA探测 — 检查筛选选项和成交API
"""
import asyncio, json, re
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT = Path(r"D:\AI共享文件夹\xianyu-market\data")
captured = []

async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    ctx = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36"
    )

    ck = OUTPUT / "xianyu_cookies.json"
    if ck.exists():
        with open(ck) as f:
            cookies = json.load(f)
        if cookies:
            await ctx.add_cookies(cookies)
            print(f"[√] Cookie: {len(cookies)}条")

    page = await ctx.new_page()
    await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")

    async def on_resp(resp):
        url = resp.url
        if "h5api" not in url:
            return
        api = re.search(r'mtop\.[a-zA-Z0-9._]+', url)
        api_name = api.group(0) if api else "unknown"
        try:
            body = await resp.text()
            kws = []
            for kw in ["soldPrice","sold","deal","market","recentSold","soldCount",
                        "soldTime","wantCount","成交","已售","history","price"]:
                if kw.lower() in body.lower():
                    kws.append(kw)
            captured.append({"api": api_name, "kws": kws, "len": len(body),
                             "preview": body[:1000] if kws else ""})
            if kws:
                print(f"  [{resp.status}] {api_name} ★{kws}")
        except:
            pass

    page.on("response", on_resp)

    # Open search page
    print("\n[1] Opening goofish.com search...")
    await page.goto("https://www.goofish.com/search?q=天斧88D PRO", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(6)

    # Get all visible filter/sort options
    print("\n[2] Filter options on search results page:")
    filters = await page.evaluate("""() => {
        const results = [];
        // Look for all clickable elements that might be filters
        const clickables = document.querySelectorAll('div, span, a, button, li');
        const seen = new Set();
        for (const el of clickables) {
            const text = el.innerText?.trim();
            if (!text || text.length > 30 || text.length < 1) continue;
            // Check if it looks like a filter/sort option
            if (['综合','最新','价格','销量','新降价','新发布','已售','已卖出','成交',
                 '验货宝','验号担保','包邮','超赞','鱼小铺','个人闲置','筛选',
                 '想要','浏览','收藏','区域','信用'].some(kw => text === kw || text.startsWith(kw))) {
                const key = text;
                if (seen.has(key)) continue;
                seen.add(key);
                results.push({
                    text: text,
                    tag: el.tagName,
                    class: el.className?.substring(0, 80),
                    rect: el.getBoundingClientRect(),
                });
            }
        }
        return results;
    }""")

    for f in filters:
        print(f"  [{f['tag']}] '{f['text']}' | class={f['class'][:50]} | pos=({int(f['rect']['x'])},{int(f['rect']['y'])})")

    # Also get the full page text around filters
    print("\n[3] Page text (filter area):")
    text = await page.evaluate("() => document.body.innerText")
    for line in text.split('\n'):
        line = line.strip()
        if any(kw in line for kw in ['综合','最新','价格','销量','已售','成交','筛选','验货','区域','个人闲置']):
            print(f"  {line}")

    # Try clicking "销量" or "已售" and see what happens
    print("\n[4] Trying to click filter options...")
    for keyword in ['销量', '已售', '已卖出', '成交', '最新', '价格']:
        btn = await page.query_selector(f'text="{keyword}"')
        if btn:
            print(f"  Found '{keyword}' - clicking...")
            await btn.click()
            await asyncio.sleep(3)
            # Check URL change
            print(f"  URL after click: {page.url}")
            # Check for new API calls
            print(f"  Total APIs captured: {len(captured)}")
            # Go back
            await page.goto("https://www.goofish.com/search?q=天斧88D PRO", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3)

    # Summary
    print(f"\n{'='*60}")
    print(f"  Total APIs: {len(captured)}")
    price_apis = [c for c in captured if c['kws']]
    print(f"  Price/sold related: {len(price_apis)}")
    for c in price_apis:
        print(f"    {c['api']} -> {c['kws']}")
    
    # Check specifically for sold/transaction APIs
    sold_apis = [c for c in captured if any(k in c['kws'] for k in ['sold','成交','已售','soldTime','soldCount'])]
    print(f"\n  SOLD/TRANSACTION APIs: {len(sold_apis)}")
    for c in sold_apis:
        print(f"    {c['api']} -> {c['kws']}")
        if c['preview']:
            # Find sold-related data in preview
            for line in c['preview'].split('"'):
                if any(k in line.lower() for k in ['sold','成交']):
                    print(f"      data: {line[:150]}")
    print(f"{'='*60}")

    await browser.close()
    await pw.stop()

asyncio.run(main())
