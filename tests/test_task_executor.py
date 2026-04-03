"""TaskExecutor core behavior tests."""
from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta
import sys
import types


if "loguru" not in sys.modules:
    class _DummyLogger:
        def debug(self, *_args, **_kwargs):
            return None

        def exception(self, *_args, **_kwargs):
            return None

    sys.modules["loguru"] = types.SimpleNamespace(logger=_DummyLogger())

from core.task_executor import TaskExecutor
from core.task_registry import TaskItem, TaskResult


class TaskExecutorTests(unittest.TestCase):
    def test_snapshot_classification_and_sorting(self):
        now = datetime.now()
        tasks = {
            "pending_low": TaskItem(
                name="pending_low",
                enabled=True,
                priority=30,
                next_run=now - timedelta(seconds=2),
                success_interval=10,
                failure_interval=5,
            ),
            "pending_high": TaskItem(
                name="pending_high",
                enabled=True,
                priority=10,
                next_run=now - timedelta(seconds=1),
                success_interval=10,
                failure_interval=5,
            ),
            "waiting": TaskItem(
                name="waiting",
                enabled=True,
                priority=50,
                next_run=now + timedelta(seconds=30),
                success_interval=10,
                failure_interval=5,
            ),
            "disabled": TaskItem(
                name="disabled",
                enabled=False,
                priority=1,
                next_run=now - timedelta(seconds=1),
                success_interval=10,
                failure_interval=5,
            ),
        }
        executor = TaskExecutor(tasks=tasks, runners={})
        snapshot = executor.snapshot(now)

        self.assertEqual([t.name for t in snapshot.pending_tasks], ["pending_high", "pending_low"])
        self.assertEqual([t.name for t in snapshot.waiting_tasks], ["waiting"])

    def test_task_delay_and_task_call(self):
        now = datetime.now()
        task = TaskItem(
            name="farm_main",
            enabled=False,
            priority=10,
            next_run=now + timedelta(minutes=5),
            success_interval=10,
            failure_interval=5,
        )
        executor = TaskExecutor(tasks={"farm_main": task}, runners={})

        self.assertFalse(executor.task_call("farm_main", force_call=False))
        self.assertTrue(executor.task_call("farm_main", force_call=True))
        self.assertTrue(task.enabled)
        self.assertLessEqual(task.next_run, datetime.now())

        self.assertTrue(executor.task_delay("farm_main", seconds=2))
        first_target = task.next_run
        self.assertGreater(first_target, datetime.now())

        earlier = datetime.now() + timedelta(seconds=1)
        self.assertTrue(executor.task_delay("farm_main", seconds=5, target_time=earlier))
        self.assertLessEqual(abs((task.next_run - earlier).total_seconds()), 0.5)

    def test_failure_backoff_after_max_failures(self):
        task = TaskItem(
            name="farm_main",
            enabled=True,
            priority=10,
            next_run=datetime.now(),
            success_interval=10,
            failure_interval=1,
            max_failures=2,
        )
        run_count = {"n": 0}

        def runner() -> TaskResult:
            run_count["n"] += 1
            return TaskResult(success=False, error="mock fail")

        executor = TaskExecutor(tasks={"farm_main": task}, runners={"farm_main": runner})
        executor.start()
        deadline = time.time() + 3.0
        while time.time() < deadline and run_count["n"] < 2:
            time.sleep(0.05)
        executor.stop()

        self.assertGreaterEqual(run_count["n"], 2)
        self.assertGreaterEqual(task.failure_count, 2)
        next_in = (task.next_run - datetime.now()).total_seconds()
        self.assertGreaterEqual(next_in, 2.0)


if __name__ == "__main__":
    unittest.main()
