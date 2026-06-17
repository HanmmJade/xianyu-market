# -*- coding: utf-8 -*-
"""
下载最后3个球拍图片
"""

import requests
import json
from pathlib import Path
from loguru import logger

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent / "web-app" / "public" / "images" / "rackets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 最后3个型号的图片
FINAL_IMAGES = {
    "疾光NF800PRO": ("https://cdn.shopify.com/s/files/1/2183/6715/files/all_nf-800p_269-1.png?v=1723675365&width=1024", "nf800pro.png"),
    "风刃900i": ("https://eqimg.badmintoncn.com/202501/s_20250101102500_ZgXHy.jpg", "fengren900i.jpg"),
    "极速10": ("https://eqimg.badmintoncn.com/202403/s_20240410115203_ev8YS.jpg", "jisu10.jpg"),
}


def download_image(url: str, filename: str) -> bool:
    """下载图片"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.badmintonavenue.com/',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        output_path = OUTPUT_DIR / filename
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"下载成功: {filename} ({len(response.content)} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"下载失败 {filename}: {e}")
        return False


def main():
    """主函数"""
    print("下载最后3个球拍图片...")
    
    downloaded = []
    for model, (url, filename) in FINAL_IMAGES.items():
        print(f"下载: {model}...")
        if download_image(url, filename):
            downloaded.append(model)
    
    print(f"\n下载完成: {len(downloaded)} 成功")
    
    # 更新配置
    update_image_config()


def update_image_config():
    """更新图片映射配置"""
    config_path = Path(__file__).parent.parent / "config" / "racket_images.json"
    
    # 读取现有配置
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {}
    
    # 更新配置
    for model, (url, filename) in FINAL_IMAGES.items():
        config[model] = f"/images/rackets/{filename}"
    
    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"更新配置: {config_path}")


if __name__ == "__main__":
    main()
