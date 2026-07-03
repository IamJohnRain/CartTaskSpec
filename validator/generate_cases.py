from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from validator import engine, registry

engine.discover_rules()
ALL_RULES = sorted(registry.all_rules(), key=lambda r: r.rule_id)


GOOD_CARD_2x2 = [
    {
        "version": "v0.9",
        "createSurface": {
            "surfaceId": "card_main",
            "catalogId": "ohos.a2ui.extended.catalog",
            "width": 140,
            "height": 140,
        },
    },
    {
        "version": "v0.9",
        "updateComponents": {
            "surfaceId": "card_main",
            "root": "root",
            "components": [
                {
                    "id": "root",
                    "component": "Column",
                    "children": ["title_text", "value_text", "cta_button"],
                    "itemMargin": 4,
                    "styles": {
                        "width": 140,
                        "height": 140,
                        "padding": 12,
                        "borderRadius": 18,
                        "clip": True,
                        "backgroundColor": "#FFFFFFFF",
                    },
                },
                {
                    "id": "title_text",
                    "component": "Text",
                    "content": "电池电量",
                    "styles": {
                        "width": 116,
                        "height": 16,
                        "fontSize": 14,
                        "fontColor": "#E5000000",
                        "maxLines": 1,
                        "textOverflow": "none",
                    },
                },
                {
                    "id": "value_text",
                    "component": "Text",
                    "content": "{{ $__dataModel.battery.percentText }}",
                    "styles": {
                        "width": 116,
                        "height": 56,
                        "fontSize": 40,
                        "fontColor": "#FF0A59F7",
                        "maxLines": 1,
                        "textOverflow": "none",
                    },
                },
                {
                    "id": "cta_button",
                    "component": "Button",
                    "label": "查看详情",
                    "styles": {
                        "width": 116,
                        "height": 32,
                        "fontSize": 14,
                        "fontColor": "#FFFFFFFF",
                        "backgroundColor": "#FF64BB5C",
                    },
                },
            ],
        },
    },
    {
        "version": "v0.9",
        "updateDataModel": {
            "surfaceId": "card_main",
            "path": "/",
            "value": {
                "battery": {"level": 18, "percentText": "18%"},
            },
        },
    },
]


GOOD_CARD_2x4 = [
    {
        "version": "v0.9",
        "createSurface": {
            "surfaceId": "card_main",
            "catalogId": "ohos.a2ui.extended.catalog",
            "width": 300,
            "height": 140,
        },
    },
    {
        "version": "v0.9",
        "updateComponents": {
            "surfaceId": "card_main",
            "root": "root",
            "components": [
                {
                    "id": "root",
                    "component": "Row",
                    "children": ["title_text", "cta_button"],
                    "itemMargin": 8,
                    "styles": {
                        "width": 300,
                        "height": 140,
                        "padding": 12,
                        "borderRadius": 22,
                        "clip": True,
                        "backgroundColor": "#FFFFFFFF",
                    },
                },
                {
                    "id": "title_text",
                    "component": "Text",
                    "content": "电池电量",
                    "styles": {
                        "width": 180,
                        "height": 116,
                        "fontSize": 18,
                        "fontColor": "#E5000000",
                        "maxLines": 1,
                        "textOverflow": "none",
                    },
                },
                {
                    "id": "cta_button",
                    "component": "Button",
                    "label": "查看",
                    "styles": {
                        "width": 88,
                        "height": 32,
                        "fontSize": 14,
                        "fontColor": "#FFFFFFFF",
                        "backgroundColor": "#FF64BB5C",
                    },
                },
            ],
        },
    },
    {
        "version": "v0.9",
        "updateDataModel": {
            "surfaceId": "card_main",
            "path": "/",
            "value": {
                "battery": {"level": 18, "percentText": "18%"},
            },
        },
    },
]


def _copy(card):
    return [copy.deepcopy(m) for m in card]


