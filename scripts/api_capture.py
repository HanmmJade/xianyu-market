"""mitmdump script to capture Xianyu API responses"""
import json
import os
from datetime import datetime
from mitmproxy import http

CAPTURE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'captured_api.jsonl')

def response(flow: http.HTTPFlow):
    """Capture Xianyu API responses"""
    url = flow.request.pretty_url
    
    # Filter for Xianyu/Goofish API endpoints
    if not any(domain in url for domain in [
        'goofish.com', 'taobao.com', 'alicdn.com',
        'h5api.m.goofish.com', 'acs.m.taobao.com',
        'guide-acs.m.taobao.com', 'acs.m.goofish.com',
        'h5.m.goofish.com'
    ]):
        return
    
    # Skip static assets
    if any(ext in url for ext in ['.js', '.css', '.png', '.jpg', '.gif', '.ico', '.woff']):
        return
    
    # Try to get response body
    content_type = flow.response.headers.get('content-type', '')
    body = None
    
    if 'json' in content_type or 'javascript' in content_type:
        try:
            text = flow.response.get_text()
            # Some responses are JSONP: callback({...})
            if text.startswith('(') or text.startswith('mtopjsonp'):
                # Extract JSON from JSONP
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    body = json.loads(text[start:end])
            else:
                body = json.loads(text)
        except:
            pass
    
    if body:
        record = {
            'timestamp': datetime.now().isoformat(),
            'url': url,
            'method': flow.request.method,
            'status': flow.response.status_code,
            'content_type': content_type,
            'body': body
        }
        
        os.makedirs(os.path.dirname(CAPTURE_FILE), exist_ok=True)
        with open(CAPTURE_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        # Print summary
        if isinstance(body, dict):
            keys = list(body.keys())[:5]
            print(f"[CAPTURED] {url[:80]} -> keys: {keys}")
        else:
            print(f"[CAPTURED] {url[:80]} -> {type(body).__name__}")
