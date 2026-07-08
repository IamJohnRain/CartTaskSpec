from __future__ import annotations

import re
from typing import Any

from .base import BaseValidator, HEX_RE, is_wrapped_expression, static_expression_value, walk_json


class AssetValidator(BaseValidator):
    stage = "hard"
    name = "asset"

    def validate(self, context, rules, reporter) -> None:
        forbidden = [re.compile(pattern, re.I) for pattern in rules.asset.get("forbiddenPatterns", [])]
        parent_by_child = self._parent_map(context)
        for component in context.components:
            component_id = component.get("id", "<unknown>")
            component_type = component.get("component")
            if component_type == "Image":
                src = component.get("src")
                self._check_asset_value(
                    src,
                    f"/updateComponents/componentsById/{component_id}/src",
                    forbidden,
                    context,
                    rules,
                    reporter,
                    required=True,
                )
                resolved = self._resolve_asset_path(src, context)
                if (
                    isinstance(resolved, str)
                    and resolved in getattr(rules, "dark_monochrome_asset_paths", set())
                    and self._has_dark_background(component_id, context, rules, parent_by_child)
                ):
                    reporter.add(
                        "warning",
                        "ASSET_DARK_MONO_SVG_ON_DARK_BG_RISK",
                        "hard",
                        "genui",
                        line=2,
                        json_pointer=f"/updateComponents/componentsById/{component_id}/src",
                        actual=resolved,
                        message="黑色或黑白实心 SVG 置于深色/暗色渐变背景上，真实渲染中容易看不清。",
                        fix_hint="为图标增加不透明浅色底板、改用可读 PNG/浅色素材，或删除该弱图标并把空间让给主文字/CTA。",
                    )
            styles = component.get("styles", {})
            if isinstance(styles, dict) and "backgroundImage" in styles:
                self._check_asset_value(
                    styles.get("backgroundImage"),
                    f"/updateComponents/componentsById/{component_id}/styles/backgroundImage",
                    forbidden,
                    context,
                    rules,
                    reporter,
                    required=False,
                )

    def _check_asset_value(self, value: Any, pointer: str, forbidden, context, rules, reporter, required: bool) -> None:
        if not isinstance(value, str):
            if required:
                reporter.add("error", "ASSET_PATH_NOT_DECLARED", "hard", "genui", line=2, json_pointer=pointer, actual=value, message="资源路径必须是字符串或完整表达式。")
            return
        if is_wrapped_expression(value):
            resolved = static_expression_value(value, context.data_model)
            if isinstance(resolved, str):
                self._check_static_path(resolved, pointer, forbidden, rules, reporter)
            else:
                reporter.add(
                    "warning",
                    "ASSET_PATH_NOT_DECLARED",
                    "hard",
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual=value,
                    message="表达式形式的资源路径无法在初始 DataModel 中解析为静态路径。",
                    fix_hint="确保该表达式运行时只返回素材库 allowlist 中的资源路径。",
                )
            return
        self._check_static_path(value, pointer, forbidden, rules, reporter)

    def _check_static_path(self, path: str, pointer: str, forbidden, rules, reporter) -> None:
        for pattern in forbidden:
            if pattern.search(path):
                reporter.add(
                    "error",
                    "ASSET_REMOTE_URL_FORBIDDEN",
                    "hard",
                    "genui",
                    line=2,
                    json_pointer=pointer,
                    actual=path,
                    message="资源路径禁止网络 URL、data:image 和 base64。",
                    fix_hint="使用素材库声明的本地 resources/base/media/*.svg。",
                )
                return
        if path not in rules.asset_allowlist:
            reporter.add(
                "error",
                "ASSET_PATH_NOT_DECLARED",
                "hard",
                "genui",
                line=2,
                json_pointer=pointer,
                actual=path,
            )

    def _resolve_asset_path(self, value: Any, context) -> str | None:
        if isinstance(value, str) and is_wrapped_expression(value):
            resolved = static_expression_value(value, context.data_model)
            return resolved if isinstance(resolved, str) else None
        return value if isinstance(value, str) else None

    def _parent_map(self, context) -> dict[str, str]:
        parent_by_child: dict[str, str] = {}
        for component in context.components:
            parent_id = component.get("id")
            children = component.get("children")
            if not isinstance(parent_id, str):
                continue
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, str):
                        parent_by_child[child] = parent_id
            elif isinstance(children, dict) and isinstance(children.get("componentId"), str):
                parent_by_child[children["componentId"]] = parent_id
        return parent_by_child

    def _has_dark_background(self, component_id: str, context, rules, parent_by_child: dict[str, str]) -> bool:
        current_id = component_id
        visited: set[str] = set()
        while current_id and current_id not in visited:
            visited.add(current_id)
            component = context.components_by_id.get(current_id)
            if isinstance(component, dict):
                state = self._background_state(component.get("styles", {}), rules)
                if state == "dark":
                    return True
                if state == "opaque_light":
                    return False
            current_id = parent_by_child.get(current_id)
        return False

    def _background_state(self, styles: Any, rules) -> str | None:
        if not isinstance(styles, dict):
            return None
        bg = styles.get("backgroundColor")
        if isinstance(bg, str):
            state = self._color_state(bg, rules)
            if state:
                return state
        gradient = styles.get("linearGradient")
        if isinstance(gradient, dict) and isinstance(gradient.get("colors"), list):
            saw_opaque_light = False
            for stop in gradient.get("colors", []):
                if not (isinstance(stop, list) and stop):
                    continue
                state = self._color_state(stop[0], rules)
                if state == "dark":
                    return "dark"
                if state == "opaque_light":
                    saw_opaque_light = True
            if saw_opaque_light:
                return "opaque_light"
        return None

    def _color_state(self, color: Any, rules) -> str | None:
        if not isinstance(color, str) or not HEX_RE.fullmatch(color):
            return None
        alpha, red, green, blue = self._rgba(color)
        threshold = rules.asset.get("darkMonochromeSvg", {}).get("backgroundLuminanceThreshold", 0.38)
        opaque_threshold = rules.asset.get("darkMonochromeSvg", {}).get("opaqueAlphaThreshold", 0.85)
        luminance = self._relative_luminance(red, green, blue)
        if alpha >= 0.35 and luminance < threshold:
            return "dark"
        if alpha >= opaque_threshold:
            return "opaque_light"
        return None

    def _rgba(self, color: str) -> tuple[float, int, int, int]:
        raw = color.lstrip("#")
        if len(raw) == 8:
            alpha = int(raw[0:2], 16) / 255
            red = int(raw[2:4], 16)
            green = int(raw[4:6], 16)
            blue = int(raw[6:8], 16)
            return alpha, red, green, blue
        return 1.0, int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)

    def _relative_luminance(self, red: int, green: int, blue: int) -> float:
        def channel(value: int) -> float:
            normalized = value / 255
            return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

        return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def collect_asset_paths(value: Any) -> list[str]:
    result = []
    for _, child in walk_json(value):
        if isinstance(child, str) and child.startswith("resources/"):
            result.append(child)
    return result
