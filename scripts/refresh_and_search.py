"""刷新cookie并直接调用搜索API"""
import asyncio
import json
import hashlib
import time
import urllib.parse
from playwright.async_api import async_playwright

COOKIES_FILE = "data/xianyu_cookies.json"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        # Load old cookies
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            valid = [c for c in cookies if c.get('name') and c.get('value')]
            if valid:
                await context.add_cookies(valid)
        
        page = await context.new_page()
        
        # Visit page to refresh cookies
        await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        # Get refreshed cookies
        all_cookies = await context.cookies()
        with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_cookies, f, ensure_ascii=False, indent=2)
        
        # Find _m_h5_tk
        cookie_dict = {c['name']: c['value'] for c in all_cookies if c.get('name') and c.get('value')}
        h5tk = cookie_dict.get('_m_h5_tk', '')
        token = h5tk.split('_')[0] if h5tk else ''
        print(f"New token: {token}")
        
        # Now call search API directly via page.evaluate
        result = await page.evaluate('''async () => {
            const cookies = document.cookie;
            const h5tk = cookies.split(';').find(c => c.trim().startsWith('_m_h5_tk='));
            const token = h5tk ? h5tk.split('=')[1].split('_')[0] : '';
            
            const appKey = '34839810';
            const t = Date.now().toString();
            const api = 'mtop.taobao.idlemtopsearch.pc.search';
            const data = JSON.stringify({keyword: '疾光800pro', pageNumber: 1, searchFrom: 'home'});
            
            const signStr = token + '&' + t + '&' + appKey + '&' + data;
            // Use SubtleCrypto for MD5... actually can't. Use fetch with cookies.
            
            const params = new URLSearchParams({
                jsv: '2.7.2', appKey, t, sign: '', v: '1.0',
                type: 'originaljson', accountSite: 'xianyu', dataType: 'json',
                timeout: '20000', api, sessionOption: 'AutoLoginOnly', data
            });
            
            // Try fetch
            const resp = await fetch(`https://h5api.m.goofish.com/h5/${api}/1.0/?${params}`, {
                credentials: 'include',
                headers: {'Referer': 'https://www.goofish.com/'}
            });
            const body = await resp.json();
            return {ret: body.ret, dataKeys: Object.keys(body.data || {}), resultListLen: (body.data?.resultList || []).length};
        }''')
        
        print(f"API result: {result}")
        
        # Also intercept real API calls on search page
        search_data = {}
        async def on_response(response):
            url = response.url
            if 'mtop.taobao.idlemtopsearch.pc.search/' in url and 'shade' not in url and 'activate' not in url:
                try:
                    text = await response.text()
                    try:
                        body = json.loads(text)
                    except:
                        start = text.find('{')
                        end = text.rfind('}') + 1
                        body = json.loads(text[start:end]) if start >= 0 else {}
                    search_data.update(body)
                    print(f"[INTERCEPTED] search API: ret={body.get('ret',[])}")
                except:
                    pass
        
        page.on('response', on_response)
        
        # Navigate to search page
        await page.goto("https://www.goofish.com/search?q=疾光800pro", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(8)
        
        if search_data:
            with open("data/search_api_response.json", 'w', encoding='utf-8') as f:
                json.dump(search_data, f, ensure_ascii=False, indent=2)
            
            data = search_data.get('data', {})
            rl = data.get('resultList', [])
            print(f"\nIntercepted resultList: {len(rl)}")
            if rl:
                print(f"First item: {json.dumps(rl[0], ensure_ascii=False)[:500]}")
        
        await browser.close()

import os
asyncio.run(main())
