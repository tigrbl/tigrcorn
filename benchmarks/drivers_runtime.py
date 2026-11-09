from __future__ import annotations

import asyncio
import importlib.util

from benchmarks.common import measure_sync
from tigrcorn.server.bootstrap import run_coro_with_runtime


def _effective_runtime(requested: str) -> str:
    if requested == "auto":
        return "uvloop" if importlib.util.find_spec("uvloop") is not None else "asyncio"
    return requested


def runtime_scheduler_driver(profile, *, source_root):
    requested_runtime = str(profile.driver_config.get("runtime", "auto"))
    task_fanout = int(profile.driver_config.get("task_fanout", 256))
    yield_count = int(profile.driver_config.get("yield_count", 4))
    payload_size = int(profile.driver_config.get("payload_size", 64))
    expected_total = sum(range(task_fanout)) + (task_fanout * payload_size)

    def operation():
        state: dict[str, object] = {}

        async def workload() -> None:
            async def unit(index: int) -> int:
                value = index + payload_size
                for _ in range(yield_count):
                    await asyncio.sleep(0)
                return value

            values = await asyncio.gather(*(unit(index) for index in range(task_fanout)))
            state["result_total"] = sum(values)
            state["task_count"] = len(values)
            state["effective_runtime"] = _effective_runtime(requested_runtime)

        run_coro_with_runtime(workload, runtime=requested_runtime)
        effective_runtime = str(state["effective_runtime"])
        return {
            "streams": task_fanout,
            "correctness": {
                "all_tasks_completed": int(state["task_count"]) == task_fanout,
                "result_total_matches": int(state["result_total"]) == expected_total,
                "auto_resolves_to_supported_runtime": effective_runtime in {"asyncio", "uvloop"},
            },
            "metadata": {
                "requested_runtime": requested_runtime,
                "effective_runtime": effective_runtime,
                "task_fanout": task_fanout,
                "yield_count": yield_count,
                "payload_size": payload_size,
            },
        }

    return measure_sync(
        operation,
        iterations=profile.iterations,
        warmups=profile.warmups,
        units_per_iteration=task_fanout,
        correctness_note="runtime-comparison benchmark verifies equal task completion across runtime modes",
    )
