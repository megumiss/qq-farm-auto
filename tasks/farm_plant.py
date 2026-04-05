"""播种任务。"""

from __future__ import annotations

from loguru import logger

from core.base.step_result import StepResult
from core.ui.assets import (
    ASSET_NAME_TO_CONST,
    BTN_CLAIM,
    BTN_CLOSE,
    BTN_CONFIRM,
    LAND_EMPTY,
    LAND_EMPTY_2,
    LAND_EMPTY_3,
)
from utils.shop_item_ocr import ShopItemOCR

# TODO: `btn_shop` asset 已删除，当前播种购买逻辑会被跳过，后续补模板后恢复。
BTN_SHOP = ASSET_NAME_TO_CONST.get('btn_shop')
# TODO: `btn_shop_close` asset 已删除，当前商店收尾依赖降级为普通关闭按钮。
BTN_SHOP_CLOSE = ASSET_NAME_TO_CONST.get('btn_shop_close')
# TODO: `btn_buy_confirm` asset 已删除，当前购买确认可能依赖兜底按钮处理。
BTN_BUY_CONFIRM = ASSET_NAME_TO_CONST.get('btn_buy_confirm')
# TODO: `btn_fertilize_popup` asset 已删除，当前施肥弹窗检测被跳过。
BTN_FERTILIZE_POPUP = ASSET_NAME_TO_CONST.get('btn_fertilize_popup')


