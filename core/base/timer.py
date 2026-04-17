"""NIKKE 语义计时器。"""

from __future__ import annotations

import time


class Timer:
    """封装 `Timer` 相关的数据与行为（对齐 NIKKE 语义）。"""

    def __init__(self, limit: float, count: int = 0):
        """初始化对象并准备运行所需状态。"""
        self.limit = max(0.0, float(limit))
        self.count = max(0, int(count))
        self._current = 0.0
        self._reach_count = self.count

    def start(self) -> 'Timer':
        """启动计时器；已启动时保持当前计时。"""
        if not self.started():
            self._current = time.time()
            self._reach_count = 0
        return self

    def started(self) -> bool:
        """判断计时器是否已经启动。"""
        return bool(self._current)

    def current(self) -> float:
        """返回已计时秒数。"""
        if self.started():
            return time.time() - self._current
        return 0.0

    def reached(self, increase: bool = True) -> bool:
        """判断是否达到设定时限。"""
        if increase:
            self._reach_count += 1
        return self.current() > self.limit and self._reach_count > self.count

    def reset(self) -> 'Timer':
        """重置计时起点与计数。"""
        self._current = time.time()
        self._reach_count = 0
        return self

    def clear(self) -> 'Timer':
        """清空当前状态并停止计时。"""
        self._current = 0.0
        self._reach_count = self.count
        return self

    def reached_and_reset(self) -> bool:
        """达到时限后自动重置。"""
        if self.reached():
            self.reset()
            return True
        return False

    def wait(self) -> None:
        """阻塞等待直到达到时限。"""
        if not self.started():
            return
        diff = self._current + self.limit - time.time()
        if diff > 0:
            time.sleep(diff)
