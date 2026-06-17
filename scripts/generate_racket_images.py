# -*- coding: utf-8 -*-
"""
生成球拍产品占位图
使用品牌配色和型号名称，生成专业的占位图片
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent / "web-app" / "public" / "images" / "rackets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 品牌配色方案
BRAND_COLORS = {
    "YONEX": {
        "primary": (220, 38, 38),      # 红色
        "secondary": (255, 255, 255),   # 白色
        "accent": (30, 30, 30),         # 黑色
        "bg_start": (255, 245, 245),    # 浅红
        "bg_end": (255, 235, 235),      # 更浅红
    },
    "李宁": {
        "primary": (37, 99, 235),       # 蓝色
        "secondary": (255, 255, 255),   # 白色
        "accent": (220, 38, 38),        # 红色
        "bg_start": (235, 245, 255),    # 浅蓝
        "bg_end": (225, 235, 255),      # 更浅蓝
    },
    "VICTOR": {
        "primary": (22, 163, 74),       # 绿色
        "secondary": (255, 255, 255),   # 白色
        "accent": (30, 30, 30),         # 黑色
        "bg_start": (235, 255, 245),    # 浅绿
        "bg_end": (225, 255, 235),      # 更浅绿
    },
}

# 型号配置
RACKET_MODELS = [
    {"model": "疾光NF800PRO", "brand": "YONEX", "series": "NANOFLARE", "filename": "nf800pro.png"},
    {"model": "天斧77PRO", "brand": "YONEX", "series": "ASTROX", "filename": "astrox77pro.png"},
    {"model": "天斧88D PRO", "brand": "YONEX", "series": "ASTROX", "filename": "astrox88dpro.png"},
    {"model": "弓箭11PRO", "brand": "YONEX", "series": "ARCSABER", "filename": "arc11pro.png"},
    {"model": "天斧100ZZ", "brand": "YONEX", "series": "ASTROX", "filename": "astrox100zz.png"},
    {"model": "雷霆80", "brand": "李宁", "series": "雷霆", "filename": "leiting80.png"},
    {"model": "战戟8000", "brand": "李宁", "series": "战戟", "filename": "zhanji8000.png"},
    {"model": "风刃900", "brand": "李宁", "series": "风刃", "filename": "fengren900.png"},
    {"model": "风刃900i", "brand": "李宁", "series": "风刃", "filename": "fengren900i.png"},
    {"model": "神速100X", "brand": "VICTOR", "series": "神速", "filename": "shensu100x.png"},
    {"model": "龙牙之刃", "brand": "VICTOR", "series": "龙牙", "filename": "longya.png"},
    {"model": "极速10", "brand": "VICTOR", "series": "极速", "filename": "jisu10.png"},
    {"model": "88dpro", "brand": "YONEX", "series": "ASTROX", "filename": "astrox88dpro_v2.png"},
]


def draw_racket_silhouette(draw, cx, cy, size, color):
    """绘制球拍剪影"""
    # 球拍头部（椭圆）
    head_width = size * 0.35
    head_height = size * 0.45
    head_top = cy - size * 0.3
    head_bottom = head_top + head_height
    
    # 绘制椭圆头部
    draw.ellipse(
        [cx - head_width, head_top, cx + head_width, head_bottom],
        outline=color, width=3
    )
    
    # 绘制弦线（横线）
    for i in range(5):
        y = head_top + head_height * (i + 1) / 6
        x_offset = head_width * math.sin(math.acos((y - head_top - head_height/2) / (head_height/2)))
        x_offset = min(x_offset, head_width * 0.9)
        draw.line([(cx - x_offset, y), (cx + x_offset, y)], fill=color, width=1)
    
    # 绘制弦线（竖线）
    for i in range(5):
        x = cx - head_width + head_width * 2 * (i + 1) / 6
        y_offset = head_height/2 * math.sin(math.acos((x - cx) / head_width))
        y_top = cy - size * 0.3 + head_height/2 - y_offset
        y_bottom = cy - size * 0.3 + head_height/2 + y_offset
        draw.line([(x, y_top), (x, y_bottom)], fill=color, width=1)
    
    # 绘制杆
    shaft_top = head_bottom - 5
    shaft_bottom = cy + size * 0.35
    shaft_width = size * 0.03
    
    draw.rectangle(
        [cx - shaft_width, shaft_top, cx + shaft_width, shaft_bottom],
        fill=color
    )
    
    # 绘制握把
    grip_top = shaft_bottom - 5
    grip_bottom = grip_top + size * 0.15
    grip_width = size * 0.05
    
    draw.rectangle(
        [cx - grip_width, grip_top, cx + grip_width, grip_bottom],
        fill=color
    )
    
    # 绘制握把底盖
    draw.rectangle(
        [cx - grip_width - 2, grip_bottom, cx + grip_width + 2, grip_bottom + 5],
        fill=color
    )


def generate_gradient(width, height, start_color, end_color):
    """生成渐变背景"""
    img = Image.new('RGB', (width, height))
    pixels = img.load()
    
    for y in range(height):
        ratio = y / height
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
        
        for x in range(width):
            pixels[x, y] = (r, g, b)
    
    return img


def get_font(size):
    """获取字体（尝试多种字体）"""
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",     # 黑体
        "C:/Windows/Fonts/simsun.ttc",     # 宋体
        "C:/Windows/Fonts/arial.ttf",      # Arial
    ]
    
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    
    return ImageFont.load_default()


def generate_racket_image(model_info):
    """生成单张球拍图片"""
    width, height = 800, 600
    brand = model_info["brand"]
    colors = BRAND_COLORS[brand]
    
    # 创建渐变背景
    img = generate_gradient(width, height, colors["bg_start"], colors["bg_end"])
    draw = ImageDraw.Draw(img)
    
    # 绘制装饰性边框
    border_margin = 20
    draw.rectangle(
        [border_margin, border_margin, width - border_margin, height - border_margin],
        outline=colors["primary"], width=2
    )
    
    # 绘制品牌标识区域
    brand_bg_height = 60
    draw.rectangle(
        [border_margin, border_margin, width - border_margin, border_margin + brand_bg_height],
        fill=colors["primary"]
    )
    
    # 绘制品牌名称
    brand_font = get_font(28)
    brand_text = brand
    brand_bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    brand_width = brand_bbox[2] - brand_bbox[0]
    draw.text(
        ((width - brand_width) // 2, border_margin + 15),
        brand_text, fill=colors["secondary"], font=brand_font
    )
    
    # 绘制球拍剪影
    racket_center_x = width // 2
    racket_center_y = height // 2 + 20
    racket_size = min(width, height) * 0.6
    
    draw_racket_silhouette(draw, racket_center_x, racket_center_y, racket_size, colors["primary"])
    
    # 绘制系列名称
    series_font = get_font(20)
    series_text = model_info["series"]
    series_bbox = draw.textbbox((0, 0), series_text, font=series_font)
    series_width = series_bbox[2] - series_bbox[0]
    draw.text(
        ((width - series_width) // 2, height - 120),
        series_text, fill=colors["accent"], font=series_font
    )
    
    # 绘制型号名称
    model_font = get_font(36)
    model_text = model_info["model"]
    model_bbox = draw.textbbox((0, 0), model_text, font=model_font)
    model_width = model_bbox[2] - model_bbox[0]
    draw.text(
        ((width - model_width) // 2, height - 80),
        model_text, fill=colors["primary"], font=model_font
    )
    
    # 保存图片
    output_path = OUTPUT_DIR / model_info["filename"]
    img.save(output_path, "PNG", quality=95)
    print(f"生成: {output_path.name}")
    
    return output_path


def main():
    """主函数"""
    print("开始生成球拍产品图...")
    print(f"输出目录: {OUTPUT_DIR}")
    print()
    
    generated = []
    for model_info in RACKET_MODELS:
        try:
            path = generate_racket_image(model_info)
            generated.append(path)
        except Exception as e:
            print(f"生成失败 {model_info['model']}: {e}")
    
    print()
    print(f"完成! 共生成 {len(generated)} 张图片")


if __name__ == "__main__":
    main()
