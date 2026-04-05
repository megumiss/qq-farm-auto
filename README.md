# QQ Farm Copilot

> ⚠️ 重构中：当前版本所有功能暂不可用

基于 OpenCV + PyQt6 的 QQ 农场自动化工具（PC 端微信小程序场景）。

## 当前实现概览

- 架构：`BotEngine` + `TaskExecutor` + UI 页面识别（`core/ui`）
- 调度：统一任务执行器，支持 `INTERVAL` / `DAILY`
- 任务配置：`configs/config.json` 中 `tasks` 为**动态字典**
- 任务优先级：`tasks.<task>.priority`（数字越小越先执行）
- UI：左侧实时截图，右侧状态/任务调度/任务功能/设置

当前内置任务（通过 `_run_task_*` 自动发现）：

- `farm_main`：农场主流程（收获维护、播种、扩建、出售、任务奖励、好友求助入口）
- `friend`：独立好友任务
- `share`：独立分享/任务奖励任务（通常配合每日触发）

## 已实现功能

- 一键收获 / 除草 / 除虫 / 浇水
- 空地检测后批量播种（拖拽）
- 种子不足时打开商店并 OCR 购买种子
- 自动扩建流程
- 仓库批量出售
- 任务奖励领取（含分享后 ESC 关闭）
- 好友求助、好友农场维护（浇水/除草/除虫/回家）
- 弹窗统一处理、未知页面回主
- 动态任务调度（优先级、间隔、每日时间、失败间隔）

## 环境要求

- Windows 10/11
- Python 3.10+
- PC 端微信（并打开 QQ 农场小程序）

## 安装

```bash
pip install -r requirements.txt
```

## 启动前准备

### 1) 模板采集（首次使用）

```bash
python tools/template_collector.py
```

采集后模板放在 `templates/`。

### 2) 生成 assets（按钮资源映射）

```bash
python tools/button_extract.py
```

会生成：`core/ui/assets.py`。

说明：程序启动时会检查 assets 数量，若为 0 会提示先运行 `button_extract`。

### 3)（可选）导入种子模板

```bash
python tools/import_seeds.py
```

## 运行

```bash
python main.py
```

热键：

- `F9`：暂停 / 恢复
- `F10`：停止

## 配置说明

主配置文件：`configs/config.json`

核心字段：

- `window_title_keyword`：窗口标题关键词（默认 `QQ经典农场`）
- `planting`：种植策略、等级、平台、窗口位置
- `executor`：空队列策略、默认间隔、最大失败次数
- `tasks`：动态任务字典

`tasks` 示例：

```json
{
  "farm_main": {
    "enabled": true,
    "priority": 10,
    "trigger": "interval",
    "interval_seconds": 60,
    "daily_time": "04:00",
    "failure_interval_seconds": 30,
    "features": {
      "auto_harvest": true,
      "auto_plant": true,
      "auto_sell": true
    }
  },
  "share": {
    "enabled": true,
    "priority": 30,
    "trigger": "daily",
    "daily_time": "04:00",
    "interval_seconds": 86400,
    "failure_interval_seconds": 300,
    "features": {
      "auto_task": true
    }
  }
}
```

调度规则：

- 到期任务按 `priority` 从小到大执行
- 任务执行后按成功/失败间隔或 `TaskResult.next_run_seconds` 计算下一次执行
- `DAILY` 与 `INTERVAL` 共用同一套执行器队列

## UI 面板

- 状态：运行状态、当前任务、队列数量、统计
- 任务调度：任务开关、间隔/每日时间、执行器策略
- 任务设置：`tasks.<task>.features` 开关
- 设置：窗口关键词、平台、位置、种植策略

> 说明：`priority` 目前在配置文件中维护，未在面板提供编辑控件。

## 新增任务（当前实现方式）

1. 在 `core/engine/bot/executor.py` 增加 `_run_task_<name>` 方法
2. 在 `configs/config.json` 的 `tasks` 增加 `<name>` 配置
3. （可选）在 `gui/configs/ui_labels.json` 增加任务与功能文案

执行器会自动发现 `_run_task_*` 并参与调度。

## 目录结构（当前）

```text
core/
  engine/
    bot/        # Bot 入口、运行态、执行器桥接、视觉桥接
    task/       # 通用任务执行器、任务模型、统计调度器
  tasks/        # 业务任务实现
  platform/     # 窗口/截图/点击执行适配
  ui/           # 页面图、assets 按钮、UI 导航
  vision/       # CV 检测器
configs/
  config.template.json
  config.json
  ui_labels.json
tools/
  template_collector.py
  button_extract.py
  import_seeds.py
```

## 免责声明

本项目仅供学习研究 OpenCV 视觉识别技术使用。自动化操作可能违反游戏服务条款，由此产生的一切后果由使用者自行承担。