def _set_path(card, line_idx: int, dotpath: str, value):
    out = _copy(card)
    obj = out[line_idx]
    parts = dotpath.split(".")
    for p in parts[:-1]:
        if p.isdigit():
            obj = obj[int(p)]
        else:
            obj = obj.setdefault(p, {})
    obj[parts[-1]] = value
    return out


def _del_path(card, line_idx: int, dotpath: str):
    out = _copy(card)
    obj = out[line_idx]
    parts = dotpath.split(".")
    for p in parts[:-1]:
        if p.isdigit():
            obj = obj[int(p)]
        else:
            obj = obj[p]
    if parts[-1].isdigit():
        del obj[int(parts[-1])]
    else:
        del obj[parts[-1]]
    return out


def _append(card, line_idx: int, dotpath: str, value):
    out = _copy(card)
    obj = out[line_idx]
    parts = dotpath.split(".")
    for p in parts[:-1]:
        if p.isdigit():
            obj = obj[int(p)]
        else:
            obj = obj.setdefault(p, [])
    obj.append(value)
    return out


def _assign_root_size_2x4(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.width", 300)


def _assign_root_radius_2x4(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.borderRadius", 22)


def _mutate_R_L0_002(card):
    return _set_path(card, 0, "version", "v1.0")


def _mutate_R_L0_003(card):
    return _set_path(card, 0, "extra", "smuggled")


def _mutate_R_L0_004(card):
    return _set_path(card, 0, "createSurface.catalogId", "ohos.a2ui.basic.catalog")


def _mutate_R_L0_005(card):
    return _set_path(card, 1, "updateComponents.surfaceId", "other_surface")


def _mutate_R_L0_006(card):
    return _set_path(card, 0, "createSurface.width", 200)


def _mutate_R_L0_007(card):
    return _set_path(card, 1, "updateComponents.components", {"oops": True})


def _mutate_R_L0_008(card):
    return _set_path(card, 1, "updateComponents.components.1.id", "")


def _mutate_R_L0_009(card):
    return _set_path(card, 1, "updateComponents.components.2.id", "title_text")


def _mutate_R_L0_010(card):
    return _set_path(card, 1, "updateComponents.root", "missing_root")


def _mutate_R_L0_011(card):
    return _set_path(card, 1, "updateComponents.components.1.component", "TextInput")


def _mutate_R_L0_012(card):
    return _set_path(card, 1, "updateComponents.components.1.component", "Paragraph")


def _mutate_R_L0_013(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.theme", "dark")


def _mutate_R_L0_014(card):
    return _set_path(card, 1, "updateComponents.components.0.onCustom", "noop")


def _mutate_R_L0_015(card):
    return _set_path(card, 1, "updateComponents.components.1.content", "https://example.com/x.png")


def _mutate_R_L0_016(card):
    return _set_path(card, 1, "updateComponents.components.1.content", "data:image/svg+xml;base64,PHN2Zy8+")


def _mutate_R_L0_017(card):
    return _set_path(card, 1, "updateComponents.components.0.children", "not-a-list")


def _mutate_R_L0_018(card):
    return _set_path(card, 1, "updateComponents.components.0.children", ["nonexistent_child"])


def _mutate_R_L0_019(card):
    return _set_path(card, 1, "updateComponents.components.0.children", {"componentId": "title_text", "path": "/battery/level", "extra": 1})


def _mutate_R_L0_020(card):
    return _set_path(card, 1, "updateComponents.components.0.children", {"componentId": "nonexistent_id", "path": "/battery/level"})


def _mutate_R_L0_021(card):
    return _set_path(card, 1, "updateComponents.components.0.children", {"componentId": "title_text", "path": "battery/level"})


def _add_onclick(card):
    return _set_path(card, 1, "updateComponents.components.3.onClick", [{"call": "clickToDeeplink", "args": {"bundleName": "com.demo", "abilityName": "Main", "uri": "demo://x"}}])


def _mutate_R_L0_022(card):
    card = _add_onclick(card)
    return _set_path(card, 1, "updateComponents.components.3.onClick", {"call": "clickToDeeplink", "args": {}})


def _mutate_R_L0_023(card):
    return _set_path(card, 1, "updateComponents.components.3.onClick", ["not_an_object"])


def _mutate_R_L0_024(card):
    return _set_path(card, 1, "updateComponents.components.3.onClick", [{"call": "clickToMagic", "args": {}}])


def _mutate_R_L0_025(card):
    return _set_path(card, 1, "updateComponents.components.3.onClick", [{"call": "clickToDeeplink", "args": "not-an-object"}])


def _mutate_R_L0_026(card):
    return _set_path(card, 1, "updateComponents.components.3.onClick", [{"call": "clickToDeeplink", "args": {"bundleName": "x", "abilityName": "y", "uri": "z", "extra": 1}}])


def _mutate_R_L0_027(card):
    return _set_path(card, 1, "updateComponents.components.3.onClick", [{"call": "clickToDeeplink", "args": {"uri": "demo://x"}}])


def _mutate_R_L0_028(card):
    return _set_path(card, 1, "updateComponents.components.3.onClick", [{"call": "clickToCallPhone", "args": {"phoneNumber": "10086", "extra": 1}}])


def _mutate_R_L0_029(card):
    return _set_path(card, 1, "updateComponents.components.1.content", "半截 {{ 没有结尾")


def _mutate_R_L0_030(card):
    return _set_path(card, 1, "updateComponents.components.1.content", "{{ $__dataModel.missing.field }}")


def _mutate_R_L0_031(card):
    return _set_path(card, 1, "updateComponents.components.1.content", {"path": "/missing/path"})


def _mutate_R_L0_032(card):
    return _set_path(card, 1, "updateComponents.components.1.content", {"call": "formatString", "args": {"value": 123}})


def _mutate_R_L0_033(card):
    return _set_path(card, 1, "updateComponents.components.1.content", {"call": "formatString", "args": {"value": "值=${/missing/path}"}})


def _mutate_R_L1_001(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.width", 200)


def _mutate_R_L1_002(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.borderRadius", 99)


def _mutate_R_L1_003(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.padding", 8)


def _mutate_R_L1_004(card):
    return _set_path(card, 1, "updateComponents.components.1.styles.fontSize", 22)


def _mutate_R_L1_005(card):
    return _set_path(card, 1, "updateComponents.components.1.styles.textOverflow", "ellipsis")


def _mutate_R_L1_006(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.padding", 7)


def _mutate_R_L1_007(card):
    return _set_path(card, 1, "updateComponents.components.0.itemMargin", 5)


def _mutate_R_L1_008(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.linearGradient", {"colors": []})


def _mutate_R_L1_009(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.linearGradient", {"colors": ["#FF0A59F7"]})


def _mutate_R_L1_010(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][1] = {
        "id": "img_1",
        "component": "Image",
        "styles": {"width": 50, "height": 50, "objectFit": "contain"},
    }
    return out


def _mutate_R_L1_011(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][1] = {
        "id": "img_1",
        "component": "Image",
        "src": "common/avatar.png",
        "styles": {"width": "auto", "height": "auto"},
    }
    return out


def _mutate_R_L1_012(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][1] = {
        "id": "img_1",
        "component": "Image",
        "src": "common/avatar.png",
        "styles": {"width": 50, "height": 50, "objectFit": "cover"},
    }
    return out


def _mutate_R_L1_013(card):
    return _set_path(card, 1, "updateComponents.components.1.content", "非常非常非常非常非常非常长的中文字符串")


def _mutate_R_L1_014(card):
    return _set_path(card, 1, "updateComponents.components.3.styles.height", 20)


def _mutate_R_L1_015(card):
    return _set_path(card, 1, "updateComponents.components.3.label", "很长的按钮文字很长的按钮文字很长的按钮文字")
def _mutate_R_L1_016(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][0]["children"] = ["title_text", "value_text", "cta_button"]
    out[1]["updateComponents"]["components"][0]["component"] = "Row"
    out[1]["updateComponents"]["components"][0]["styles"]["width"] = 200
    return out


def _mutate_R_L1_017(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][0]["children"] = ["title_text", "value_text"]
    out[1]["updateComponents"]["components"][0]["component"] = "Row"
    out[1]["updateComponents"]["components"][0]["styles"]["width"] = 240
    out[1]["updateComponents"]["components"][0]["styles"]["height"] = 40
    out[1]["updateComponents"]["components"][1]["styles"]["height"] = 80
    return out


def _mutate_R_L1_018(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][1]["styles"]["height"] = 200
    return out


def _mutate_R_L1_019(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][1]["styles"]["width"] = 200
    return out


def _mutate_R_L1_020(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][0]["children"] = ["title_text"]
    return out


def _mutate_R_L2_001(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.backgroundColor", "red")


def _mutate_R_L2_002(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.backgroundColor", "#FFF7E8")


def _mutate_R_L2_003(card):
    return _set_path(card, 1, "updateComponents.components.0.styles.linearGradient", {"colors": [["#FFF7E8", 0], ["#FF64BB5C", 1]]})


def _mutate_R_L2_004(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][3]["label"] = "电池电量"
    return out


def _mutate_R_L2_005(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][3]["label"] = "查看电池电量详情"
    return out


def _mutate_R_L2_006(card):
    out = _copy(card)
    out[1]["updateComponents"]["components"][0]["children"] = ["hint_text", "cta_button"]
    out[1]["updateComponents"]["components"][0]["component"] = "Row"
    out[1]["updateComponents"]["components"][0]["styles"]["width"] = 240
    out[1]["updateComponents"]["components"][0]["styles"]["height"] = 40
    out[1]["updateComponents"]["components"][0]["styles"]["padding"] = {"top": 4, "bottom": 4, "left": 8, "right": 8}
    out[1]["updateComponents"]["components"][0]["itemMargin"] = 4
    out[1]["updateComponents"]["components"][0]["styles"]["backgroundColor"] = "#FFFFFFFF"
    out[1]["updateComponents"]["components"][2] = {
        "id": "hint_text",
        "component": "Text",
        "content": "提示",
        "styles": {
            "width": 120,
            "height": 32,
            "fontSize": 12,
            "fontColor": "#E5000000",
            "maxLines": 1,
            "textOverflow": "none",
        },
    }
    return out


MUTATORS = {
    "R-L0-002": _mutate_R_L0_002,
    "R-L0-003": _mutate_R_L0_003,
    "R-L0-004": _mutate_R_L0_004,
    "R-L0-005": _mutate_R_L0_005,
    "R-L0-006": _mutate_R_L0_006,
    "R-L0-007": _mutate_R_L0_007,
    "R-L0-008": _mutate_R_L0_008,
    "R-L0-009": _mutate_R_L0_009,
    "R-L0-010": _mutate_R_L0_010,
    "R-L0-011": _mutate_R_L0_011,
    "R-L0-012": _mutate_R_L0_012,
    "R-L0-013": _mutate_R_L0_013,
    "R-L0-014": _mutate_R_L0_014,
    "R-L0-015": _mutate_R_L0_015,
    "R-L0-016": _mutate_R_L0_016,
    "R-L0-017": _mutate_R_L0_017,
    "R-L0-018": _mutate_R_L0_018,
    "R-L0-019": _mutate_R_L0_019,
    "R-L0-020": _mutate_R_L0_020,
    "R-L0-021": _mutate_R_L0_021,
    "R-L0-022": _mutate_R_L0_022,
    "R-L0-023": _mutate_R_L0_023,
    "R-L0-024": _mutate_R_L0_024,
    "R-L0-025": _mutate_R_L0_025,
    "R-L0-026": _mutate_R_L0_026,
    "R-L0-027": _mutate_R_L0_027,
    "R-L0-028": _mutate_R_L0_028,
    "R-L0-029": _mutate_R_L0_029,
    "R-L0-030": _mutate_R_L0_030,
    "R-L0-031": _mutate_R_L0_031,
    "R-L0-032": _mutate_R_L0_032,
    "R-L0-033": _mutate_R_L0_033,
    "R-L1-001": _mutate_R_L1_001,
    "R-L1-002": _mutate_R_L1_002,
    "R-L1-003": _mutate_R_L1_003,
    "R-L1-004": _mutate_R_L1_004,
    "R-L1-005": _mutate_R_L1_005,
    "R-L1-006": _mutate_R_L1_006,
    "R-L1-007": _mutate_R_L1_007,
    "R-L1-008": _mutate_R_L1_008,
    "R-L1-009": _mutate_R_L1_009,
    "R-L1-010": _mutate_R_L1_010,
    "R-L1-011": _mutate_R_L1_011,
    "R-L1-012": _mutate_R_L1_012,
    "R-L1-013": _mutate_R_L1_013,
    "R-L1-014": _mutate_R_L1_014,
    "R-L1-015": _mutate_R_L1_015,
    "R-L1-016": _mutate_R_L1_016,
    "R-L1-017": _mutate_R_L1_017,
    "R-L1-018": _mutate_R_L1_018,
    "R-L1-019": _mutate_R_L1_019,
    "R-L1-020": _mutate_R_L1_020,
    "R-L2-001": _mutate_R_L2_001,
    "R-L2-002": _mutate_R_L2_002,
    "R-L2-003": _mutate_R_L2_003,
    "R-L2-004": _mutate_R_L2_004,
    "R-L2-005": _mutate_R_L2_005,
    "R-L2-006": _mutate_R_L2_006,
}


USE_2x4_FOR_PASS = {
    "R-L0-006",
    "R-L1-001",
    "R-L1-002",
}


def dump_jsonl(card) -> str:
    return "\n".join(json.dumps(m, ensure_ascii=False) for m in card) + "\n"


def main():
    cases_root = ROOT / "cases"
    cases_root.mkdir(exist_ok=True)
    written = 0
    missing_mutator: list[str] = []
    for rule in ALL_RULES:
        rid = rule.rule_id
        mutator = MUTATORS.get(rid)
        rule_dir = cases_root / rid
        rule_dir.mkdir(exist_ok=True)
        if mutator is None:
            (rule_dir / "README.md").write_text(
                f"# {rid} {rule.name}\n\n{rule.description}\n\n待补 mutator。\n",
                encoding="utf-8",
            )
            missing_mutator.append(rid)
            continue
        pass_card = GOOD_CARD_2x4 if rid in USE_2x4_FOR_PASS else GOOD_CARD_2x2
        pass_jsonl = rule_dir / "pass.jsonl"
        pass_jsonl.write_text(dump_jsonl(pass_card), encoding="utf-8")
        try:
            fail_card = mutator(pass_card)
        except Exception as e:
            (rule_dir / "ERROR.txt").write_text(f"mutator crashed: {e}\n", encoding="utf-8")
            continue
        fail_jsonl = rule_dir / "fail.jsonl"
        fail_jsonl.write_text(dump_jsonl(fail_card), encoding="utf-8")
        expected = {
            "rule_id": rid,
            "should_fire_on_fail": True,
            "should_fire_on_pass": False,
        }
        (rule_dir / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
        readme = (
            f"# {rid} {rule.name}\n\n"
            f"**严重度**: {rule.severity.value}\n\n"
            f"**描述**: {rule.description}\n\n"
            f"**标签**: {', '.join(rule.meta.tags)}\n\n"
            f"## 反例 (fail.jsonl)\n\n"
            f"最小化破坏该规则的卡片，用于回归测试与人工复核。\n\n"
            f"## 正例 (pass.jsonl)\n\n"
            f"满足该规则的基线卡片，runner 应当不触发 `{rid}`。\n\n"
            f"## 期望 (expected.json)\n\n"
            f"```json\n{json.dumps(expected, ensure_ascii=False, indent=2)}\n```\n"
        )
        (rule_dir / "README.md").write_text(readme, encoding="utf-8")
        written += 1
    print(f"generated {written} case dirs under {cases_root}")
    if missing_mutator:
        print(f"missing mutators: {missing_mutator}")


if __name__ == "__main__":
    main()
