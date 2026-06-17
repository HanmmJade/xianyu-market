# -*- coding: utf-8 -*-
"""
从中羽在线装备库批量获取球拍图片
"""

import requests
import re
import json
import time
from pathlib import Path
from loguru import logger

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent / "web-app" / "public" / "images" / "rackets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 加载产品库
RACKET_DB_PATH = Path(__file__).parent.parent / "config" / "racket_database.json"

with open(RACKET_DB_PATH, 'r', encoding='utf-8') as f:
    RACKET_DB = json.load(f)


def solve_verification(session):
    """解决中羽在线的验证问题"""
    # 访问主页获取验证问题
    resp = session.get('https://www.badmintoncn.com/cbo_eq/')
    
    if '验证' in resp.text or '֤' in resp.text:
        # 解析问题
        match = re.search(r'(\d+)\+(\d+)=', resp.text)
        if match:
            a, b = int(match.group(1)), int(match.group(2))
            answer = a + b
            
            # 提取ak值
            ak_match = re.search(r'name="ak"\s+value="(\d+)"', resp.text)
            ak = ak_match.group(1) if ak_match else '2'
            
            # 提交答案
            data = {'a': str(answer), 'ak': ak}
            resp2 = session.post('https://www.badmintoncn.com/cbo_function.php?action=clickcookie', data=data)
            
            if resp2.status_code == 200:
                logger.info(f"验证成功: {a}+{b}={answer}")
                return True
    
    return False


def search_equipment(session, keyword):
    """搜索装备"""
    url = f'https://www.badmintoncn.com/cbo_eq/search.php?keyword={keyword}'
    resp = session.get(url)
    
    # 提取装备页面链接和图片
    equip_links = re.findall(r'view\.php\?eid=(\d+)', resp.text)
    img_urls = re.findall(r'eqimg\.badmintoncn\.com/\d+/s_\d+_[a-zA-Z0-9]+\.jpg', resp.text)
    
    return equip_links, img_urls


def get_equipment_images(session, eid):
    """获取装备页面的图片"""
    url = f'https://www.badmintoncn.com/cbo_eq/view.php?eid={eid}'
    resp = session.get(url)
    
    # 提取图片URL
    img_urls = re.findall(r'eqimg\.badmintoncn\.com/\d+/[^"\']+\.(?:jpg|png)', resp.text)
    
    return img_urls


def download_image(session, url, filename):
    """下载图片"""
    try:
        if not url.startswith('http'):
            url = 'https://' + url
        
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        
        output_path = OUTPUT_DIR / filename
        with open(output_path, 'wb') as f:
            f.write(resp.content)
        
        logger.info(f"下载成功: {filename} ({len(resp.content)} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"下载失败 {filename}: {e}")
        return False


def main():
    """主函数"""
    print("从中羽在线装备库批量获取球拍图片...")
    print(f"产品库: {len(RACKET_DB)} 个型号")
    print()
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    
    # 解决验证
    solve_verification(session)
    
    # 图片映射
    image_map = {}
    
    # 遍历产品库
    for model_name, info in RACKET_DB.items():
        brand = info.get('brand', '')
        aliases = info.get('aliases', [])
        
        # 用第一个别名搜索
        search_keyword = aliases[0] if aliases else model_name
        
        print(f"搜索: {model_name} ({search_keyword})...")
        
        try:
            equip_links, img_urls = search_equipment(session, search_keyword)
            
            if img_urls:
                # 下载第一张图片
                img_url = img_urls[0]
                ext = 'jpg' if 'jpg' in img_url else 'png'
                filename = f"{model_name.replace(' ', '_').lower()}.{ext}"
                
                if download_image(session, img_url, filename):
                    image_map[model_name] = f"/images/rackets/{filename}"
            
            time.sleep(1)  # 避免请求过快
            
        except Exception as e:
            logger.error(f"搜索失败 {model_name}: {e}")
    
    # 保存图片映射
    config_path = Path(__file__).parent.parent / "config" / "racket_images.json"
    
    # 读取现有配置
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    else:
        existing = {}
    
    # 合并
    existing.update(image_map)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成! 下载了 {len(image_map)} 张图片")
    print(f"图片映射已保存: {config_path}")


if __name__ == "__main__":
    main()
