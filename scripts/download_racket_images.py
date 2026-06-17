# -*- coding: utf-8 -*-
"""
从中羽在线装备库下载球拍产品图
"""

import requests
import json
from pathlib import Path
from loguru import logger

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent / "web-app" / "public" / "images" / "rackets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 中羽在线装备库图片映射
# 格式: 型号 -> (图片URL, 文件名)
RACKET_IMAGES = {
    "天斧88D PRO": ("https://eqimg.badmintoncn.com/202402/s_20240223103404_Wzs2M.jpg", "astrox88dpro.jpg"),
    "天斧100ZZ": ("https://eqimg.badmintoncn.com/202403/s_20240306104309_a17ap.jpg", "astrox100zz.jpg"),
    "天斧77PRO": ("https://eqimg.badmintoncn.com/202209/s_20220926110609unB8J39OMi.jpg", "astrox77pro.jpg"),
    "弓箭11PRO": ("https://eqimg.badmintoncn.com/202403/s_20240313153227_95kB4.jpg", "arc11pro.jpg"),
    "雷霆80": ("https://eqimg.badmintoncn.com/202501/s_20250101221310_WCXR2.jpg", "leiting80.jpg"),
    "战戟8000": ("https://eqimg.badmintoncn.com/202501/s_20250101221641lWVUpbyDkv.jpg", "zhanji8000.jpg"),
}

# 需要额外搜索的型号
SEARCH_NEEDED = [
    "疾光NF800PRO",
    "风刃900",
    "风刃900i",
    "神速100X",
    "龙牙之刃",
    "极速10",
]


def download_image(url: str, filename: str) -> bool:
    """下载图片"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.badmintoncn.com/',
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
    print("开始从中羽在线下载球拍产品图...")
    print(f"输出目录: {OUTPUT_DIR}")
    print()
    
    downloaded = []
    failed = []
    
    for model, (url, filename) in RACKET_IMAGES.items():
        print(f"下载: {model}...")
        if download_image(url, filename):
            downloaded.append(model)
        else:
            failed.append(model)
    
    print()
    print(f"下载完成: {len(downloaded)} 成功, {len(failed)} 失败")
    
    if failed:
        print(f"失败型号: {', '.join(failed)}")
    
    # 更新图片映射配置
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
    for model, (url, filename) in RACKET_IMAGES.items():
        config[model] = f"/images/rackets/{filename}"
    
    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"更新配置: {config_path}")


if __name__ == "__main__":
    main()
