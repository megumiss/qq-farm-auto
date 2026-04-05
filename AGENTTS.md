# AGENTTS

本文件定义本仓库内自动化/编码代理的工作约定。以当前代码实现为准。

## 0. 当前状态

- 项目名：`QQ Farm Copilot`
- 调度模式：`TaskExecutor` 单线程串行执行
- 任务配置：`configs/config.json -> tasks`（动态字典）
- 视觉按钮来源：`core/ui/assets.py`（由 `tools/button_extract.py` 生成）

## 1. 核心架构与职责

- `core/engine/bot/engine.py`
: `BotEngine` 入口，组合 `bootstrap/executor/runtime/vision`。

- `core/engine/bot/runtime.py`
: 生命周期与会话控制（start/stop/pause/resume/run_once）、配置更新、可中断睡眠、坐标映射。

- `core/engine/bot/executor.py`
: 任务注册与调度桥接（自动发现 `_run_task_*`）。

- `core/engine/task/executor.py`
: 通用任务执行器（pending/waiting 队列、优先级排序、结果回写 next_run）。

- `core/tasks/*.py`
: 业务任务实现（`farm_main/friend/share` 及 farm 子任务）。

- `core/ui/ui.py` + `core/base/module_base.py`
: 页面识别、导航、弹窗清理、`appear/appear_then_click` 等模板点击能力。

## 2. 调度语义（必须遵守）

### 2.1 任务来源

- 执行器自动发现 `BotExecutorMixin` 中所有 `_run_task_<name>`。
- 任务启停与参数从 `config.tasks[<name>]` 读取。

### 2.2 排序规则

- 仅执行 `enabled=true` 且 `next_run <= now` 的任务。
- `pending` 队列按 `priority` 升序排序（值越小优先级越高）。
- 同一时刻到期任务按 `priority` 串行执行，不并发。

### 2.3 触发类型

- `trigger=interval`：按 `interval_seconds`。
- `trigger=daily`：按 `daily_time` 计算距离下一次秒数。
- `TaskResult.next_run_seconds` 若设置，会覆盖本次默认成功/失败间隔。

### 2.4 失败语义

- `TaskResult.success=false` 时计入失败并使用 `failure_interval_seconds`（除非 next_run_seconds 覆盖）。
- 不要新增会影响调度推进的“业务阻断标记”。

## 3. 常用方法速查

## 3.1 Runtime/Bot 常用

- `_is_cancel_requested(session_id=None) -> bool`
: 判断当前会话或执行器是否停止。

- `_sleep_interruptible(seconds, session_id=None) -> bool`
: 可中断睡眠，返回 `False` 表示被取消。

- `_prepare_window() -> rect | None`（vision）
: 刷新窗口、激活、更新 `action_executor/nk_device` 窗口矩形。

- `_clear_screen(rect, session_id=None)`
: 连续点击 `GOTO_MAIN` 兜底回主。

- `resolve_live_click_point(x, y) -> (x, y)`
: 逻辑坐标映射到当前截图坐标系（考虑 nonclient 裁剪偏移）。

- `_nklite_click(x, y, desc) -> bool`
: 统一通过 `ActionExecutor` 执行点击动作。

- `_capture_frame(rect, save=False) -> (cv_img, pil_img)`
: 截图并推送 GUI 预览。

- `_capture_and_detect(...)`
: 当前只负责截图返回，模板检测由业务侧按需调用 detector。

## 3.2 UI/模板点击常用

- `ui.ui_get_current_page(...)`
: 页面识别（未知页会尝试回主+清弹窗）。

- `ui.ui_goto(page)` / `ui.ui_ensure(page)`
: 页面导航与确保到达。

- `ui.ui_additional()`
: 统一弹窗处理入口（等级、奖励、公告等）。

- `appear(button, offset=(30,30), threshold=0.8, static=False)`
: 仅判断出现。

- `appear_then_click(..., interval=1, ...)`
: 出现后点击；**interval 最低保持 1**。

- `appear_then_click_any([...], interval=1, ...)`
: 依次尝试多个按钮。

## 3.3 TaskExecutor 常用

- `task_call(task_name, force_call=True)`
: 立即将任务置为可执行。

- `task_delay(task_name, seconds=..., target_time=...)`
: 推迟任务下一次执行。

- `update_task(name, **kwargs)`
: 热更新任务参数（enabled/priority/interval 等）。

## 4. 业务任务逻辑（当前实现）

- `farm_main`
: 主流程任务，内部先巡查维护，再按页面分发子任务。

- `farm_main` 在主页面的子任务顺序（命中即短路）：
1. `plant`
2. `upgrade(expand)`
3. `sell`
4. `reward`
5. `friend`

- `farm_harvest` 内部顺序（命中即返回）：
1. 收获
2. 除草
3. 除虫
4. 浇水

- `friend`
: 独立好友任务，复用 `TaskFarmFriend`。

- `share`
: 独立分享/任务奖励任务，复用 `TaskFarmReward`。

## 5. 新增任务标准流程

1. 在 `core/engine/bot/executor.py` 增加 `_run_task_<name>(ctx)`。
2. 在 `configs/config.template.json` 与用户配置中增加 `tasks.<name>`。
3. 任务业务代码放入 `core/tasks/<name>.py`（或复用已有子任务）。
4. 在任务中通过 `engine.get_task_features('<name>')` 读取开关。
5. 必要时补充 `configs/ui_labels.json` 文案映射。

## 6. 配置字段约定（tasks）

每个任务项建议包含：

- `enabled: bool`
- `priority: int`（>=1）
- `trigger: "interval" | "daily"`
- `interval_seconds: int`（>=1）
- `daily_time: "HH:MM"`
- `failure_interval_seconds: int`（>=1）
- `features: {str: bool}`

## 7. 修改边界与禁令

- 不要恢复旧 `core/ops` 业务层。
- 不要新增重复包装（例如多余 click/appear 兼容层）。
- 不要把任务列表改回 `models/config.py` 固定字段模型。
- 不要将 `appear_then_click` 的最小 `interval` 改成小于 `1`。
- 不要用会中断调度链路的业务状态去“跳过下次执行时间计算”。

## 8. 提交前检查（最低）

```bash
python -m compileall -q core gui models main.py
rg -n "from core\.ops|core\.ops|model_fields\.keys\(\)" core gui models
```

## 9. 常见问题排查

- 启动提示 assets 为 0
: 先运行 `python tools/button_extract.py`。

- 页面识别卡 unknown
: 检查 `window_title_keyword`、窗口平台（QQ/微信）、模板是否与平台匹配。

- 任务未执行
: 检查 `tasks.<name>.enabled`、`trigger/daily_time/interval_seconds`、`priority`。

- 点击偏移明显
: 检查 `resolve_live_click_point` 是否被绕过；优先走 `_nklite_click` / `ActionExecutor`。

## 10. 文档同步要求

- 若改动调度规则、任务入口、配置结构，必须同步更新：
1. `README.md`
2. 本文件 `AGENTTS.md`
