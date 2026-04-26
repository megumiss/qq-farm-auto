"""异常路由：将异常类型映射为恢复决策。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.exceptions import GamePageUnknownError, LoginRecoveryRequiredError, LoginRepeatError
from core.platform.device import DeviceStuckError, DeviceTooManyClickError


class RecoveryPhase(str, Enum):
    """恢复决策阶段。"""

    STARTUP = 'startup'
    TASK = 'task'


class RecoveryAction(str, Enum):
    """恢复动作类型。"""

    RECOVER_LOGIN_FLOW = 'recover_login_flow'
    RESTART_WINDOW = 'restart_window'
    RETRY_STARTUP_LOOP = 'retry_startup_loop'
    FAIL_STARTUP = 'fail_startup'
    REQUEST_MANUAL_TAKEOVER = 'request_manual_takeover'


@dataclass(frozen=True)
class RecoveryDecision:
    """异常恢复决策。

    - `phase`：决策发生阶段（启动阶段/任务阶段）。
    - `action`：执行层应采取的恢复动作。
    - `error_key`：用于日志/统计的稳定错误分类键。
    - `retry_delay_seconds`：重试类动作的延迟秒数。
    - `max_attempts`：重启窗口类动作的最大尝试次数。
    - `require_shortcut`：执行动作前是否必须校验 `.lnk` 可用。
    """

    phase: RecoveryPhase
    action: RecoveryAction
    error_key: str
    retry_delay_seconds: int = 1
    max_attempts: int = 1
    require_shortcut: bool = False


class ErrorRouter:
    """统一异常 -> 恢复动作映射。"""

    def __init__(self, *, task_restart_attempts: int = 3, task_retry_delay_seconds: int = 1):
        self._task_restart_attempts = max(1, int(task_restart_attempts))
        self._task_retry_delay_seconds = max(1, int(task_retry_delay_seconds))

    def update_policy(self, *, task_restart_attempts: int, task_retry_delay_seconds: int) -> None:
        """更新恢复策略参数。"""
        self._task_restart_attempts = max(1, int(task_restart_attempts))
        self._task_retry_delay_seconds = max(1, int(task_retry_delay_seconds))

    @staticmethod
    def _is_print_window_failure(exc: Exception) -> bool:
        """判断是否为 PrintWindow 连续失败异常。"""
        return isinstance(exc, RuntimeError) and str(exc or '').startswith('PrintWindow连续失败')

    def route(self, *, phase: RecoveryPhase, exc: Exception) -> RecoveryDecision:
        """根据阶段与异常类型返回恢复决策。

        Args:
            phase: 当前恢复阶段（`startup/task`）。
            exc: 触发恢复流程的原始异常。
        """
        if phase == RecoveryPhase.STARTUP:
            return self._route_startup(exc)
        return self._route_task(exc)

    def _route_startup(self, exc: Exception) -> RecoveryDecision:
        """启动阶段路由。

        启动阶段优先保证“能否继续收敛到主界面”，
        因此结果只会是“继续启动循环”或“终止启动”。
        """
        if isinstance(exc, LoginRepeatError):
            return RecoveryDecision(
                phase=RecoveryPhase.STARTUP,
                action=RecoveryAction.FAIL_STARTUP,
                error_key='login_repeat',
            )

        if isinstance(exc, LoginRecoveryRequiredError):
            return RecoveryDecision(
                phase=RecoveryPhase.STARTUP,
                action=RecoveryAction.RETRY_STARTUP_LOOP,
                error_key='login_recovery_required',
            )

        if isinstance(exc, GamePageUnknownError):
            return RecoveryDecision(
                phase=RecoveryPhase.STARTUP,
                action=RecoveryAction.RETRY_STARTUP_LOOP,
                error_key='page_unknown',
            )

        return RecoveryDecision(
            phase=RecoveryPhase.STARTUP,
            action=RecoveryAction.RETRY_STARTUP_LOOP,
            error_key='startup_exception',
        )

    def _route_task(self, exc: Exception) -> RecoveryDecision:
        """任务阶段路由。

        任务阶段会区分：
        - 登录恢复（不重跑当前任务）
        - 窗口重启恢复（可重试）
        - 人工接管（立即停止）
        """
        if isinstance(exc, LoginRecoveryRequiredError):
            return RecoveryDecision(
                phase=RecoveryPhase.TASK,
                action=RecoveryAction.RECOVER_LOGIN_FLOW,
                error_key='login_recovery_required',
            )

        if isinstance(exc, LoginRepeatError):
            return RecoveryDecision(
                phase=RecoveryPhase.TASK,
                action=RecoveryAction.REQUEST_MANUAL_TAKEOVER,
                error_key='login_repeat',
            )

        if isinstance(exc, GamePageUnknownError):
            return RecoveryDecision(
                phase=RecoveryPhase.TASK,
                action=RecoveryAction.RESTART_WINDOW,
                error_key='page_unknown',
                retry_delay_seconds=self._task_retry_delay_seconds,
                max_attempts=self._task_restart_attempts,
                require_shortcut=True,
            )

        if isinstance(exc, DeviceStuckError):
            return RecoveryDecision(
                phase=RecoveryPhase.TASK,
                action=RecoveryAction.RESTART_WINDOW,
                error_key='device_stuck',
                retry_delay_seconds=self._task_retry_delay_seconds,
                max_attempts=self._task_restart_attempts,
                require_shortcut=True,
            )

        if isinstance(exc, DeviceTooManyClickError):
            return RecoveryDecision(
                phase=RecoveryPhase.TASK,
                action=RecoveryAction.RESTART_WINDOW,
                error_key='too_many_click',
                retry_delay_seconds=self._task_retry_delay_seconds,
                max_attempts=self._task_restart_attempts,
                require_shortcut=True,
            )

        if self._is_print_window_failure(exc):
            return RecoveryDecision(
                phase=RecoveryPhase.TASK,
                action=RecoveryAction.RESTART_WINDOW,
                error_key='print_window_failure',
                retry_delay_seconds=self._task_retry_delay_seconds,
                max_attempts=self._task_restart_attempts,
                require_shortcut=True,
            )

        return RecoveryDecision(
            phase=RecoveryPhase.TASK,
            action=RecoveryAction.RESTART_WINDOW,
            error_key='task_exception',
            retry_delay_seconds=self._task_retry_delay_seconds,
            max_attempts=self._task_restart_attempts,
            require_shortcut=True,
        )
