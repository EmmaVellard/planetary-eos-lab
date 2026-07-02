"""Progress indication and background task management for GUI."""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Callable, Optional

import streamlit as st


@dataclass
class TaskProgress:
    """Progress state for a running task."""

    task_name: str
    status: str  # "running", "completed", "failed"
    output_lines: list[str]
    returncode: Optional[int] = None
    error_message: Optional[str] = None


class BackgroundTaskRunner:
    """Run command-line tasks in background with progress updates."""

    def __init__(self):
        self.tasks: dict[str, TaskProgress] = {}
        self.output_queues: dict[str, Queue] = {}

    def start_task(
        self,
        task_id: str,
        task_name: str,
        command: list[str],
        cwd: Optional[Path] = None,
        callback: Optional[Callable[[TaskProgress], None]] = None,
    ) -> None:
        """Start a background task.

        Args:
            task_id: Unique identifier for the task
            task_name: Display name for the task
            command: Command to run
            cwd: Working directory
            callback: Optional callback when task completes
        """
        if task_id in self.tasks:
            raise ValueError(f"Task {task_id} already running")

        progress = TaskProgress(task_name=task_name, status="running", output_lines=[])
        self.tasks[task_id] = progress
        output_queue: Queue[str] = Queue()
        self.output_queues[task_id] = output_queue

        def run_task():
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(cwd) if cwd else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )

                if process.stdout:
                    for line in process.stdout:
                        output_queue.put(line)
                        progress.output_lines.append(line)

                returncode = process.wait()
                progress.returncode = returncode
                progress.status = "completed" if returncode == 0 else "failed"

                if returncode != 0:
                    progress.error_message = f"Command failed with return code {returncode}"

            except Exception as e:
                progress.status = "failed"
                progress.error_message = str(e)

            finally:
                if callback:
                    callback(progress)

        thread = threading.Thread(target=run_task, daemon=True)
        thread.start()

    def get_progress(self, task_id: str) -> Optional[TaskProgress]:
        """Get current progress for a task.

        Args:
            task_id: Task identifier

        Returns:
            TaskProgress or None if task doesn't exist
        """
        return self.tasks.get(task_id)

    def is_running(self, task_id: str) -> bool:
        """Check if a task is currently running.

        Args:
            task_id: Task identifier

        Returns:
            True if task is running
        """
        progress = self.get_progress(task_id)
        return progress is not None and progress.status == "running"

    def get_new_output(self, task_id: str) -> list[str]:
        """Get new output lines since last check.

        Args:
            task_id: Task identifier

        Returns:
            List of new output lines
        """
        if task_id not in self.output_queues:
            return []

        queue = self.output_queues[task_id]
        lines = []

        while not queue.empty():
            lines.append(queue.get_nowait())

        return lines

    def cleanup_task(self, task_id: str) -> None:
        """Clean up completed task.

        Args:
            task_id: Task identifier
        """
        self.tasks.pop(task_id, None)
        self.output_queues.pop(task_id, None)


def show_task_progress(progress: TaskProgress, container: Optional[st.delta_generator.DeltaGenerator] = None) -> None:
    """Display task progress in Streamlit.

    Args:
        progress: Task progress state
        container: Optional Streamlit container to render in
    """
    ctx = container if container else st

    if progress.status == "running":
        ctx.info(f"Running: {progress.task_name}")
        with ctx.expander("Output", expanded=True):
            st.code("\\n".join(progress.output_lines[-50:]), language="text")  # Last 50 lines
    elif progress.status == "completed":
        ctx.success(f"Completed: {progress.task_name}")
        with ctx.expander("Output"):
            st.code("\\n".join(progress.output_lines), language="text")
    elif progress.status == "failed":
        ctx.error(f"Failed: {progress.task_name}")
        if progress.error_message:
            ctx.error(progress.error_message)
        with ctx.expander("Output", expanded=True):
            st.code("\\n".join(progress.output_lines), language="text")
