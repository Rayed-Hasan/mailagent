"""Persistent local task queue for personal deployments."""

import asyncio
import logging
from datetime import timezone
from typing import Any, Callable, Dict, Optional

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class LocalTaskQueue:
    """An in-process scheduler with a SQLite-backed job store.

    APScheduler persists schedules and reloads them after restart. Callables must
    be importable by APScheduler for a persisted job to run in a new process.
    """

    def __init__(
        self,
        db_path: str = "mailagent-queue.db",
        kill_switch_checker: Optional[Callable[[], Any]] = None,
    ):
        self.scheduler = AsyncIOScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{db_path}")},
            timezone=timezone.utc,
        )
        self.running = False
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.kill_switch_checker = kill_switch_checker

    async def start(self) -> None:
        if not self.running:
            self.scheduler.start()
            self.running = True
            logger.info("Local task queue started")

    async def stop(self) -> None:
        if self.running:
            self.scheduler.shutdown(wait=False)
            self.running = False
            logger.info("Local task queue stopped")

    def schedule_task(
        self,
        task_id: str,
        func: Callable,
        interval_seconds: int = 300,
        **kwargs,
    ) -> bool:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if self.kill_switch_checker is not None:
            active = self.kill_switch_checker()
            if not asyncio.iscoroutine(active) and active:
                logger.warning("Refusing to schedule task while kill switch is active")
                return False
        try:
            self.scheduler.add_job(
                func,
                trigger=IntervalTrigger(seconds=interval_seconds),
                id=task_id,
                replace_existing=True,
                kwargs=kwargs,
            )
            self.tasks[task_id] = {"func": func, "interval": interval_seconds, "kwargs": kwargs}
            return True
        except Exception:
            logger.exception("Failed to schedule task %s", task_id)
            return False

    def cancel_task(self, task_id: str) -> bool:
        try:
            self.scheduler.remove_job(task_id)
            self.tasks.pop(task_id, None)
            return True
        except Exception:
            logger.exception("Failed to cancel task %s", task_id)
            return False

    def cancel_all(self) -> int:
        """Cancel every persisted job, used by the kill switch."""
        job_ids = self.get_scheduled_tasks()
        for task_id in job_ids:
            self.cancel_task(task_id)
        return len(job_ids)

    def get_scheduled_tasks(self) -> list:
        return [job.id for job in self.scheduler.get_jobs()]

    def is_running(self) -> bool:
        return self.running

    async def execute_once(self, func: Callable, **kwargs) -> Any:
        if asyncio.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)
