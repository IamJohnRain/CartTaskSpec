#!/usr/bin/env python3
"""分析 references/media 中的 PNG/SVG 并生成完整素材清单。"""
from __future__ import annotations

import argparse
import colorsys
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image


IMAGE_EXTENSIONS = {".png", ".svg"}
BACKGROUND_KEYWORDS = ("background", "backgroud", "wallpaper", "backdrop")
OVERLAY_KEYWORDS = ("foreground", "watermark", "overlay")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="分析 PNG/SVG 的尺寸、主色和透明度，生成 A2UI 素材清单。",
    )
    parser.add_argument(
        "-i", "--input", type=Path, default=Path("references/media"),
        help="素材目录，默认 references/media。",
    )
    parser.add_argument(
        "-o", "--output", type=Path,
        default=Path("references/media/media_manifest.json"),
        help="清单输出路径。",
    )
    return parser.parse_args()


def hex_color(red: int, green: int, blue: int) -> str:
    return f"#{red:02X}{green:02X}{blue:02X}"


def luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        channel = value / 255
        channels.append(channel / 12.92 if channel <= 0.04045
                        else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def tone_name(rgb: tuple[int, int, int], saturation: float) -> str:
    red, green, blue = rgb
    lightness = max(rgb) / 255
    if lightness < 0.18:
        return "深色/近黑"
    if min(rgb) > 220 and saturation < 0.12:
        return "浅色/近白"
    if saturation < 0.12:
        return "中性灰"
    hue = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)[0] * 360
    if hue < 15 or hue >= 345:
        family = "红色"
    elif hue < 45:
        family = "橙色"
    elif hue < 70:
        family = "黄色"
    elif hue < 165:
        family = "绿色"
    elif hue < 200:
        family = "青色"
    elif hue < 255:
        family = "蓝色"
    elif hue < 290:
        family = "紫色"
    elif hue < 345:
        family = "洋红"
    else:
        family = "彩色"
    return ("浅" if lightness > 0.78 else "深" if lightness < 0.42 else "中等") + family


def recommend_background(
    average_rgb: tuple[int, int, int], saturation: float,
) -> dict[str, Any]:
    value = luminance(average_rgb)
    if value < 0.28:
        colors = ["#FFFFFF", "#F5F5F5", "#FFF7E8"]
        reason = "素材主体偏深，推荐不透明浅色或暖白背景以保证轮廓对比。"
    elif value > 0.72:
        colors = ["#1F1F1F", "#263238", "#24324A"]
        reason = "素材主体偏浅，推荐深色中性背景以避免融入底色。"
    elif saturation > 0.35:
        colors = ["#FFFFFF", "#F5F7FA", "#1F2937"]
        reason = "素材为中高饱和彩色，优先使用低干扰中性背景。"
    else:
        colors = ["#FFFFFF", "#F2F3F5", "#202124"]
        reason = "素材主体为中性中间调，按卡片主题选择纯净浅色或深色背景。"
    return {"colors": colors, "reason": reason}


def recommended_use(path: Path, width: int, height: int,
                    coverage: float | None) -> dict[str, str]:
    stem = path.stem.lower()
    if any(keyword in stem for keyword in BACKGROUND_KEYWORDS):
        return {
            "role": "background",
            "reason": "文件名明确指向背景素材，适合作为低层视觉表面。",
        }
    if any(keyword in stem for keyword in OVERLAY_KEYWORDS):
        return {
            "role": "decorative_overlay",
            "reason": "文件名指向前景/水印，适合作为弱装饰层，不承担主要信息。",
        }
    if width >= 512 and height >= 512 and coverage is not None and coverage > 0.7:
        return {
            "role": "background",
            "reason": "高分辨率且有效像素覆盖率高，更适合作为背景或主媒体。",
        }
    return {
        "role": "logo_or_icon",
        "reason": "透明图形或矢量轮廓适合作为 Logo、语义图标或视觉锚点。",
    }


def png_pixels(image: Image.Image) -> tuple[list[tuple[int, int, int]], float, list[int] | None]:
    rgba = image.convert("RGBA")
    rgba.thumbnail((160, 160))
    visible: list[tuple[int, int, int]] = []
    alpha_count = 0
    for red, green, blue, alpha in rgba.getdata():
        if alpha <= 24:
            continue
        alpha_count += 1
        visible.append((red, green, blue))
    coverage = alpha_count / max(1, rgba.width * rgba.height)
    bbox = image.convert("RGBA").getchannel("A").getbbox()
    return visible, coverage, list(bbox) if bbox else None


