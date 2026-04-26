"""异常恢复执行器：按决策执行具体恢复动作。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from core.exceptions import GamePageUnknownError
from core.platform.device import DeviceStuckError, DeviceTooManyClickError

from .error_router import RecoveryAction, RecoveryDecision


class RecoveryEngine(Protocol):
    """恢复执行器依赖的最小引擎接口。"""

    def recover_after_login_again(self, *, task_name: str) -> bool: ...

    def _validate_window_shortcut_for_recovery(self) -> tuple[bool, str]: ...

    def _restart_target_window_for_recovery(
        self,
        *,
        task_name: str,
        attempt: int,
        limit: int,
        err_type: str,
    ) -> bool: ...


class RecoveryResult(str, Enum):
    """恢复执行结果类型。"""

    RETRY_TASK = 'retry_task'
    SKIP_TASK = 'skip_task'
    STOP = 'stop'
    CONTINUE_STARTUP = 'continue_startup'
    ABORT_STARTUP = 'abort_startup'


@dataclass(frozen=True)
class RecoveryOutcome:
    """恢复执行结果。

    - `result`：恢复后上层应执行的流程控制指令。
    - `delay_seconds`：当 `result=RETRY_TASK` 时的延迟秒数。
    - `reason`：停止/告警时用于日志与提示的原因文本。
    """

    result: RecoveryResult
    delay_seconds: int = 0
    reason: str = ''


class RecoveryRunner:
    """执行恢复动作并返回标准化结果。"""

    def __init__(self, engine: RecoveryEngine):
        self.engine = engine

    def run_task(
        self,
        *,
        decision: RecoveryDecision,
        task_name: str,
        exc: Exception,
        attempt: int = 1,
    ) -> RecoveryOutcome:
        """执行任务阶段恢复动作。

        Args:
            decision: 路由层给出的恢复决策。
            task_name: 当前异常所属任务名（用于日志与提示）。
            exc: 原始异常对象。
            attempt: 当前恢复尝试次数（从 1 开始）。
        """
        if decision.action == RecoveryAction.RECOVER_LOGIN_FLOW:
            # 重新登录恢复成功后，不重跑当前任务，交还调度器推进下一轮。
            recovered = bool(self.engine.recover_after_login_again(task_name=task_name))
            if recovered:
                return RecoveryOutcome(result=RecoveryResult.SKIP_TASK)
            return RecoveryOutcome(
                result=RecoveryResult.STOP,
                reason=f'检测到重新登录异常({task_name})，登录恢复失败，已停止任务',
            )

        if decision.action == RecoveryAction.REQUEST_MANUAL_TAKEOVER:
            err_type = type(exc).__name__
            return RecoveryOutcome(
                result=RecoveryResult.STOP,
                reason=f'任务异常({task_name}): {err_type}，需人工接管，已停止任务',
            )

        if decision.action == RecoveryAction.RESTART_WINDOW:
            # 超出次数上限直接停止，避免无穷重启。
            if int(attempt) > int(decision.max_attempts):
                return RecoveryOutcome(
                    result=RecoveryResult.STOP,
                    reason=self._build_stop_reason(task_name=task_name, exc=exc, restart_limit=decision.max_attempts),
                )

            if decision.require_shortcut:
                # 重启窗口前先校验快捷方式，避免无效重试。
                valid_shortcut, shortcut_error = self.engine._validate_window_shortcut_for_recovery()
                if not valid_shortcut:
                    stop_reason = (
                        f'任务异常({task_name}): {type(exc).__name__}，无法重启窗口（{shortcut_error}），已停止任务'
                    )
                    return RecoveryOutcome(
                        result=RecoveryResult.STOP,
                        reason=stop_reason,
                    )

            restart_ok = bool(
                self.engine._restart_target_window_for_recovery(
                    task_name=task_name,
                    attempt=attempt,
                    limit=decision.max_attempts,
                    err_type=type(exc).__name__,
                )
            )
            if restart_ok:
                return RecoveryOutcome(
                    result=RecoveryResult.RETRY_TASK,
                    delay_seconds=max(1, int(decision.retry_delay_seconds)),
                    reason='restart_success',
                )

            if attempt < int(decision.max_attempts):
                return RecoveryOutcome(
                    result=RecoveryResult.RETRY_TASK,
                    delay_seconds=max(1, int(decision.retry_delay_seconds)),
                    reason='restart_failed_retry',
                )

            return RecoveryOutcome(
                result=RecoveryResult.STOP,
                reason=self._build_stop_reason(task_name=task_name, exc=exc, restart_limit=decision.max_attempts),
            )

        return RecoveryOutcome(
            result=RecoveryResult.STOP,
            reason=f'任务异常({task_name}): {type(exc).__name__}，恢复动作未实现，已停止任务',
        )

    def run_startup(self, *, decision: RecoveryDecision, exc: Exception) -> RecoveryOutcome:
        """执行启动阶段恢复动作。

        启动阶段只返回两类控制结果：
        - `CONTINUE_STARTUP`：继续启动收敛循环；
        - `ABORT_STARTUP`：终止本次启动。
        """
        if decision.action == RecoveryAction.RETRY_STARTUP_LOOP:
            return RecoveryOutcome(
                result=RecoveryResult.CONTINUE_STARTUP,
                reason=str(exc or type(exc).__name__),
            )

        if decision.action == RecoveryAction.FAIL_STARTUP:
            return RecoveryOutcome(
                result=RecoveryResult.ABORT_STARTUP,
                reason=str(exc or type(exc).__name__),
            )

        return RecoveryOutcome(
            result=RecoveryResult.ABORT_STARTUP,
            reason=str(exc or type(exc).__name__),
        )

    @staticmethod
    def _build_stop_reason(task_name: str, exc: Exception, restart_limit: int) -> str:
        """按异常类型生成停止原因。"""
        err_type = type(exc).__name__
        if isinstance(exc, GamePageUnknownError):
            return f'检测到未知页面异常({task_name})，重启窗口已达{restart_limit}次，已停止任务'
        if isinstance(exc, (DeviceStuckError, DeviceTooManyClickError)):
            return f'检测到设备卡死异常({task_name})，重启窗口已达{restart_limit}次，已停止任务'
        return f'任务异常({task_name}): {err_type}，重启窗口已达{restart_limit}次，已停止任务'
