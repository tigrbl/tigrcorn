from __future__ import annotations

from .imports import *
from .models import *

class _ManagedProcess:
    def __init__(self, process: subprocess.Popen[Any], stdout_path: Path, stderr_path: Path) -> None:
        self.process = process
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path

    def stop(self, *, timeout: float = 5.0) -> int | None:
        if os.name == 'nt' and self.process.poll() is None:
            try:
                subprocess.run(
                    ['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except Exception:
                pass
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                return None
            return self.process.returncode
        if self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    self.process.kill()
                except Exception:
                    pass
                try:
                    self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    return None
        return self.process.returncode

__all__ = [name for name in globals() if not name.startswith('__')]
