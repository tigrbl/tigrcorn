from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


APP_SOURCE = r'''
async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    path = scope.get("path", "/")
    body = b'{"ok":true,"server":"tigrcorn"}' if path == "/json" else b"tigrcorn-open-loop\n"
    content_type = b"application/json" if path == "/json" else b"text/plain"
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [
            (b"content-type", content_type),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
    })
    await send({"type": "http.response.body", "body": body})
'''


def require_binary(binary: str) -> str:
    resolved = shutil.which(binary)
    if resolved is None:
        raise RuntimeError(
            f"required open-loop benchmark binary not found: {binary!r}; "
            "install it or set the profile driver_config binary value"
        )
    return resolved


def parse_duration_seconds(value: str | int | float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().lower()
    if raw.endswith("ms"):
        return float(raw[:-2]) / 1000.0
    if raw.endswith("s"):
        return float(raw[:-1])
    if raw.endswith("m"):
        return float(raw[:-1]) * 60.0
    if raw.endswith("h"):
        return float(raw[:-1]) * 3600.0
    return float(raw)


def parse_rate_per_second(value: str | int | float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().lower()
    for suffix in ("/second", "/sec", "/s", "rps"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    return float(raw)


def latency_samples_from_percentiles(p50: float, p95: float, p99: float, p99_9: float) -> list[float]:
    samples = [float(p50)] * 50
    samples.extend([float(p95)] * 45)
    samples.extend([float(p99)] * 4)
    samples.append(float(p99_9))
    return samples


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_port(port: int, *, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError(f"tigrcorn benchmark listener did not become ready on 127.0.0.1:{port}") from last_error


@contextmanager
def local_http11_target(source_root: Path, *, path: str = "/plain") -> Iterator[str]:
    port = find_free_port()
    with tempfile.TemporaryDirectory(prefix="tigrcorn-open-loop-") as temp_root:
        app_path = Path(temp_root) / "open_loop_app.py"
        app_path.write_text(textwrap.dedent(APP_SOURCE).strip() + "\n", encoding="utf-8")
        env = os.environ.copy()
        python_paths = [str(source_root / "src"), str(source_root)]
        existing = env.get("PYTHONPATH")
        if existing:
            python_paths.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(python_paths)
        command = [
            sys.executable,
            "-m",
            "tigrcorn",
            "open_loop_app:app",
            "--app-dir",
            temp_root,
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--http",
            "1.1",
            "--no-access-log",
        ]
        process = subprocess.Popen(
            command,
            cwd=str(source_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            wait_for_port(port)
            yield f"http://127.0.0.1:{port}{path}"
        finally:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)


def run_command(command: list[str], *, cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
