"""场景识别层 — 根据检测结果判断当前画面场景"""
from enum import Enum
import numpy as np
from core.cv_detector import CVDetector, DetectResult


class Scene(str, Enum):
    """当前画面场景"""
    FARM_OVERVIEW = "farm_overview"
    FRIEND_FARM = "friend_farm"
    PLOT_MENU = "plot_menu"
    SEED_SELECT = "seed_select"
    SHOP_PAGE = "shop_page"
    BUY_CONFIRM = "buy_confirm"
    POPUP = "popup"
    LEVEL_UP = "level_up"
    UNKNOWN = "unknown"


def identify_scene(detections: list[DetectResult], detector: CVDetector,
                   cv_image: np.ndarray) -> Scene:
    """根据检测结果识别当前场景"""
    names = {d.name for d in detections}

    if {"btn_buy_confirm", "btn_buy_max"} & names:
        return Scene.BUY_CONFIRM

    if "btn_shop_close" in names and "btn_shop" not in names:
        return Scene.SHOP_PAGE

    if "btn_home" in names:
        return Scene.FRIEND_FARM

    if {"btn_plant", "btn_remove", "btn_fertilize"} & names:
        return Scene.PLOT_MENU

    if any(n.startswith("seed_") for n in names):
        return Scene.SEED_SELECT

    if {"btn_close", "btn_claim", "btn_confirm", "btn_cancel"} & names:
        if "icon_levelup" in names:
            return Scene.LEVEL_UP
        return Scene.POPUP

    farm_indicators = {
        "crop_mature", "crop_dead", "crop_growing",
        "icon_mature", "icon_weed", "icon_bug", "icon_water",
        "btn_shop", "btn_harvest", "btn_weed", "btn_bug", "btn_water",
        "btn_friend_help", "btn_expand",
    }
    has_land = any(n.startswith("land_empty") for n in names)
    if has_land or (names & farm_indicators):
        return Scene.FARM_OVERVIEW

    return Scene.UNKNOWN