def color_summary(pixels: list[tuple[int, int, int]]) -> dict[str, Any]:
    if not pixels:
        return {
            "average": None,
            "dominant": [],
            "tone": "完全透明或无法提取",
            "saturation": 0.0,
            "recommended_background": {
                "colors": ["#FFFFFF", "#1F1F1F"],
                "reason": "未提取到可见像素，需要结合实际渲染人工确认。",
            },
        }
    average = tuple(round(sum(pixel[index] for pixel in pixels) / len(pixels))
                    for index in range(3))
    quantized = Counter(
        tuple((channel // 32) * 32 + 16 for channel in pixel)
        for pixel in pixels
    )
    dominant = [
        {"color": hex_color(*rgb), "share": round(count / len(pixels), 4)}
        for rgb, count in quantized.most_common(4)
    ]
    saturation = colorsys.rgb_to_hsv(*(value / 255 for value in average))[1]
    return {
        "average": hex_color(*average),
        "dominant": dominant,
        "tone": tone_name(average, saturation),
        "saturation": round(saturation, 4),
        "recommended_background": recommend_background(average, saturation),
    }


def analyze_png(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        width, height = image.size
        pixels, coverage, bbox = png_pixels(image)
        colors = color_summary(pixels)
        return {
            "format": "png",
            "resolution": {"width_px": width, "height_px": height},
            "aspect_ratio": round(width / height, 4) if height else None,
            "alpha": "A" in image.getbands(),
            "content_bbox_px": bbox,
            "visible_coverage": round(coverage, 4),
            "colors": colors,
            "recommended_use": recommended_use(path, width, height, coverage),
        }


def parse_number(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*([0-9.]+)", value)
    return float(match.group(1)) if match else None


def parse_svg_color(value: str) -> tuple[int, int, int] | None:
    value = value.strip().lower()
    if value in {"none", "transparent", "currentcolor"}:
        return None
    if value.startswith("#"):
        raw = value[1:]
        if len(raw) == 3:
            raw = "".join(character * 2 for character in raw)
        if len(raw) >= 6:
            try:
                return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))
            except ValueError:
                return None
    numbers = re.findall(r"[0-9.]+", value)
    if value.startswith("rgb") and len(numbers) >= 3:
        return tuple(max(0, min(255, round(float(number)))) for number in numbers[:3])
    named = {"black": (0, 0, 0), "white": (255, 255, 255),
             "red": (255, 0, 0), "blue": (0, 0, 255), "green": (0, 128, 0)}
    return named.get(value)


def analyze_svg(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    width = parse_number(root.get("width"))
    height = parse_number(root.get("height"))
    view_box = root.get("viewBox") or root.get("viewbox")
    view_values = [float(value) for value in re.findall(r"-?[0-9.]+", view_box or "")]
    if (width is None or height is None) and len(view_values) == 4:
        width = width or view_values[2]
        height = height or view_values[3]
    colors: list[tuple[int, int, int]] = []
    for element in root.iter():
        candidates = [element.get("fill"), element.get("stroke")]
        style = element.get("style") or ""
        candidates.extend(re.findall(r"(?:fill|stroke)\s*:\s*([^;]+)", style))
        for candidate in candidates:
            if not candidate:
                continue
            parsed = parse_svg_color(candidate)
            if parsed is not None:
                colors.append(parsed)
    if not colors:
        colors = [(0, 0, 0)]
    color_data = color_summary(colors)
    vector_width = round(width or 0)
    vector_height = round(height or 0)
    return {
        "format": "svg",
        "resolution": {
            "type": "vector",
            "intrinsic_width": width,
            "intrinsic_height": height,
            "view_box": view_values if view_values else None,
        },
        "aspect_ratio": round(width / height, 4) if width and height else None,
        "alpha": True,
        "content_bbox_px": None,
        "visible_coverage": None,
        "colors": color_data,
        "recommended_use": recommended_use(
            path, vector_width, vector_height, None
        ),
    }


def analyze_asset(path: Path, root: Path) -> dict[str, Any]:
    analysis = analyze_png(path) if path.suffix.lower() == ".png" else analyze_svg(path)
    relative = path.relative_to(root).as_posix()
    return {
        "file": relative,
        "src": f"resources/base/media/{relative}",
        "file_size_bytes": path.stat().st_size,
        **analysis,
    }


def main() -> int:
    args = parse_args()
    root = args.input.resolve()
    if not root.is_dir():
        raise SystemExit(f"素材目录不存在: {root}")
    paths = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    assets = [analyze_asset(path, root) for path in paths]
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(root),
        "asset_count": len(assets),
        "method": {
            "png": "Pillow alpha-aware sampling, average color and quantized dominant colors",
            "svg": "XML intrinsic size/viewBox plus fill/stroke color extraction",
            "recommendation": "Luminance, saturation, transparency, dimensions and filename semantics",
        },
        "usage_notes": [
            "background 表示适合底层背景；logo_or_icon 表示适合 Logo、语义图标或视觉锚点；decorative_overlay 表示弱装饰层。",
            "recommended_background 仅用于保证素材可读性，最终颜色仍需服从卡片场景和状态语义。",
            "SVG 为矢量素材，resolution 中记录固有尺寸与 viewBox，不代表像素上限。",
            "Image.src 必须使用清单中的 src 原值，不得编造或重命名路径。",
        ],
        "assets": assets,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已生成素材清单: {output} | assets={len(assets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