class TaskFarmPlant:
    """封装 `TaskFarmPlant` 任务的执行入口与步骤。"""

    def __init__(self, engine, ui):
        """初始化对象并准备运行所需状态。"""
        self.engine = engine
        self.ui = ui
        self.shop_ocr = ShopItemOCR()

    def run(self, rect, features) -> StepResult:
        """执行当前模块主流程并返回结果。"""
        if not features.get('auto_plant', False):
            return StepResult()

        has_land = self.ui.appear_any(
            [LAND_EMPTY, LAND_EMPTY_2, LAND_EMPTY_3],
            offset=(30, 30),
            threshold=0.89,
            static=False,
        )
        if not has_land:
            return StepResult()
        out = StepResult.from_value(self._plant_all(rect, self.engine._resolve_crop_name()))
        return out

    def _plant_all(self, rect: tuple[int, int, int, int], crop_name: str) -> list[str]:
        """执行整块农田播种流程（识别空地、拉种子、补种购买）。"""
        all_actions: list[str] = []

        cv_img = self.ui.device.screenshot(rect=rect, save=False)
        if cv_img is None:
            return all_actions
        dets = self.engine.cv_detector.detect_templates(
            cv_img,
            template_names=['land_empty', 'land_empty_2', 'land_empty_3'],
            default_threshold=0.89,
            thresholds={'land_empty': 0.89, 'land_empty_2': 0.89, 'land_empty_3': 0.89},
        )
        lands = [d for d in dets if d.name.startswith('land_empty')]
        if not lands:
            return all_actions

        self.ui.device.click_point(int(lands[0].x), int(lands[0].y), desc='点击空地')
        self.ui.device.sleep(0.3)

        seed_det = None
        for _ in range(2):
            cv_img = self.ui.device.screenshot(rect=rect, save=False)
            if cv_img is None:
                return all_actions
            seed_dets = self.engine.cv_detector.detect_seed_template(cv_img, crop_name_or_template=crop_name)
            if seed_dets:
                seed_det = seed_dets[0]
                break
            self.ui.device.sleep(0.3)

        if not seed_det:
            buy_result = self._buy_seeds(rect, crop_name)
            if buy_result:
                all_actions.append(buy_result)
                return all_actions + self._plant_all(rect, crop_name)
            return all_actions

        if not self.engine.action_executor or not self.engine.device:
            return all_actions

        planted_count = 0
        dragging = False
        try:
            if not self.engine.device.drag_down_point(int(seed_det.x), int(seed_det.y), duration=0.05):
                return all_actions
            dragging = True
            if not self.ui.device.sleep(0.1):
                return all_actions

            for land in lands:
                if not self.engine.device.drag_move_point(int(land.x), int(land.y), duration=0.1):
                    break
                if not self.ui.device.sleep(0.15):
                    break
                planted_count += 1
        finally:
            if dragging:
                self.engine.device.drag_up()

        if planted_count > 0:
            all_actions.append(f'播种{crop_name}×{planted_count}')

        self.ui.device.sleep(0.5)
        cv_check = self.ui.device.screenshot(rect=rect, save=False)
        if cv_check is not None:
            if BTN_SHOP_CLOSE is not None and self.ui.appear(BTN_SHOP_CLOSE, offset=(30, 30), threshold=0.8, static=False):
                self._close_shop_and_buy(rect, crop_name, all_actions)

            if BTN_FERTILIZE_POPUP is not None and self.ui.appear(
                BTN_FERTILIZE_POPUP, offset=(30, 30), threshold=0.8, static=False
            ):
                x, y = self.engine._resolve_goto_main_point(rect)
                self.engine.device.click_point(x, y, desc='点击回主按钮')

        return all_actions

    def _close_shop_and_buy(self, rect: tuple[int, int, int, int], crop_name: str, actions_done: list[str]):
        """关闭商店后立刻执行一次补种购买。"""
        self._close_shop(rect)
        buy_result = self._buy_seeds(rect, crop_name)
        if buy_result:
            actions_done.append(buy_result)

    def _buy_seeds(self, rect: tuple[int, int, int, int], crop_name: str) -> str | None:
        """执行买种流程：开商店 -> OCR 定位 -> 选择并确认购买。"""
        cv_img = self.ui.device.screenshot(rect=rect, save=False)
        if cv_img is None:
            return None

        if BTN_SHOP is None:
            logger.warning('购买流程: 未配置商店按钮模板')
            return None
        if not self.ui.appear_then_click(BTN_SHOP, offset=(30, 30), interval=1, threshold=0.8, static=False):
            logger.warning('购买流程: 未找到商店按钮')
            return None
        self.ui.device.sleep(1.0)

        shop_cv = None
        for _ in range(5):
            cv_img = self.ui.device.screenshot(rect=rect, save=False)
            if cv_img is None:
                return None
            if BTN_SHOP_CLOSE is not None and self.ui.appear(BTN_SHOP_CLOSE, offset=(30, 30), threshold=0.8, static=False):
                shop_cv = cv_img
                break
            self.ui.device.sleep(0.5)
        if shop_cv is None:
            self._close_shop(rect)
            return None

        matched_item = None
        for _ in range(3):
            ocr_match = self.shop_ocr.find_item(shop_cv, crop_name, min_similarity=0.70)
            if ocr_match.target:
                matched_item = ocr_match.target
                break
            self.ui.device.sleep(0.3)
            cv_img = self.ui.device.screenshot(rect=rect, save=False)
            if cv_img is None:
                return None
            shop_cv = cv_img

        if not matched_item:
            logger.warning(f"购买流程: OCR未找到 '{crop_name}'")
            self._close_shop(rect)
            return None

        self.ui.device.click_point(int(matched_item.center_x), int(matched_item.center_y), desc=f'选择{crop_name}')
        self.ui.device.sleep(1.0)
        return self._confirm_purchase(rect, crop_name)

    def _confirm_purchase(self, rect: tuple[int, int, int, int], crop_name: str) -> str | None:
        """在购买弹窗中执行确认并处理伴随弹窗。"""
        for _ in range(5):
            cv_img = self.ui.device.screenshot(rect=rect, save=False)
            if cv_img is None:
                return None

            if BTN_BUY_CONFIRM is not None and self.ui.appear_then_click(
                BTN_BUY_CONFIRM, offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                self.ui.device.sleep(0.3)
                self._close_shop(rect)
                return f'购买{crop_name}'

            if self.ui.appear_then_click_any(
                [BTN_CLOSE, BTN_CONFIRM, BTN_CLAIM], offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                self.ui.device.sleep(0.2)
                continue

            self.ui.device.sleep(0.3)

        self._close_shop(rect)
        return None

    def _close_shop(self, rect: tuple[int, int, int, int]):
        """尽可能关闭商店页残留弹窗，回到主流程页面。"""
        for _ in range(3):
            cv_img = self.ui.device.screenshot(rect=rect, save=False)
            if cv_img is None:
                return
            buttons = [BTN_CLOSE] if BTN_SHOP_CLOSE is None else [BTN_SHOP_CLOSE, BTN_CLOSE]
            if not self.ui.appear_then_click_any(buttons, offset=(30, 30), interval=1, threshold=0.8, static=False):
                return
            self.ui.device.sleep(0.3)


